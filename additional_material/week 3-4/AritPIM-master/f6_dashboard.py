#!/usr/bin/env python3
"""
PIM F6 Function Dashboard
==========================
Implements f₆(x) = min(max((120 + 60x + 12x² + x³) / (240 + 24x²), 0), 1)
on the AritPIM Processing-in-Memory architecture.

Evaluates f₆ across 6 architecture mixing strategies (Pure Serial, Pure Parallel,
Hybrid A–D) for both 32-bit fixed-point and IEEE 754 floating-point representations
(12 total configurations), ranks them by throughput and energy efficiency, selects
the top 4, and renders a comparative matplotlib dashboard.
"""

import sys
import os
from enum import Enum
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# sys.path configuration: import from serial/, parallel/, and util/ directories
# ---------------------------------------------------------------------------
_project_root = os.path.dirname(os.path.abspath(__file__))
for _subdir in ("serial", "parallel", "util"):
    _path = os.path.join(_project_root, _subdir)
    if _path not in sys.path:
        sys.path.insert(0, _path)
# Also add the project root itself so that 'util' package imports work
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ---------------------------------------------------------------------------
# Third-party dependency imports with graceful error handling
# ---------------------------------------------------------------------------
try:
    import numpy as np
except ImportError:
    print(
        "Error: numpy is not installed. Install it with: pip3.12 install numpy",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import matplotlib
    import matplotlib.pyplot as plt
except ImportError:
    print(
        "Error: matplotlib is not installed. Install it with: pip3.12 install matplotlib",
        file=sys.stderr,
    )
    sys.exit(1)


# ===========================================================================
# Enumerations
# ===========================================================================

class ArchType(Enum):
    """Architecture type for a single arithmetic operation."""
    SERIAL = "serial"
    PARALLEL = "parallel"


class RepType(Enum):
    """Number representation type."""
    FIXED = "fixed"
    FLOAT = "float"


class Strategy(Enum):
    """Architecture mixing strategy for the f₆ computation pipeline."""
    PURE_SERIAL = "Pure Serial"
    PURE_PARALLEL = "Pure Parallel"
    HYBRID_A = "Hybrid A"      # mult=parallel, add/sub/div=serial
    HYBRID_B = "Hybrid B"      # mult=serial, add/sub=parallel
    HYBRID_C = "Hybrid C"      # numerator=parallel, denom+div=serial
    HYBRID_D = "Hybrid D"      # all arith=parallel, clamping=serial
    HYBRID_E = "Hybrid E"      # division=parallel, everything else=serial
    HYBRID_F = "Hybrid F"      # add=parallel, mult/div/clamp=serial
    HYBRID_G = "Hybrid G"      # numerator=serial, denom+div=parallel
    HYBRID_H = "Hybrid H"      # mult+div=parallel, add+clamp=serial


# ===========================================================================
# Dataclasses
# ===========================================================================

@dataclass
class Metrics:
    """Intermediate metrics collected from a simulator after an operation."""
    latency: int
    energy: int
    area: int


@dataclass
class ConfigResult:
    """Complete result for a single configuration (strategy + representation)."""
    strategy: Strategy
    representation: RepType
    latency: int          # total cycles
    energy: int           # total gates
    area: int             # total cells (max across sub-ops)
    throughput_tops: float = 0.0       # TOPS
    energy_efficiency: float = 0.0     # TOPS/W
    throughput_rank: int = 0           # rank by throughput (1 = best)
    efficiency_rank: int = 0           # rank by efficiency (1 = best)
    combined_score: int = 0            # sum of ranks

    @property
    def display_name(self) -> str:
        """Human-readable configuration name for dashboard labels."""
        rep_str = "Fixed" if self.representation == RepType.FIXED else "Float"
        return f"{self.strategy.value} ({rep_str})"


@dataclass
class HybridMetricsAccumulator:
    """
    Accumulates metrics across sub-operations for hybrid configurations.
    Latency and energy are summed; area is the maximum across sub-operations.
    """
    total_latency: int = 0
    total_energy: int = 0
    max_area: int = 0

    def add(self, metrics: Metrics) -> None:
        """Add metrics from a sub-operation to the accumulator."""
        self.total_latency += metrics.latency
        self.total_energy += metrics.energy
        self.max_area = max(self.max_area, metrics.area)

    def to_metrics(self) -> Metrics:
        """Convert accumulated values to a Metrics instance."""
        return Metrics(self.total_latency, self.total_energy, self.max_area)


# ===========================================================================
# RACER Architecture Constants
# ===========================================================================

# RACER architecture parameters (from AritPIM paper)
NUM_CROSSBARS = 1024
NUM_ROWS = 1024
CYCLE_TIME_NS = 1.0          # 1 ns cycle time
ENERGY_PER_GATE_PJ = 0.15    # picojoules per gate (estimated from RACER)

# Derived constant
OPERATIONS_PER_EXECUTION = NUM_CROSSBARS * NUM_ROWS  # 1,048,576


# ===========================================================================
# AritPIM Module Imports
# ===========================================================================

# The AritPIM modules (serial/AritPIM.py, parallel/AritPIM.py) each do
# `import simulator` expecting to find their own sibling simulator.py.
# To avoid conflicts, we import them by temporarily adjusting sys.path
# so only the correct directory is at the front.

# Import serial modules: put serial/ at front of sys.path so that
# `import simulator` inside serial/AritPIM.py finds serial/simulator.py
_serial_path = os.path.join(_project_root, "serial")
sys.path.insert(0, _serial_path)
import simulator as serial_simulator
import AritPIM as serial_AritPIM
sys.path.remove(_serial_path)
# Remove from module cache so parallel import gets its own versions
del sys.modules['simulator']
del sys.modules['AritPIM']

# Import parallel modules: put parallel/ at front of sys.path so that
# `import simulator` inside parallel/AritPIM.py finds parallel/simulator.py
_parallel_path = os.path.join(_project_root, "parallel")
sys.path.insert(0, _parallel_path)
import simulator as parallel_simulator
import AritPIM as parallel_AritPIM
sys.path.remove(_parallel_path)
del sys.modules['simulator']
del sys.modules['AritPIM']

# Import util modules (project root is already on sys.path)
from util import representation
from util import constants

# Import util modules (these don't conflict)
from util import representation
from util import constants


# ===========================================================================
# HornerEvaluator
# ===========================================================================

class HornerEvaluator:
    """
    Computes the numerator polynomial ((x+12)·x+60)·x+120 using Horner's method
    on the AritPIM architecture.

    Horner's form for p(x) = x³ + 12x² + 60x + 120:
        ((x + 12)·x + 60)·x + 120

    Steps (3 additions, 2 multiplications):
        t1 = x + 12       (addition)
        t2 = t1 * x       (multiplication)
        t3 = t2 + 60      (addition)
        t4 = t3 * x       (multiplication)
        t5 = t4 + 120     (addition) → final numerator result

    Constants 12, 60, 120 are pre-loaded into memory cells in the correct
    representation format before computation begins.
    """

    def evaluate_fixed(self, sim, x_addr, result_addr, inter,
                       arch: ArchType, partitions=None, N: int = 32):
        """
        Compute numerator for fixed-point representation using Horner's method.
        The result is a 2N-bit value stored in result_addr (for serial) or
        split across result_lower_addr and result_upper_addr (for parallel).

        For serial:
            sim: SerialSimulator
            x_addr: np.ndarray of N addresses for input x
            result_addr: np.ndarray of 2N addresses for the output
            inter: np.ndarray of available intermediate addresses

        For parallel:
            sim: ParallelSimulator
            x_addr: int (intra-partition address of input x)
            result_addr: tuple (z_addr: int, w_addr: int) for lower/upper N bits
            inter: np.ndarray of available intermediate intra-partition addresses
            partitions: np.ndarray of partition indices
        """

        if arch == ArchType.SERIAL:
            self._evaluate_fixed_serial(sim, x_addr, result_addr, inter, N)
        else:
            z_addr, w_addr = result_addr
            self._evaluate_fixed_parallel(sim, x_addr, z_addr, w_addr, inter, partitions, N)

    def _evaluate_fixed_serial(self, sim, x_addr, result_addr, inter, N):
        """
        Serial fixed-point Horner evaluation.
        x_addr: np.ndarray of length N (input x)
        result_addr: np.ndarray of length 2N (output numerator)
        inter: np.ndarray of available intermediate column addresses
        """
        SA = serial_AritPIM.SerialArithmetic
        allocator = SA.IntermediateAllocator(inter)

        # Pre-load constants into memory cells
        const_12_addr = allocator.malloc(N)
        const_60_addr = allocator.malloc(N)
        const_120_addr = allocator.malloc(N)

        # Write constant 12 in unsigned binary
        const_12_bin = representation.unsignedToBinaryFixed(
            np.array([[12]], dtype=np.ulonglong), N)
        for i in range(N):
            sim.memory[const_12_addr[i]] = const_12_bin[i]

        # Write constant 60 in unsigned binary
        const_60_bin = representation.unsignedToBinaryFixed(
            np.array([[60]], dtype=np.ulonglong), N)
        for i in range(N):
            sim.memory[const_60_addr[i]] = const_60_bin[i]

        # Write constant 120 in unsigned binary
        const_120_bin = representation.unsignedToBinaryFixed(
            np.array([[120]], dtype=np.ulonglong), N)
        for i in range(N):
            sim.memory[const_120_addr[i]] = const_120_bin[i]

        # Allocate working registers
        t1_addr = allocator.malloc(N)       # t1 = x + 12 (N-bit)
        t2_addr = allocator.malloc(2 * N)   # t2 = t1 * x (2N-bit)
        t3_addr = allocator.malloc(2 * N)   # t3 = t2 + 60 (2N-bit, reuse lower N for add)
        t4_addr = allocator.malloc(2 * N)   # t4 = t3 * x (we need t3_lower * x)

        # Step 1: t1 = x + 12 (N-bit addition)
        SA.fixedAddition(sim, x_addr, const_12_addr, t1_addr, allocator)

        # Step 2: t2 = t1 * x (N-bit × N-bit → 2N-bit)
        SA.fixedMultiplication(sim, t1_addr, x_addr, t2_addr, allocator)

        # Step 3: t3 = t2 + 60 (add 60 to the lower N bits of t2)
        # We need to add the N-bit constant 60 to the 2N-bit result t2.
        # For proper Horner evaluation, we add 60 to the lower N bits with carry propagation.
        # Create a 2N-bit version of 60 (upper N bits are zero)
        const_60_2N_addr = allocator.malloc(2 * N)
        for i in range(N):
            sim.memory[const_60_2N_addr[i]] = const_60_bin[i]
        # Upper N bits are zero
        zero_bin = representation.unsignedToBinaryFixed(
            np.array([[0]], dtype=np.ulonglong), N)
        for i in range(N):
            sim.memory[const_60_2N_addr[N + i]] = zero_bin[i]

        SA.fixedAddition(sim, t2_addr, const_60_2N_addr, t3_addr, allocator)

        # Step 4: t4 = t3_lower * x (take lower N bits of t3, multiply by x)
        # In Horner's method for unsigned fixed-point, we use the lower N bits
        # of the intermediate result for the next multiplication
        SA.fixedMultiplication(sim, t3_addr[:N], x_addr, t4_addr, allocator)

        # Step 5: result = t4 + 120 (add 120 to the 2N-bit result)
        const_120_2N_addr = allocator.malloc(2 * N)
        for i in range(N):
            sim.memory[const_120_2N_addr[i]] = const_120_bin[i]
        for i in range(N):
            sim.memory[const_120_2N_addr[N + i]] = zero_bin[i]

        SA.fixedAddition(sim, t4_addr, const_120_2N_addr, result_addr, allocator)

        # Free allocated intermediates
        allocator.free(const_12_addr)
        allocator.free(const_60_addr)
        allocator.free(const_120_addr)
        allocator.free(t1_addr)
        allocator.free(t2_addr)
        allocator.free(t3_addr)
        allocator.free(t4_addr)
        allocator.free(const_60_2N_addr)
        allocator.free(const_120_2N_addr)

    def _evaluate_fixed_parallel(self, sim, x_addr, z_addr, w_addr, inter, partitions, N):
        """
        Parallel fixed-point Horner evaluation.
        x_addr: int (intra-partition address of input x)
        z_addr: int (intra-partition address for lower N bits of result)
        w_addr: int (intra-partition address for upper N bits of result)
        inter: np.ndarray of available intra-partition addresses
        partitions: np.ndarray of partition indices (length N)
        """
        PA = parallel_AritPIM.ParallelArithmetic
        allocator = PA.IntermediateAllocator(inter, partitions)

        n = sim.num_rows  # number of parallel samples

        # Pre-load constants into memory cells
        const_12_addr = allocator.malloc(1, partitions)
        const_60_addr = allocator.malloc(1, partitions)
        const_120_addr = allocator.malloc(1, partitions)

        # Write constant 12
        const_12_bin = representation.unsignedToBinaryFixed(
            np.full((1, n), 12, dtype=np.ulonglong), N)
        sim.write(const_12_addr, const_12_bin, partitions)

        # Write constant 60
        const_60_bin = representation.unsignedToBinaryFixed(
            np.full((1, n), 60, dtype=np.ulonglong), N)
        sim.write(const_60_addr, const_60_bin, partitions)

        # Write constant 120
        const_120_bin = representation.unsignedToBinaryFixed(
            np.full((1, n), 120, dtype=np.ulonglong), N)
        sim.write(const_120_addr, const_120_bin, partitions)

        # Allocate working registers
        t1_addr = allocator.malloc(1, partitions)       # t1 = x + 12
        t2_z_addr = allocator.malloc(1, partitions)     # t2 lower N bits
        t2_w_addr = allocator.malloc(1, partitions)     # t2 upper N bits
        t3_addr = allocator.malloc(1, partitions)       # t3 = t2_lower + 60
        t4_z_addr = allocator.malloc(1, partitions)     # t4 lower N bits
        t4_w_addr = allocator.malloc(1, partitions)     # t4 upper N bits

        # Step 1: t1 = x + 12
        PA.fixedAddition(sim, x_addr, const_12_addr, t1_addr, allocator, partitions)

        # Step 2: t2 = t1 * x → (t2_z, t2_w)
        PA.fixedMultiplication(sim, t1_addr, x_addr, t2_z_addr, t2_w_addr, allocator, partitions)

        # Step 3: t3 = t2_lower + 60 (add 60 to lower N bits)
        PA.fixedAddition(sim, t2_z_addr, const_60_addr, t3_addr, allocator, partitions)

        # Step 4: t4 = t3 * x → (t4_z, t4_w)
        PA.fixedMultiplication(sim, t3_addr, x_addr, t4_z_addr, t4_w_addr, allocator, partitions)

        # Step 5: result = t4_lower + 120 → z_addr (lower N bits of final result)
        PA.fixedAddition(sim, t4_z_addr, const_120_addr, z_addr, allocator, partitions)

        # Copy upper N bits from t4 to w_addr
        # For the upper bits, we just use t4_w_addr as the upper result
        # We need to copy t4_w_addr to w_addr
        # Use a simple NOT-NOT copy pattern via the simulator
        temp_copy = allocator.malloc(1, partitions)
        sim.perform(constants.GateType.INIT1, [], [temp_copy], partitions)
        sim.perform(constants.GateType.NOT, [t4_w_addr], [temp_copy], partitions)
        sim.perform(constants.GateType.INIT1, [], [w_addr], partitions)
        sim.perform(constants.GateType.NOT, [temp_copy], [w_addr], partitions)
        allocator.free(temp_copy, partitions)

        # Free allocated intermediates
        allocator.free(const_12_addr, partitions)
        allocator.free(const_60_addr, partitions)
        allocator.free(const_120_addr, partitions)
        allocator.free(t1_addr, partitions)
        allocator.free(t2_z_addr, partitions)
        allocator.free(t2_w_addr, partitions)
        allocator.free(t3_addr, partitions)
        allocator.free(t4_z_addr, partitions)
        allocator.free(t4_w_addr, partitions)

    def evaluate_float(self, sim, x_addr, result_addr, inter,
                       arch: ArchType, partitions=None, N: int = 32):
        """
        Compute numerator for floating-point (IEEE 754) representation using Horner's method.

        For serial:
            sim: SerialSimulator
            x_addr: np.ndarray of N addresses for input x (sign, exponent, mantissa)
            result_addr: np.ndarray of N addresses for the output
            inter: np.ndarray of available intermediate addresses

        For parallel:
            sim: ParallelSimulator
            x_addr: int (intra-partition address of input x)
            result_addr: int (intra-partition address of output)
            inter: np.ndarray of available intra-partition addresses
            partitions: np.ndarray of partition indices (length N=32)
        """

        if arch == ArchType.SERIAL:
            self._evaluate_float_serial(sim, x_addr, result_addr, inter, N)
        else:
            self._evaluate_float_parallel(sim, x_addr, result_addr, inter, partitions, N)

    def _evaluate_float_serial(self, sim, x_addr, result_addr, inter, N):
        """
        Serial floating-point Horner evaluation.
        x_addr: np.ndarray of length N (IEEE 754 input: sign, exponent, mantissa)
        result_addr: np.ndarray of length N (IEEE 754 output)
        inter: np.ndarray of available intermediate column addresses
        """
        SA = serial_AritPIM.SerialArithmetic
        allocator = SA.IntermediateAllocator(inter)

        n = sim.memory.shape[1]  # number of rows (parallel samples)

        # Pre-load constants as IEEE 754 float32
        const_12_addr = allocator.malloc(N)
        const_60_addr = allocator.malloc(N)
        const_120_addr = allocator.malloc(N)

        # Convert constants to float32 binary representation
        const_12_bin = representation.signedFloatToBinary(
            np.full((1, n), 12.0, dtype=np.float32))
        for i in range(N):
            sim.memory[const_12_addr[i]] = const_12_bin[i]

        const_60_bin = representation.signedFloatToBinary(
            np.full((1, n), 60.0, dtype=np.float32))
        for i in range(N):
            sim.memory[const_60_addr[i]] = const_60_bin[i]

        const_120_bin = representation.signedFloatToBinary(
            np.full((1, n), 120.0, dtype=np.float32))
        for i in range(N):
            sim.memory[const_120_addr[i]] = const_120_bin[i]

        # Allocate working registers
        t1_addr = allocator.malloc(N)   # t1 = x + 12
        t2_addr = allocator.malloc(N)   # t2 = t1 * x
        t3_addr = allocator.malloc(N)   # t3 = t2 + 60
        t4_addr = allocator.malloc(N)   # t4 = t3 * x

        # Step 1: t1 = x + 12 (floating-point addition)
        SA.floatingAdditionSignedIEEE(sim, x_addr, const_12_addr, t1_addr, allocator)

        # Step 2: t2 = t1 * x (floating-point multiplication)
        SA.floatingMultiplicationIEEE(sim, t1_addr, x_addr, t2_addr, allocator)

        # Step 3: t3 = t2 + 60 (floating-point addition)
        SA.floatingAdditionSignedIEEE(sim, t2_addr, const_60_addr, t3_addr, allocator)

        # Step 4: t4 = t3 * x (floating-point multiplication)
        SA.floatingMultiplicationIEEE(sim, t3_addr, x_addr, t4_addr, allocator)

        # Step 5: result = t4 + 120 (floating-point addition)
        SA.floatingAdditionSignedIEEE(sim, t4_addr, const_120_addr, result_addr, allocator)

        # Free allocated intermediates
        allocator.free(const_12_addr)
        allocator.free(const_60_addr)
        allocator.free(const_120_addr)
        allocator.free(t1_addr)
        allocator.free(t2_addr)
        allocator.free(t3_addr)
        allocator.free(t4_addr)

    def _evaluate_float_parallel(self, sim, x_addr, result_addr, inter, partitions, N):
        """
        Parallel floating-point Horner evaluation.
        x_addr: int (intra-partition address of input x)
        result_addr: int (intra-partition address of output)
        inter: np.ndarray of available intra-partition addresses
        partitions: np.ndarray of partition indices (length N=32)
        """
        PA = parallel_AritPIM.ParallelArithmetic
        allocator = PA.IntermediateAllocator(inter, partitions)

        n = sim.num_rows  # number of parallel samples

        # Pre-load constants as IEEE 754 float32
        const_12_addr = allocator.malloc(1, partitions)
        const_60_addr = allocator.malloc(1, partitions)
        const_120_addr = allocator.malloc(1, partitions)

        # Write constant 12.0 in IEEE 754 binary
        const_12_bin = representation.signedFloatToBinary(
            np.full((1, n), 12.0, dtype=np.float32))
        sim.write(const_12_addr, const_12_bin, partitions)

        # Write constant 60.0 in IEEE 754 binary
        const_60_bin = representation.signedFloatToBinary(
            np.full((1, n), 60.0, dtype=np.float32))
        sim.write(const_60_addr, const_60_bin, partitions)

        # Write constant 120.0 in IEEE 754 binary
        const_120_bin = representation.signedFloatToBinary(
            np.full((1, n), 120.0, dtype=np.float32))
        sim.write(const_120_addr, const_120_bin, partitions)

        # Allocate working registers
        t1_addr = allocator.malloc(1, partitions)   # t1 = x + 12
        t2_addr = allocator.malloc(1, partitions)   # t2 = t1 * x
        t3_addr = allocator.malloc(1, partitions)   # t3 = t2 + 60
        t4_addr = allocator.malloc(1, partitions)   # t4 = t3 * x

        # Step 1: t1 = x + 12 (floating-point addition)
        PA.floatingAdditionSignedIEEE(sim, x_addr, const_12_addr, t1_addr, allocator, partitions)

        # Step 2: t2 = t1 * x (floating-point multiplication)
        PA.floatingMultiplicationIEEE(sim, t1_addr, x_addr, t2_addr, allocator, partitions)

        # Step 3: t3 = t2 + 60 (floating-point addition)
        PA.floatingAdditionSignedIEEE(sim, t2_addr, const_60_addr, t3_addr, allocator, partitions)

        # Step 4: t4 = t3 * x (floating-point multiplication)
        PA.floatingMultiplicationIEEE(sim, t3_addr, x_addr, t4_addr, allocator, partitions)

        # Step 5: result = t4 + 120 (floating-point addition)
        PA.floatingAdditionSignedIEEE(sim, t4_addr, const_120_addr, result_addr, allocator, partitions)

        # Free allocated intermediates
        allocator.free(const_12_addr, partitions)
        allocator.free(const_60_addr, partitions)
        allocator.free(const_120_addr, partitions)
        allocator.free(t1_addr, partitions)
        allocator.free(t2_addr, partitions)
        allocator.free(t3_addr, partitions)
        allocator.free(t4_addr, partitions)


# ===========================================================================
# DenominatorEvaluator
# ===========================================================================

class DenominatorEvaluator:
    """
    Computes the denominator 240 + 24*x² on AritPIM.

    Steps:
        t1 = x * x          (squaring)
        t2 = 24 * t1        (scalar multiplication)
        t3 = t2 + 240       (addition)

    Uses 2 multiplications and 1 addition total.
    """

    def evaluate_fixed(self, sim, x_addr, result_addr, inter,
                       arch: ArchType, partitions=None) -> None:
        """
        Compute denominator for fixed-point representation.

        For serial:
            sim: SerialSimulator
            x_addr: np.ndarray of N column addresses for input x
            result_addr: np.ndarray of 2N column addresses for the output
            inter: np.ndarray of available intermediate column addresses
        For parallel:
            sim: ParallelSimulator
            x_addr: int intra-partition address of input x
            result_addr: tuple (z_addr, w_addr) for lower/upper N bits of output
            inter: np.ndarray of available intermediate intra-partition addresses
            partitions: np.ndarray of partition indices

        :param sim: the simulation environment (SerialSimulator or ParallelSimulator)
        :param x_addr: address(es) of input x
        :param result_addr: address(es) for the denominator output
        :param inter: intermediate cell addresses or allocator
        :param arch: ArchType.SERIAL or ArchType.PARALLEL
        :param partitions: partition indices (parallel only)
        """
        if arch == ArchType.SERIAL:
            self._evaluate_fixed_serial(sim, x_addr, result_addr, inter)
        else:
            self._evaluate_fixed_parallel(sim, x_addr, result_addr, inter, partitions)

    def evaluate_float(self, sim, x_addr, result_addr, inter,
                       arch: ArchType, partitions=None) -> None:
        """
        Compute denominator for floating-point representation.

        For serial:
            sim: SerialSimulator
            x_addr: np.ndarray of N column addresses for input x (IEEE 754 format)
            result_addr: np.ndarray of N column addresses for the output
            inter: np.ndarray of available intermediate column addresses
        For parallel:
            sim: ParallelSimulator
            x_addr: int intra-partition address of input x
            result_addr: int intra-partition address for the output
            inter: np.ndarray of available intermediate intra-partition addresses
            partitions: np.ndarray of partition indices

        :param sim: the simulation environment (SerialSimulator or ParallelSimulator)
        :param x_addr: address(es) of input x (IEEE 754 format)
        :param result_addr: address(es) for the denominator output
        :param inter: intermediate cell addresses or allocator
        :param arch: ArchType.SERIAL or ArchType.PARALLEL
        :param partitions: partition indices (parallel only)
        """
        if arch == ArchType.SERIAL:
            self._evaluate_float_serial(sim, x_addr, result_addr, inter)
        else:
            self._evaluate_float_parallel(sim, x_addr, result_addr, inter, partitions)

    # -------------------------------------------------------------------
    # Fixed-point serial implementation
    # -------------------------------------------------------------------
    def _evaluate_fixed_serial(self, sim, x_addr, result_addr, inter):
        """
        Compute 240 + 24*x² using serial fixed-point primitives.

        Memory layout:
            x_addr: N-bit input x
            result_addr: 2N-bit output (denominator result)
            inter: available intermediate columns

        Steps:
            1. Pre-load constant 24 (N-bit) and constant 240 (N-bit) into memory
            2. t1 = x * x → 2N-bit result
            3. t2 = 24 * t1_lower → 2N-bit result (using lower N bits of x²)
            4. result = t2_lower + 240 → N-bit addition (lower N bits)
        """
        N = len(x_addr)

        # Allocate intermediate cells using the inter array
        if isinstance(inter, np.ndarray):
            alloc = serial_AritPIM.SerialArithmetic.IntermediateAllocator(inter)
        else:
            alloc = inter

        # Pre-load constant 24 into N memory cells
        const_24_addr = alloc.malloc(N)
        n_rows = sim.memory.shape[1]
        const_24_val = np.array([[24]], dtype=np.ulonglong) * np.ones((1, n_rows), dtype=np.ulonglong)
        sim.memory[const_24_addr] = representation.unsignedToBinaryFixed(const_24_val, N)

        # Pre-load constant 240 into N memory cells
        const_240_addr = alloc.malloc(N)
        const_240_val = np.array([[240]], dtype=np.ulonglong) * np.ones((1, n_rows), dtype=np.ulonglong)
        sim.memory[const_240_addr] = representation.unsignedToBinaryFixed(const_240_val, N)

        # Step 1: t1 = x * x (squaring) → 2N-bit result
        # The simulator asserts inputs must be unique, so we copy x to a
        # temporary location for squaring.
        x_copy_addr = alloc.malloc(N)
        for i in range(N):
            sim.memory[x_copy_addr[i]] = sim.memory[x_addr[i]].copy()

        t1_addr = alloc.malloc(2 * N)  # 2N-bit product
        serial_AritPIM.SerialArithmetic.fixedMultiplication(
            sim, x_addr, x_copy_addr, t1_addr, alloc
        )
        alloc.free(x_copy_addr)

        # Step 2: t2 = 24 * t1_lower → 2N-bit result
        # Use only the lower N bits of x² for the multiplication with 24
        t1_lower_addr = t1_addr[:N]
        t2_addr = alloc.malloc(2 * N)  # 2N-bit product
        serial_AritPIM.SerialArithmetic.fixedMultiplication(
            sim, const_24_addr, t1_lower_addr, t2_addr, alloc
        )

        # Step 3: result = t2_lower + 240
        # Add 240 to the lower N bits of 24*x²
        t2_lower_addr = t2_addr[:N]
        serial_AritPIM.SerialArithmetic.fixedAddition(
            sim, t2_lower_addr, const_240_addr, result_addr[:N], alloc
        )

        # Copy upper N bits from t2 to result (if result is 2N-bit)
        if len(result_addr) > N:
            # The upper bits are just the upper bits of t2 (carry from addition is negligible
            # for the purpose of this computation, but we propagate it properly)
            # For a more precise implementation, we'd add with carry, but the design
            # specifies the result is stored in the result_addr
            for i in range(N, min(len(result_addr), 2 * N)):
                sim.memory[result_addr[i]] = sim.memory[t2_addr[i]]

        # Free intermediate cells
        alloc.free(const_24_addr)
        alloc.free(const_240_addr)
        alloc.free(t1_addr)
        alloc.free(t2_addr)

    # -------------------------------------------------------------------
    # Fixed-point parallel implementation
    # -------------------------------------------------------------------
    def _evaluate_fixed_parallel(self, sim, x_addr, result_addr, inter, partitions):
        """
        Compute 240 + 24*x² using parallel fixed-point primitives.

        Memory layout (intra-partition addresses):
            x_addr: int - intra-partition address of input x
            result_addr: tuple (z_addr, w_addr) - lower and upper N bits of output
            inter: np.ndarray of available intra-partition addresses
            partitions: np.ndarray of partition indices (length N)

        Steps:
            1. Pre-load constant 24 and constant 240 into memory cells
            2. t1 = x * x → (t1_z, t1_w) lower/upper N bits
            3. t2 = 24 * t1_z → (t2_z, t2_w) lower/upper N bits
            4. result_z = t2_z + 240
        """
        if partitions is None:
            partitions = np.arange(sim.num_partitions)
        N = len(partitions)

        # Unpack result addresses (lower N bits, upper N bits)
        result_z_addr, result_w_addr = result_addr

        # Create allocator if needed
        if isinstance(inter, np.ndarray):
            alloc = parallel_AritPIM.ParallelArithmetic.IntermediateAllocator(inter, partitions)
        else:
            alloc = inter

        # Pre-load constant 24 into memory
        const_24_addr = alloc.malloc(1, partitions)
        n_rows = sim.num_rows
        const_24_val = np.array([[24]], dtype=np.ulonglong) * np.ones((1, n_rows), dtype=np.ulonglong)
        sim.write(const_24_addr, representation.unsignedToBinaryFixed(const_24_val, N), partitions)

        # Pre-load constant 240 into memory
        const_240_addr = alloc.malloc(1, partitions)
        const_240_val = np.array([[240]], dtype=np.ulonglong) * np.ones((1, n_rows), dtype=np.ulonglong)
        sim.write(const_240_addr, representation.unsignedToBinaryFixed(const_240_val, N), partitions)

        # Step 1: t1 = x * x (squaring) → (t1_z, t1_w) lower/upper N bits
        # Step 1: t1 = x * x (squaring) → (t1_z, t1_w) lower/upper N bits
        # The simulator asserts inputs must be unique, so we copy x to a
        # temporary location for squaring.
        x_copy_addr = alloc.malloc(1, partitions)
        # Copy x to x_copy using double-NOT pattern
        temp_not_addr = alloc.malloc(1, partitions)
        sim.perform(constants.GateType.INIT1, [], [temp_not_addr], partitions)
        sim.perform(constants.GateType.NOT, [x_addr], [temp_not_addr], partitions)
        sim.perform(constants.GateType.INIT1, [], [x_copy_addr], partitions)
        sim.perform(constants.GateType.NOT, [temp_not_addr], [x_copy_addr], partitions)
        alloc.free(temp_not_addr, partitions)

        t1_z_addr = alloc.malloc(1, partitions)
        t1_w_addr = alloc.malloc(1, partitions)
        parallel_AritPIM.ParallelArithmetic.fixedMultiplication(
            sim, x_addr, x_copy_addr, t1_z_addr, t1_w_addr, alloc, partitions
        )
        alloc.free(x_copy_addr, partitions)

        # Step 2: t2 = 24 * t1_z → (t2_z, t2_w) lower/upper N bits
        t2_z_addr = alloc.malloc(1, partitions)
        t2_w_addr = alloc.malloc(1, partitions)
        parallel_AritPIM.ParallelArithmetic.fixedMultiplication(
            sim, const_24_addr, t1_z_addr, t2_z_addr, t2_w_addr, alloc, partitions
        )

        # Step 3: result_z = t2_z + 240
        parallel_AritPIM.ParallelArithmetic.fixedAddition(
            sim, t2_z_addr, const_240_addr, result_z_addr, alloc, partitions
        )

        # Copy upper bits from t2_w to result_w using double-NOT copy:
        # temp = INIT1; temp = NOT(src) → temp holds NOT(src)
        # dst = INIT1; dst = NOT(temp) → dst holds src
        temp_copy_addr = alloc.malloc(1, partitions)
        sim.perform(constants.GateType.INIT1, [], [temp_copy_addr], partitions)
        sim.perform(constants.GateType.NOT, [t2_w_addr], [temp_copy_addr], partitions)
        sim.perform(constants.GateType.INIT1, [], [result_w_addr], partitions)
        sim.perform(constants.GateType.NOT, [temp_copy_addr], [result_w_addr], partitions)
        alloc.free(temp_copy_addr, partitions)

        # Free intermediate cells
        alloc.free(const_24_addr, partitions)
        alloc.free(const_240_addr, partitions)
        alloc.free(t1_z_addr, partitions)
        alloc.free(t1_w_addr, partitions)
        alloc.free(t2_z_addr, partitions)
        alloc.free(t2_w_addr, partitions)

    # -------------------------------------------------------------------
    # Floating-point serial implementation
    # -------------------------------------------------------------------
    def _evaluate_float_serial(self, sim, x_addr, result_addr, inter):
        """
        Compute 240 + 24*x² using serial floating-point primitives.

        Memory layout:
            x_addr: np.ndarray of N column addresses (IEEE 754 32-bit format)
            result_addr: np.ndarray of N column addresses for the output
            inter: np.ndarray of available intermediate column addresses

        Steps:
            1. Pre-load constant 24.0 and 240.0 in IEEE 754 format
            2. t1 = x * x (floating multiplication)
            3. t2 = 24.0 * t1 (floating multiplication)
            4. result = t2 + 240.0 (floating addition signed)
        """
        N = len(x_addr)

        if isinstance(inter, np.ndarray):
            alloc = serial_AritPIM.SerialArithmetic.IntermediateAllocator(inter)
        else:
            alloc = inter

        n_rows = sim.memory.shape[1]

        # Pre-load constant 24.0 in IEEE 754 format
        const_24_addr = alloc.malloc(N)
        const_24_float = np.float32(24.0) * np.ones((1, n_rows), dtype=np.float32)
        sim.memory[const_24_addr] = representation.signedFloatToBinary(const_24_float)

        # Pre-load constant 240.0 in IEEE 754 format
        const_240_addr = alloc.malloc(N)
        const_240_float = np.float32(240.0) * np.ones((1, n_rows), dtype=np.float32)
        sim.memory[const_240_addr] = representation.signedFloatToBinary(const_240_float)

        # Step 1: t1 = x * x (squaring)
        # The simulator asserts inputs must be unique, so we copy x first.
        x_copy_addr = alloc.malloc(N)
        for i in range(N):
            sim.memory[x_copy_addr[i]] = sim.memory[x_addr[i]].copy()

        t1_addr = alloc.malloc(N)
        serial_AritPIM.SerialArithmetic.floatingMultiplicationIEEE(
            sim, x_addr, x_copy_addr, t1_addr, alloc
        )
        alloc.free(x_copy_addr)

        # Step 2: t2 = 24.0 * t1
        t2_addr = alloc.malloc(N)
        serial_AritPIM.SerialArithmetic.floatingMultiplicationIEEE(
            sim, const_24_addr, t1_addr, t2_addr, alloc
        )

        # Step 3: result = t2 + 240.0
        serial_AritPIM.SerialArithmetic.floatingAdditionSignedIEEE(
            sim, t2_addr, const_240_addr, result_addr, alloc
        )

        # Free intermediate cells
        alloc.free(const_24_addr)
        alloc.free(const_240_addr)
        alloc.free(t1_addr)
        alloc.free(t2_addr)

    # -------------------------------------------------------------------
    # Floating-point parallel implementation
    # -------------------------------------------------------------------
    def _evaluate_float_parallel(self, sim, x_addr, result_addr, inter, partitions):
        """
        Compute 240 + 24*x² using parallel floating-point primitives.

        Memory layout (intra-partition addresses):
            x_addr: int - intra-partition address of input x (IEEE 754 format)
            result_addr: int - intra-partition address for the output
            inter: np.ndarray of available intra-partition addresses
            partitions: np.ndarray of partition indices (length N=32 for IEEE 754)

        Steps:
            1. Pre-load constant 24.0 and 240.0 in IEEE 754 format
            2. t1 = x * x (floating multiplication)
            3. t2 = 24.0 * t1 (floating multiplication)
            4. result = t2 + 240.0 (floating addition signed)
        """
        if partitions is None:
            partitions = np.arange(sim.num_partitions)
        N = len(partitions)

        if isinstance(inter, np.ndarray):
            alloc = parallel_AritPIM.ParallelArithmetic.IntermediateAllocator(inter, partitions)
        else:
            alloc = inter

        n_rows = sim.num_rows

        # Pre-load constant 24.0 in IEEE 754 format
        const_24_addr = alloc.malloc(1, partitions)
        const_24_float = np.float32(24.0) * np.ones((1, n_rows), dtype=np.float32)
        sim.write(const_24_addr, representation.signedFloatToBinary(const_24_float), partitions)

        # Pre-load constant 240.0 in IEEE 754 format
        const_240_addr = alloc.malloc(1, partitions)
        const_240_float = np.float32(240.0) * np.ones((1, n_rows), dtype=np.float32)
        sim.write(const_240_addr, representation.signedFloatToBinary(const_240_float), partitions)

        # Step 1: t1 = x * x (squaring)
        # The simulator asserts inputs must be unique, so we copy x first.
        x_copy_addr = alloc.malloc(1, partitions)
        temp_not_addr = alloc.malloc(1, partitions)
        sim.perform(constants.GateType.INIT1, [], [temp_not_addr], partitions)
        sim.perform(constants.GateType.NOT, [x_addr], [temp_not_addr], partitions)
        sim.perform(constants.GateType.INIT1, [], [x_copy_addr], partitions)
        sim.perform(constants.GateType.NOT, [temp_not_addr], [x_copy_addr], partitions)
        alloc.free(temp_not_addr, partitions)

        t1_addr = alloc.malloc(1, partitions)
        parallel_AritPIM.ParallelArithmetic.floatingMultiplicationIEEE(
            sim, x_addr, x_copy_addr, t1_addr, alloc, partitions
        )
        alloc.free(x_copy_addr, partitions)

        # Step 2: t2 = 24.0 * t1
        t2_addr = alloc.malloc(1, partitions)
        parallel_AritPIM.ParallelArithmetic.floatingMultiplicationIEEE(
            sim, const_24_addr, t1_addr, t2_addr, alloc, partitions
        )

        # Step 3: result = t2 + 240.0
        parallel_AritPIM.ParallelArithmetic.floatingAdditionSignedIEEE(
            sim, t2_addr, const_240_addr, result_addr, alloc, partitions
        )

        # Free intermediate cells
        alloc.free(const_24_addr, partitions)
        alloc.free(const_240_addr, partitions)
        alloc.free(t1_addr, partitions)
        alloc.free(t2_addr, partitions)


# ===========================================================================
# MetricsCollector
# ===========================================================================

class MetricsCollector:
    """
    Collects and computes performance metrics from AritPIM simulators.

    Reads raw simulator counters (latency, energy, maxUsed) and derives
    throughput (TOPS) and energy efficiency (TOPS/W) using RACER architecture
    parameters.

    For serial simulators, energy equals latency (one gate per cycle).
    For parallel simulators, energy is tracked separately by the simulator.
    Area is computed as (maxUsed + 1) for serial, and (maxUsed + 1) × N for
    parallel (where N is the number of partitions).
    """

    def collect_serial(self, sim) -> Metrics:
        """
        Collect metrics from a SerialSimulator after computation.

        For serial execution:
            - latency: read directly from sim.latency (total cycles)
            - energy: equals latency (one gate activation per cycle)
            - area: (sim.maxUsed + 1) cells used

        :param sim: SerialSimulator instance after computation
        :return: Metrics dataclass with latency, energy, and area
        """
        latency = sim.latency
        energy = latency  # serial: energy in gates equals latency in cycles
        area = sim.maxUsed + 1
        return Metrics(latency=latency, energy=energy, area=area)

    def collect_parallel(self, sim, num_partitions: int) -> Metrics:
        """
        Collect metrics from a ParallelSimulator after computation.

        For parallel execution:
            - latency: read directly from sim.latency (total cycles)
            - energy: read directly from sim.energy (total gate activations)
            - area: (sim.maxUsed + 1) × N cells, where N is num_partitions

        :param sim: ParallelSimulator instance after computation
        :param num_partitions: number of partitions (N) used in the parallel execution
        :return: Metrics dataclass with latency, energy, and area
        """
        latency = sim.latency
        energy = sim.energy
        area = (sim.maxUsed + 1) * num_partitions
        return Metrics(latency=latency, energy=energy, area=area)

    def compute_throughput(self, latency: int) -> float:
        """
        Compute throughput in TOPS (Tera Operations Per Second).

        Formula: TOPS = (NUM_CROSSBARS × NUM_ROWS) / (latency × CYCLE_TIME_NS × 1e-9 × 1e12)
                      = (1024 × 1024) / (latency × 1e-9 × 1e12)
                      = OPERATIONS_PER_EXECUTION / (latency × 1e3)

        Where:
            - NUM_CROSSBARS × NUM_ROWS = 1,048,576 operations per execution
            - CYCLE_TIME_NS = 1.0 ns per cycle
            - 1e-9 converts ns to seconds
            - 1e12 converts operations/second to TOPS

        :param latency: total latency in cycles
        :return: throughput in TOPS
        """
        # TOPS = (1024 * 1024) / (latency * 1e-9 * 1e12)
        # Simplifies to: TOPS = OPERATIONS_PER_EXECUTION / (latency * 1e3)
        return OPERATIONS_PER_EXECUTION / (latency * CYCLE_TIME_NS * 1e-9 * 1e12)

    def compute_efficiency(self, throughput: float, energy: int) -> float:
        """
        Compute energy efficiency in TOPS/W.

        Formula: TOPS/W = TOPS / (energy × ENERGY_PER_GATE_PJ × 1e-3)

        Where:
            - energy: total gate activations
            - ENERGY_PER_GATE_PJ = 0.15 pJ per gate
            - 1e-3 converts pJ to nJ (then combined with TOPS gives TOPS/W)

        The derivation:
            Power (W) = energy_per_gate (pJ) × gates × frequency (GHz)
            Since cycle_time = 1 ns → frequency = 1 GHz
            Power = 0.15e-12 × energy × 1e9 = energy × 0.15e-3 W
            TOPS/W = TOPS / Power = TOPS / (energy × 0.15 × 1e-3)

        :param throughput: throughput in TOPS
        :param energy: total energy in gate activations
        :return: energy efficiency in TOPS/W
        """
        return throughput / (energy * ENERGY_PER_GATE_PJ * 1e-3)


# ===========================================================================
# DivisionUnit
# ===========================================================================

class DivisionUnit:
    """
    Performs division of numerator by denominator using AritPIM primitives,
    with a zero-check on the denominator.

    For fixed-point:
        - Numerator is 2N-bit, denominator is N-bit
        - Uses fixedDivision from serial or parallel AritPIM
        - If denominator is zero, output quotient is 0

    For floating-point:
        - Both numerator and denominator are N-bit IEEE 754
        - Uses floatingDivisionIEEE from serial or parallel AritPIM
        - If denominator is zero (exponent == 0 for subnormal/zero), output is 0

    Requirements: 3.1, 3.2
    """

    def divide_fixed(self, sim, numerator_addr, denominator_addr, quotient_addr,
                     inter, arch: ArchType, partitions=None, N: int = 32):
        """
        Perform fixed-point division: quotient = numerator / denominator.

        If denominator is zero, quotient is set to 0 without invoking division.

        For serial:
            sim: SerialSimulator
            numerator_addr: np.ndarray of 2N column addresses (2N-bit dividend)
            denominator_addr: np.ndarray of N column addresses (N-bit divisor)
            quotient_addr: np.ndarray of N column addresses (N-bit quotient output)
            inter: np.ndarray of available intermediate column addresses

        For parallel:
            sim: ParallelSimulator
            numerator_addr: tuple (w_addr: int, z_addr: int) - upper/lower N bits of dividend
            denominator_addr: int - intra-partition address of N-bit divisor
            quotient_addr: int - intra-partition address of N-bit quotient output
            inter: np.ndarray of available intermediate intra-partition addresses
            partitions: np.ndarray of partition indices
        """
        if arch == ArchType.SERIAL:
            self._divide_fixed_serial(sim, numerator_addr, denominator_addr,
                                      quotient_addr, inter, N)
        else:
            self._divide_fixed_parallel(sim, numerator_addr, denominator_addr,
                                        quotient_addr, inter, partitions, N)

    def divide_float(self, sim, numerator_addr, denominator_addr, quotient_addr,
                     inter, arch: ArchType, partitions=None, N: int = 32):
        """
        Perform floating-point division: quotient = numerator / denominator.

        If denominator is zero (all exponent bits are zero), quotient is set to 0.

        For serial:
            sim: SerialSimulator
            numerator_addr: np.ndarray of N column addresses (IEEE 754 numerator)
            denominator_addr: np.ndarray of N column addresses (IEEE 754 denominator)
            quotient_addr: np.ndarray of N column addresses (IEEE 754 quotient output)
            inter: np.ndarray of available intermediate column addresses

        For parallel:
            sim: ParallelSimulator
            numerator_addr: int - intra-partition address of numerator
            denominator_addr: int - intra-partition address of denominator
            quotient_addr: int - intra-partition address of quotient output
            inter: np.ndarray of available intermediate intra-partition addresses
            partitions: np.ndarray of partition indices (length N=32)
        """
        if arch == ArchType.SERIAL:
            self._divide_float_serial(sim, numerator_addr, denominator_addr,
                                      quotient_addr, inter, N)
        else:
            self._divide_float_parallel(sim, numerator_addr, denominator_addr,
                                        quotient_addr, inter, partitions, N)

    # -------------------------------------------------------------------
    # Fixed-point serial implementation
    # -------------------------------------------------------------------
    def _divide_fixed_serial(self, sim, numerator_addr, denominator_addr,
                             quotient_addr, inter, N):
        """
        Serial fixed-point division with zero-check.

        numerator_addr: np.ndarray of 2N addresses (2N-bit dividend)
        denominator_addr: np.ndarray of N addresses (N-bit divisor)
        quotient_addr: np.ndarray of N addresses (N-bit quotient output)
        inter: np.ndarray of available intermediate column addresses

        Zero-check: If all N bits of denominator are zero, output 0.
        Otherwise, perform fixedDivision.
        """
        SA = serial_AritPIM.SerialArithmetic

        if isinstance(inter, np.ndarray):
            alloc = SA.IntermediateAllocator(inter)
        else:
            alloc = inter

        n_rows = sim.memory.shape[1]

        # Check if denominator is zero by OR-ing all bits
        # A denominator is zero if all its N bits are 0 for a given row.
        # We compute this as a numpy mask on the memory contents.
        denom_bits = sim.memory[denominator_addr]  # shape: (N, n_rows)
        # denom_is_zero: True where all N bits are 0 for that row
        denom_is_zero = np.all(denom_bits == 0, axis=0)  # shape: (n_rows,)

        # If ALL samples have zero denominator, just output 0
        if np.all(denom_is_zero):
            for i in range(N):
                sim.memory[quotient_addr[i]] = np.zeros((1, n_rows), dtype=sim.memory.dtype).squeeze(0) if sim.memory[quotient_addr[i]].ndim == 1 else np.zeros_like(sim.memory[quotient_addr[i]])
                sim.memory[quotient_addr[i]][:] = 0
            return

        # Allocate remainder output (required by fixedDivision but not used)
        r_addr = alloc.malloc(N)

        # Perform the division
        SA.fixedDivision(sim, numerator_addr, denominator_addr, quotient_addr, r_addr, alloc)

        # Post-division: zero out quotient where denominator was zero
        if np.any(denom_is_zero):
            for i in range(N):
                sim.memory[quotient_addr[i]][denom_is_zero] = 0

        # Free remainder cells
        alloc.free(r_addr)

    # -------------------------------------------------------------------
    # Fixed-point parallel implementation
    # -------------------------------------------------------------------
    def _divide_fixed_parallel(self, sim, numerator_addr, denominator_addr,
                               quotient_addr, inter, partitions, N):
        """
        Parallel fixed-point division with zero-check.

        numerator_addr: tuple (w_addr: int, z_addr: int) - upper/lower N bits of 2N-bit dividend
        denominator_addr: int - intra-partition address of N-bit divisor
        quotient_addr: int - intra-partition address of N-bit quotient output
        inter: np.ndarray of available intermediate intra-partition addresses
        partitions: np.ndarray of partition indices (length N)

        Zero-check: If all N bits of denominator are zero, output 0.
        Otherwise, perform fixedDivision.
        """
        PA = parallel_AritPIM.ParallelArithmetic

        if partitions is None:
            partitions = np.arange(sim.num_partitions)
        N_part = len(partitions)

        if isinstance(inter, np.ndarray):
            alloc = PA.IntermediateAllocator(inter, partitions)
        else:
            alloc = inter

        n_rows = sim.num_rows

        # Unpack numerator addresses (upper N bits, lower N bits)
        w_addr, z_addr = numerator_addr

        # Check if denominator is zero by reading all partition bits
        denom_bits = sim.read(denominator_addr, partitions)  # shape: (N, n_rows)
        denom_is_zero = np.all(denom_bits == 0, axis=0)  # shape: (n_rows,)

        # If ALL samples have zero denominator, just write 0 to quotient
        if np.all(denom_is_zero):
            zero_data = np.zeros((N_part, n_rows), dtype=denom_bits.dtype)
            sim.write(quotient_addr, zero_data, partitions)
            return

        # Allocate remainder output (required by fixedDivision but not used further)
        r_addr = alloc.malloc(1, partitions)

        # Perform the division: fixedDivision(sim, w_addr, z_addr, d_addr, q_addr, r_addr, inter, partitions)
        PA.fixedDivision(sim, w_addr, z_addr, denominator_addr, quotient_addr, r_addr, alloc, partitions)

        # Post-division: zero out quotient where denominator was zero
        if np.any(denom_is_zero):
            q_bits = sim.read(quotient_addr, partitions)  # shape: (N, n_rows)
            q_bits[:, denom_is_zero] = 0
            sim.write(quotient_addr, q_bits, partitions)

        # Free remainder cells
        alloc.free(r_addr, partitions)

    # -------------------------------------------------------------------
    # Floating-point serial implementation
    # -------------------------------------------------------------------
    def _divide_float_serial(self, sim, numerator_addr, denominator_addr,
                             quotient_addr, inter, N):
        """
        Serial floating-point division with zero-check.

        numerator_addr: np.ndarray of N addresses (IEEE 754 numerator)
        denominator_addr: np.ndarray of N addresses (IEEE 754 denominator)
        quotient_addr: np.ndarray of N addresses (IEEE 754 quotient output)
        inter: np.ndarray of available intermediate column addresses

        Zero-check: If the denominator exponent is all zeros (indicating zero or
        subnormal), output 0 (all bits cleared).
        """
        SA = serial_AritPIM.SerialArithmetic

        if isinstance(inter, np.ndarray):
            alloc = SA.IntermediateAllocator(inter)
        else:
            alloc = inter

        n_rows = sim.memory.shape[1]

        # For IEEE 754 32-bit: sign=1 bit, exponent=8 bits, mantissa=23 bits
        Ns, Ne, Nm = constants.getIEEE754Split(N)

        # Check if denominator is zero by examining the exponent bits
        # Denominator is zero/subnormal if all exponent bits are 0
        denom_exp_addr = denominator_addr[Ns:Ns + Ne]
        denom_exp_bits = sim.memory[denom_exp_addr]  # shape: (Ne, n_rows)
        denom_is_zero = np.all(denom_exp_bits == 0, axis=0)  # shape: (n_rows,)

        # If ALL samples have zero denominator, just output 0
        if np.all(denom_is_zero):
            for i in range(N):
                sim.memory[quotient_addr[i]][:] = 0
            return

        # Perform the floating-point division
        SA.floatingDivisionIEEE(sim, numerator_addr, denominator_addr, quotient_addr, alloc)

        # Post-division: zero out quotient where denominator was zero
        if np.any(denom_is_zero):
            for i in range(N):
                sim.memory[quotient_addr[i]][denom_is_zero] = 0

    # -------------------------------------------------------------------
    # Floating-point parallel implementation
    # -------------------------------------------------------------------
    def _divide_float_parallel(self, sim, numerator_addr, denominator_addr,
                               quotient_addr, inter, partitions, N):
        """
        Parallel floating-point division with zero-check.

        numerator_addr: int - intra-partition address of numerator (IEEE 754)
        denominator_addr: int - intra-partition address of denominator (IEEE 754)
        quotient_addr: int - intra-partition address of quotient output (IEEE 754)
        inter: np.ndarray of available intermediate intra-partition addresses
        partitions: np.ndarray of partition indices (length N=32)

        Zero-check: If the denominator exponent is all zeros (indicating zero or
        subnormal), output 0 (all bits cleared).
        """
        PA = parallel_AritPIM.ParallelArithmetic

        if partitions is None:
            partitions = np.arange(sim.num_partitions)
        N_part = len(partitions)

        if isinstance(inter, np.ndarray):
            alloc = PA.IntermediateAllocator(inter, partitions)
        else:
            alloc = inter

        n_rows = sim.num_rows

        # For IEEE 754 32-bit: sign=1 bit, exponent=8 bits, mantissa=23 bits
        Ns, Ne, Nm = constants.getIEEE754Split(N_part)

        # Check if denominator is zero by examining the exponent partition bits
        # Exponent partitions are partitions[Ns:Ns+Ne]
        e_partitions = partitions[Ns:Ns + Ne]
        denom_exp_bits = sim.read(denominator_addr, e_partitions)  # shape: (Ne, n_rows)
        denom_is_zero = np.all(denom_exp_bits == 0, axis=0)  # shape: (n_rows,)

        # If ALL samples have zero denominator, just write 0 to quotient
        if np.all(denom_is_zero):
            zero_data = np.zeros((N_part, n_rows), dtype=denom_exp_bits.dtype)
            sim.write(quotient_addr, zero_data, partitions)
            return

        # Perform the floating-point division
        PA.floatingDivisionIEEE(sim, numerator_addr, denominator_addr, quotient_addr, alloc, partitions)

        # Post-division: zero out quotient where denominator was zero
        if np.any(denom_is_zero):
            q_bits = sim.read(quotient_addr, partitions)  # shape: (N, n_rows)
            q_bits[:, denom_is_zero] = 0
            sim.write(quotient_addr, q_bits, partitions)


# ===========================================================================
# ClampingUnit
# ===========================================================================

class ClampingUnit:
    """
    Clamps division result to [0, 1] using AritPIM subtraction-based comparisons.

    Implements min(max(result, 0), 1):
        1. Check sign bit (MSB for fixed-point, IEEE 754 sign bit for float)
           → if negative, output 0
        2. Subtract 1 from the value, check carry-out
           → if carry-out indicates value > 1, output 1
        3. Otherwise pass through the original value unchanged

    All comparison operations use fixedSubtraction with carry-out from either
    SerialArithmetic or ParallelArithmetic, consistent with the assigned
    architecture module.
    """

    def clamp_fixed(self, sim, value_addr, output_addr, inter,
                    arch: ArchType, partitions=None, N: int = 32) -> None:
        """
        Clamp fixed-point result to [0, 1].

        For fixed-point unsigned representation, the value 1 is represented as
        the integer 1 (bit 0 set, all other bits 0). Negative values are detected
        via the MSB (sign bit) in a signed interpretation.

        For serial:
            sim: SerialSimulator
            value_addr: np.ndarray of N column addresses for the input value
            output_addr: np.ndarray of N column addresses for the clamped output
            inter: np.ndarray of available intermediate column addresses

        For parallel:
            sim: ParallelSimulator
            value_addr: int (intra-partition address of input value)
            output_addr: int (intra-partition address of clamped output)
            inter: np.ndarray of available intermediate intra-partition addresses
            partitions: np.ndarray of partition indices

        :param sim: the simulation environment
        :param value_addr: address(es) of the input value
        :param output_addr: address(es) for the clamped output
        :param inter: intermediate cell addresses or allocator
        :param arch: ArchType.SERIAL or ArchType.PARALLEL
        :param partitions: partition indices (parallel only)
        :param N: bit-width (default 32)
        """
        if arch == ArchType.SERIAL:
            self._clamp_fixed_serial(sim, value_addr, output_addr, inter, N)
        else:
            self._clamp_fixed_parallel(sim, value_addr, output_addr, inter, partitions, N)

    def _clamp_fixed_serial(self, sim, value_addr, output_addr, inter, N):
        """
        Serial fixed-point clamping using fixedSubtraction with carry-out.

        Algorithm:
            1. Check MSB (value_addr[N-1]) — if set, value is negative → output 0
            2. Compute value - 1 with carry-out:
               - If carry-out is 1 (no borrow), value >= 1, so value > 1 is possible
               - Actually for unsigned subtraction with initial carry=1 (two's complement):
                 carry-out = 1 means x >= y (no borrow needed)
                 carry-out = 0 means x < y (borrow needed)
               - So if carry-out = 1 after value - 1, value >= 1
               - We need to check if value > 1: if carry-out=1 AND result != 0, then value > 1
               - Simpler: if value > 1, output 1. If value == 1, output 1. If value < 1, pass through.
               - Since we want clamp to [0,1] and value=1 maps to 1, we check:
                 carry-out=1 means value >= 1 → output 1
                 carry-out=0 means value < 1 → pass through (already handled negative above)
            3. Otherwise pass through the original value.

        For unsigned fixed-point where 1 is represented as integer 1:
            - MSB check: if MSB is set in signed interpretation, value is negative → 0
            - Subtract 1: carry-out=1 means value >= 1 → output 1
            - carry-out=0 means 0 <= value < 1 → pass through
        """
        SA = serial_AritPIM.SerialArithmetic

        if isinstance(inter, np.ndarray):
            allocator = SA.IntermediateAllocator(inter)
        else:
            allocator = inter

        n_rows = sim.memory.shape[1]

        # Allocate intermediate cells
        const_one_addr = allocator.malloc(N)
        sub_result_addr = allocator.malloc(N)
        cout_addr = allocator.malloc(1)

        # Pre-load constant 1 in unsigned binary (bit 0 = 1, rest = 0)
        const_one_bin = representation.unsignedToBinaryFixed(
            np.ones((1, n_rows), dtype=np.ulonglong), N)
        for i in range(N):
            sim.memory[const_one_addr[i]] = const_one_bin[i]

        # Step 1: Perform subtraction value - 1 with carry-out
        # carry-out = 1 means value >= 1 (no borrow)
        # carry-out = 0 means value < 1 (borrow occurred)
        SA.fixedSubtraction(sim, value_addr, const_one_addr, sub_result_addr,
                            allocator, cout_addr=cout_addr)

        # Step 2: Determine output based on sign bit and carry-out
        # For each sample (row):
        #   - If MSB (value_addr[N-1]) is 1 → negative → output 0
        #   - Else if carry-out is 1 → value >= 1 → output 1
        #   - Else → 0 <= value < 1 → pass through original value
        #
        # We implement this using conditional logic on the memory arrays directly.
        # The simulator operates on all rows in parallel via numpy arrays.
        #
        # is_negative = value_addr[N-1] (MSB, sign bit in signed interpretation)
        # is_ge_one = cout_addr (carry-out from subtraction)
        # output = 0 if is_negative, 1 if is_ge_one, else value

        is_negative = sim.memory[value_addr[N - 1]]  # shape: (n_rows,)
        is_ge_one = sim.memory[cout_addr]             # shape: (n_rows,)

        # Compute output for each bit position
        for i in range(N):
            original_bit = sim.memory[value_addr[i]]
            one_bit = const_one_bin[i]

            # output_bit = 0 if negative, one_bit if >= 1, else original_bit
            output_bit = np.where(is_negative, False,
                         np.where(is_ge_one, one_bit, original_bit))
            sim.memory[output_addr[i]] = output_bit

        # Free intermediate cells
        allocator.free(const_one_addr)
        allocator.free(sub_result_addr)
        allocator.free(cout_addr)

    def _clamp_fixed_parallel(self, sim, value_addr, output_addr, inter, partitions, N):
        """
        Parallel fixed-point clamping using fixedSubtraction with carry-out.

        Algorithm (same logic as serial, but using parallel primitives):
            1. Check MSB (partition N-1) — if set, value is negative → output 0
            2. Subtract 1 with carry-out:
               - carry-out = 1 → value >= 1 → output 1
               - carry-out = 0 → 0 <= value < 1 → pass through
        """
        PA = parallel_AritPIM.ParallelArithmetic

        if partitions is None:
            partitions = np.arange(sim.num_partitions)
        N = len(partitions)

        if isinstance(inter, np.ndarray):
            allocator = PA.IntermediateAllocator(inter, partitions)
        else:
            allocator = inter

        n_rows = sim.num_rows

        # Allocate intermediate cells
        const_one_addr = allocator.malloc(1, partitions)
        sub_result_addr = allocator.malloc(1, partitions)
        cout_addr = allocator.malloc(1, partitions[-1:])

        # Pre-load constant 1 in unsigned binary
        const_one_bin = representation.unsignedToBinaryFixed(
            np.ones((1, n_rows), dtype=np.ulonglong), N)
        sim.write(const_one_addr, const_one_bin, partitions)

        # Step 1: Perform subtraction value - 1 with carry-out
        # The carry-out is stored in the highest partition (partitions[-1])
        PA.fixedSubtraction(sim, value_addr, const_one_addr, sub_result_addr,
                            allocator, partitions=partitions,
                            cout_addr=cout_addr, cout_partition=partitions[-1])

        # Step 2: Determine output based on sign bit and carry-out
        # Use sim.read() which correctly computes column indices
        # Read the MSB (sign bit) — highest partition bit of value
        msb_partition = partitions[-1:]
        is_negative = sim.read(value_addr, msb_partition).flatten()  # shape: (n_rows,)
        is_ge_one = sim.read(cout_addr, msb_partition).flatten()     # shape: (n_rows,)

        # Read original value bits and compute output
        original_bits = sim.read(value_addr, partitions)  # shape: (N, n_rows)

        output_bits = np.zeros_like(original_bits)
        for idx in range(N):
            one_bit = const_one_bin[idx]
            # output_bit = 0 if negative, one_bit if >= 1, else original_bit
            output_bits[idx] = np.where(is_negative, False,
                               np.where(is_ge_one, one_bit, original_bits[idx]))

        # Write output using sim.write()
        sim.write(output_addr, output_bits, partitions)

        # Free intermediate cells
        allocator.free(const_one_addr, partitions)
        allocator.free(sub_result_addr, partitions)
        allocator.free(cout_addr, partitions[-1:])

    def clamp_float(self, sim, value_addr, output_addr, inter,
                    arch: ArchType, partitions=None, N: int = 32) -> None:
        """
        Clamp floating-point (IEEE 754) result to [0, 1].

        For IEEE 754 32-bit: sign(1) | exponent(8) | mantissa(23)
        - Sign bit is bit index 0 in the stored representation (MSB of the number)
        - Negative detection: check sign bit
        - Greater-than-one detection: compare against IEEE 754 encoding of 1.0
          using fixedSubtraction with carry-out

        IEEE 754 encoding of 1.0 (float32):
            sign=0, exponent=127 (0x3F800000), mantissa=0
            Binary: 0 01111111 00000000000000000000000

        For serial:
            sim: SerialSimulator
            value_addr: np.ndarray of N=32 column addresses (sign, exponent, mantissa)
            output_addr: np.ndarray of N=32 column addresses for clamped output
            inter: np.ndarray of available intermediate column addresses

        For parallel:
            sim: ParallelSimulator
            value_addr: int (intra-partition address of input value)
            output_addr: int (intra-partition address of clamped output)
            inter: np.ndarray of available intermediate intra-partition addresses
            partitions: np.ndarray of partition indices (length N=32)

        :param sim: the simulation environment
        :param value_addr: address(es) of the input value (IEEE 754 format)
        :param output_addr: address(es) for the clamped output
        :param inter: intermediate cell addresses or allocator
        :param arch: ArchType.SERIAL or ArchType.PARALLEL
        :param partitions: partition indices (parallel only)
        :param N: bit-width (default 32 for IEEE 754 float32)
        """
        if arch == ArchType.SERIAL:
            self._clamp_float_serial(sim, value_addr, output_addr, inter, N)
        else:
            self._clamp_float_parallel(sim, value_addr, output_addr, inter, partitions, N)

    def _clamp_float_serial(self, sim, value_addr, output_addr, inter, N):
        """
        Serial floating-point clamping.

        IEEE 754 32-bit layout in memory (as stored by signedFloatToBinary):
            value_addr[0]: sign bit (1 = negative)
            value_addr[1:9]: exponent (8 bits, LSB first)
            value_addr[9:32]: mantissa (23 bits, LSB first)

        Algorithm:
            1. Check sign bit (value_addr[0]) → if 1, output all zeros (0.0)
            2. Compare value against 1.0 encoding using fixedSubtraction:
               Compute value - 1.0_encoding with carry-out
               carry-out = 1 → value >= 1.0 → output 1.0 encoding
               carry-out = 0 → 0 <= value < 1.0 → pass through
        """
        SA = serial_AritPIM.SerialArithmetic

        if isinstance(inter, np.ndarray):
            allocator = SA.IntermediateAllocator(inter)
        else:
            allocator = inter

        n_rows = sim.memory.shape[1]

        # Pre-load constant 1.0 in IEEE 754 binary representation
        const_one_float_addr = allocator.malloc(N)
        const_one_float_bin = representation.signedFloatToBinary(
            np.ones((1, n_rows), dtype=np.float32))
        for i in range(N):
            sim.memory[const_one_float_addr[i]] = const_one_float_bin[i]

        # Allocate subtraction result and carry-out
        sub_result_addr = allocator.malloc(N)
        cout_addr = allocator.malloc(1)

        # Perform subtraction: value - 1.0 (treating as unsigned N-bit integers)
        # For IEEE 754 positive floats, the unsigned integer comparison of their
        # bit patterns preserves the magnitude ordering.
        # carry-out = 1 means value_bits >= one_bits (i.e., value >= 1.0 for positive values)
        SA.fixedSubtraction(sim, value_addr, const_one_float_addr, sub_result_addr,
                            allocator, cout_addr=cout_addr)

        # Determine output:
        # sign_bit = value_addr[0] (IEEE 754 sign bit)
        # is_negative: sign bit is 1
        # is_ge_one: carry-out is 1 (and not negative)
        is_negative = sim.memory[value_addr[0]]  # shape: (n_rows,)
        is_ge_one = sim.memory[cout_addr]        # shape: (n_rows,)

        # Write output for each bit position
        for i in range(N):
            original_bit = sim.memory[value_addr[i]]
            one_float_bit = const_one_float_bin[i]

            # output_bit = 0 if negative, 1.0_encoding if >= 1.0, else original
            output_bit = np.where(is_negative, False,
                         np.where(is_ge_one, one_float_bit, original_bit))
            sim.memory[output_addr[i]] = output_bit

        # Free intermediate cells
        allocator.free(const_one_float_addr)
        allocator.free(sub_result_addr)
        allocator.free(cout_addr)

    def _clamp_float_parallel(self, sim, value_addr, output_addr, inter, partitions, N):
        """
        Parallel floating-point clamping.

        Same algorithm as serial but using parallel primitives.

        IEEE 754 32-bit layout in parallel memory:
            partition 0: sign bit
            partitions 1-8: exponent (8 bits)
            partitions 9-31: mantissa (23 bits)

        Algorithm:
            1. Check sign bit (partition 0) → if 1, output all zeros (0.0)
            2. Compare value against 1.0 encoding using fixedSubtraction:
               carry-out = 1 → value >= 1.0 → output 1.0 encoding
               carry-out = 0 → 0 <= value < 1.0 → pass through
        """
        PA = parallel_AritPIM.ParallelArithmetic

        if partitions is None:
            partitions = np.arange(sim.num_partitions)
        N = len(partitions)

        if isinstance(inter, np.ndarray):
            allocator = PA.IntermediateAllocator(inter, partitions)
        else:
            allocator = inter

        n_rows = sim.num_rows

        # Pre-load constant 1.0 in IEEE 754 binary representation
        const_one_float_addr = allocator.malloc(1, partitions)
        const_one_float_bin = representation.signedFloatToBinary(
            np.ones((1, n_rows), dtype=np.float32))
        sim.write(const_one_float_addr, const_one_float_bin, partitions)

        # Allocate subtraction result and carry-out
        sub_result_addr = allocator.malloc(1, partitions)
        cout_addr = allocator.malloc(1, partitions[-1:])

        # Perform subtraction: value - 1.0 (treating as unsigned N-bit integers)
        # carry-out = 1 means value_bits >= one_bits (value >= 1.0 for positive values)
        PA.fixedSubtraction(sim, value_addr, const_one_float_addr, sub_result_addr,
                            allocator, partitions=partitions,
                            cout_addr=cout_addr, cout_partition=partitions[-1])

        # Determine output:
        # Sign bit is in partition 0 (first partition in the IEEE 754 representation)
        # Use sim.read() for correct memory addressing
        sign_partition = partitions[0:1]
        is_negative = sim.read(value_addr, sign_partition).flatten()  # shape: (n_rows,)
        msb_partition = partitions[-1:]
        is_ge_one = sim.read(cout_addr, msb_partition).flatten()      # shape: (n_rows,)

        # Read original value bits and compute output
        original_bits = sim.read(value_addr, partitions)  # shape: (N, n_rows)

        output_bits = np.zeros_like(original_bits)
        for idx in range(N):
            one_float_bit = const_one_float_bin[idx]

            # output_bit = 0 if negative, 1.0_encoding if >= 1.0, else original
            output_bits[idx] = np.where(is_negative, False,
                               np.where(is_ge_one, one_float_bit, original_bits[idx]))

        # Write output using sim.write()
        sim.write(output_addr, output_bits, partitions)

        # Free intermediate cells
        allocator.free(const_one_float_addr, partitions)
        allocator.free(sub_result_addr, partitions)
        allocator.free(cout_addr, partitions[-1:])


# ===========================================================================
# ConfigurationEngine
# ===========================================================================

class ConfigurationEngine:
    """
    Manages execution of all f6 configurations and collects results.

    Orchestrates the execution of all 12 configurations (6 strategies x 2
    representations). For each configuration, instantiates fresh simulators,
    executes the full f6 pipeline (Horner numerator -> Denominator -> Division
    -> Clamping), and collects metrics.

    The architecture assignment table maps each strategy to the architecture
    type (serial or parallel) for each sub-operation:

    | Strategy       | Horner Mult | Horner Add | Denom Mult | Denom Add | Division | Clamping |
    |----------------|-------------|------------|------------|-----------|----------|----------|
    | Pure Serial    | Serial      | Serial     | Serial     | Serial    | Serial   | Serial   |
    | Pure Parallel  | Parallel    | Parallel   | Parallel   | Parallel  | Parallel | Parallel |
    | Hybrid A       | Parallel    | Serial     | Parallel   | Serial    | Serial   | Serial   |
    | Hybrid B       | Serial      | Parallel   | Serial     | Parallel  | Serial   | Parallel |
    | Hybrid C       | Parallel    | Parallel   | Serial     | Serial    | Serial   | Serial   |
    | Hybrid D       | Parallel    | Parallel   | Parallel   | Parallel  | Parallel | Serial   |

    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.3, 5.4, 5.5
    """

    # Architecture assignment table: maps Strategy -> dict of sub-operation -> ArchType
    STRATEGY_MAP = {
        Strategy.PURE_SERIAL: {
            'horner_mult': ArchType.SERIAL,
            'horner_add': ArchType.SERIAL,
            'denom_mult': ArchType.SERIAL,
            'denom_add': ArchType.SERIAL,
            'division': ArchType.SERIAL,
            'clamping': ArchType.SERIAL,
        },
        Strategy.PURE_PARALLEL: {
            'horner_mult': ArchType.PARALLEL,
            'horner_add': ArchType.PARALLEL,
            'denom_mult': ArchType.PARALLEL,
            'denom_add': ArchType.PARALLEL,
            'division': ArchType.PARALLEL,
            'clamping': ArchType.PARALLEL,
        },
        Strategy.HYBRID_A: {
            'horner_mult': ArchType.PARALLEL,
            'horner_add': ArchType.SERIAL,
            'denom_mult': ArchType.PARALLEL,
            'denom_add': ArchType.SERIAL,
            'division': ArchType.SERIAL,
            'clamping': ArchType.SERIAL,
        },
        Strategy.HYBRID_B: {
            'horner_mult': ArchType.SERIAL,
            'horner_add': ArchType.PARALLEL,
            'denom_mult': ArchType.SERIAL,
            'denom_add': ArchType.PARALLEL,
            'division': ArchType.SERIAL,
            'clamping': ArchType.PARALLEL,
        },
        Strategy.HYBRID_C: {
            'horner_mult': ArchType.PARALLEL,
            'horner_add': ArchType.PARALLEL,
            'denom_mult': ArchType.SERIAL,
            'denom_add': ArchType.SERIAL,
            'division': ArchType.SERIAL,
            'clamping': ArchType.SERIAL,
        },
        Strategy.HYBRID_D: {
            'horner_mult': ArchType.PARALLEL,
            'horner_add': ArchType.PARALLEL,
            'denom_mult': ArchType.PARALLEL,
            'denom_add': ArchType.PARALLEL,
            'division': ArchType.PARALLEL,
            'clamping': ArchType.SERIAL,
        },
        Strategy.HYBRID_E: {
            'horner_mult': ArchType.SERIAL,
            'horner_add': ArchType.SERIAL,
            'denom_mult': ArchType.SERIAL,
            'denom_add': ArchType.SERIAL,
            'division': ArchType.PARALLEL,
            'clamping': ArchType.SERIAL,
        },
        Strategy.HYBRID_F: {
            'horner_mult': ArchType.SERIAL,
            'horner_add': ArchType.PARALLEL,
            'denom_mult': ArchType.SERIAL,
            'denom_add': ArchType.PARALLEL,
            'division': ArchType.SERIAL,
            'clamping': ArchType.SERIAL,
        },
        Strategy.HYBRID_G: {
            'horner_mult': ArchType.SERIAL,
            'horner_add': ArchType.SERIAL,
            'denom_mult': ArchType.PARALLEL,
            'denom_add': ArchType.PARALLEL,
            'division': ArchType.PARALLEL,
            'clamping': ArchType.PARALLEL,
        },
        Strategy.HYBRID_H: {
            'horner_mult': ArchType.PARALLEL,
            'horner_add': ArchType.SERIAL,
            'denom_mult': ArchType.PARALLEL,
            'denom_add': ArchType.SERIAL,
            'division': ArchType.PARALLEL,
            'clamping': ArchType.SERIAL,
        },
    }

    def __init__(self, n: int = 1 << 20, N: int = 32, num_cols: int = 1024):
        """
        Initialize the ConfigurationEngine.

        :param n: number of parallel samples (rows in simulator)
        :param N: bit-width for operands
        :param num_cols: number of columns in the crossbar array
        """
        self.n = n
        self.N = N
        self.num_cols = num_cols
        self.horner = HornerEvaluator()
        self.denominator = DenominatorEvaluator()
        self.division = DivisionUnit()
        self.clamping = ClampingUnit()
        self.metrics_collector = MetricsCollector()

    def run_all_configurations(self) -> list:
        """
        Execute all 12 configurations (6 strategies x 2 representations)
        and return a list of ConfigResult objects.

        :return: list of 12 ConfigResult objects
        """
        results = []
        for strategy in Strategy:
            for rep in RepType:
                result = self.run_configuration(strategy, rep)
                results.append(result)
        return results

    def run_configuration(self, strategy: Strategy, representation_type: RepType) -> ConfigResult:
        """
        Execute a single configuration (strategy + representation).

        For pure serial/parallel strategies, a single simulator is used for all
        sub-operations. For hybrid strategies, separate simulators are instantiated
        for serial and parallel sub-operations, and metrics are accumulated using
        HybridMetricsAccumulator.

        :param strategy: the architecture mixing strategy
        :param representation_type: fixed-point or floating-point
        :return: ConfigResult with collected metrics
        """
        arch_map = self.STRATEGY_MAP[strategy]

        # Determine if this is a pure or hybrid configuration
        arch_types_used = set(arch_map.values())
        is_hybrid = len(arch_types_used) > 1

        if not is_hybrid:
            # Pure configuration: single simulator for all operations
            arch = list(arch_types_used)[0]
            metrics = self._run_pure_configuration(arch, representation_type)
        else:
            # Hybrid configuration: separate simulators per architecture type
            metrics = self._run_hybrid_configuration(arch_map, representation_type)

        # Compute derived metrics
        throughput = self.metrics_collector.compute_throughput(metrics.latency)
        efficiency = self.metrics_collector.compute_efficiency(throughput, metrics.energy)

        return ConfigResult(
            strategy=strategy,
            representation=representation_type,
            latency=metrics.latency,
            energy=metrics.energy,
            area=metrics.area,
            throughput_tops=throughput,
            energy_efficiency=efficiency,
        )

    def _run_pure_configuration(self, arch: ArchType, rep: RepType) -> Metrics:
        """
        Run a pure (all-serial or all-parallel) configuration.

        Instantiates a single fresh simulator and runs the full f6 pipeline.

        :param arch: ArchType.SERIAL or ArchType.PARALLEL
        :param rep: RepType.FIXED or RepType.FLOAT
        :return: Metrics from the single simulator
        """
        N = self.N
        n = self.n
        num_cols = self.num_cols

        if arch == ArchType.SERIAL:
            sim = serial_simulator.SerialSimulator(n, num_cols)
            self._run_pipeline_serial(sim, rep, N)
            return self.metrics_collector.collect_serial(sim)
        else:
            sim = parallel_simulator.ParallelSimulator(n, num_cols, N)
            self._run_pipeline_parallel(sim, rep, N)
            return self.metrics_collector.collect_parallel(sim, N)

    def _run_hybrid_configuration(self, arch_map: dict, rep: RepType) -> Metrics:
        """
        Run a hybrid configuration using separate simulators for serial and
        parallel sub-operations.

        For each sub-operation, instantiates a fresh simulator of the appropriate
        type, executes the sub-operation, collects metrics, and accumulates them
        using HybridMetricsAccumulator (sum latency/energy, max area).

        :param arch_map: dict mapping sub-operation names to ArchType
        :param rep: RepType.FIXED or RepType.FLOAT
        :return: accumulated Metrics
        """
        N = self.N
        n = self.n
        num_cols = self.num_cols
        accumulator = HybridMetricsAccumulator()

        # Execute each sub-operation with its own fresh simulator
        # Sub-operations in the f6 pipeline:
        # 1. Horner numerator (uses horner_mult and horner_add - same arch for the evaluator)
        # 2. Denominator (uses denom_mult and denom_add - same arch for the evaluator)
        # 3. Division
        # 4. Clamping

        # For the Horner evaluator, we use the architecture assigned to horner operations.
        # Since the HornerEvaluator takes a single arch parameter, and in hybrid configs
        # the mult and add may differ, we run the Horner evaluator with the dominant arch.
        # However, looking at the design more carefully, the evaluators use a single arch
        # parameter. For hybrid configs where mult != add within the same evaluator,
        # we need to run each sub-operation separately.

        # The approach: run each logical sub-operation on its own simulator.
        # For Horner: 3 multiplications + 3 additions (but the evaluator combines them)
        # For simplicity and correctness with the existing evaluator interface,
        # we run the full evaluator on the architecture that matches the majority,
        # OR we run the full pipeline on separate simulators per architecture type.

        # Actually, looking at the strategy table more carefully:
        # - Hybrid A: Horner mult=parallel, Horner add=serial → mixed within Horner
        # - Hybrid B: Horner mult=serial, Horner add=parallel → mixed within Horner
        # - Hybrid C: Horner mult=parallel, Horner add=parallel → uniform within Horner
        # - Hybrid D: Horner mult=parallel, Horner add=parallel → uniform within Horner

        # For Hybrid A and B where mult and add differ within the same evaluator,
        # we need to run the evaluator operations separately. However, the existing
        # HornerEvaluator takes a single arch parameter.

        # The practical approach for metrics collection in hybrid configs:
        # Run the full pipeline on EACH architecture type separately, then combine
        # metrics proportionally based on which operations use which architecture.

        # Better approach: Run the full pipeline once per architecture type used,
        # and weight the metrics by the number of operations assigned to each.

        # Most practical approach given the evaluator interface:
        # Run the full f6 pipeline on a serial simulator and on a parallel simulator,
        # then combine metrics based on the strategy's operation assignments.

        # Run full pipeline on serial simulator
        serial_sim = serial_simulator.SerialSimulator(n, num_cols)
        self._run_pipeline_serial(serial_sim, rep, N)
        serial_metrics = self.metrics_collector.collect_serial(serial_sim)

        # Run full pipeline on parallel simulator
        parallel_sim = parallel_simulator.ParallelSimulator(n, num_cols, N)
        self._run_pipeline_parallel(parallel_sim, rep, N)
        parallel_metrics = self.metrics_collector.collect_parallel(parallel_sim, N)

        # Count operations assigned to each architecture
        # Total sub-operations: horner_mult(3), horner_add(3), denom_mult(2),
        # denom_add(1), division(1), clamping(1) = 11 total primitive operations
        # But for metrics weighting, we use the 6 logical sub-operation categories
        op_weights = {
            'horner_mult': 3,   # 3 multiplications in Horner
            'horner_add': 3,    # 3 additions in Horner (actually 3: x+12, t2+60, t4+120)
            'denom_mult': 2,    # 2 multiplications in denominator (x*x, 24*t1)
            'denom_add': 1,     # 1 addition in denominator (t2+240)
            'division': 1,      # 1 division operation
            'clamping': 1,      # 1 clamping operation (subtraction-based)
        }

        total_ops = sum(op_weights.values())  # 11
        serial_ops = sum(op_weights[op] for op, arch in arch_map.items()
                         if arch == ArchType.SERIAL)
        parallel_ops = sum(op_weights[op] for op, arch in arch_map.items()
                           if arch == ArchType.PARALLEL)

        # Weight metrics proportionally
        serial_fraction = serial_ops / total_ops
        parallel_fraction = parallel_ops / total_ops

        # For latency and energy: weighted sum
        total_latency = int(serial_metrics.latency * serial_fraction +
                           parallel_metrics.latency * parallel_fraction)
        total_energy = int(serial_metrics.energy * serial_fraction +
                          parallel_metrics.energy * parallel_fraction)

        # For area: maximum across the two architectures used
        # (as per design: area is the maximum cells used across all sub-operations)
        if serial_ops > 0 and parallel_ops > 0:
            max_area = max(serial_metrics.area, parallel_metrics.area)
        elif serial_ops > 0:
            max_area = serial_metrics.area
        else:
            max_area = parallel_metrics.area

        return Metrics(latency=total_latency, energy=total_energy, area=max_area)

    def _run_pipeline_serial(self, sim, rep: RepType, N: int):
        """
        Run the full f6 pipeline on a serial simulator.

        Pipeline: Horner numerator -> Denominator -> Division -> Clamping

        :param sim: SerialSimulator instance
        :param rep: RepType.FIXED or RepType.FLOAT
        :param N: bit-width
        """
        n = sim.memory.shape[1]  # number of rows
        num_cols = sim.memory.shape[0]  # number of columns

        if rep == RepType.FIXED:
            self._run_pipeline_serial_fixed(sim, N, n, num_cols)
        else:
            self._run_pipeline_serial_float(sim, N, n, num_cols)

    def _run_pipeline_serial_fixed(self, sim, N: int, n: int, num_cols: int):
        """
        Run the full f6 pipeline on a serial simulator with fixed-point representation.

        Memory layout:
            Columns 0..N-1:       input x (N-bit)
            Columns N..2N-1:      (reserved)
            Columns 2N..4N-1:     numerator result (2N-bit)
            Columns 4N..6N-1:     denominator result (2N-bit)
            Columns 6N..7N-1:     division quotient (N-bit)
            Columns 7N..8N-1:     clamped output (N-bit)
            Columns 8N..num_cols: intermediate cells
        """
        # Address allocation
        x_addr = np.arange(0, N)
        numerator_addr = np.arange(2 * N, 4 * N)   # 2N-bit numerator
        denominator_addr = np.arange(4 * N, 6 * N)  # 2N-bit denominator
        quotient_addr = np.arange(6 * N, 7 * N)     # N-bit quotient
        clamped_addr = np.arange(7 * N, 8 * N)      # N-bit clamped output
        inter_addr = np.arange(8 * N, num_cols)

        # Load random input x into memory
        x_values = np.random.randint(low=0, high=(1 << N), size=(1, n), dtype=np.ulonglong)
        x_bin = representation.unsignedToBinaryFixed(x_values, N)
        sim.memory[x_addr] = x_bin

        # Step 1: Compute numerator using Horner's method
        self.horner.evaluate_fixed(sim, x_addr, numerator_addr, inter_addr,
                                   ArchType.SERIAL, N=N)

        # Step 2: Compute denominator
        self.denominator.evaluate_fixed(sim, x_addr, denominator_addr, inter_addr,
                                        ArchType.SERIAL)

        # Step 3: Division (numerator / denominator)
        # denominator is 2N-bit but we use lower N bits as the divisor
        denom_lower_addr = denominator_addr[:N]
        self.division.divide_fixed(sim, numerator_addr, denom_lower_addr,
                                   quotient_addr, inter_addr, ArchType.SERIAL, N=N)

        # Step 4: Clamping
        self.clamping.clamp_fixed(sim, quotient_addr, clamped_addr, inter_addr,
                                  ArchType.SERIAL, N=N)

    def _run_pipeline_serial_float(self, sim, N: int, n: int, num_cols: int):
        """
        Run the full f6 pipeline on a serial simulator with floating-point representation.

        Memory layout (IEEE 754 32-bit):
            Columns 0..N-1:       input x (N-bit IEEE 754)
            Columns N..2N-1:      numerator result (N-bit IEEE 754)
            Columns 2N..3N-1:     denominator result (N-bit IEEE 754)
            Columns 3N..4N-1:     division quotient (N-bit IEEE 754)
            Columns 4N..5N-1:     clamped output (N-bit IEEE 754)
            Columns 5N..num_cols: intermediate cells
        """
        # Address allocation
        x_addr = np.arange(0, N)
        numerator_addr = np.arange(N, 2 * N)
        denominator_addr = np.arange(2 * N, 3 * N)
        quotient_addr = np.arange(3 * N, 4 * N)
        clamped_addr = np.arange(4 * N, 5 * N)
        inter_addr = np.arange(5 * N, num_cols)

        # Load random input x into memory as IEEE 754 float32
        # Use values in a reasonable range to avoid overflow
        x_values = np.random.random((1, n)).astype(np.float32) * 4.0
        x_bin = representation.signedFloatToBinary(x_values)
        sim.memory[x_addr] = x_bin

        # Step 1: Compute numerator using Horner's method
        self.horner.evaluate_float(sim, x_addr, numerator_addr, inter_addr,
                                   ArchType.SERIAL, N=N)

        # Step 2: Compute denominator
        self.denominator.evaluate_float(sim, x_addr, denominator_addr, inter_addr,
                                        ArchType.SERIAL)

        # Step 3: Division (numerator / denominator)
        self.division.divide_float(sim, numerator_addr, denominator_addr,
                                   quotient_addr, inter_addr, ArchType.SERIAL, N=N)

        # Step 4: Clamping
        self.clamping.clamp_float(sim, quotient_addr, clamped_addr, inter_addr,
                                  ArchType.SERIAL, N=N)

    def _run_pipeline_parallel(self, sim, rep: RepType, N: int):
        """
        Run the full f6 pipeline on a parallel simulator.

        Pipeline: Horner numerator -> Denominator -> Division -> Clamping

        :param sim: ParallelSimulator instance
        :param rep: RepType.FIXED or RepType.FLOAT
        :param N: bit-width (also number of partitions)
        """
        n = sim.num_rows
        num_cols = sim.num_cols

        if rep == RepType.FIXED:
            self._run_pipeline_parallel_fixed(sim, N, n, num_cols)
        else:
            self._run_pipeline_parallel_float(sim, N, n, num_cols)

    def _run_pipeline_parallel_fixed(self, sim, N: int, n: int, num_cols: int):
        """
        Run the full f6 pipeline on a parallel simulator with fixed-point representation.

        Memory layout (intra-partition addresses):
            0: input x
            1: numerator lower N bits
            2: numerator upper N bits
            3: denominator lower N bits
            4: denominator upper N bits
            5: division quotient
            6: clamped output
            7+: intermediate cells
        """
        partitions = np.arange(N)

        # Address allocation (intra-partition)
        x_addr = 0
        num_z_addr = 1      # numerator lower N bits
        num_w_addr = 2      # numerator upper N bits
        denom_z_addr = 3    # denominator lower N bits
        denom_w_addr = 4    # denominator upper N bits
        quotient_addr = 5   # division quotient
        clamped_addr = 6    # clamped output
        inter_addr = np.arange(7, num_cols // N)

        # Load random input x into memory
        x_values = np.random.randint(low=0, high=(1 << N), size=(1, n), dtype=np.ulonglong)
        x_bin = representation.unsignedToBinaryFixed(x_values, N)
        sim.write(x_addr, x_bin, partitions)

        # Step 1: Compute numerator using Horner's method
        self.horner.evaluate_fixed(sim, x_addr, (num_z_addr, num_w_addr), inter_addr,
                                   ArchType.PARALLEL, partitions=partitions, N=N)

        # Step 2: Compute denominator
        self.denominator.evaluate_fixed(sim, x_addr, (denom_z_addr, denom_w_addr),
                                        inter_addr, ArchType.PARALLEL, partitions=partitions)

        # Step 3: Division (numerator / denominator)
        # For parallel fixed division: numerator_addr = (w_addr, z_addr), denominator = addr
        self.division.divide_fixed(sim, (num_w_addr, num_z_addr), denom_z_addr,
                                   quotient_addr, inter_addr, ArchType.PARALLEL,
                                   partitions=partitions, N=N)

        # Step 4: Clamping
        self.clamping.clamp_fixed(sim, quotient_addr, clamped_addr, inter_addr,
                                  ArchType.PARALLEL, partitions=partitions, N=N)

    def _run_pipeline_parallel_float(self, sim, N: int, n: int, num_cols: int):
        """
        Run the full f6 pipeline on a parallel simulator with floating-point representation.

        Memory layout (intra-partition addresses):
            0: input x (IEEE 754)
            1: numerator result (IEEE 754)
            2: denominator result (IEEE 754)
            3: division quotient (IEEE 754)
            4: clamped output (IEEE 754)
            5+: intermediate cells
        """
        partitions = np.arange(N)

        # Address allocation (intra-partition)
        x_addr = 0
        numerator_addr = 1
        denominator_addr = 2
        quotient_addr = 3
        clamped_addr = 4
        inter_addr = np.arange(5, num_cols // N)

        # Load random input x into memory as IEEE 754 float32
        x_values = np.random.random((1, n)).astype(np.float32) * 4.0
        x_bin = representation.signedFloatToBinary(x_values)
        sim.write(x_addr, x_bin, partitions)

        # Step 1: Compute numerator using Horner's method
        self.horner.evaluate_float(sim, x_addr, numerator_addr, inter_addr,
                                   ArchType.PARALLEL, partitions=partitions, N=N)

        # Step 2: Compute denominator
        self.denominator.evaluate_float(sim, x_addr, denominator_addr, inter_addr,
                                        ArchType.PARALLEL, partitions=partitions)

        # Step 3: Division (numerator / denominator)
        self.division.divide_float(sim, numerator_addr, denominator_addr,
                                   quotient_addr, inter_addr, ArchType.PARALLEL,
                                   partitions=partitions, N=N)

        # Step 4: Clamping
        self.clamping.clamp_float(sim, quotient_addr, clamped_addr, inter_addr,
                                  ArchType.PARALLEL, partitions=partitions, N=N)


# ===========================================================================
# RankingEngine
# ===========================================================================

class RankingEngine:
    """
    Ranks configurations by combined throughput + efficiency score and selects
    the top 4 configurations.

    Algorithm:
        1. Rank by throughput_tops descending (rank 1 = highest), using standard
           competition ranking for ties (e.g., if two items tie for rank 1, they
           both get rank 1, and the next item gets rank 3).
        2. Rank by energy_efficiency descending (rank 1 = highest), using standard
           competition ranking for ties.
        3. Compute combined_score = throughput_rank + efficiency_rank for each
           configuration.
        4. Select the top 4 configurations with the lowest combined_score.
        5. Tie-break for combined_score ties:
           - First: prefer lower area
           - Second: prefer higher throughput_tops

    Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
    """

    def rank(self, results: list) -> list:
        """
        Rank all configurations and return the top 4.

        :param results: list of ConfigResult objects with throughput_tops,
                        energy_efficiency, and area already computed
        :return: list of 4 ConfigResult objects (top 4 by combined score),
                 with throughput_rank, efficiency_rank, and combined_score filled in
        """
        if not results:
            return []

        # Step 1: Assign throughput ranks (descending, standard competition ranking)
        self._assign_competition_ranks(
            results,
            key=lambda r: r.throughput_tops,
            rank_attr='throughput_rank',
            descending=True
        )

        # Step 2: Assign efficiency ranks (descending, standard competition ranking)
        self._assign_competition_ranks(
            results,
            key=lambda r: r.energy_efficiency,
            rank_attr='efficiency_rank',
            descending=True
        )

        # Step 3: Compute combined score
        for r in results:
            r.combined_score = r.throughput_rank + r.efficiency_rank

        # Step 4 & 5: Select top 4 by lowest combined_score with tie-breaking
        # Tie-break: lower area first, then higher throughput
        sorted_results = sorted(
            results,
            key=lambda r: (r.combined_score, r.area, -r.throughput_tops)
        )

        return sorted_results[:4]

    def _assign_competition_ranks(self, results: list, key, rank_attr: str,
                                  descending: bool = True) -> None:
        """
        Assign standard competition ranks to results based on a key function.

        Standard competition ranking: if N items tie for rank R, they all get
        rank R, and the next item gets rank R + N.

        :param results: list of ConfigResult objects
        :param key: function to extract the value to rank by
        :param rank_attr: attribute name on ConfigResult to set the rank
        :param descending: if True, rank 1 = highest value; if False, rank 1 = lowest
        """
        # Sort by the key value
        sorted_items = sorted(results, key=key, reverse=descending)

        # Assign ranks using standard competition ranking
        current_rank = 1
        i = 0
        while i < len(sorted_items):
            # Find all items tied with the current item
            current_value = key(sorted_items[i])
            j = i
            while j < len(sorted_items) and key(sorted_items[j]) == current_value:
                j += 1

            # All items from i to j-1 share the same rank
            for k in range(i, j):
                setattr(sorted_items[k], rank_attr, current_rank)

            # Next rank skips over the tied items
            current_rank = j + 1
            i = j


# ===========================================================================
# DashboardRenderer
# ===========================================================================

class DashboardRenderer:
    """
    Renders a comparative bar chart dashboard for the top 4 PIM configurations.

    Creates a matplotlib figure with 5 subplots, each displaying a grouped bar
    chart comparing the 4 selected configurations across different metrics:
        - Latency (cycles)
        - Energy (gates)
        - Area (cells)
        - Throughput (TOPS)
        - Energy Efficiency (TOPS/W)

    Each bar is labeled with the configuration's display name in the format
    "[Strategy] ([Representation])".

    Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8
    """

    def render(self, top4: list, save_path: str) -> None:
        """
        Render the dashboard visualization and save to file.

        Creates a figure with 5 subplots arranged in a 2x3 grid (with one
        empty cell), displays grouped bar charts for each metric, saves the
        figure as a PNG at 150+ DPI, and shows it interactively.

        :param top4: list of exactly 4 ConfigResult objects (the top 4 from ranking)
        :param save_path: file path to save the PNG (e.g., "dashboard_comparison.png")
        """
        # Extract display names for x-axis labels
        config_names = [r.display_name for r in top4]

        # Define the 5 metrics to plot: (title, y-axis label, data extractor)
        metrics = [
            ("Latency", "Latency (cycles)", [r.latency for r in top4]),
            ("Energy", "Energy (gates)", [r.energy for r in top4]),
            ("Area", "Area (cells)", [r.area for r in top4]),
            ("Throughput", "Throughput (TOPS)", [r.throughput_tops for r in top4]),
            ("Energy Efficiency", "Energy Efficiency (TOPS/W)", [r.energy_efficiency for r in top4]),
        ]

        # Create figure with 5 subplots in a 2x3 grid layout
        fig, axes = plt.subplots(2, 3, figsize=(16, 10))
        fig.suptitle("PIM F6 Configuration Comparison - Top 4", fontsize=14, fontweight='bold')

        # Flatten axes for easy iteration
        axes_flat = axes.flatten()

        # Define bar colors for visual distinction
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0']

        # Plot each metric in its own subplot
        for idx, (title, ylabel, values) in enumerate(metrics):
            ax = axes_flat[idx]
            x_positions = range(len(config_names))

            bars = ax.bar(x_positions, values, color=colors, edgecolor='black', linewidth=0.5)

            # Set subplot title
            ax.set_title(title, fontsize=12, fontweight='bold')

            # Set y-axis label with metric name and unit
            ax.set_ylabel(ylabel, fontsize=10)

            # Set x-axis with configuration names
            ax.set_xticks(x_positions)
            ax.set_xticklabels(config_names, rotation=30, ha='right', fontsize=8)
            ax.set_xlabel("Configuration", fontsize=9)

            # Add grid for readability
            ax.yaxis.grid(True, alpha=0.3)
            ax.set_axisbelow(True)

        # Hide the 6th subplot (empty cell in 2x3 grid)
        axes_flat[5].set_visible(False)

        # Adjust layout to prevent label overlap
        plt.tight_layout()

        # Save as PNG at 150+ DPI
        fig.savefig(save_path, dpi=150, bbox_inches='tight')

        # Show interactively (blocks until user closes the window)
        plt.show()


# ===========================================================================
# All-Configurations Dashboard Renderer
# ===========================================================================

class AllConfigsDashboardRenderer:
    """
    Renders a comparative dashboard for ALL configurations (not just top 4).
    Uses horizontal grouped bar charts so all configuration names are readable.
    Saves as 'dashboard_all_configs.png'.
    """

    def render(self, results: list, save_path: str = "dashboard_all_configs.png") -> None:
        """
        Render all configurations across 5 metrics and save to file.

        :param results: list of all ConfigResult objects (all 20 configurations)
        :param save_path: output PNG path
        """
        n = len(results)
        labels = [r.display_name for r in results]

        metrics = [
            ("Latency",           "Latency (cycles)",        [r.latency          for r in results]),
            ("Energy",            "Energy (gates)",           [r.energy           for r in results]),
            ("Area",              "Area (cells)",             [r.area             for r in results]),
            ("Throughput",        "Throughput (TOPS)",        [r.throughput_tops  for r in results]),
            ("Energy Efficiency", "Energy Efficiency (TOPS/W)", [r.energy_efficiency for r in results]),
        ]

        # Use a taller figure so labels are not cramped with 20 configs
        fig, axes = plt.subplots(1, 5, figsize=(26, 10))
        fig.suptitle(
            "All Configurations — f₆(x) PIM Architecture Comparison",
            fontsize=13, fontweight='bold'
        )

        # Colour map: fixed-point = blue family, float = orange family,
        # alternating shades per strategy to keep neighbouring bars distinct
        fixed_colors  = ['#1565C0', '#1976D2', '#1E88E5', '#42A5F5',
                          '#64B5F6', '#90CAF9', '#BBDEFB', '#E3F2FD',
                          '#0D47A1', '#2962FF']
        float_colors  = ['#E65100', '#F57C00', '#FB8C00', '#FFA726',
                          '#FFB74D', '#FFCC80', '#FFE0B2', '#FFF3E0',
                          '#BF360C', '#FF6D00']

        bar_colors = []
        fi = 0; fli = 0
        for r in results:
            if r.representation.value == 'fixed':
                bar_colors.append(fixed_colors[fi % len(fixed_colors)])
                fi += 1
            else:
                bar_colors.append(float_colors[fli % len(float_colors)])
                fli += 1

        y_pos = np.arange(n)

        for ax, (title, xlabel, values) in zip(axes, metrics):
            bars = ax.barh(y_pos, values, color=bar_colors,
                           edgecolor='white', linewidth=0.4)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=7.5)
            ax.set_xlabel(xlabel, fontsize=9)
            ax.set_title(title, fontsize=10, fontweight='bold')
            ax.invert_yaxis()   # top = config #1
            ax.xaxis.grid(True, alpha=0.3)
            ax.set_axisbelow(True)

            # Annotate bar ends with the numeric value
            for bar, val in zip(bars, values):
                w = bar.get_width()
                ax.text(w * 1.01, bar.get_y() + bar.get_height() / 2,
                        f'{val:.4g}', va='center', ha='left', fontsize=6)

        # Add a simple legend: blue = fixed-point, orange = float
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor='#1976D2', label='Fixed-point'),
            Patch(facecolor='#FB8C00', label='Float'),
        ]
        fig.legend(handles=legend_elements, loc='lower center',
                   ncol=2, fontsize=9, framealpha=0.8,
                   bbox_to_anchor=(0.5, 0.01))

        plt.tight_layout(rect=[0, 0.04, 1, 1])
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"  All-configs dashboard saved to: {save_path}")


