#!/usr/bin/env python3
"""
Compare exact DAFTPUM-LAT dividers with approximate dividers (AAXD, INZeD,
AXDr1, AXDr3, SEERAD-4, DAXD, SC, RAPID, 3D-FPCA) across bit precision.

Generates four panels:
  1. Latency (ns) vs bit precision
  2. Energy (nJ) vs bit precision  [log scale]
  3. Gate-equivalent area vs bit precision
  4. Error scatter: NED vs MRED% @ 16-bit (bubble size = ED_max)

Usage:
    python plot_division_comparison.py
    python plot_division_comparison.py --bp-min 4 --bp-max 32
    python plot_division_comparison.py --output division_comparison.png
    python plot_division_comparison.py --csv division_metrics.csv --no-plot
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines

from divider_cost_model import (
    ALL_DIVIDERS,
    APPROX_DIVIDERS,
    EXACT_DIVIDERS,
    DividerFamily,
    evaluate_all_dividers,
    get_divider_metrics,
    summary_table,
)

# ------------------------------------------------------------------
# Style maps
# ------------------------------------------------------------------
EXACT_COLORS = {
    "exact_array": "#1f77b4",
    "exact_log":   "#ff7f0e",
}
EXACT_MARKERS = {
    "exact_array": "o",
    "exact_log":   "s",
}

APPROX_COLORS = {
    "aaxd":    "#e41a1c",
    "inzed":   "#984ea3",
    "axdr1":   "#4daf4a",
    "axdr3":   "#377eb8",
    "seerad4": "#ff7f00",
    "daxd":    "#a65628",
    "sc":      "#999999",
    "rapid":   "#f781bf",
    "fpca3d":  "#17becf",
}
APPROX_MARKERS = {
    "aaxd":    "D",
    "inzed":   "^",
    "axdr1":   "v",
    "axdr3":   "P",
    "seerad4": "X",
    "daxd":    "*",
    "sc":      "H",
    "rapid":   "p",
    "fpca3d":  "8",
}


def _labels() -> dict[str, str]:
    return {s.key: s.label for s in ALL_DIVIDERS}


# Dividers excluded from latency/area panels because their scaling is
# incompatible with the linear y-axis (e.g. SC Divider: 2^bp clock cycles).
_SKIP_LATENCY_AREA = frozenset({"sc"})


def plot_comparison(
    bit_precisions: list[int],
    metrics: dict,
    output_path: str,
    size: int,
) -> None:
    labels = _labels()
    fig, axes = plt.subplots(2, 2, figsize=(22, 14))
    axes = axes.flatten()

    # ---- panel 0: Latency ----
    ax = axes[0]
    for spec in EXACT_DIVIDERS:
        k = spec.key
        ax.plot(bit_precisions, metrics["latency_ns"][k],
                label=labels[k],
                color=EXACT_COLORS[k], marker=EXACT_MARKERS[k],
                linewidth=2.2, markersize=5, linestyle="-")
    for spec in APPROX_DIVIDERS:
        k = spec.key
        if k in _SKIP_LATENCY_AREA:
            continue
        ax.plot(bit_precisions, metrics["latency_ns"][k],
                label=labels[k],
                color=APPROX_COLORS[k], marker=APPROX_MARKERS[k],
                linewidth=1.8, markersize=5, linestyle="--")
    ax.set_xlabel("Bit precision (bits)", fontsize=12)
    ax.set_ylabel("Latency (ns)", fontsize=12)
    ax.set_title("Latency vs Bit Precision", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xticks([bp for bp in bit_precisions if bp % 4 == 0 or bp == bit_precisions[0]])

    # ---- panel 1: Energy (log) — SC included, log-scale handles range ----
    ax = axes[1]
    for spec in EXACT_DIVIDERS:
        k = spec.key
        ax.plot(bit_precisions, metrics["energy_nj"][k],
                label=labels[k],
                color=EXACT_COLORS[k], marker=EXACT_MARKERS[k],
                linewidth=2.2, markersize=5, linestyle="-")
    for spec in APPROX_DIVIDERS:
        k = spec.key
        ax.plot(bit_precisions, metrics["energy_nj"][k],
                label=labels[k],
                color=APPROX_COLORS[k], marker=APPROX_MARKERS[k],
                linewidth=1.8, markersize=5, linestyle="--")
    ax.set_yscale("log")
    ax.set_xlabel("Bit precision (bits)", fontsize=12)
    ax.set_ylabel(f"Energy (nJ, size={size:,})", fontsize=12)
    ax.set_title("Energy vs Bit Precision (log scale)", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xticks([bp for bp in bit_precisions if bp % 4 == 0 or bp == bit_precisions[0]])

    # ---- panel 2: Area ----
    ax = axes[2]
    for spec in EXACT_DIVIDERS:
        k = spec.key
        ax.plot(bit_precisions, metrics["area_ge"][k],
                label=labels[k],
                color=EXACT_COLORS[k], marker=EXACT_MARKERS[k],
                linewidth=2.2, markersize=5, linestyle="-")
    for spec in APPROX_DIVIDERS:
        k = spec.key
        if k in _SKIP_LATENCY_AREA:
            continue
        ax.plot(bit_precisions, metrics["area_ge"][k],
                label=labels[k],
                color=APPROX_COLORS[k], marker=APPROX_MARKERS[k],
                linewidth=1.8, markersize=5, linestyle="--")
    ax.set_xlabel("Bit precision (bits)", fontsize=12)
    ax.set_ylabel("Area (gate-equivalent units)", fontsize=12)
    ax.set_title("Area vs Bit Precision", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xticks([bp for bp in bit_precisions if bp % 4 == 0 or bp == bit_precisions[0]])

    # ---- panel 3: Error scatter @ 16-bit (NED vs MRED%, bubble=ED_max) ----
    ax = axes[3]
    bp16 = 16 if 16 in bit_precisions else bit_precisions[len(bit_precisions) // 2]
    for spec in APPROX_DIVIDERS:
        m = get_divider_metrics(bp16, spec.key)
        if m.ned == 0.0 and m.mred_pct == 0.0:
            continue
        sz = max(30, min(m.ed_max, 800))
        ax.scatter(m.ned, m.mred_pct, s=sz,
                   color=APPROX_COLORS[spec.key],
                   marker=APPROX_MARKERS[spec.key],
                   edgecolors="black", linewidths=0.6, alpha=0.88,
                   label=f"{spec.label}  (ED_max={m.ed_max})", zorder=5)
        ax.annotate(spec.label, (m.ned, m.mred_pct),
                    fontsize=7.5, ha="left", va="bottom",
                    xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("NED (Normalized Error Distance)", fontsize=12)
    ax.set_ylabel("MRED (%)", fontsize=12)
    ax.set_title(f"Error Metrics @ {bp16}-bit  (bubble ∝ ED_max)", fontsize=13, fontweight="bold")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.text(0.01, 0.99,
            "Note: SC Divider excluded from Latency/Area panels\n(2ⁿ clock cycles → impractical at n>16)",
            transform=ax.transAxes, fontsize=6.5, va="top", ha="left",
            color="gray", style="italic")

    # ---- shared legend ----
    solid_line  = mlines.Line2D([], [], color="dimgray", linestyle="-",  linewidth=2, label="Exact (solid)")
    dashed_line = mlines.Line2D([], [], color="dimgray", linestyle="--", linewidth=2, label="Approx (dashed)")
    handles, leg_labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles + [solid_line, dashed_line],
        leg_labels + ["Exact (solid)", "Approx (dashed)"],
        loc="upper center",
        ncol=6,
        fontsize=7.5,
        frameon=True,
        bbox_to_anchor=(0.5, 1.04),
    )

    fig.suptitle(
        "Exact vs. Approximate Dividers — DAFTPUM-LAT Cost Model\n"
        "AAXD · INZeD · AXDr1 · AXDr3 · SEERAD-4 · DAXD · SC · RAPID · 3D-FPCA",
        fontsize=14,
        fontweight="bold",
        y=1.10,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved plot to {output_path}")
    plt.close()


def write_csv(rows: list[dict], path: str) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved CSV to {path}")


def print_snapshot(bit_precisions: list[int], size: int) -> None:
    sample_bps = [bp for bp in (8, 16, 32) if bp in bit_precisions]
    print("\nSample divider comparison (latency ns / energy nJ / area GE / NED / MRED%):")
    print("-" * 100)
    for bp in sample_bps:
        print(f"\n  {bp}-bit:")
        for spec in ALL_DIVIDERS:
            m = get_divider_metrics(bp, spec.key, size)
            fam = "exact" if spec.family == DividerFamily.EXACT else "approx"
            err = f"NED={m.ned:.2f}  MRED={m.mred_pct:.2f}%" if fam == "approx" else "exact"
            print(
                f"    {spec.label:16s} [{fam:6s}]  "
                f"lat={m.latency_ns:9.3f} ns  "
                f"E={m.energy_nj:12.5f} nJ  "
                f"area={m.area_ge:9.1f} GE  "
                f"{err}"
            )


def parse_args() -> argparse.Namespace:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Plot exact vs approximate divider cost metrics vs bit precision.",
    )
    parser.add_argument("--size",   type=int, default=1024,
                        help="Workload size (elements)")
    parser.add_argument("--bp-min", type=int, default=2,
                        help="Minimum bit precision")
    parser.add_argument("--bp-max", type=int, default=32,
                        help="Maximum bit precision")
    parser.add_argument(
        "--output",
        default=os.path.join(here, "division_comparison.png"),
        help="Output PNG path",
    )
    parser.add_argument("--csv",     default="", help="Optional CSV export path")
    parser.add_argument("--no-plot", action="store_true", help="Skip plot generation")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bp_min < 1 or args.bp_max < args.bp_min or args.bp_max > 63:
        print("Error: invalid bit precision range", file=sys.stderr)
        return 1

    bit_precisions = list(range(args.bp_min, args.bp_max + 1))
    metrics = evaluate_all_dividers(bit_precisions, size=args.size)

    print_snapshot(bit_precisions, args.size)

    rows = summary_table(bit_precisions, size=args.size)
    if args.csv:
        write_csv(rows, args.csv)

    if not args.no_plot:
        plot_comparison(bit_precisions, metrics, args.output, args.size)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
