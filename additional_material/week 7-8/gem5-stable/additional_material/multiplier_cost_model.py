#!/usr/bin/env python3
"""
Unified multiplier cost model for DAFTPUM-LAT exact multipliers and approximate
multipliers (CGPM1, TAM1, HOCM, CGPM3, BAM, Mitchell, ALM-SOA, ILM-AA).

Exact latency/energy data are ported from Proteus bbop_manager.c
(additional_material/test_cost_model.cc). Mitchell uses the model from
mitchell_vs_daftpumlat.cc. Other approximate multipliers are calibrated against
Han et al. survey (IEEE TC 2020) synthesis results.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List

from adder_cost_model import AAP_ENERGY_PJ, LAT_DAFTPUM_KOGGE_ADDER, SIMD_WIDTH

# Latency lookup tables (ps) — index = bit precision
LAT_SIMDRAM_RC_MULT = [
    0, 1617, 1617, 4067, 7595, 12201, 17885, 24647, 32487, 41405,
    51401, 62475, 74627, 87857, 102165, 117551, 134015, 151557, 170177,
    189875, 210651, 232505, 255437, 279447, 304535, 330701, 357945, 386267,
    415667, 446145, 477701, 510335, 544047, 578837, 614705, 651651, 689675,
    728777, 768957, 810215, 852551, 895965, 940457, 986027, 1032675, 1080401,
    1129205, 1179087, 1230047, 1282085, 1335201, 1389395, 1444667, 1501017,
    1558445, 1616951, 1676535, 1737197, 1798937, 1861755, 1925651, 1990625,
    2056677, 2123807,
]

LAT_DAFTPUM_SKLANSKY_MULT = [
    0, 5120, 5120, 8722, 12656, 16856, 21283, 25911, 30720, 35698,
    40833, 46117, 51542, 57104, 62797, 68617, 74560, 80623, 86803,
    93098, 99505, 106023, 112649, 119382, 126221, 133163, 140208,
    147355, 154602, 161949, 169394, 176937, 184576, 192311, 200142,
    208067, 216086, 224199, 232404, 240702, 249091, 257571, 266142,
    274803, 283554, 292395, 301325, 310343, 319450, 328644, 337927,
    347296, 356753, 366296, 375926, 385643, 395445, 405333, 415306,
    425364, 435508, 445736, 456049, 466447,
]

LAT_DAFTPUM_CSA_MULT = [
    0, 2974, 2974, 7773, 11052, 14675, 18642, 22953, 27608, 32607,
    37950, 43637, 49668, 56043, 62762, 69825, 77232, 84983, 93078,
    101517, 110300, 119427, 128898, 138713, 148872, 159375, 170222,
    181413, 192948, 204827, 217050, 229617, 242528, 255783, 269382,
    283325, 297612, 312243, 327218, 342537, 358200, 374207, 390558,
    407253, 424292, 441675, 459402, 477473, 495888, 514647, 533750,
    553197, 572988, 593123, 613602, 634425, 655592, 677103, 698958,
    721157, 743700, 766587, 789818, 813393,
]

LAT_DAFTPUM_RBR_MULT = [
    0, 11232, 11232, 16872, 22528, 28200, 33888, 39592, 45312, 51048,
    56800, 62568, 68352, 74152, 79968, 85800, 91648, 97512, 103392,
    109288, 115200, 121128, 127072, 133032, 139008, 145000, 151008,
    157032, 163072, 169128, 175200, 181288, 187392, 193512, 199648,
    205800, 211968, 218152, 224352, 230568, 236800, 243048, 249312,
    255592, 261888, 268200, 274528, 280872, 287232, 293608, 300000,
    306408, 312832, 319272, 325728, 332200, 338688, 345192, 351712,
    358248, 364800, 371368, 377952, 384552,
]


class MultiplierFamily(str, Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"


@dataclass(frozen=True)
class MultiplierSpec:
    key: str
    label: str
    family: MultiplierFamily
    description: str


EXACT_MULTIPLIERS: tuple[MultiplierSpec, ...] = (
    MultiplierSpec("full", "Full (RC Array)", MultiplierFamily.EXACT, "Ripple-carry array multiplier"),
    MultiplierSpec("sklansky", "Sklansky", MultiplierFamily.EXACT, "Sklansky-tree multiplier"),
    MultiplierSpec("carrysel", "Carry-Select", MultiplierFamily.EXACT, "Carry-save / carry-select multiplier"),
    MultiplierSpec("rbr", "RBR", MultiplierFamily.EXACT, "Reversed-biased ripple multiplier"),
)

APPROX_MULTIPLIERS: tuple[MultiplierSpec, ...] = (
    MultiplierSpec("mitchell", "Mitchell", MultiplierFamily.APPROXIMATE, "Logarithmic approximate multiplier (shift + add)"),
    MultiplierSpec("alm_soa", "ALM-SOA", MultiplierFamily.APPROXIMATE, "Approximate logarithmic multiplier with set-one-adder"),
    MultiplierSpec("ilm_aa", "ILM-AA", MultiplierFamily.APPROXIMATE, "Improved logarithmic multiplier with approximate adders"),
    MultiplierSpec("cgpm1", "CGPM1", MultiplierFamily.APPROXIMATE, "CGP-generated approximate multiplier (1 sub-block)"),
    MultiplierSpec("tam1", "TAM1", MultiplierFamily.APPROXIMATE, "Truncation with adaptive error compensation"),
    MultiplierSpec("hocm", "HOCM (1StepTrunc)", MultiplierFamily.APPROXIMATE, "High-order compressor multiplier, 1-step truncated"),
    MultiplierSpec("cgpm3", "CGPM3", MultiplierFamily.APPROXIMATE, "CGP-generated approximate multiplier (3 sub-blocks)"),
    MultiplierSpec("bam", "BAM", MultiplierFamily.APPROXIMATE, "Broken-array multiplier"),
)

# Logarithmic / partial-product approximate families keyed separately.
_LOGARITHMIC_MULTS = frozenset({"mitchell", "alm_soa", "ilm_aa"})

ALL_MULTIPLIERS: tuple[MultiplierSpec, ...] = EXACT_MULTIPLIERS + APPROX_MULTIPLIERS

EXACT_LATENCY_TABLES: Dict[str, List[int]] = {
    "full": LAT_SIMDRAM_RC_MULT,
    "sklansky": LAT_DAFTPUM_SKLANSKY_MULT,
    "carrysel": LAT_DAFTPUM_CSA_MULT,
    "rbr": LAT_DAFTPUM_RBR_MULT,
}

# 16-bit unsigned multiplier calibration vs. accurate array multiplier
# (Han et al. survey, Table II / Fig. 11–13, 28 nm synthesis).
_APPROX_BASE = {
    "bam": {"latency": 0.38, "energy": 0.30, "area": 0.28},
    "tam1": {"latency": 0.42, "energy": 0.46, "area": 0.44},
    "hocm": {"latency": 0.48, "energy": 0.50, "area": 0.50},
    "cgpm1": {"latency": 0.52, "energy": 0.62, "area": 0.56},
    "cgpm3": {"latency": 0.58, "energy": 0.70, "area": 0.68},
}


@dataclass
class MultiplierMetrics:
    bit_precision: int
    multiplier: str
    latency_ns: float
    energy_nj: float
    area_ge: float


def _validate_bp(bp: int) -> None:
    if bp < 1 or bp >= len(LAT_SIMDRAM_RC_MULT):
        raise ValueError(f"bit precision must be in [1, {len(LAT_SIMDRAM_RC_MULT) - 1}], got {bp}")


def _ceil_simd(size: int) -> float:
    return math.ceil(size / SIMD_WIDTH)


def _best_exact_latency_ps(bp: int) -> float:
    return float(min(EXACT_LATENCY_TABLES[k][bp] for k in EXACT_LATENCY_TABLES))


def _truncated_lsb_bits(bp: int, mult: str) -> int:
    if mult == "bam":
        return max(2, min(bp - 2, round(0.55 * bp)))
    if mult == "tam1":
        return max(2, min(bp - 2, round(0.45 * bp)))
    if mult == "hocm":
        return max(2, min(bp - 2, round(0.50 * bp)))
    if mult in ("cgpm1", "cgpm3"):
        sub_blocks = 1 if mult == "cgpm1" else 3
        return max(2, round(bp / (2 * sub_blocks)))
    return max(2, round(bp / 3))


def _approx_scale_factor(mult: str, bp: int, metric: str) -> float:
    base = _APPROX_BASE[mult][metric]
    d = float(bp)
    lsb = _truncated_lsb_bits(bp, mult)
    accurate_bits = max(1, bp - lsb)

    if mult == "bam":
        # Broken-array: PP tree pruned horizontally and vertically.
        if metric == "latency":
            return base * (0.70 + 0.30 * accurate_bits / d)
        if metric == "energy":
            pruned = 1.0 - (lsb / d) ** 1.4
            return base * (0.60 + 0.40 * pruned)
        return base * (0.65 + 0.35 * (accurate_bits / d) ** 1.2)

    if mult == "tam1":
        # Truncation + MSB error compensation (TAM1-16 reference config).
        if metric == "latency":
            return base * (0.72 + 0.28 * math.log2(max(2, accurate_bits)) / math.log2(16))
        if metric == "energy":
            return base * (0.68 + 0.32 * (accurate_bits / d))
        return base * (0.70 + 0.30 * (accurate_bits / d))

    if mult == "hocm":
        # 1StepTrunc: approximate compressors in first accumulation stage.
        if metric == "latency":
            return base * (0.75 + 0.25 * math.log2(max(2, accurate_bits)) / math.log2(16))
        if metric == "energy":
            return base * (0.72 + 0.28 * (1.0 - lsb / (2 * d)))
        return base * (0.74 + 0.26 * (accurate_bits / d))

    if mult == "cgpm1":
        # One 8x8 CGP sub-multiplier block per segment.
        if metric == "latency":
            segments = max(1, math.ceil(d / 8))
            return base * (0.78 + 0.22 / segments)
        if metric == "energy":
            return base * (0.80 + 0.20 * (d / 32))
        return base * (0.76 + 0.24 * (d / 32))

    if mult == "cgpm3":
        # Three 8x8 CGP sub-blocks — higher accuracy, more hardware.
        if metric == "latency":
            segments = max(1, math.ceil(d / 8))
            return base * (0.82 + 0.18 / segments)
        if metric == "energy":
            return base * (0.85 + 0.15 * (d / 32))
        return base * (0.82 + 0.18 * (d / 32))

    raise KeyError(f"unknown approximate multiplier: {mult}")


def mitchell_latency_ps(bp: int) -> float:
    """Four Kogge-Stone adder-equivalent stages (mitchell_vs_daftpumlat.cc)."""
    return 4.0 * float(LAT_DAFTPUM_KOGGE_ADDER[bp])


def mitchell_energy_pj(bp: int, size: int) -> float:
    return 4.0 * 8.1075 * float(bp) * _ceil_simd(size) * AAP_ENERGY_PJ


def mitchell_area_ge(bp: int) -> float:
    return 4.0 * float(bp)


def _logarithmic_scale(mult: str, bp: int, metric: str) -> float:
    """
    ALM-SOA and ILM-AA relative to Mitchell baseline (Han et al. Table II).

    ALM-SOA: lowest PDP among logarithmic designs (very low delay/power).
    ILM-AA: improved accuracy at the cost of higher delay, still low power.
    """
    d = float(bp)
    if mult == "alm_soa":
        if metric == "latency":
            return 1.12 * (0.92 + 0.08 * math.log2(max(2, d)) / math.log2(16))
        if metric == "energy":
            return 1.18 * (0.90 + 0.10 * (d / 32))
        return 1.35 * (0.88 + 0.12 * (d / 32))

    if mult == "ilm_aa":
        if metric == "latency":
            return 3.25 * (0.85 + 0.15 * math.log2(max(2, d)) / math.log2(16))
        if metric == "energy":
            return 1.45 * (0.88 + 0.12 * (d / 32))
        return 2.10 * (0.82 + 0.18 * (d / 32))

    raise KeyError(f"unknown logarithmic multiplier: {mult}")


def logarithmic_multiplier_latency_ps(bp: int, mult: str) -> float:
    if mult == "mitchell":
        return mitchell_latency_ps(bp)
    return mitchell_latency_ps(bp) * _logarithmic_scale(mult, bp, "latency")


def logarithmic_multiplier_energy_pj(bp: int, mult: str, size: int) -> float:
    if mult == "mitchell":
        return mitchell_energy_pj(bp, size)
    return mitchell_energy_pj(bp, size) * _logarithmic_scale(mult, bp, "energy")


def logarithmic_multiplier_area_ge(bp: int, mult: str) -> float:
    if mult == "mitchell":
        return mitchell_area_ge(bp)
    return mitchell_area_ge(bp) * _logarithmic_scale(mult, bp, "area")


def exact_multiplier_energy_pj(bp: int, mult: str, size: int) -> float:
    d = float(bp)
    simd = _ceil_simd(size)

    if mult == "full":
        return (11 * d * d - 5 * d - 1) * simd * AAP_ENERGY_PJ
    if mult in ("sklansky", "carrysel"):
        return (
            4 * d
            + 0.0075 * d * (d - 1)
            + 0.0075 * 2 * 0.1 * d
            + d * (19.15 * 2 * d + math.log2(2 * d) - 19)
        ) * simd * AAP_ENERGY_PJ
    if mult == "rbr":
        return (18.0325 * d * d + 70.218 * d) * simd * AAP_ENERGY_PJ
    raise KeyError(f"unknown exact multiplier: {mult}")


def exact_multiplier_area_ge(bp: int, mult: str) -> float:
    """Gate-equivalent area proxy; Full multiplier normalized to bp^2 units."""
    full = d = float(bp) ** 2
    energy = exact_multiplier_energy_pj(bp, mult, SIMD_WIDTH)
    full_energy = exact_multiplier_energy_pj(bp, "full", SIMD_WIDTH)
    return full * (energy / full_energy)


def approximate_multiplier_latency_ps(bp: int, mult: str) -> float:
    ref = _best_exact_latency_ps(bp)
    scale = _approx_scale_factor(mult, bp, "latency")
    return ref * scale


def approximate_multiplier_energy_pj(bp: int, mult: str, size: int) -> float:
    full_energy = exact_multiplier_energy_pj(bp, "full", size)
    scale = _approx_scale_factor(mult, bp, "energy")
    return full_energy * scale


def approximate_multiplier_area_ge(bp: int, mult: str) -> float:
    full_area = float(bp) ** 2
    scale = _approx_scale_factor(mult, bp, "area")
    return full_area * scale


def get_multiplier_metrics(bp: int, mult: str, size: int = 1024) -> MultiplierMetrics:
    _validate_bp(bp)

    if mult in EXACT_LATENCY_TABLES:
        latency_ns = EXACT_LATENCY_TABLES[mult][bp] / 1000.0
        energy_nj = exact_multiplier_energy_pj(bp, mult, size) / 1000.0
        area_ge = exact_multiplier_area_ge(bp, mult)
    elif mult in _LOGARITHMIC_MULTS:
        latency_ns = logarithmic_multiplier_latency_ps(bp, mult) / 1000.0
        energy_nj = logarithmic_multiplier_energy_pj(bp, mult, size) / 1000.0
        area_ge = logarithmic_multiplier_area_ge(bp, mult)
    elif mult in _APPROX_BASE:
        latency_ns = approximate_multiplier_latency_ps(bp, mult) / 1000.0
        energy_nj = approximate_multiplier_energy_pj(bp, mult, size) / 1000.0
        area_ge = approximate_multiplier_area_ge(bp, mult)
    else:
        raise KeyError(f"unknown multiplier: {mult}")

    return MultiplierMetrics(bp, mult, latency_ns, energy_nj, area_ge)


def evaluate_all_multipliers(
    bit_precisions: Iterable[int],
    size: int = 1024,
    multipliers: Iterable[str] | None = None,
) -> Dict[str, Dict[str, List[float]]]:
    selected = list(multipliers) if multipliers else [m.key for m in ALL_MULTIPLIERS]
    result: Dict[str, Dict[str, List[float]]] = {
        "latency_ns": {k: [] for k in selected},
        "energy_nj": {k: [] for k in selected},
        "area_ge": {k: [] for k in selected},
    }

    for bp in bit_precisions:
        for mult in selected:
            m = get_multiplier_metrics(bp, mult, size)
            result["latency_ns"][mult].append(m.latency_ns)
            result["energy_nj"][mult].append(m.energy_nj)
            result["area_ge"][mult].append(m.area_ge)

    return result


def best_exact_multiplier(bp: int) -> str:
    _validate_bp(bp)
    lats = {k: EXACT_LATENCY_TABLES[k][bp] for k in EXACT_LATENCY_TABLES}
    return min(lats, key=lats.get)


def summary_table(
    bit_precisions: Iterable[int],
    size: int = 1024,
) -> List[Dict[str, float | str | int]]:
    rows: List[Dict[str, float | str | int]] = []
    for bp in bit_precisions:
        for spec in ALL_MULTIPLIERS:
            m = get_multiplier_metrics(bp, spec.key, size)
            rows.append({
                "bit_precision": bp,
                "multiplier": spec.key,
                "label": spec.label,
                "family": spec.family.value,
                "latency_ns": round(m.latency_ns, 4),
                "energy_nj": round(m.energy_nj, 6),
                "area_ge": round(m.area_ge, 3),
            })
    return rows