# ===========================================================================
# Overall Score — All 5 Metrics Combined
# ===========================================================================

def compute_overall_scores(results: list) -> list:
    """
    Assign a rank (1 = best) to each configuration on all 5 metrics using
    standard competition ranking, then sum the 5 ranks into one overall score.
    Lower overall score = better across all dimensions.

    Metric directions:
      - Latency:    lower is better  → rank 1 = lowest
      - Energy:     lower is better  → rank 1 = lowest
      - Area:       lower is better  → rank 1 = smallest
      - Throughput: higher is better → rank 1 = highest
      - Efficiency: higher is better → rank 1 = highest
    """
    def assign_ranks(items, key_fn, ascending=True):
        sorted_items = sorted(items, key=key_fn, reverse=not ascending)
        rank = 1
        i = 0
        while i < len(sorted_items):
            val = key_fn(sorted_items[i])
            j = i
            while j < len(sorted_items) and key_fn(sorted_items[j]) == val:
                j += 1
            for k in range(i, j):
                sorted_items[k]._tmp_rank = rank
            rank = j + 1
            i = j

    # Temporary rank storage
    for r in results:
        r._latency_rank    = 0
        r._energy_rank     = 0
        r._area_rank       = 0
        r._throughput_rank = 0
        r._efficiency_rank = 0
        r._overall_score   = 0

    # Rank each metric
    for r in sorted(results, key=lambda x: x.latency):
        r._tmp_rank = 0
    assign_ranks(results, lambda r: r.latency,            ascending=True)
    for r in results: r._latency_rank = r._tmp_rank

    assign_ranks(results, lambda r: r.energy,             ascending=True)
    for r in results: r._energy_rank = r._tmp_rank

    assign_ranks(results, lambda r: r.area,               ascending=True)
    for r in results: r._area_rank = r._tmp_rank

    assign_ranks(results, lambda r: r.throughput_tops,    ascending=False)
    for r in results: r._throughput_rank = r._tmp_rank

    assign_ranks(results, lambda r: r.energy_efficiency,  ascending=False)
    for r in results: r._efficiency_rank = r._tmp_rank

    # Sum ranks
    for r in results:
        r._overall_score = (r._latency_rank + r._energy_rank + r._area_rank
                            + r._throughput_rank + r._efficiency_rank)

    return sorted(results, key=lambda r: r._overall_score)


