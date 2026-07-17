# -*- mode:python -*-

# Copyright (c) 2025 CMU SAFARI Group
# Licensed under the MIT License.

# Example configuration: DAFTPUM-LAT controller with gem5 BRAM
#
# This script demonstrates how to configure a DAFTPUM-LAT controller
# attached to a BRAM memory channel in gem5.

import m5
from m5.objects import *
from m5.params import *
from m5.convert import *

# ---- System setup ----
system = System()
system.clk_domain = SrcClockDomain(clock="2GHz", voltage_domain=VoltageDomain())
system.mem_mode = 'timing'

# ---- Memory controller (BRAM channel) ----
# BRAM: 32KB capacity, 40ns latency, 64-byte cache line
bram = DDR3_1600_8x8()
bram.range = AddrRange(size="32kB")
bram.tCL = 11  # CAS latency (ticks)
bram.tRCD = 11
bram.tRP = 11
system.mem_ctrl = bram

# ---- DAFTPUM-LAT Controller ----
# Attach to BRAM channel with 64 subarrays, SIMD width 65536
daftpum = DaftpumLatController(
    system=system,
    bram_channel=bram,
    num_subarrays=64,
    simd_width=65536,
    tfaw_enabled=False,
    aap_latency_ns=49.0,
    aap_energy_nj=0.871,
    bbop_budget_ns=0.0,     # no per-bbop budget
    bbop_budget_nj=0.0,     # no per-bbop energy budget
    max_bit_precision=63
)

# ---- Example: Process a vector of 1024 fixed-point elements ----
print("DAFTPUM-LAT controller configured:")
print(f"  Subarrays: {daftpum.num_subarrays}")
print(f"  SIMD width: {daftpum.simd_width}")
print(f"  TFAW enabled: {daftpum.tfaw_enabled}")
print(f"  AAP latency: {daftpum.aap_latency_ns} ns")
print(f"  AAP energy: {daftpum.aap_energy_nj} nJ")
print(f"  Max bit precision: {daftpum.max_bit_precision}")

# ---- Simulate workload ----
# In a real simulation, the C++ DaftpumLatController would:
#   1. Read BRAM data to detect dynamic bit-precision
#   2. Auto-select fastest adder/multiplier circuit
#   3. Compute latency/energy using the cost model
#   4. Partition work across 64 subarrays
#   5. Schedule completion events at predicted finish time
#
# Example workflow:
#   finish_tick = daftpum.submitBbop(
#       BbopOp.BBOP_MUL, addrA, addrB, addrC, size=1024, bbopId=0)
#   m5.simulate()  # runs until finish_tick
#   result = daftpum.getLastResult()
#   print(f"Latency: {result.parallelLatencyNs} ns, "
#         f"Energy: {result.energyNj} nJ")

system.port = system.mem_ctrl.port
m5.simulate()
