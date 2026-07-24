/*
 * sigmoid_compare_pim.c
 *
 * Compares PIM cost of:
 *   - Original sigmoid via Taylor expansion: 1/(1 + exp(-x))
 *     approximated as 1/(1 + 1 + x + x^2/2 + x^3/6 + x^4/24 + x^5/120)
 *     = 1/(2 + x + x^2/2 + x^3/6 + x^4/24 + x^5/120)
 *
 *   - f_6 approximation: (120 + 60x + 12x^2 + x^3) / (240 + 24x^2)
 *     clamped to [0,1]
 *
 * Both are decomposed into bbop operations to measure latency/energy
 * via the Proteus analytical model.
 *
 * Build:
 *   gcc -O3 -DRUN_PIM -DSIGMOID_TAYLOR -o sigmoid_taylor_pim sigmoid_compare_pim.c util/bbop_manager.c -lm -fopenmp -w
 *   gcc -O3 -DRUN_PIM -DSIGMOID_F6 -o sigmoid_f6_pim sigmoid_compare_pim.c util/bbop_manager.c -lm -fopenmp -w
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

/*
 * Taylor expansion sigmoid decomposition (PIM):
 *   exp(-x) ~ 1 + (-x) + (-x)^2/2 + (-x)^3/6 + (-x)^4/24 + (-x)^5/120
 *   sigmoid(x) = 1 / (1 + exp(-x))
 *
 * Operations needed:
 *   Step 0:  neg_x = 0 - x                    (BBOP_SUB)  -- negate
 *   Step 1:  x2 = neg_x * neg_x               (BBOP_MUL)
 *   Step 2:  x3 = x2 * neg_x                  (BBOP_MUL)
 *   Step 3:  x4 = x3 * neg_x                  (BBOP_MUL)
 *   Step 4:  x5 = x4 * neg_x                  (BBOP_MUL)
 *   Step 5:  t2 = x2 / 2                      (BBOP_DIV)  -- or MUL by 0.5 in fixed
 *   Step 6:  t3 = x3 / 6                      (BBOP_DIV)
 *   Step 7:  t4 = x4 / 24                     (BBOP_DIV)
 *   Step 8:  t5 = x5 / 120                    (BBOP_DIV)
 *   Step 9:  sum = 1 + neg_x + t2 + t3 + t4 + t5  (5x BBOP_ADD)
 *   Step 10: denom = 1 + sum                   (BBOP_ADD)
 *   Step 11: result = 1 / denom                (BBOP_DIV)
 *
 * Total: 1 SUB + 4 MUL + 4 DIV + 6 ADD + 1 DIV = 1 SUB + 4 MUL + 5 DIV + 6 ADD
 *        = 16 bbop operations
 */
void sigmoid_taylor_pim(DATATYPE_BBOP *input, DATATYPE_BBOP *output, int size)
{
    DATATYPE_BBOP *neg_x  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *x2     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *x3     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *x4     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *x5     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *t2     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *t3     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *t4     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *t5     = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *sum    = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *denom  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *temp   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));

    DATATYPE_BBOP *const_0   = (DATATYPE_BBOP *) calloc(size, sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_1   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_2   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_6   = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_24  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *const_120 = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));

    for (int i = 0; i < size; i++) {
        const_1[i] = 1;
        const_2[i] = 2;
        const_6[i] = 6;
        const_24[i] = 24;
        const_120[i] = 120;
    }

    /* Step 0: neg_x = 0 - x */
    bbop_op(BBOP_SUB, const_0, input, neg_x, size, 0, BBOP_SUB);

    /* Step 1: x2 = neg_x * neg_x */
    bbop_op(BBOP_MUL, neg_x, neg_x, x2, size, 1, BBOP_MUL);

    /* Step 2: x3 = x2 * neg_x */
    bbop_op(BBOP_MUL, x2, neg_x, x3, size, 2, BBOP_MUL);

    /* Step 3: x4 = x3 * neg_x */
    bbop_op(BBOP_MUL, x3, neg_x, x4, size, 3, BBOP_MUL);

    /* Step 4: x5 = x4 * neg_x */
    bbop_op(BBOP_MUL, x4, neg_x, x5, size, 4, BBOP_MUL);

    /* Step 5: t2 = x2 / 2 */
    bbop_op(BBOP_DIV, x2, const_2, t2, size, 5, BBOP_DIV);

    /* Step 6: t3 = x3 / 6 */
    bbop_op(BBOP_DIV, x3, const_6, t3, size, 6, BBOP_DIV);

    /* Step 7: t4 = x4 / 24 */
    bbop_op(BBOP_DIV, x4, const_24, t4, size, 7, BBOP_DIV);

    /* Step 8: t5 = x5 / 120 */
    bbop_op(BBOP_DIV, x5, const_120, t5, size, 8, BBOP_DIV);

    /* Step 9: sum = 1 + neg_x + t2 + t3 + t4 + t5 */
    bbop_op(BBOP_ADD, const_1, neg_x, sum, size, 9, BBOP_ADD);
    bbop_op(BBOP_ADD, sum, t2, temp, size, 10, BBOP_ADD);
    bbop_op(BBOP_ADD, temp, t3, sum, size, 11, BBOP_ADD);
    bbop_op(BBOP_ADD, sum, t4, temp, size, 12, BBOP_ADD);
    bbop_op(BBOP_ADD, temp, t5, sum, size, 13, BBOP_ADD);

    /* Step 10: denom = 1 + sum */
    bbop_op(BBOP_ADD, const_1, sum, denom, size, 14, BBOP_ADD);

    /* Step 11: result = 1 / denom */
    bbop_op(BBOP_DIV, const_1, denom, output, size, 15, BBOP_DIV);

    free(neg_x); free(x2); free(x3); free(x4); free(x5);
    free(t2); free(t3); free(t4); free(t5);
    free(sum); free(denom); free(temp);
    free(const_0); free(const_1); free(const_2);
    free(const_6); free(const_24); free(const_120);
}