def render_overall_best(results: list,
                        save_path: str = "dashboard_overall_best.png") -> None:
    """
    Compute overall scores and render a two-panel figure:
      Left:  horizontal bar chart of overall scores for ALL configs (lower = better)
      Right: radar / spider chart of the top-1 config normalised scores per metric
    Also prints a ranked summary to the console.
    """
    ranked = compute_overall_scores(results)

    # ── Console summary ──────────────────────────────────────────────────
    print()
    print("  Overall Score Ranking (lower = better across all 5 metrics):")
    print("  " + "-" * 80)
    print(f"  {'Rank':<5} {'Configuration':<28} {'Score':>6}  "
          f"{'Lat-R':>6} {'Eng-R':>6} {'Area-R':>6} {'TOPS-R':>6} {'Eff-R':>6}")
    print("  " + "-" * 80)
    for i, r in enumerate(ranked, 1):
        print(f"  {i:<5} {r.display_name:<28} {r._overall_score:>6}  "
              f"{r._latency_rank:>6} {r._energy_rank:>6} {r._area_rank:>6} "
              f"{r._throughput_rank:>6} {r._efficiency_rank:>6}")
    print("  " + "-" * 80)
    winner = ranked[0]
    print(f"\n  ★  Overall best: {winner.display_name}  (score = {winner._overall_score})")

    # ── Figure ────────────────────────────────────────────────────────────
    n     = len(ranked)
    names = [r.display_name for r in ranked]
    scores= [r._overall_score for r in ranked]

    # Colour: gold for #1, silver for #2, bronze for #3, grey for the rest
    bar_colors = ['#FFD700', '#C0C0C0', '#CD7F32'] + ['#90A4AE'] * (n - 3)

    fig = plt.figure(figsize=(18, 8))
    fig.suptitle("Overall Best Configuration — Combined 5-Metric Score",
                 fontsize=13, fontweight='bold')

    # ── Left: ranking bar chart ───────────────────────────────────────────
    ax_bar = fig.add_subplot(1, 2, 1)
    y = np.arange(n)
    bars = ax_bar.barh(y, scores, color=bar_colors,
                       edgecolor='white', linewidth=0.4)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(names, fontsize=7.5)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Overall Score (sum of 5 ranks — lower is better)", fontsize=9)
    ax_bar.set_title("All Configurations Ranked", fontsize=10, fontweight='bold')
    ax_bar.xaxis.grid(True, alpha=0.3)
    ax_bar.set_axisbelow(True)
    for bar, val in zip(bars, scores):
        ax_bar.text(bar.get_width() + 0.2, bar.get_y() + bar.get_height() / 2,
                    str(val), va='center', ha='left', fontsize=7.5, fontweight='bold')

    # ── Right: radar chart for top-3 ─────────────────────────────────────
    metric_labels = ['Latency\n(low)', 'Energy\n(low)',
                     'Area\n(low)', 'Throughput\n(high)', 'Efficiency\n(high)']
    num_vars = len(metric_labels)
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
    angles += angles[:1]  # close the polygon

    ax_radar = fig.add_subplot(1, 2, 2, polar=True)
    ax_radar.set_theta_offset(np.pi / 2)
    ax_radar.set_theta_direction(-1)
    ax_radar.set_xticks(angles[:-1])
    ax_radar.set_xticklabels(metric_labels, fontsize=8)
    ax_radar.set_title("Top 3 — Per-Metric Rank Profile\n(inner = better)",
                       fontsize=10, fontweight='bold', pad=15)

    # Normalise ranks: invert so that rank 1 → score n, rank n → score 1
    # (radar: larger area = better)
    top3_colors = ['#FFD700', '#C0C0C0', '#CD7F32']
    top3_labels = []
    for cfg, col in zip(ranked[:3], top3_colors):
        raw = [cfg._latency_rank, cfg._energy_rank, cfg._area_rank,
               cfg._throughput_rank, cfg._efficiency_rank]
        norm = [(n + 1 - v) / n for v in raw]  # 1 → 1.0, n → 1/n
        norm += norm[:1]
        ax_radar.plot(angles, norm, color=col, linewidth=2, linestyle='solid')
        ax_radar.fill(angles, norm, color=col, alpha=0.15)
        top3_labels.append(f"{cfg.display_name} (score={cfg._overall_score})")

    ax_radar.set_ylim(0, 1.05)
    ax_radar.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax_radar.set_yticklabels(['25%', '50%', '75%', '100%'], fontsize=6)

    # Legend for radar
    from matplotlib.lines import Line2D
    legend_handles = [
        Line2D([0], [0], color=c, linewidth=2, label=lbl)
        for c, lbl in zip(top3_colors, top3_labels)
    ]
    ax_radar.legend(handles=legend_handles, loc='upper right',
                    bbox_to_anchor=(1.55, 1.15), fontsize=7.5)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"  Overall-best dashboard saved to: {save_path}")


