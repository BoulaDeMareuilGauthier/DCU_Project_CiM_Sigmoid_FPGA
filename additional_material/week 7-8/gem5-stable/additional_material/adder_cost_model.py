#!/usr/bin/env python3
"""
Unified adder cost model for DAFTPUM-LAT exact adders and approximate adders.

Exact adder latency/energy data are ported from Proteus bbop_manager.c
(additional_material/test_cost_model.cc). Approximate adder models (LOA,
CCBA, TruA, GeAr, CSA) are calibrated against published synthesis results
(Han et al. survey, GLSVLSI'15, MDPI 2021, CCBA JETCAS 2018).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Tuple

AAP_ENERGY_PJ = 0.871
SIMD_WIDTH = 65536

# Latency lookup tables (ps) — index = bit precision
LAT_DAFTPUM_FULL_ADDER = [
    0, 676, 676, 915, 1154, 1393, 1632, 1871, 2110, 2349,
    2588, 2827, 3066, 3305, 3544, 3783, 4022, 4261, 4500, 4739,
    4978, 5217, 5456, 5695, 5934, 6173, 6412, 6651, 6890, 7129,
    7368, 7607, 7846, 8085, 8324, 8563, 8802, 9041, 9280, 9519,
    9758, 9997, 10236, 10475, 10714, 10953, 11192, 11431, 11670, 11909,
    12148, 12387, 12626, 12865, 13104, 13343, 13582, 13821, 14060, 14299,
    14538, 14777, 15016, 15255,
]

LAT_DAFTPUM_SKLANSKY_ADDER = [
    0, 1757, 1757, 2556, 2556, 3152, 3152, 3152, 3152, 3812,
    3812, 3812, 3812, 3812, 3812, 3812, 3812, 4600, 4600, 4600,
    4600, 4600, 4600, 4600, 4600, 4600, 4600, 4600, 4600, 4600,
    4600, 4600, 4600, 5644, 5644, 5644, 5644, 5644, 5644, 5644,
    5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644,
    5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644,
    5644, 5644, 5644, 5644,
]

LAT_DAFTPUM_KOGGE_ADDER = [
    0, 1663, 1663, 2227, 2227, 2823, 2823, 2823, 2823, 3483,
    3483, 3483, 3483, 3483, 3483, 3483, 3483, 4271, 4271, 4271,
    4271, 4271, 4271, 4271, 4271, 4271, 4271, 4271, 4271, 4271,
    4271, 4271, 4271, 5315, 5315, 5315, 5315, 5315, 5315, 5315,
    5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315,
    5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315,
    5315, 5315, 5315, 5315,
]

LAT_DAFTPUM_CARRYSEL_ADDER = [
    0, 676, 676, 915, 1154, 2398, 2398, 2398, 2398, 3046,
    3046, 3046, 3046, 3046, 3046, 3046, 3046, 4342, 4342, 4342,
    4342, 4342, 4342, 4342, 4342, 4342, 4342, 4342, 4342, 4342,
    4342, 4342, 4342, 6934, 6934, 6934, 6934, 6934, 6934, 6934,
    6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934,
    6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934,
    6934, 6934, 6934, 6934,
]

LAT_DAFTPUM_RBR_ADDER = [
    0, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194,
]


class AdderFamily(str, Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"


@dataclass(frozen=True)
class AdderSpec:
    key: str
    label: str
    family: AdderFamily
    description: str


EXACT_ADDERS: Tuple[AdderSpec, ...] = (
    AdderSpec("full", "Full (RCA)", AdderFamily.EXACT, "Ripple-carry / full adder"),
    AdderSpec("sklansky", "Sklansky", AdderFamily.EXACT, "Brent-Kung / Sklansky prefix"),
    AdderSpec("kogge", "Kogge-Stone", AdderFamily.EXACT, "Kogge-Stone prefix"),
    AdderSpec("carrysel", "Carry-Select", AdderFamily.EXACT, "Carry-select adder"),
    AdderSpec("rbr", "RBR", AdderFamily.EXACT, "Reversed-biased ripple adder"),
)

APPROX_ADDERS: Tuple[AdderSpec, ...] = (
    AdderSpec("loa", "LOA", AdderFamily.APPROXIMATE, "Lower-part-OR adder"),
    AdderSpec("ccba", "CCBA", AdderFamily.APPROXIMATE, "Carry cut-back adder"),
    AdderSpec("trua", "TruA", AdderFamily.APPROXIMATE, "Truncated adder"),
    AdderSpec("gear", "GeAr", AdderFamily.APPROXIMATE, "Generic accuracy-configurable adder"),
    AdderSpec("csa", "CSA", AdderFamily.APPROXIMATE, "Carry speculative adder"),
)

ALL_ADDERS: Tuple[AdderSpec, ...] = EXACT_ADDERS + APPROX_ADDERS

EXACT_LATENCY_TABLES: Dict[str, List[int]] = {
    "full": LAT_DAFTPUM_FULL_ADDER,
    "sklansky": LAT_DAFTPUM_SKLANSKY_ADDER,
    "kogge": LAT_DAFTPUM_KOGGE_ADDER,
    "carrysel": LAT_DAFTPUM_CARRYSEL_ADDER,
    "rbr": LAT_DAFTPUM_RBR_ADDER,
}

# 16-bit calibration ratios vs. accurate CLA from literature (delay, power, area).
# Values are interpolated smoothly with bit precision.
_APPROX_BASE = {
    "loa": {"latency": 0.49, "energy": 0.57, "area": 0.61},
    "ccba": {"latency": 0.52, "energy": 0.48, "area": 0.58},
    "trua": {"latency": 0.44, "energy": 0.50, "area": 0.52},
    "gear": {"latency": 0.58, "energy": 0.68, "area": 0.84},
    "csa": {"latency": 0.63, "energy": 0.62, "area": 0.72},
}


@dataclass
class AdderMetrics:
    bit_precision: int
    adder: str
    latency_ns: float
    energy_nj: float
    area_ge: float


def _validate_bp(bp: int) -> None:
    if bp < 1 or bp >= len(LAT_DAFTPUM_FULL_ADDER):
        raise ValueError(f"bit precision must be in [1, {len(LAT_DAFTPUM_FULL_ADDER) - 1}], got {bp}")


def _ceil_simd(size: int) -> float:
    return math.ceil(size / SIMD_WIDTH)


def _approx_lsb_bits(bp: int) -> int:
    """Approximate LSB count for LOA/TruA-style designs."""
    return max(3, min(bp - 1, round(bp / 3)))


def _approx_block_width(bp: int) -> int:
    """Block width k for segmented / speculative approximate adders."""
    if bp <= 8:
        return 4
    if bp <= 16:
        return 5
    if bp <= 32:
        return 6
    return max(4, round(math.sqrt(bp)))


def _approx_scale_factor(adder: str, bp: int, metric: str) -> float:
    """
    Scale literature-calibrated 16-bit ratios across bit precisions.

    Approximate adders save more at low precision (shorter carry chains) and
    converge toward exact cost at very high precision.
    """
    base = _APPROX_BASE[adder][metric]
    l = _approx_lsb_bits(bp)
    k = _approx_block_width(bp)
    accurate_bits = max(1, bp - l)

    if adder in ("loa", "trua"):
        # Critical path ~ O(log(accurate_bits)); approximate part is cheap.
        log_ratio = math.log2(max(2, accurate_bits)) / math.log2(16)
        if metric == "latency":
            return base * (0.75 + 0.25 * log_ratio)
        if metric == "energy":
            approx_share = l / bp
            return base * (0.55 + 0.45 * (1.0 - 0.35 * approx_share))
        return base * (0.70 + 0.30 * (accurate_bits / bp))

    if adder == "ccba":
        # CCBA cuts carry propagation; energy savings grow with precision.
        if metric == "latency":
            return base * (0.80 + 0.20 * math.log2(k) / math.log2(6))
        if metric == "energy":
            return base * (0.85 + 0.15 * (bp / 32))
        return base * (0.75 + 0.25 * (bp / 32))

    if adder == "gear":
        # GeAr trades redundant blocks for configurability -> higher area.
        blocks = max(2, math.ceil(bp / 8))
        if metric == "latency":
            return base * (0.78 + 0.22 * math.log2(k) / math.log2(6))
        if metric == "energy":
            return base * (0.80 + 0.20 * blocks / 4)
        return base * (0.70 + 0.30 * blocks / 4)

    if adder == "csa":
        # CSA targets high accuracy; savings are moderate.
        if metric == "latency":
            return base * (0.82 + 0.18 * math.log2(2 * k) / math.log2(12))
        if metric == "energy":
            return base * (0.88 + 0.12 * (k / 6))
        return base * (0.78 + 0.22 * (k / 6))

    raise KeyError(f"unknown approximate adder: {adder}")


def exact_adder_energy_pj(bp: int, adder: str, size: int) -> float:
    d = float(bp)
    simd = _ceil_simd(size)

    if adder == "full":
        return 8.1075 * d * simd * AAP_ENERGY_PJ
    if adder == "sklansky":
        return (19.5 * d - 10.8 * math.log2(d) - 0.125) * AAP_ENERGY_PJ * simd
    if adder == "kogge":
        return (
            0.025 * d ** 3 + 0.1 * d ** 2
            + 5.5 * math.log2(d) * math.log(d)
            - 5.5 * math.log(d) + 18.875 * d - 19
        ) * AAP_ENERGY_PJ * simd
    if adder == "carrysel":
        return 22.1465 * d * simd * AAP_ENERGY_PJ
    if adder == "rbr":
        return 35.075 * d * simd * AAP_ENERGY_PJ
    raise KeyError(f"unknown exact adder: {adder}")


def exact_adder_area_ge(bp: int, adder: str) -> float:
    """Gate-equivalent area proxy normalized to Full adder (= bp units)."""
    full = float(bp)
    energy = exact_adder_energy_pj(bp, adder, SIMD_WIDTH)
    full_energy = exact_adder_energy_pj(bp, "full", SIMD_WIDTH)
    # Energy coefficients correlate with switching capacitance / area.
    return full * (energy / full_energy)


def approximate_adder_latency_ps(bp: int, adder: str) -> float:
    full_lat = float(LAT_DAFTPUM_FULL_ADDER[bp])
    scale = _approx_scale_factor(adder, bp, "latency")
    return full_lat * scale


def approximate_adder_energy_pj(bp: int, adder: str, size: int) -> float:
    full_energy = exact_adder_energy_pj(bp, "full", size)
    scale = _approx_scale_factor(adder, bp, "energy")
    return full_energy * scale


def approximate_adder_area_ge(bp: int, adder: str) -> float:
    full_area = float(bp)
    scale = _approx_scale_factor(adder, bp, "area")
    return full_area * scale


def get_adder_metrics(bp: int, adder: str, size: int = 1024) -> AdderMetrics:
    _validate_bp(bp)

    if adder in EXACT_LATENCY_TABLES:
        latency_ns = EXACT_LATENCY_TABLES[adder][bp] / 1000.0
        energy_nj = exact_adder_energy_pj(bp, adder, size) / 1000.0
        area_ge = exact_adder_area_ge(bp, adder)
    elif adder in _APPROX_BASE:
        latency_ns = approximate_adder_latency_ps(bp, adder) / 1000.0
        energy_nj = approximate_adder_energy_pj(bp, adder, size) / 1000.0
        area_ge = approximate_adder_area_ge(bp, adder)
    else:
        raise KeyError(f"unknown adder: {adder}")

    return AdderMetrics(bp, adder, latency_ns, energy_nj, area_ge)


def evaluate_all_adders(
    bit_precisions: Iterable[int],
    size: int = 1024,
    adders: Iterable[str] | None = None,
) -> Dict[str, Dict[str, List[float]]]:
    selected = list(adders) if adders else [a.key for a in ALL_ADDERS]
    result: Dict[str, Dict[str, List[float]]] = {
        "latency_ns": {k: [] for k in selected},
        "energy_nj": {k: [] for k in selected},
        "area_ge": {k: [] for k in selected},
    }

    for bp in bit_precisions:
        for adder in selected:
            m = get_adder_metrics(bp, adder, size)
            result["latency_ns"][adder].append(m.latency_ns)
            result["energy_nj"][adder].append(m.energy_nj)
            result["area_ge"][adder].append(m.area_ge)

    return result


def best_exact_adder(bp: int) -> str:
    """Return the latency-optimal exact adder at a given precision."""
    _validate_bp(bp)
    lats = {k: EXACT_LATENCY_TABLES[k][bp] for k in EXACT_LATENCY_TABLES}
    return min(lats, key=lats.get)


def summary_table(
    bit_precisions: Iterable[int],
    size: int = 1024,
) -> List[Dict[str, float | str | int]]:
    rows: List[Dict[str, float | str | int]] = []
    for bp in bit_precisions:
        for spec in ALL_ADDERS:
            m = get_adder_metrics(bp, spec.key, size)
            rows.append({
                "bit_precision": bp,
                "adder": spec.key,
                "label": spec.label,
                "family": spec.family.value,
                "latency_ns": round(m.latency_ns, 4),
                "energy_nj": round(m.energy_nj, 6),
                "area_ge": round(m.area_ge, 3),
            })
    return rows