/*
 * f_6 approximation decomposition (PIM):
 *   f_6(x) = clamp((120 + 60x + 12x^2 + x^3) / (240 + 24x^2), 0, 1)
 *
 * Operations:
 *   Step 0: x2 = x * x                        (BBOP_MUL)
 *   Step 1: x3 = x2 * x                       (BBOP_MUL)
 *   Step 2: t60x = 60 * x                     (BBOP_MUL)
 *   Step 3: t12x2 = 12 * x2                   (BBOP_MUL)
 *   Step 4: num = 120 + t60x + t12x2 + x3     (3x BBOP_ADD)
 *   Step 5: t24x2 = 24 * x2                   (BBOP_MUL)
 *   Step 6: den = 240 + t24x2                  (BBOP_ADD)
 *   Step 7: result = num / den                 (BBOP_DIV)
 *   Step 8: clamp (RELU)                       (BBOP_RELU)
 *
 * Total: 5 MUL + 4 ADD + 1 DIV + 1 RELU = 11 bbop operations
 */
void sigmoid_f6_pim(DATATYPE_BBOP *input, DATATYPE_BBOP *output, int size)
{
    DATATYPE_BBOP *x2         = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *x3         = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *t60x       = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *t12x2      = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *t24x2      = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *num        = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *den        = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *temp       = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));

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

    bbop_op(BBOP_MUL, input, input, x2, size, 0, BBOP_MUL);
    bbop_op(BBOP_MUL, x2, input, x3, size, 1, BBOP_MUL);
    bbop_op(BBOP_MUL, const_60, input, t60x, size, 2, BBOP_MUL);
    bbop_op(BBOP_MUL, const_12, x2, t12x2, size, 3, BBOP_MUL);

    bbop_op(BBOP_ADD, const_120, t60x, num, size, 4, BBOP_ADD);
    bbop_op(BBOP_ADD, num, t12x2, temp, size, 5, BBOP_ADD);
    bbop_op(BBOP_ADD, temp, x3, num, size, 6, BBOP_ADD);

    bbop_op(BBOP_MUL, const_24, x2, t24x2, size, 7, BBOP_MUL);
    bbop_op(BBOP_ADD, const_240, t24x2, den, size, 8, BBOP_ADD);

    bbop_op(BBOP_DIV, num, den, output, size, 9, BBOP_DIV);
    bbop_op(BBOP_RELU, output, output, output, size, 10, BBOP_RELU);

    free(x2); free(x3); free(t60x); free(t12x2); free(t24x2);
    free(num); free(den); free(temp);
    free(const_60); free(const_12); free(const_24);
    free(const_120); free(const_240);
}


int main(int argc, char **argv)
{
    int size = SIZE;

    printf("Sigmoid PIM comparison\n");
    printf("Array size: %d\n\n", size);

    initialize_bbop_statistics();

    DATATYPE_BBOP *input  = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));
    DATATYPE_BBOP *output = (DATATYPE_BBOP *) malloc(size * sizeof(DATATYPE_BBOP));

    for (int i = 0; i < size; i++) {
        input[i] = (DATATYPE_BBOP)(i % 10);  /* values 0-9 */
    }

#ifdef SIGMOID_TAYLOR
    printf("Running: Taylor expansion sigmoid (16 bbops)\n");
    sigmoid_taylor_pim(input, output, size);
#endif

#ifdef SIGMOID_F6
    printf("Running: f_6 rational approximation (11 bbops)\n");
    sigmoid_f6_pim(input, output, size);
#endif

    print_bbop_statistic();

    free(input);
    free(output);
    return 0;
}
