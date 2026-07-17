#!/usr/bin/env python3
"""
Unified divider cost model for DAFTPUM-LAT.

Covers:
  Exact (2):
    exact_array  — restoring array divider  (exact)
    exact_log    — LNS Mitchell logarithmic divider

  Approximate (9):
    aaxd         — Adaptive Approximate Divider      (IEEE TC 2020)
    inzed        — Inexact Zero-based Divider         (DATE 2019)
    axdr1        — Approximate Restoring Divider v1   (IEEE TC 2018)
    axdr3        — Approximate Restoring Divider v3   (IEEE TC 2018)
    seerad4      — Rounding-based Approx Divider l=4  (DATE 2016)
    daxd         — Dual-path Approximate Divider      (MICPRO 2020)
    sc           — Stochastic-Computing Divider       (IEEE TC 2017)
    rapid        — RAPID Mitchell Logarithmic         (FPGA 2018)
    fpca3d       — 3D-FPCA RRAM Reciprocal Divider    (prior work)

Latency/energy for exact_array are derived by scaling the best-DAFTPUM-LAT
multiplier (CSA/Sklansky) by ratio 2.3× (array divider ≈ n iterations of a
partial-remainder step, standard in the literature).

Approximate dividers use published latency-savings ratios relative to
exact_array @ 16-bit as the calibration anchor (see updatetwo.md table).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

from adder_cost_model import (
    AAP_ENERGY_PJ,
    SIMD_WIDTH,
    LAT_DAFTPUM_FULL_ADDER,
    LAT_DAFTPUM_RBR_ADDER,
    exact_adder_energy_pj,
    get_adder_metrics,
)

# ------------------------------------------------------------------
# Best-multiplier latency LUTs (copied to avoid circular import)
# ------------------------------------------------------------------
_LAT_CSA_MULT = [
    0, 2974, 2974, 7773, 11052, 14675, 18642, 22953, 27608, 32607,
    37950, 43637, 49668, 56043, 62762, 69825, 77232, 84983, 93078,
    101517, 110300, 119427, 128898, 138713, 148872, 159375, 170222,
    181413, 192948, 204827, 217050, 229617, 242528, 255783, 269382,
    283325, 297612, 312243, 327218, 342537, 358200, 374207, 390558,
    407253, 424292, 441675, 459402, 477473, 495888, 514647, 533750,
    553197, 572988, 593123, 613602, 634425, 655592, 677103, 698958,
    721157, 743700, 766587, 789818, 813393,
]

_LAT_SKLANSKY_MULT = [
    0, 5120, 5120, 8722, 12656, 16856, 21283, 25911, 30720, 35698,
    40833, 46117, 51542, 57104, 62797, 68617, 74560, 80623, 86803,
    93098, 99505, 106023, 112649, 119382, 126221, 133163, 140208,
    147355, 154602, 161949, 169394, 176937, 184576, 192311, 200142,
    208067, 216086, 224199, 232404, 240702, 249091, 257571, 266142,
    274803, 283554, 292395, 301325, 310343, 319450, 328644, 337927,
    347296, 356753, 366296, 375926, 385643, 395445, 405333, 415306,
    425364, 435508, 445736, 456049, 466447,
]

_ARRAY_DIV_SCALE = 2.3          # divider ≈ 2.3× multiplier latency/energy
_EXACT_ARRAY_AREA_16_GE = 2048.0  # gate-equivalents @ 16-bit, 28 nm estimate


def _best_mult_lat_ps(bp: int) -> int:
    bp = max(1, min(bp, 63))
    return min(_LAT_CSA_MULT[bp], _LAT_SKLANSKY_MULT[bp])


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------

class DividerFamily(str, Enum):
    EXACT       = "exact"
    APPROXIMATE = "approximate"


@dataclass(frozen=True)
class DividerSpec:
    key:         str
    label:       str
    family:      DividerFamily
    description: str
    ned:         float = 0.0   # Normalized Error Distance
    mred_pct:    float = 0.0   # Mean Relative Error Distance (%)
    ed_max:      int   = 0     # Maximum absolute error


@dataclass
class DividerMetrics:
    latency_ns: float
    energy_nj:  float
    area_ge:    float
    ned:        float
    mred_pct:   float
    ed_max:     int


EXACT_DIVIDERS: tuple[DividerSpec, ...] = (
    DividerSpec(
        "exact_array", "Exact Array",
        DividerFamily.EXACT,
        "Restoring array divider (n iterations of a partial-remainder step)",
    ),
    DividerSpec(
        "exact_log", "Exact Logarithmic",
        DividerFamily.EXACT,
        "LNS/Mitchell-based logarithmic divider (subtraction in log domain)",
    ),
)

APPROX_DIVIDERS: tuple[DividerSpec, ...] = (
    DividerSpec(
        "aaxd", "AAXD",
        DividerFamily.APPROXIMATE,
        "Adaptive Approximate Divider — adaptive LSB pruning (IEEE TC 2020)",
        ned=2.97, mred_pct=6.61, ed_max=49,
    ),
    DividerSpec(
        "inzed", "INZeD",
        DividerFamily.APPROXIMATE,
        "Inexact Zero-based Divider — zero-based partial products (DATE 2019)",
        ned=4.50, mred_pct=8.20, ed_max=85,
    ),
    DividerSpec(
        "axdr1", "AXDr1",
        DividerFamily.APPROXIMATE,
        "Approximate Restoring Divider v1, depth-8 approx subtractor (IEEE TC 2018)",
        ned=1.32, mred_pct=4.32, ed_max=51,
    ),
    DividerSpec(
        "axdr3", "AXDr3",
        DividerFamily.APPROXIMATE,
        "Approximate Restoring Divider v3, higher-accuracy variant (IEEE TC 2018)",
        ned=0.97, mred_pct=3.25, ed_max=85,
    ),
    DividerSpec(
        "seerad4", "SEERAD-4",
        DividerFamily.APPROXIMATE,
        "Rounding-based approximate divider, accuracy level 4 (DATE 2016)",
        ned=1.09, mred_pct=2.71, ed_max=165,
    ),
    DividerSpec(
        "daxd", "DAXD",
        DividerFamily.APPROXIMATE,
        "Dual-path Approximate Divider with bit-width reduction (MICPRO 2020)",
        ned=7.44, mred_pct=16.39, ed_max=240,
    ),
    DividerSpec(
        "sc", "SC Divider",
        DividerFamily.APPROXIMATE,
        "Stochastic-Computing divider, bit-stream encoding (IEEE TC 2017)",
        ned=15.0, mred_pct=25.0, ed_max=500,
    ),
    DividerSpec(
        "rapid", "RAPID",
        DividerFamily.APPROXIMATE,
        "RAPID reconfigurable logarithmic approximate divider (FPGA 2018)",
        ned=3.5, mred_pct=7.2, ed_max=120,
    ),
    DividerSpec(
        "fpca3d", "3D-FPCA",
        DividerFamily.APPROXIMATE,
        "3D-FPCA RRAM reciprocal + multiply: 0.63·n adder steps + 1 mult",
        ned=2.5, mred_pct=5.8, ed_max=60,
    ),
)

ALL_DIVIDERS: tuple[DividerSpec, ...] = EXACT_DIVIDERS + APPROX_DIVIDERS

# ------------------------------------------------------------------
# Published latency / energy savings vs exact_array @ 16-bit
# (from updatetwo.md)
# ------------------------------------------------------------------
_APPROX_SAVINGS: Dict[str, Dict[str, float]] = {
    "aaxd":    {"latency": 0.610, "energy": 0.694, "area": 0.620},
    "inzed":   {"latency": 0.580, "energy": 0.662, "area": 0.580},
    "axdr1":   {"latency": 0.510, "energy": 0.601, "area": 0.510},
    "axdr3":   {"latency": 0.480, "energy": 0.584, "area": 0.480},
    "seerad4": {"latency": 0.420, "energy": 0.519, "area": 0.420},
    "daxd":    {"latency": 0.450, "energy": 0.549, "area": 0.450},
}


# ------------------------------------------------------------------
# Cost helpers
# ------------------------------------------------------------------

def _array_lat_ns(bp: int) -> float:
    return _ARRAY_DIV_SCALE * _best_mult_lat_ps(bp) / 1000.0


def _array_energy_nj(bp: int, size: int) -> float:
    """Approximate array-divider energy = 2.3 × best-multiplier energy."""
    ceil_simd = math.ceil(size / SIMD_WIDTH)
    d = float(bp)
    # Sklansky/CSA energy formula (from multiplier_cost_model.py)
    energy_pj = (4*d + 0.0075*d*(d-1) + 0.0075*2*0.1*d
                 + d*(19.15*2*d + math.log2(max(2*d, 1)) - 19))
    return _ARRAY_DIV_SCALE * energy_pj * ceil_simd * AAP_ENERGY_PJ / 1000.0


def _array_area_ge(bp: int) -> float:
    return _EXACT_ARRAY_AREA_16_GE * (bp / 16.0) ** 2


def _log_lat_ns(bp: int) -> float:
    """LNS: two log conversions + log-domain subtraction + antilog.
    Modelled as 1.3 × 2 × RBR-adder latency at bp."""
    bp_safe = max(1, min(bp, 63))
    return 1.3 * 2 * LAT_DAFTPUM_RBR_ADDER[bp_safe] / 1000.0


def _log_energy_nj(bp: int, size: int) -> float:
    """LNS energy ≈ 1.5 × RBR adder energy (two-stage pipeline)."""
    ceil_simd = math.ceil(size / SIMD_WIDTH)
    return 1.5 * exact_adder_energy_pj(bp, "rbr", size) / 1000.0


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def get_divider_metrics(bp: int, key: str, size: int = 1024) -> DividerMetrics:
    spec = next(s for s in ALL_DIVIDERS if s.key == key)
    bp = max(1, min(bp, 63))

    if key == "exact_array":
        lat    = _array_lat_ns(bp)
        energy = _array_energy_nj(bp, size)
        area   = _array_area_ge(bp)

    elif key == "exact_log":
        lat    = _log_lat_ns(bp)
        energy = _log_energy_nj(bp, size)
        area   = _array_area_ge(bp) * 0.55  # LNS circuit ≈ 45% smaller

    elif key == "fpca3d":
        # Reciprocal via 0.63·bp repeated subtractions + 1 multiplication
        lat_add  = LAT_DAFTPUM_FULL_ADDER[bp] / 1000.0
        lat_mult = _best_mult_lat_ps(bp) / 1000.0
        lat      = 0.63 * bp * lat_add + lat_mult

        e_add  = exact_adder_energy_pj(bp, "full", size) / 1000.0
        e_mult = _array_energy_nj(bp, size) / _ARRAY_DIV_SCALE
        energy = 0.63 * bp * e_add + e_mult
        area   = _array_area_ge(bp) * 0.85

    elif key == "sc":
        # Stochastic: 2^bp clock cycles
        num_cycles = 2.0 ** bp
        lat        = num_cycles * 4.1                                # ns/cycle estimate
        ceil_simd  = math.ceil(size / SIMD_WIDTH)
        energy     = 0.000624 * num_cycles * ceil_simd               # nJ
        area       = _array_area_ge(bp) * 0.30                      # very small hw

    elif key == "rapid":
        # RAPID: logarithmic design, depth ∝ log2(bp)
        log2_bp = math.log2(bp) if bp > 1 else 0.0
        lat     = 1.2 * log2_bp + 1.6                               # ns
        ceil_simd = math.ceil(size / SIMD_WIDTH)
        energy  = ((0.1 * bp**2 + 0.5 * bp) / 1000.0) * ceil_simd  # nJ
        area    = _array_area_ge(bp) * 0.32

    else:
        # Savings-table approximate dividers
        sav    = _APPROX_SAVINGS[key]
        lat    = _array_lat_ns(bp)    * (1.0 - sav["latency"])
        energy = _array_energy_nj(bp, size) * (1.0 - sav["energy"])
        area   = _array_area_ge(bp)   * (1.0 - sav["area"])

    return DividerMetrics(
        latency_ns=lat,
        energy_nj=energy,
        area_ge=area,
        ned=spec.ned,
        mred_pct=spec.mred_pct,
        ed_max=spec.ed_max,
    )


def evaluate_all_dividers(
    bit_precisions: List[int],
    size: int = 1024,
) -> Dict[str, Dict[str, list]]:
    result: Dict[str, Dict[str, list]] = {
        "latency_ns": {s.key: [] for s in ALL_DIVIDERS},
        "energy_nj":  {s.key: [] for s in ALL_DIVIDERS},
        "area_ge":    {s.key: [] for s in ALL_DIVIDERS},
    }
    for bp in bit_precisions:
        for spec in ALL_DIVIDERS:
            m = get_divider_metrics(bp, spec.key, size)
            result["latency_ns"][spec.key].append(m.latency_ns)
            result["energy_nj"][spec.key].append(m.energy_nj)
            result["area_ge"][spec.key].append(m.area_ge)
    return result


def summary_table(
    bit_precisions: List[int],
    size: int = 1024,
) -> List[dict]:
    rows = []
    for bp in bit_precisions:
        for spec in ALL_DIVIDERS:
            m = get_divider_metrics(bp, spec.key, size)
            rows.append({
                "bp":         bp,
                "key":        spec.key,
                "label":      spec.label,
                "family":     spec.family.value,
                "latency_ns": round(m.latency_ns, 6),
                "energy_nj":  round(m.energy_nj,  6),
                "area_ge":    round(m.area_ge,     2),
                "ned":        m.ned,
                "mred_pct":   m.mred_pct,
                "ed_max":     m.ed_max,
            })
    return rows
