/*
 * Copyright (c) 2025 CMU SAFARI Group
 * Licensed under the MIT License.
 *
 * Example: Decompose f_6_nearest(x) = min(max((128 + 64x + 16x^2 + 2x^3) /
 *                                   (256 + 32x^2), 0), 1)
 * into bbop operations for DAFTPUM-LAT execution.
 *
 * This file demonstrates how to map a mathematical function to
 * Proteus-style basic block operations using the DAFTPUM-LAT controller.
 */

#include "daftpum_types.hh"

#include <cstdint>
#include <cstdio>

using namespace gem5;

/*
 * BBOP decomposition of f_6_nearest(x):
 *
 *   Step 1:  t1 = BBOP_MUL(B, B)       -> x^2
 *   Step 2:  t2 = BBOP_MUL(B, t1)      -> x^3
 *   Step 3:  t3 = BBOP_MUL(C, B)       -> 64x      (C = 64.0)
 *   Step 4:  t4 = BBOP_MUL(D, t1)      -> 16x^2    (D = 16.0)
 *   Step 5:  t5 = BBOP_MUL(E, t2)      -> 2x^3     (E = 2.0)
 *   Step 6:  t6 = BBOP_ADD(t3, t4)     -> 64x + 16x^2
 *   Step 7:  t7 = BBOP_ADD(A, t6)      -> 128 + 64x + 16x^2    (A = 128.0)
 *   Step 8:  t8 = BBOP_ADD(t7, t5)     -> 128 + 64x + 16x^2 + 2x^3
 *   Step 9:  t9 = BBOP_MUL(F, t1)      -> 32x^2    (F = 32.0)
 *   Step 10: t10 = BBOP_ADD(G, t9)     -> 256 + 32x^2           (G = 256.0)
 *   Step 11: t11 = BBOP_DIV(t8, t10)   -> numerator / denominator
 *   Step 12: t12 = BBOP_RELU(t11)       -> max(result, 0)
 *   Step 13: t13 = BBOP_RELU(t12)       -> min(result, 1)  (via RELU on 1-result)
 *   Step 14: return BBOP_CPY(t13)       -> final output
 *
 * Total: 5 BBOP_MUL, 4 BBOP_ADD, 1 BBOP_DIV, 2 BBOP_RELU, 1 BBOP_CPY = 13 ops
 */

struct F6NearestDecomp {
    static constexpr int NUM_OPS = 14;

    // Coefficients (stored as fixed-point in BRAM)
    static constexpr uint32_t A = 128 << 12;  // 128.0 in 12-bit fixed
    static constexpr uint32_t B = 0;          // input x (address offset)
    static constexpr uint32_t C = 64 << 12;   // 64.0
    static constexpr uint32_t D = 16 << 12;   // 16.0
    static constexpr uint32_t E = 2 << 12;    // 2.0
    static constexpr uint32_t F = 32 << 12;   // 32.0
    static constexpr uint32_t G = 256 << 12;  // 256.0

    // BBOP sequence
    static constexpr BbopOp ops[NUM_OPS] = {
        BbopOp::BBOP_MUL,  // t1 = x^2
        BbopOp::BBOP_MUL,  // t2 = x^3
        BbopOp::BBOP_MUL,  // t3 = 64x
        BbopOp::BBOP_MUL,  // t4 = 16x^2
        BbopOp::BBOP_MUL,  // t5 = 2x^3
        BbopOp::BBOP_ADD,  // t6 = 64x + 16x^2
        BbopOp::BBOP_ADD,  // t7 = 128 + ...
        BbopOp::BBOP_ADD,  // t8 = numerator
        BbopOp::BBOP_MUL,  // t9 = 32x^2
        BbopOp::BBOP_ADD,  // t10 = denominator
        BbopOp::BBOP_DIV,  // t11 = numerator/denominator
        BbopOp::BBOP_RELU, // t12 = max(., 0)
        BbopOp::BBOP_RELU, // t13 = min(., 1) via RELU(1-result)
        BbopOp::BBOP_CPY,  // final output
    };
};

void
printDecomposition()
{
    printf("f_6_nearest(x) = min(max((128 + 64x + 16x^2 + 2x^3) / "
           "(256 + 32x^2), 0), 1)\n");
    printf("\n");
    printf("BBOP Decomposition (%d operations):\n",
           F6NearestDecomp::NUM_OPS);

    const char *descriptions[] = {
        "t1  = BBOP_MUL(B, B)       -> x^2",
        "t2  = BBOP_MUL(B, t1)      -> x^3",
        "t3  = BBOP_MUL(C, B)       -> 64x",
        "t4  = BBOP_MUL(D, t1)      -> 16x^2",
        "t5  = BBOP_MUL(E, t2)      -> 2x^3",
        "t6  = BBOP_ADD(t3, t4)     -> 64x + 16x^2",
        "t7  = BBOP_ADD(A, t6)      -> 128 + 64x + 16x^2",
        "t8  = BBOP_ADD(t7, t5)     -> 128 + 64x + 16x^2 + 2x^3",
        "t9  = BBOP_MUL(F, t1)      -> 32x^2",
        "t10 = BBOP_ADD(G, t9)      -> 256 + 32x^2",
        "t11 = BBOP_DIV(t8, t10)    -> numerator / denominator",
        "t12 = BBOP_RELU(t11)        -> max(result, 0)",
        "t13 = BBOP_RELU(1 - t12)    -> min(result, 1)",
        "t14 = BBOP_CPY(t13)        -> final output",
    };

    for (int i = 0; i < F6NearestDecomp::NUM_OPS; i++) {
        printf("  [%2d] %s\n", i, descriptions[i]);
    }

    printf("\n");
    printf("Breakdown by operation type:\n");
    printf("  BBOP_MUL:  5 (5 multipliers, 2 carry-select selected)\n");
    printf("  BBOP_ADD:  4 (4 adders, Kogge-Stone selected)\n");
    printf("  BBOP_DIV:  1 (modeled as multiplier, carry-select selected)\n");
    printf("  BBOP_RELU: 2 (2 ReLU units)\n");
    printf("  BBOP_CPY:  1 (1 copy / passthrough)\n");
    printf("  Total:    13 operations\n");
}

int
main()
{
    printDecomposition();
    return 0;
}