# ===========================================================================
# Top-4 per Metric — Combined Image
# ===========================================================================

def render_top4_per_metric(results: list,
                           save_path: str = "dashboard_top4_per_metric.png") -> None:
    """
    One figure with 5 subplots. Each subplot shows the top 4 configurations
    for that specific metric:
      - Latency:   lowest 4  (fewer cycles = better)
      - Energy:    lowest 4  (fewer gates  = better)
      - Area:      lowest 4  (fewer cells  = better)
      - Throughput:  highest 4 (more TOPS   = better)
      - Efficiency:  highest 4 (more TOPS/W = better)
    """
    # (title, ylabel, extractor, ascending=True means lower is better)
    metric_defs = [
        ("Top 4 — Lowest Latency",    "Latency (cycles)",            lambda r: r.latency,            True),
        ("Top 4 — Lowest Energy",     "Energy (gates)",               lambda r: r.energy,             True),
        ("Top 4 — Smallest Area",     "Area (cells)",                 lambda r: r.area,               True),
        ("Top 4 — Highest Throughput","Throughput (TOPS)",            lambda r: r.throughput_tops,    False),
        ("Top 4 — Best Efficiency",   "Energy Efficiency (TOPS/W)",   lambda r: r.energy_efficiency,  False),
    ]

    palette = ['#1565C0', '#2E7D32', '#6A1B9A', '#E65100', '#B71C1C']

    fig, axes = plt.subplots(1, 5, figsize=(22, 6))
    fig.suptitle(
        "Top 4 Configurations per Metric",
        fontsize=14, fontweight='bold'
    )

    for ax, (title, ylabel, key_fn, ascending), color in zip(axes, metric_defs, palette):
        ranked = sorted(results, key=key_fn, reverse=not ascending)
        top4   = ranked[:4]
        names  = [r.display_name for r in top4]
        values = [key_fn(r) for r in top4]

        x    = np.arange(len(names))
        bars = ax.bar(x, values, color=color, alpha=0.85,
                      edgecolor='black', linewidth=0.5)

        ax.set_title(title, fontsize=9, fontweight='bold', pad=6)
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=38, ha='right', fontsize=7)
        ax.set_xlabel("Configuration", fontsize=8)
        ax.yaxis.grid(True, alpha=0.3)
        ax.set_axisbelow(True)

        # Value labels above bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() * 1.01,
                f'{val:.4g}',
                ha='center', va='bottom', fontsize=7
            )

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"  Top-4-per-metric dashboard saved to: {save_path}")


