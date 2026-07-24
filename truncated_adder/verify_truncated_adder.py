#!/usr/bin/env python3
"""
verify_truncated_adder.py
========================
Python verification and error analysis script for the Truncated Adder (ADD_APPROX).
Replicates the evaluation methodology and metrics from the paper:
"Truncated Adder Integration in a Convolutional Neural Network Approximate Accelerator"
(Lim Qi Yang et al., 2025 IEEE ICSyS)
Zero external dependencies (uses standard python random module).
"""

import random

def to_q4_12(val: float) -> int:
    """Convert a float to 16-bit Q4.12 2's complement integer."""
    scaled = int(round(val * 4096.0))
    # Clamp to 16-bit signed range [-32768, 32767]
    clamped = max(-32768, min(32767, scaled))
    return clamped & 0xFFFF

def q4_12_to_float(val_16bit: int) -> float:
    """Convert a 16-bit 2's complement integer to float (Q4.12)."""
    if val_16bit & 0x8000:
        signed_val = val_16bit - 65536
    else:
        signed_val = val_16bit
    return signed_val / 4096.0

def add_approx(a_16bit: int, b_16bit: int, approx_bits: int) -> int:
    """
    Simulates ADD_APPROX hardware logic:
    - n LSB bits (0..n-1): Sum = 0 (zero truncation)
    - (16-n) MSB bits (n..15): Full addition using accurate bit addition with carry.
    """
    if approx_bits >= 16:
        return 0
    if approx_bits <= 0:
        return (a_16bit + b_16bit) & 0xFFFF

    # Mask for approximation bits
    approx_mask = (1 << approx_bits) - 1
    accurate_mask = (~approx_mask) & 0xFFFF

    # Truncate LSBs (zero truncation)
    a_msb = a_16bit & accurate_mask
    b_msb = b_16bit & accurate_mask

    # Precise addition on MSBs
    approx_sum = (a_msb + b_msb) & accurate_mask

    return approx_sum & 0xFFFF

def run_evaluation():
    print("=" * 80)
    print(" TRUNCATED ADDER (ADD_APPROX) VERIFICATION & ERROR ANALYSIS")
    print(" Reference: Lim Qi Yang et al., IEEE ICSyS 2025")
    print("=" * 80)

    random.seed(42)

    # Approximate bit configurations to evaluate (Table IV in paper)
    approx_configs = [2, 4, 6, 8, 10, 12, 14, 16]

    num_samples = 1000
    num_datasets = 5

    mpe_results = {}

    for n_bits in approx_configs:
        dataset_errors = []
        for ds in range(num_datasets):
            a_floats = [random.uniform(-4.0, 4.0) for _ in range(num_samples)]
            b_floats = [random.uniform(-4.0, 4.0) for _ in range(num_samples)]

            errors_pct = []
            for af, bf in zip(a_floats, b_floats):
                a_q = to_q4_12(af)
                b_q = to_q4_12(bf)

                # Exact hardware addition
                exact_q = (a_q + b_q) & 0xFFFF
                exact_val = q4_12_to_float(exact_q)

                # Approximate hardware addition
                approx_q = add_approx(a_q, b_q, n_bits)
                approx_val = q4_12_to_float(approx_q)

                # Absolute Percentage Error (%)
                if abs(exact_val) > 1e-4:
                    err_pct = abs(exact_val - approx_val) / abs(exact_val) * 100.0
                else:
                    err_pct = abs(exact_val - approx_val) * 100.0

                errors_pct.append(err_pct)

            dataset_errors.append(sum(errors_pct) / len(errors_pct))

        mean_mpe = sum(dataset_errors) / len(dataset_errors)
        mpe_results[n_bits] = (dataset_errors, mean_mpe)

    print("\n--- REPRODUCED ERROR METRICS (Compare with Paper Table IV) ---")
    header = f"{'Approx Bits':<12} | {'Data 1 [%]':<10} | {'Data 2 [%]':<10} | {'Data 3 [%]':<10} | {'Data 4 [%]':<10} | {'Data 5 [%]':<10} | {'Mean Error [%]':<14}"
    print(header)
    print("-" * len(header))

    # Paper Table IV reference values for comparison
    paper_ref = {
        2: 0.83,
        4: 1.74,
        6: 2.90,
        8: 6.89,
        10: 22.76,
        12: 82.14,
        14: 365.0,
        16: 100.0
    }

    for n_bits in approx_configs:
        ds_errs, mean_err = mpe_results[n_bits]
        ds_str = " | ".join([f"{e:10.2f}" for e in ds_errs])
        print(f"{n_bits:<12} | {ds_str} | {mean_err:14.2f} (Paper: {paper_ref[n_bits]:.2f}%)")

    print("\n--- PPA SAVINGS TABLE (Paper Table III Summary) ---")
    print(f"{'Approx Bits':<12} | {'Cell Count Saved [%]':<20} | {'Area Saved [%]':<15} | {'Power Saved [%]':<15}")
    print("-" * 70)
    ppa_data = [
        (2,  5.26,  5.46,  6.32),
        (4, 10.91, 12.13, 14.95),
        (6, 16.87, 18.90, 23.67),
        (8, 22.12, 24.58, 32.22),
        (10, 27.96, 30.99, 40.83),
        (12, 35.27, 36.97, 49.37),
        (14, 53.40, 50.58, 58.41),
        (16, 73.83, 75.24, 72.05)
    ]
    for b, c, a, p in ppa_data:
        print(f"{b:<12} | {c:<20.2f} | {a:<15.2f} | {p:<15.2f}")

    print("\nVerification execution finished cleanly.")

if __name__ == "__main__":
    run_evaluation()
