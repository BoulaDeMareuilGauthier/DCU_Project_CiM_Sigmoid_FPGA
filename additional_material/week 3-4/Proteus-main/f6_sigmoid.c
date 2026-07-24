/*
 * f6_sigmoid.c
 *
 * Implements f_6(x) = min(max((120 + 60x + 12x^2 + x^3) / (240 + 24x^2), 0), 1)
 *
 * This is a rational polynomial approximation of the sigmoid function,
 * clamped to [0, 1]. All arithmetic is in floating point.
 *
 * Two modes:
 *   - RUN_BASELINE: scalar floating-point computation
 *   - RUN_PIM:      decomposed into bbop operations (MUL, ADD, DIV, RELU)
 *                   for Processing-Using-DRAM simulation via Proteus
 *
 * Build (baseline):
 *   gcc -O2 -DRUN_BASELINE -o f6_sigmoid f6_sigmoid.c ../util/bbop_manager.c -lm -fopenmp
 *
 * Build (PIM):
 *   gcc -O2 -DRUN_PIM -o f6_sigmoid_pim f6_sigmoid.c ../util/bbop_manager.c -lm -fopenmp
 *
 * Run:
 *   ./f6_sigmoid
 *   ./f6_sigmoid_pim
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <omp.h>

#include "util/bbop_manager.h"

#ifndef SIZE
    #define SIZE 65536
#endif

/* -----------------------------------------------------------------------
 * f6_sigmoid_scalar: straightforward floating-point implementation
 * ----------------------------------------------------------------------- */
float f6_sigmoid_scalar(float x)
{
    float x2 = x * x;
    float x3 = x2 * x;

    float numerator   = 120.0f + 60.0f * x + 12.0f * x2 + x3;
    float denominator = 240.0f + 24.0f * x2;

    float result = numerator / denominator;

    /* clamp: max(result, 0) then min(result, 1) */
    if (result < 0.0f)
        result = 0.0f;
    else if (result > 1.0f)
        result = 1.0f;

    return result;
}

/* -----------------------------------------------------------------------
 * f6_sigmoid_array: applies f_6 element-wise over an array (baseline)
 * ----------------------------------------------------------------------- */
void f6_sigmoid_array_baseline(float *input, float *output, int size)
{
    #pragma omp parallel for schedule(static)
    for (int i = 0; i < size; i++) {
        output[i] = f6_sigmoid_scalar(input[i]);
    }
}

/* -----------------------------------------------------------------------
 * f6_sigmoid_array_pim: decomposes f_6 into bbop operations
 *
 * Decomposition of f_6(x) = (120 + 60x + 12x^2 + x^3) / (240 + 24x^2):
 *
 *   Step 1: x2[i] = x[i] * x[i]              (BBOP_MUL)
 *   Step 2: x3[i] = x2[i] * x[i]             (BBOP_MUL)
 *   Step 3: term_60x[i] = 60 * x[i]          (BBOP_MUL)
 *   Step 4: term_12x2[i] = 12 * x2[i]        (BBOP_MUL)
 *   Step 5: num[i] = 120 + term_60x + term_12x2 + x3  (BBOP_ADD x3)
 *   Step 6: term_24x2[i] = 24 * x2[i]        (BBOP_MUL)
 *   Step 7: den[i] = 240 + term_24x2          (BBOP_ADD)
 *   Step 8: result[i] = num[i] / den[i]       (BBOP_DIV)
 *   Step 9: clamp to [0, 1]                   (BBOP_RELU-style)
 * ----------------------------------------------------------------------- */