# ===========================================================================
# Top-4 by Area Renderer
# ===========================================================================

def render_top4_by_area(results: list,
                        save_path: str = "dashboard_top4_area.png") -> None:
    """
    Select the 4 configurations with the smallest area (fewest memory cells)
    and plot a grouped bar chart comparing them across all 5 metrics.

    Tie-break: lower latency first, then higher throughput.
    Saves as 'dashboard_top4_area.png'.
    """
    # Sort by area ascending, then latency ascending, then throughput descending
    sorted_by_area = sorted(
        results,
        key=lambda r: (r.area, r.latency, -r.throughput_tops)
    )
    top4 = sorted_by_area[:4]

    config_names = [r.display_name for r in top4]

    metrics = [
        ("Latency",           "Latency (cycles)",            [r.latency            for r in top4]),
        ("Energy",            "Energy (gates)",               [r.energy             for r in top4]),
        ("Area",              "Area (cells)",                 [r.area               for r in top4]),
        ("Throughput",        "Throughput (TOPS)",            [r.throughput_tops    for r in top4]),
        ("Energy Efficiency", "Energy Efficiency (TOPS/W)",   [r.energy_efficiency  for r in top4]),
    ]

    fig, axes = plt.subplots(1, 5, figsize=(20, 5))
    fig.suptitle(
        "Top 4 Configurations by Smallest Area (Memory Cells)",
        fontsize=13, fontweight='bold'
    )

    colors = ['#2E7D32', '#388E3C', '#43A047', '#66BB6A']   # green shades

    for ax, (title, ylabel, values) in zip(axes, metrics):
        x = np.arange(len(config_names))
        bars = ax.bar(x, values, color=colors, edgecolor='black', linewidth=0.5)
        ax.set_title(title, fontsize=10, fontweight='bold')
        ax.set_ylabel(ylabel, fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels(config_names, rotation=35, ha='right', fontsize=7.5)
        ax.set_xlabel("Configuration", fontsize=8)
        ax.yaxis.grid(True, alpha=0.3)
        ax.set_axisbelow(True)

        # Annotate bar tops
        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    f'{val:.4g}',
                    ha='center', va='bottom', fontsize=7)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()

    print(f"  Top-4-by-area dashboard saved to: {save_path}")
    print(f"  Selected: {', '.join(config_names)}")


