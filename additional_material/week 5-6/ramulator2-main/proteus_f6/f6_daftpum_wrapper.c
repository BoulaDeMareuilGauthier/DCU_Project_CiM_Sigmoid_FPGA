/*
 * f6_daftpum_wrapper.c
 * ---------------------------------------------------------------------------
 * Thin WRAPPER around the *unmodified* Proteus DAFTPUM analytical model
 * (util/bbop_manager.c / .h from https://github.com/CMU-SAFARI/Proteus).
 *
 * Goal (per task):
 *   - Use the function
 *        f6(x) = min(max( (128 + 64x + 16x^2 + 2x^3) / (256 + 32x^2), 0), 1)
 *     to generate 10000 data points.
 *   - Feed that data into the Proteus DAFTPUM latency model (DAFTPUM_LAT).
 *   - Compare DAFTPUM_LAT against the SIMDRAM baselines.
 *   - Emit a Ramulator2 LoadStore trace built from the same data so a real
 *     cycle-accurate DRAM simulation can be run on it.
 *
 * The original Proteus code is NOT modified: this file only *calls* the public
 * API declared in bbop_manager.h (initialize_bbop_statistics, bbop_op,
 * print_bbop_statistic) and writes the standard bbop_statistics.csv.
 * ---------------------------------------------------------------------------
 */

#include <stdio.h>
#include <stdlib.h>
#include <math.h>

#include "bbop_manager.h"

#define N_DATA          10000     /* number of data points requested */
#define X_MIN          (-8.0)     /* sweep range for x ...           */
#define X_MAX           ( 8.0)
#define INT_SCALE       1000000   /* map f6(x) in [0,1] to integers   */

/* The exact function requested:
 *   f6_nearest(x) = min(max( (128 + 64x + 16x^2 + 2x^3) / (256 + 32x^2), 0), 1)
 */
static double f6_nearest(double x)
{
    double num = 128.0 + 64.0 * x + 16.0 * x * x + 2.0 * x * x * x;
    double den = 256.0 + 32.0 * x * x;
    double v   = num / den;
    if (v < 0.0) v = 0.0;
    if (v > 1.0) v = 1.0;
    return v;
}

int main(void)
{
    printf("=== f6 -> Proteus DAFTPUM_LAT vs SIMDRAM wrapper ===\n");
    printf("Generating %d data points from f6(x) over [%g, %g]\n",
           N_DATA, X_MIN, X_MAX);

    /* Initialise the (unmodified) Proteus statistics module. */
    initialize_bbop_statistics();

    /* Allocate the operand / result arrays expected by bbop_op(). */
    DATATYPE_BBOP *A = (DATATYPE_BBOP *) malloc(sizeof(DATATYPE_BBOP) * N_DATA);
    DATATYPE_BBOP *B = (DATATYPE_BBOP *) malloc(sizeof(DATATYPE_BBOP) * N_DATA);
    DATATYPE_BBOP *C = (DATATYPE_BBOP *) malloc(sizeof(DATATYPE_BBOP) * N_DATA);
    if (!A || !B || !C) { fprintf(stderr, "alloc failed\n"); return 1; }

    /* Also write a Ramulator2 LoadStore trace built from the same data:
     *   - every operand load -> "LD <addr>"
     *   - every result store -> "ST <addr>"
     * Addresses are derived from the data so the access pattern reflects f6. */
    FILE *trace = fopen("f6_ramulator.trace", "w");
    if (!trace) { fprintf(stderr, "cannot open trace file\n"); return 1; }

    const double step = (X_MAX - X_MIN) / (double)(N_DATA - 1);
    for (int i = 0; i < N_DATA; i++) {
        double x  = X_MIN + step * (double) i;
        double fa = f6_nearest(x);
        /* second operand: sample a shifted x so B differs from A          */
        double fb = f6_nearest(x + 0.5 * step * (N_DATA / 2));

        A[i] = (DATATYPE_BBOP) (fa * INT_SCALE);
        B[i] = (DATATYPE_BBOP) (fb * INT_SCALE);
        C[i] = 0;

        /* Ramulator trace: contiguous 64B cache lines, two loads + one store
         * per element. base offset keeps addresses positive & aligned.      */
        unsigned long long base = 0x100000ULL + (unsigned long long) i * 64ULL;
        fprintf(trace, "LD %llu\n", base);
        fprintf(trace, "LD %llu\n", base + (unsigned long long) N_DATA * 64ULL);
        fprintf(trace, "ST %llu\n", base + (unsigned long long) 2 * N_DATA * 64ULL);
    }
    fclose(trace);
    printf("Wrote Ramulator2 trace: f6_ramulator.trace (%d elements)\n", N_DATA);

    /* Drive the unmodified Proteus model.
     * bbop_op fills bbop_statistics[bbop_id] with BOTH the SIMDRAM baselines
     * and the DAFTPUM (incl. DAFTPUM_LAT, the latency-optimised) numbers.
     *
     * bbop_id 0 : element-wise ADD of the f6 data
     * bbop_id 1 : element-wise MUL of the f6 data
     */
    bbop_op(BBOP_ADD, A, B, C, (unsigned long long) N_DATA, 0, BBOP_ADD);
    bbop_op(BBOP_MUL, A, B, C, (unsigned long long) N_DATA, 1, BBOP_MUL);

    /* Emit the standard Proteus CSV (contains DAFTPUM_LAT and SIMDRAM rows). */
    print_bbop_statistic();
    printf("Wrote Proteus model output: bbop_statistics.csv\n");

    free(A); free(B); free(C);
    return 0;
}