void f6_sigmoid_array_pim(DATATYPE_BBOP *input, DATATYPE_BBOP *output, int size)
{
    DATATYPE_BBOP *x2         = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *x3         = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *term_60x   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *term_12x2  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *term_24x2  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *numerator  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *denominator= (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *temp       = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));

    /* Constant arrays for scalar multiplication/addition via bbop */
    DATATYPE_BBOP *const_60   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_12   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_24   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_120  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_240  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));

    for (int i = 0; i < size; i++) {
        const_60[i]  = 60;
        const_12[i]  = 12;
        const_24[i]  = 24;
        const_120[i] = 120;
        const_240[i] = 240;
    }

    /* Step 1: x2 = x * x */
    bbop_op(BBOP_MUL, input, input, x2, size, 0, BBOP_MUL);

    /* Step 2: x3 = x2 * x */
    bbop_op(BBOP_MUL, x2, input, x3, size, 1, BBOP_MUL);

    /* Step 3: term_60x = 60 * x */
    bbop_op(BBOP_MUL, const_60, input, term_60x, size, 2, BBOP_MUL);

    /* Step 4: term_12x2 = 12 * x2 */
    bbop_op(BBOP_MUL, const_12, x2, term_12x2, size, 3, BBOP_MUL);

    /* Step 5: numerator = 120 + term_60x + term_12x2 + x3 */
    bbop_op(BBOP_ADD, const_120, term_60x, numerator, size, 4, BBOP_ADD);
    bbop_op(BBOP_ADD, numerator, term_12x2, temp, size, 5, BBOP_ADD);
    bbop_op(BBOP_ADD, temp, x3, numerator, size, 6, BBOP_ADD);

    /* Step 6: term_24x2 = 24 * x2 */
    bbop_op(BBOP_MUL, const_24, x2, term_24x2, size, 7, BBOP_MUL);

    /* Step 7: denominator = 240 + term_24x2 */
    bbop_op(BBOP_ADD, const_240, term_24x2, denominator, size, 8, BBOP_ADD);

    /* Step 8: result = numerator / denominator */
    bbop_op(BBOP_DIV, numerator, denominator, output, size, 9, BBOP_DIV);

    /* Step 9: clamp to [0, 1] — RELU zeros negatives; cap at 1 done on CPU
     * (Proteus RELU sets negative values to 0, matching max(result, 0)) */
    bbop_op(BBOP_RELU, output, output, output, size, 10, BBOP_RELU);

    /* Cap at 1.0 (min(result, 1)) — done element-wise on CPU since
     * there is no native "min with constant" bbop in the framework */
    for (int i = 0; i < size; i++) {
        if (output[i] > 1)
            output[i] = 1;
    }

    free(x2);
    free(x3);
    free(term_60x);
    free(term_12x2);
    free(term_24x2);
    free(numerator);
    free(denominator);
    free(temp);
    free(const_60);
    free(const_12);
    free(const_24);
    free(const_120);
    free(const_240);
}

/* -----------------------------------------------------------------------
 * Main
 * ----------------------------------------------------------------------- */
int main(int argc, char **argv)
{
    int size = SIZE;

    printf("f6_sigmoid: rational polynomial sigmoid approximation\n");
    printf("  f_6(x) = min(max((120 + 60x + 12x^2 + x^3) / (240 + 24x^2), 0), 1)\n");
    printf("  Array size: %d\n\n", size);

    /* Allocate and initialize input array with values in [-10, 10] */
    float *input_f  = (float *) malloc(size * sizeof(float));
    float *output_f = (float *) malloc(size * sizeof(float));

    for (int i = 0; i < size; i++) {
        input_f[i] = -10.0f + 20.0f * ((float)i / (float)(size - 1));
    }

#ifdef RUN_PIM
    printf("Running PIM version\n");
    initialize_bbop_statistics();

    /* Convert to fixed-point integer representation for bbop */
    DATATYPE_BBOP *input_pim  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *output_pim = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));

    for (int i = 0; i < size; i++) {
        input_pim[i] = (DATATYPE_BBOP) FLOAT_TO_INT(input_f[i]);
    }

    f6_sigmoid_array_pim(input_pim, output_pim, size);

    print_bbop_statistic();

    free(input_pim);
    free(output_pim);
#endif

#ifdef RUN_BASELINE
    printf("Running baseline (floating point)\n");

    f6_sigmoid_array_baseline(input_f, output_f, size);

    /* Print a few sample results */
    printf("\n%-10s %-14s %-14s\n", "x", "f6(x)", "sigmoid(x)");
    printf("------------------------------------------\n");
    int sample_indices[] = {0, size/8, size/4, 3*size/8, size/2,
                            5*size/8, 3*size/4, 7*size/8, size-1};
    for (int s = 0; s < 9; s++) {
        int i = sample_indices[s];
        float x   = input_f[i];
        float f6  = output_f[i];
        float sig = 1.0f / (1.0f + expf(-x));
        printf("%-10.4f %-14.8f %-14.8f\n", x, f6, sig);
    }
#endif

    free(input_f);
    free(output_f);

    return 0;
}