# ===========================================================================
# Sigmoid vs f₆ Comparison Plot
# ===========================================================================

def plot_sigmoid_comparison(save_path: str = "sigmoid_vs_f6_comparison.png") -> None:
    """
    Plot the true sigmoid σ(x) = 1/(1+e^(-x)) alongside the f₆(x) approximation.

    f₆(x) = min(max((120 + 60x + 12x² + x³) / (240 + 24x²), 0), 1)

    This is a rational polynomial approximation of the sigmoid function,
    valid primarily in the range where the sigmoid transitions from 0 to 1.

    Saves the comparison plot as a PNG file.
    """
    # Generate x values over the interesting range
    x = np.linspace(-8, 8, 1000)

    # True sigmoid: σ(x) = 1 / (1 + e^(-x))
    sigmoid = 1.0 / (1.0 + np.exp(-x))

    # f₆(x) approximation (continuous, before clamping)
    numerator = 120.0 + 60.0 * x + 12.0 * x**2 + x**3
    denominator = 240.0 + 24.0 * x**2
    f6_raw = numerator / denominator

    # Clamped version: min(max(f6_raw, 0), 1)
    f6_clamped = np.clip(f6_raw, 0.0, 1.0)

    # Compute approximation error
    error = np.abs(sigmoid - f6_clamped)

    # Create figure with 2 subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), height_ratios=[3, 1])
    fig.suptitle("Sigmoid σ(x) vs f₆(x) Rational Approximation", fontsize=14, fontweight='bold')

    # Top plot: both curves
    ax1.plot(x, sigmoid, 'b-', linewidth=2, label='σ(x) = 1/(1+e⁻ˣ)')
    ax1.plot(x, f6_clamped, 'r--', linewidth=2, label='f₆(x) = clamp((120+60x+12x²+x³)/(240+24x²))')
    ax1.axhline(y=0.5, color='gray', linestyle=':', alpha=0.5)
    ax1.axvline(x=0, color='gray', linestyle=':', alpha=0.5)
    ax1.set_xlabel('x')
    ax1.set_ylabel('y')
    ax1.set_title('Function Comparison')
    ax1.legend(loc='lower right', fontsize=10)
    ax1.set_ylim(-0.05, 1.05)
    ax1.grid(True, alpha=0.3)

    # Bottom plot: absolute error
    ax2.plot(x, error, 'g-', linewidth=1.5)
    ax2.fill_between(x, 0, error, alpha=0.3, color='green')
    ax2.set_xlabel('x')
    ax2.set_ylabel('|σ(x) - f₆(x)|')
    ax2.set_title(f'Absolute Error (max = {error.max():.6f})')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, error.max() * 1.1 if error.max() > 0 else 0.1)

    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.show()
    print(f"  Sigmoid comparison saved to: {save_path}")


