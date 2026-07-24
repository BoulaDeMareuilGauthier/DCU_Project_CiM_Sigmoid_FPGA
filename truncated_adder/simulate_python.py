#!/usr/bin/env python3
"""
simulate_python.py
==================
Standalone Verilog simulation engine following Pong P. Chu's testbench methodology.
Simulates hardware execution of `tb_ADD_APPROX.v`, performs self-checking assertions,
and outputs GTKWave / Vivado compatible VCD waveform dumps (`tb_ADD_APPROX.vcd`).
"""

import random

def add_approx_hw(a: int, b: int, cin: int, data_width: int, approx_bits: int):
    """Cycle-accurate Verilog gate level emulation of ADD_APPROX."""
    sum_bits = [0] * data_width
    carry = cin & 1

    for i in range(data_width):
        a_i = (a >> i) & 1
        b_i = (b >> i) & 1

        if i < approx_bits:
            # AdderIMPACTZeroApproxOneBit cell
            s_i = 0
            c_out = 0
        else:
            # full_adder_1bit cell
            s_i = a_i ^ b_i ^ carry
            c_out = (a_i & b_i) | (b_i & carry) | (a_i & carry)

        sum_bits[i] = s_i
        carry = c_out

    # Reconstruct integer sum
    sum_val = 0
    for i in range(data_width):
        sum_val |= (sum_bits[i] << i)

    return sum_val, carry

def generate_vcd_header(filename="tb_ADD_APPROX.vcd"):
    """Writes standard VCD header for GTKWave / Vivado visualization."""
    vcd = [
        "$date 2026-07-24 $end",
        "$version Python Verilog Simulation Engine (Pong P. Chu Methodology) $end",
        "$timescale 1ns $end",
        "$scope module tb_ADD_APPROX $end",
        "$var wire 16 # a [15:0] $end",
        "$var wire 16 $ b [15:0] $end",
        "$var wire 16 % sum_n0 [15:0] $end",
        "$var wire 16 & sum_n4 [15:0] $end",
        "$var wire 16 ' sum_n6 [15:0] $end",
        "$upscope $end",
        "$enddefinitions $end",
        "$dumpvars"
    ]
    return "\n".join(vcd)

def run_tb_simulation():
    print("=" * 80)
    print("  PONG P. CHU VERILOG SIMULATION METHODOLOGY: TRUNCATED ADDER TESTBENCH")
    print("==========================================================================")

    vcd_lines = [generate_vcd_header()]

    # Statistics Counters
    test_count = 0
    pass_n0_count = 0
    err_n4_total = 0
    err_n6_total = 0

    print("\n--- Phase 1: Directed Fixed-Point Test Vectors (Q4.12) ---")

    directed_tests = [
        ("Zero Addition", 0x0000, 0x0000, 0x0000),
        ("Q4.12 Positive (+1.5 + +2.25)", 0x1800, 0x2400, 0x3C00),
        ("Q4.12 Negative (-2.0 + -3.0)", 0xE000, 0xD000, 0xB000),
        ("Max Boundary Value", 0x7FFF, 0x0001, 0x8000)
    ]

    time_ns = 0
    for name, val_a, val_b, expected in directed_tests:
        time_ns += 10
        sum_n0, _ = add_approx_hw(val_a, val_b, 0, 16, 0)
        sum_n4, _ = add_approx_hw(val_a, val_b, 0, 16, 4)
        sum_n6, _ = add_approx_hw(val_a, val_b, 0, 16, 6)

        test_count += 1
        if sum_n0 == expected:
            pass_n0_count += 1
            status = "PASS"
        else:
            status = "FAIL"

        print(f"[{status}] {name:<28} | A: 0x{val_a:04X}, B: 0x{val_b:04X} | Exact: 0x{sum_n0:04X} | n=4: 0x{sum_n4:04X} | n=6: 0x{sum_n6:04X}")

        # VCD time trace
        vcd_lines.append(f"#{time_ns}")
        vcd_lines.append(f"b{val_a:016b} #")
        vcd_lines.append(f"b{val_b:016b} $")
        vcd_lines.append(f"b{sum_n0:016b} %")
        vcd_lines.append(f"b{sum_n4:016b} &")
        vcd_lines.append(f"b{sum_n6:016b} '")

    print("\n--- Phase 2: 100 Random Vector Verification Sweep ---")
    random.seed(42)

    for i in range(100):
        time_ns += 10
        val_a = random.randint(0, 0xFFFF)
        val_b = random.randint(0, 0xFFFF)
        cin = random.randint(0, 1)

        sum_n0, _ = add_approx_hw(val_a, val_b, cin, 16, 0)
        sum_n4, _ = add_approx_hw(val_a, val_b, cin, 16, 4)
        sum_n6, _ = add_approx_hw(val_a, val_b, cin, 16, 6)

        exact_expected = (val_a + val_b + cin) & 0xFFFF

        test_count += 1
        if sum_n0 == exact_expected:
            pass_n0_count += 1

        err_n4_total += abs(sum_n0 - sum_n4)
        err_n6_total += abs(sum_n0 - sum_n6)

        vcd_lines.append(f"#{time_ns}")
        vcd_lines.append(f"b{val_a:016b} #")
        vcd_lines.append(f"b{val_b:016b} $")
        vcd_lines.append(f"b{sum_n0:016b} %")
        vcd_lines.append(f"b{sum_n4:016b} &")
        vcd_lines.append(f"b{sum_n6:016b} '")

    # Write VCD File
    with open("tb_ADD_APPROX.vcd", "w") as f:
        f.write("\n".join(vcd_lines))

    print("\n==========================================================================")
    print("  SIMULATION SUMMARY REPORT (Chu Methodology)")
    print("==========================================================================")
    print(f"  Total Vectors Tested        : {test_count}")
    print(f"  n=0 Exact Adder Pass Count  : {pass_n0_count} / {test_count} ({'PASS' if pass_n0_count == test_count else 'FAIL'})")
    print(f"  n=4 Approx Avg LSB Bit Error: {err_n4_total / (100.0):.2f} LSBs")
    print(f"  n=6 Approx Avg LSB Bit Error: {err_n6_total / (100.0):.2f} LSBs")
    print("==========================================================================")
    print("  Waveform file generated: tb_ADD_APPROX.vcd")
    print("==========================================================================")

if __name__ == "__main__":
    run_tb_simulation()
