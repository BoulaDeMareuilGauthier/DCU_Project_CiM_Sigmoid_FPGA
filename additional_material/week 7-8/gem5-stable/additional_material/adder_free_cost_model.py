#!/usr/bin/env python3
"""
Adder-free cost model based on AFSRAM-CIM architecture.

This model implements the adder-tree free approach described in:
"AFSRAM-CIM: Adder Free SRAM-Based Digital Computation-in-Memory for BNN"
by El arrassi et al., VLSI-SoC 2024.

Key innovations:
- Uses digital counters instead of adder-trees for popcount operations
- Sequential processing through flip-flops and multiplexers
- Achieves 3× energy savings and ≈17× area savings vs adder-tree
- Energy: 11.86 fJ per operation at 40nm
- Area: 74.91 μm² for 128-bit vs 1246 μm² for adder-tree
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

# Constants from AFSRAM-CIM paper (40nm technology)
AFSRAM_ENERGY_PER_OP_FJ = 11.86  # fJ per binary MAC operation
AFSRAM_AREA_128BIT_UM2 = 74.91  # μm² for 128-bit popcount unit
ADDER_TREE_AREA_128BIT_UM2 = 1246.0  # μm² for conventional 128-bit adder-tree
AFSRAM_TECHNOLOGY_NM = 40  # Technology node from paper

# Scaling factors for different bit precisions
# Based on the paper's 128-bit implementation
BASE_BIT_PRECISION = 128


@dataclass
class AdderFreeMetrics:
    bit_precision: int
    latency_ns: float
    energy_nj: float
    area_um2: float
    area_ge: float  # Gate-equivalent area for comparison


def adder_free_latency_ns(bp: int, num_banks: int = 8) -> float:
    """
    Calculate latency for adder-free popcount operation.
    
    From the paper: The architecture uses sequential processing where:
    - Each bank processes one row at a time
    - Flip-flops deliver RBL outputs sequentially
    - Counter receives XNOR outputs from all rows sequentially
    
    Latency model:
    - Base latency per bit: scales with log2(bit_precision) for counter
    - Sequential bank processing: num_banks cycles
    - Each cycle includes: XNOR operation + flip-flop transfer + counter increment
    """
    # Base counter latency scales with bit precision (logarithmic for digital counter)
    counter_latency_ns = 0.5 * math.log2(max(1, bp))
    
    # Sequential processing through banks
    # Paper mentions 16 rows per bank, 128 columns
    # We model this as num_banks sequential cycles
    bank_cycles = num_banks
    
    # Each cycle: XNOR (in SRAM cell) + flip-flop transfer + counter increment
    cycle_time_ns = 0.3 + counter_latency_ns / bank_cycles
    
    total_latency_ns = cycle_time_ns * bank_cycles
    
    return total_latency_ns


def adder_free_energy_nj(bp: int, size: int = 1024) -> float:
    """
    Calculate energy for adder-free popcount operation.
    
    From the paper: 11.86 fJ per operation at 40nm for binary MAC.
    Energy scales with:
    - Bit precision (counter size)
    - Number of elements (size)
    - Technology scaling
    
    Model:
    - Base energy from paper: 11.86 fJ per 128-bit operation
    - Scale linearly with bit precision
    - Scale with element count
    """
    # Scale from 128-bit baseline
    bp_scale = bp / BASE_BIT_PRECISION
    
    # Scale with element count (linear scaling as in traditional adders)
    # Using SIMD width from adder_cost_model.py
    SIMD_WIDTH = 65536
    simd_scale = math.ceil(size / SIMD_WIDTH)
    
    # Base energy in nJ (convert from fJ)
    base_energy_nj = AFSRAM_ENERGY_PER_OP_FJ / 1000.0
    
    # Total energy
    total_energy_nj = base_energy_nj * bp_scale * simd_scale
    
    return total_energy_nj


def adder_free_area_um2(bp: int) -> float:
    """
    Calculate area for adder-free popcount unit.
    
    From the paper: 74.91 μm² for 128-bit popcount unit.
    This includes:
    - Digital counter
    - Flip-flops
    - Multiplexers
    
    Area scales with bit precision (counter size).
    """
    # Scale from 128-bit baseline
    bp_scale = bp / BASE_BIT_PRECISION
    
    # Area scales roughly linearly with bit precision for counters
    total_area_um2 = AFSRAM_AREA_128BIT_UM2 * bp_scale
    
    return total_area_um2


def adder_free_area_ge(bp: int) -> float:
    """
    Convert area to gate-equivalents for comparison with adder_cost_model.
    
    Using the same normalization as adder_cost_model.py:
    - Full adder area = bp gate-equivalents
    - We normalize adder-free area to this scale based on paper's area measurements
    
    From paper:
    - Adder-tree area: 1246 μm² for 128-bit
    - Adder-free area: 74.91 μm² for 128-bit
    - Ratio: 1246 / 74.91 ≈ 16.6× area savings
    
    We normalize so that the adder-free area reflects this savings ratio.
    """
    # Get physical area
    area_um2 = adder_free_area_um2(bp)
    
    # Normalize based on the paper's area ratio
    # For 128-bit: adder_tree = 1246 μm², adder_free = 74.91 μm²
    # In adder_cost_model.py, Full adder at 128-bit = 128 GE
    # So we need: adder_free GE = 128 / 16.6 ≈ 7.7 GE for 128-bit
    
    # Calculate the area ratio from paper
    area_ratio = ADDER_TREE_AREA_128BIT_UM2 / AFSRAM_AREA_128BIT_UM2  # ≈ 16.6
    
    # Normalize: Full adder at bp has area = bp GE
    # Adder-free should have area = bp / area_ratio GE
    area_ge = bp / area_ratio
    
    return area_ge


def get_adder_free_metrics(bp: int, size: int = 1024, num_banks: int = 8) -> AdderFreeMetrics:
    """
    Get complete metrics for adder-free implementation at given bit precision.
    """
    if bp < 1 or bp > 256:
        raise ValueError(f"bit precision must be in [1, 256], got {bp}")
    
    latency_ns = adder_free_latency_ns(bp, num_banks)
    energy_nj = adder_free_energy_nj(bp, size)
    area_um2 = adder_free_area_um2(bp)
    area_ge = adder_free_area_ge(bp)
    
    return AdderFreeMetrics(bp, latency_ns, energy_nj, area_um2, area_ge)


def compare_with_adder_tree(bp: int, size: int = 1024) -> Dict[str, float]:
    """
    Compare adder-free approach with conventional adder-tree.
    
    Returns savings ratios (energy_savings, area_savings).
    Note: adder_cost_model.py supports up to 63-bit precision.
    For higher precisions, we extrapolate using the Full adder formula.
    """
    # Get adder-free metrics
    af_metrics = get_adder_free_metrics(bp, size)
    
    # Estimate adder-tree metrics (using Full adder as baseline)
    # From adder_cost_model.py
    from adder_cost_model import get_adder_metrics, exact_adder_energy_pj, exact_adder_area_ge
    
    # Check if bp is within supported range
    if bp <= 63:
        adder_tree_metrics = get_adder_metrics(bp, "full", size)
        adder_tree_latency = adder_tree_metrics.latency_ns
        adder_tree_energy = adder_tree_metrics.energy_nj
        adder_tree_area = adder_tree_metrics.area_ge
    else:
        # Extrapolate for higher precisions using Full adder formulas
        # Use the last known latency from the table and extrapolate
        from adder_cost_model import LAT_DAFTPUM_FULL_ADDER
        last_known_bp = 63
        last_known_lat = LAT_DAFTPUM_FULL_ADDER[last_known_bp]
        # Linear extrapolation for latency (conservative estimate)
        adder_tree_latency = (last_known_lat / 1000.0) * (bp / last_known_bp)
        
        # Use energy formula directly
        adder_tree_energy = exact_adder_energy_pj(bp, "full", size) / 1000.0
        adder_tree_area = exact_adder_area_ge(bp, "full")
    
    # Calculate savings
    energy_savings = (adder_tree_energy - af_metrics.energy_nj) / adder_tree_energy
    area_savings = (adder_tree_area - af_metrics.area_ge) / adder_tree_area
    
    return {
        "energy_savings": energy_savings,
        "area_savings": area_savings,
        "adder_free_latency_ns": af_metrics.latency_ns,
        "adder_tree_latency_ns": adder_tree_latency,
        "adder_free_energy_nj": af_metrics.energy_nj,
        "adder_tree_energy_nj": adder_tree_energy,
        "adder_free_area_ge": af_metrics.area_ge,
        "adder_tree_area_ge": adder_tree_area,
    }


def evaluate_all_precisions(
    bit_precisions: List[int],
    size: int = 1024,
    num_banks: int = 8,
) -> List[Dict[str, float]]:
    """
    Evaluate adder-free metrics across multiple bit precisions.
    """
    results = []
    for bp in bit_precisions:
        metrics = get_adder_free_metrics(bp, size, num_banks)
        comparison = compare_with_adder_tree(bp, size)
        
        results.append({
            "bit_precision": bp,
            "latency_ns": round(metrics.latency_ns, 4),
            "energy_nj": round(metrics.energy_nj, 6),
            "area_um2": round(metrics.area_um2, 3),
            "area_ge": round(metrics.area_ge, 3),
            "energy_savings_vs_adder_tree": round(comparison["energy_savings"], 3),
            "area_savings_vs_adder_tree": round(comparison["area_savings"], 3),
        })
    
    return results


def summary_table(bit_precisions: List[int], size: int = 1024) -> List[Dict[str, float | str]]:
    """
    Generate summary table for adder-free approach.
    """
    rows = []
    for bp in bit_precisions:
        m = get_adder_free_metrics(bp, size)
        comp = compare_with_adder_tree(bp, size)
        
        rows.append({
            "bit_precision": bp,
            "approach": "adder_free",
            "latency_ns": round(m.latency_ns, 4),
            "energy_nj": round(m.energy_nj, 6),
            "area_ge": round(m.area_ge, 3),
            "energy_savings_vs_adder_tree": f"{comp['energy_savings']*100:.1f}%",
            "area_savings_vs_adder_tree": f"{comp['area_savings']*100:.1f}%",
        })
    
    return rows


if __name__ == "__main__":
    # Test the model
    print("Adder-Free Cost Model Test")
    print("=" * 60)
    
    # Test at 128-bit (paper's baseline)
    print("\n128-bit (paper baseline):")
    m = get_adder_free_metrics(128)
    print(f"  Latency: {m.latency_ns:.4f} ns")
    print(f"  Energy: {m.energy_nj:.6f} nJ")
    print(f"  Area: {m.area_um2:.3f} um^2")
    print(f"  Area (GE): {m.area_ge:.3f}")
    
    # Test comparison with adder-tree
    print("\nComparison with adder-tree at 128-bit:")
    comp = compare_with_adder_tree(128)
    print(f"  Energy savings: {comp['energy_savings']*100:.1f}%")
    print(f"  Area savings: {comp['area_savings']*100:.1f}%")
    
    # Test across precisions
    print("\nSummary across bit precisions:")
    print("-" * 60)
    for row in summary_table([8, 16, 32, 64, 128]):
        print(f"  {row['bit_precision']:3d}-bit: "
              f"E={row['energy_savings_vs_adder_tree']:>7s}, "
              f"A={row['area_savings_vs_adder_tree']:>7s}")