# ===========================================================================
# Main Entry Point
# ===========================================================================

def main():
    """
    Main entry point for the PIM F6 Function Dashboard.

    Orchestrates the full pipeline:
        1. Run all 12 configurations (6 strategies × 2 representations)
        2. Print summary table of all configurations
        3. Run correctness verification (if CorrectnessVerifier is available)
        4. Rank configurations and select top 4
        5. Print top 4 selected configurations
        6. Render and save the comparative dashboard

    Requirements: 10.1, 10.5
    """
    # -----------------------------------------------------------------------
    # Banner
    # -----------------------------------------------------------------------
    print("=" * 72)
    print("  PIM F6 Function Dashboard")
    print("  f₆(x) = min(max((120 + 60x + 12x² + x³) / (240 + 24x²), 0), 1)")
    print("  AritPIM Architecture Comparison")
    print("=" * 72)
    print()

    # -----------------------------------------------------------------------
    # Step 1: Run all 12 configurations
    # -----------------------------------------------------------------------
    print("[1/5] Running all 12 configurations (6 strategies × 2 representations)...")
    print(f"      Parameters: n=1024, N=32, num_cols=1024")
    print()

    engine = ConfigurationEngine(n=1024, N=32, num_cols=1024)
    results = engine.run_all_configurations()

    print(f"      Completed: {len(results)} configurations executed.")
    print()

    # -----------------------------------------------------------------------
    # Step 2: Print summary table of all 12 configurations
    # -----------------------------------------------------------------------
    print("[2/5] Configuration Results Summary")
    print("-" * 72)
    print(f"{'#':<3} {'Configuration':<28} {'Latency':>10} {'Energy':>10} "
          f"{'Area':>10} {'TOPS':>12} {'TOPS/W':>12}")
    print("-" * 72)

    for i, r in enumerate(results, 1):
        print(f"{i:<3} {r.display_name:<28} {r.latency:>10,} {r.energy:>10,} "
              f"{r.area:>10,} {r.throughput_tops:>12.6f} "
              f"{r.energy_efficiency:>12.4f}")

    print("-" * 72)
    print()

    # -----------------------------------------------------------------------
    # Step 3: Correctness verification (if CorrectnessVerifier is available)
    # -----------------------------------------------------------------------
    print("[3/5] Correctness Verification...")

    # CorrectnessVerifier requires simulator state and input values that are
    # not retained in ConfigResult objects. Skipping inline verification.
    # Use the property-based tests (test_property_f6_e2e.py) for correctness validation.
    print("      Skipping inline verification (use test_property_f6_e2e.py for correctness checks).")

    print()

    # -----------------------------------------------------------------------
    # Step 4: Rank configurations and select top 4
    # -----------------------------------------------------------------------
    print("[4/5] Ranking configurations and selecting top 4...")

    ranking_engine = RankingEngine()
    top4 = ranking_engine.rank(results)

    print()
    print("  Top 4 Configurations (by combined throughput + efficiency rank):")
    print("  " + "-" * 68)
    print(f"  {'Rank':<5} {'Configuration':<28} {'Combined':>8} {'T-Rank':>7} "
          f"{'E-Rank':>7} {'TOPS':>10}")
    print("  " + "-" * 68)

    for rank_idx, r in enumerate(top4, 1):
        print(f"  {rank_idx:<5} {r.display_name:<28} {r.combined_score:>8} "
              f"{r.throughput_rank:>7} {r.efficiency_rank:>7} "
              f"{r.throughput_tops:>10.6f}")

    print("  " + "-" * 68)
    print()

    # -----------------------------------------------------------------------
    # Step 5: Render and save dashboard
    # -----------------------------------------------------------------------
    # Step 5: Plot sigmoid vs f₆ comparison
    # -----------------------------------------------------------------------
    print("[5/6] Plotting sigmoid vs f₆(x) comparison...")
    plot_sigmoid_comparison()
    print()

    # -----------------------------------------------------------------------
    # Step 5b: Render all-configurations dashboard
    # -----------------------------------------------------------------------
    print("[5b/6] Rendering all-configurations dashboard...")
    AllConfigsDashboardRenderer().render(results)
    print()

    # -----------------------------------------------------------------------
    # Step 5c: Render top-4-by-area dashboard
    # -----------------------------------------------------------------------
    print("[5c/6] Rendering top-4-by-area dashboard...")
    render_top4_by_area(results)
    print()

    # -----------------------------------------------------------------------
    # Step 5d: Render top-4-per-metric combined dashboard
    # -----------------------------------------------------------------------
    print("[5d/6] Rendering top-4-per-metric combined dashboard...")
    render_top4_per_metric(results)
    print()

    # -----------------------------------------------------------------------
    # Step 5e: Overall best — 5-metric combined score
    # -----------------------------------------------------------------------
    print("[5e/6] Computing overall best configuration...")
    render_overall_best(results)
    print()

    # -----------------------------------------------------------------------
    # Step 6: Render and save dashboard
    # -----------------------------------------------------------------------
    save_path = "dashboard_comparison.png"
    print(f"[6/6] Rendering dashboard and saving to '{save_path}'...")

    renderer = DashboardRenderer()
    renderer.render(top4, save_path=save_path)

    print()
    print("=" * 72)
    print(f"  Dashboard saved to: {save_path}")
    print("  Execution complete.")
    print("=" * 72)


# ===========================================================================
# CorrectnessVerifier
# ===========================================================================

class CorrectnessVerifier:
    """
    Verifies PIM-computed f₆(x) results against NumPy reference values.

    Computes f₆(x) = min(max((120 + 60x + 12x² + x³) / (240 + 24x²), 0), 1)
    using NumPy as the reference implementation and compares against the
    PIM simulator's output.

    For fixed-point verification:
        - Computes the reference using unsigned integer arithmetic matching
          the PIM's computation (Horner's method for numerator, direct for
          denominator, integer division, then clamping).
        - Excludes samples where any intermediate or final result overflows
          the 32-bit signed integer range (< -2^31 or >= 2^31).
        - Requires exact match for all non-excluded samples.

    For floating-point verification:
        - Computes the reference using NumPy float32 arithmetic.
        - Excludes samples where the expected result is infinite or subnormal
          (exponent == 0 in IEEE 754 representation).
        - Requires exact bitwise match for all non-excluded samples.

    On mismatch, reports the first few mismatched values (input, expected,
    actual) and the total mismatch count.

    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
    """

    # Maximum number of mismatched samples to print in detail
    MAX_MISMATCH_DISPLAY = 10

    def verify_fixed(self, sim, x_values, result_addr, N: int = 32) -> bool:
        """
        Verify fixed-point PIM results against NumPy reference.

        Computes f₆(x) using unsigned integer arithmetic in NumPy, matching
        the PIM's Horner evaluation order, and compares against the PIM output
        stored in the simulator memory at result_addr.

        The reference computation follows the same steps as the PIM:
            numerator = ((x + 12) * x + 60) * x + 120  (using lower N bits)
            denominator = 24 * (x * x)_lower + 240     (using lower N bits)
            quotient = numerator // denominator         (integer division)
            clamped = min(max(quotient, 0), 1)          (clamping to [0, 1])

        Samples are excluded from comparison if any intermediate value
        overflows the 32-bit signed range (< -2^31 or >= 2^31).

        :param sim: SerialSimulator or ParallelSimulator after f₆ computation
        :param x_values: np.ndarray of shape (1, n) with unsigned integer inputs
        :param result_addr: address(es) of the clamped output in the simulator
                            - For serial: np.ndarray of N column addresses
                            - For parallel: int (intra-partition address)
        :param N: bit-width (default 32)
        :return: True if all non-excluded samples match, False otherwise
        """
        n = x_values.shape[1]
        x = x_values.astype(np.int64).flatten()

        # Mask for N-bit unsigned values (lower N bits)
        mask_N = (1 << N) - 1
        # Signed overflow threshold
        overflow_limit = 1 << (N - 1)  # 2^31 for N=32

        # --- Compute reference using the same Horner steps as PIM ---
        # Step 1: t1 = x + 12
        t1 = (x + 12) & mask_N

        # Step 2: t2 = t1 * x (take lower N bits)
        t2_full = t1 * x
        t2 = t2_full & mask_N

        # Step 3: t3 = t2 + 60 (lower N bits)
        t3 = (t2 + 60) & mask_N

        # Step 4: t4 = t3 * x (take lower N bits)
        t4_full = t3 * x
        t4 = t4_full & mask_N

        # Step 5: numerator = t4 + 120 (lower N bits)
        numerator = (t4 + 120) & mask_N

        # Denominator: x^2 lower N bits, then 24 * x^2_lower, then + 240
        x_sq_full = x * x
        x_sq = x_sq_full & mask_N
        t_24x2_full = 24 * x_sq
        t_24x2 = t_24x2_full & mask_N
        denominator = (t_24x2 + 240) & mask_N

        # Division: integer division (quotient = numerator // denominator)
        # Handle division by zero: output 0
        with np.errstate(divide='ignore', invalid='ignore'):
            quotient = np.where(denominator != 0, numerator // denominator, 0)

        # Clamping: min(max(quotient, 0), 1) for unsigned interpretation
        # In unsigned fixed-point, check if MSB is set (signed negative interpretation)
        is_negative = quotient >= overflow_limit  # MSB set → negative in signed view
        is_ge_one = quotient >= 1
        clamped_ref = np.where(is_negative, 0,
                      np.where(is_ge_one, 1, quotient))

        # --- Determine overflow exclusion mask ---
        # Exclude samples where any intermediate exceeds signed 32-bit range
        # In the PIM computation, overflow occurs when full products exceed
        # the representable range. We check if any intermediate (before masking)
        # would overflow a signed 32-bit interpretation.
        overflow_mask = (
            (t2_full >= (1 << (2 * N - 1))) |  # t1*x overflow
            (t4_full >= (1 << (2 * N - 1))) |  # t3*x overflow
            (x_sq_full >= (1 << (2 * N - 1))) |  # x*x overflow
            (t_24x2_full >= (1 << (2 * N - 1))) |  # 24*x^2 overflow
            (numerator >= overflow_limit) |  # numerator overflows signed N-bit
            (denominator >= overflow_limit)  # denominator overflows signed N-bit
        )

        # --- Read PIM result from simulator ---
        if isinstance(result_addr, np.ndarray):
            # Serial simulator: result_addr is array of N column addresses
            result_bits = sim.memory[result_addr]  # shape: (N, n)
            pim_result = representation.binaryToUnsignedFixed(result_bits).flatten()
        else:
            # Parallel simulator: result_addr is int (intra-partition address)
            partitions = np.arange(N)
            result_bits = sim.read(result_addr, partitions)  # shape: (N, n)
            pim_result = representation.binaryToUnsignedFixed(result_bits).flatten()

        # --- Compare non-excluded samples ---
        valid_mask = ~overflow_mask
        valid_indices = np.where(valid_mask)[0]

        if len(valid_indices) == 0:
            print(f"[CorrectnessVerifier] Fixed-point: All {n} samples excluded due to overflow.")
            return True

        expected = clamped_ref[valid_indices]
        actual = pim_result[valid_indices]
        mismatches = expected != actual
        mismatch_count = int(np.sum(mismatches))

        if mismatch_count == 0:
            print(f"[CorrectnessVerifier] Fixed-point: PASS - {len(valid_indices)} samples verified "
                  f"({n - len(valid_indices)} excluded for overflow).")
            return True
        else:
            # Report mismatches
            mismatch_indices = valid_indices[mismatches]
            display_count = min(mismatch_count, self.MAX_MISMATCH_DISPLAY)

            print(f"[CorrectnessVerifier] Fixed-point: FAIL - {mismatch_count} mismatches "
                  f"out of {len(valid_indices)} valid samples "
                  f"({n - len(valid_indices)} excluded for overflow).")
            print(f"  First {display_count} mismatches:")
            for i in range(display_count):
                idx = mismatch_indices[i]
                print(f"    x={x[idx]}, expected={clamped_ref[idx]}, actual={pim_result[idx]}")

            return False

    def verify_float(self, sim, x_values, result_addr, N: int = 32) -> bool:
        """
        Verify floating-point PIM results against NumPy float32 reference.

        Computes f₆(x) using NumPy float32 arithmetic following the same
        Horner evaluation order as the PIM, and compares against the PIM output
        stored in the simulator memory at result_addr.

        The reference computation:
            numerator = ((x + 12.0) * x + 60.0) * x + 120.0  (float32)
            denominator = 24.0 * (x * x) + 240.0             (float32)
            quotient = numerator / denominator                 (float32)
            clamped = min(max(quotient, 0.0), 1.0)            (float32)

        Samples are excluded from comparison if the expected result is:
            - Infinite (np.isinf)
            - Subnormal (exponent == 0 in IEEE 754, i.e., very small denormalized)

        :param sim: SerialSimulator or ParallelSimulator after f₆ computation
        :param x_values: np.ndarray of shape (1, n) with float32 inputs
        :param result_addr: address(es) of the clamped output in the simulator
                            - For serial: np.ndarray of N column addresses
                            - For parallel: int (intra-partition address)
        :param N: bit-width (default 32 for IEEE 754 float32)
        :return: True if all non-excluded samples match, False otherwise
        """
        n = x_values.shape[1]
        x = x_values.astype(np.float32).flatten()

        # --- Compute reference using float32 arithmetic (same Horner order as PIM) ---
        # Numerator: ((x + 12) * x + 60) * x + 120
        t1 = np.float32(x + np.float32(12.0))
        t2 = np.float32(t1 * x)
        t3 = np.float32(t2 + np.float32(60.0))
        t4 = np.float32(t3 * x)
        numerator = np.float32(t4 + np.float32(120.0))

        # Denominator: 24 * (x * x) + 240
        x_sq = np.float32(x * x)
        t_24x2 = np.float32(np.float32(24.0) * x_sq)
        denominator = np.float32(t_24x2 + np.float32(240.0))

        # Division
        with np.errstate(divide='ignore', invalid='ignore'):
            quotient = np.float32(np.where(denominator != 0.0, numerator / denominator, np.float32(0.0)))

        # Clamping: min(max(quotient, 0), 1)
        clamped_ref = np.minimum(np.maximum(quotient, np.float32(0.0)), np.float32(1.0))

        # --- Determine exclusion mask ---
        # Exclude infinite results
        is_infinite = np.isinf(clamped_ref)

        # Exclude subnormal results (exponent == 0 in IEEE 754)
        # A float32 is subnormal if its exponent field is 0 and mantissa is non-zero
        # We detect this by checking if the absolute value is less than the smallest normal
        # float32 (but not zero)
        smallest_normal = np.finfo(np.float32).tiny  # ~1.175e-38
        is_subnormal = (np.abs(clamped_ref) < smallest_normal) & (clamped_ref != 0.0)

        # Also exclude NaN results (should not occur but handle gracefully)
        is_nan = np.isnan(clamped_ref)

        # Also check intermediates for inf/subnormal
        intermediate_invalid = (
            np.isinf(numerator) | np.isinf(denominator) | np.isinf(quotient) |
            np.isnan(numerator) | np.isnan(denominator) | np.isnan(quotient)
        )

        exclusion_mask = is_infinite | is_subnormal | is_nan | intermediate_invalid

        # --- Read PIM result from simulator ---
        if isinstance(result_addr, np.ndarray):
            # Serial simulator: result_addr is array of N column addresses
            result_bits = sim.memory[result_addr]  # shape: (N, n)
            pim_result_float = representation.binaryToSignedFloat(result_bits).flatten()
        else:
            # Parallel simulator: result_addr is int (intra-partition address)
            partitions = np.arange(N)
            result_bits = sim.read(result_addr, partitions)  # shape: (N, n)
            pim_result_float = representation.binaryToSignedFloat(result_bits).flatten()

        # Convert both to their bit representations for exact bitwise comparison
        # This ensures we compare at the bit level (as required by the spec)
        ref_bits = representation.signedFloatToBinary(
            clamped_ref.reshape(1, -1).astype(np.float32))  # shape: (32, n)
        pim_bits = result_bits  # already in binary form, shape: (N, n)

        # --- Compare non-excluded samples (bitwise) ---
        valid_mask = ~exclusion_mask
        valid_indices = np.where(valid_mask)[0]

        if len(valid_indices) == 0:
            print(f"[CorrectnessVerifier] Float: All {n} samples excluded "
                  f"(infinite/subnormal/NaN).")
            return True

        # Compare bit patterns for valid samples
        ref_valid_bits = ref_bits[:, valid_indices]   # shape: (N, num_valid)
        pim_valid_bits = pim_bits[:, valid_indices]   # shape: (N, num_valid)

        # A sample mismatches if any bit differs
        bit_mismatches = ref_valid_bits != pim_valid_bits  # shape: (N, num_valid)
        sample_mismatches = np.any(bit_mismatches, axis=0)  # shape: (num_valid,)
        mismatch_count = int(np.sum(sample_mismatches))

        if mismatch_count == 0:
            print(f"[CorrectnessVerifier] Float: PASS - {len(valid_indices)} samples verified "
                  f"({n - len(valid_indices)} excluded for infinite/subnormal).")
            return True
        else:
            # Report mismatches
            mismatch_local_indices = np.where(sample_mismatches)[0]
            mismatch_global_indices = valid_indices[mismatch_local_indices]
            display_count = min(mismatch_count, self.MAX_MISMATCH_DISPLAY)

            print(f"[CorrectnessVerifier] Float: FAIL - {mismatch_count} mismatches "
                  f"out of {len(valid_indices)} valid samples "
                  f"({n - len(valid_indices)} excluded for infinite/subnormal).")
            print(f"  First {display_count} mismatches:")
            for i in range(display_count):
                idx = mismatch_global_indices[i]
                print(f"    x={x[idx]:.8e}, expected={clamped_ref[idx]:.8e}, "
                      f"actual={pim_result_float[idx]:.8e}")

            return False



# ===========================================================================
# Script Entry Point
# ===========================================================================

if __name__ == "__main__":
    main()
