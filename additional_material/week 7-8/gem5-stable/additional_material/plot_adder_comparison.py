#!/usr/bin/env python3
"""
Compare exact DAFTPUM-LAT adders with approximate adders (LOA, CCBA, TruA,
GeAr, CSA) across bit precision.

Generates latency, energy, and area (space) vs. precision plots.

Usage:
    python plot_adder_comparison.py
    python plot_adder_comparison.py --size 65536 --bp-min 4 --bp-max 32
    python plot_adder_comparison.py --output adder_comparison.png
    python plot_adder_comparison.py --csv adder_metrics.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

from adder_cost_model import (
    ALL_ADDERS,
    APPROX_ADDERS,
    EXACT_ADDERS,
    AdderFamily,
    evaluate_all_adders,
    summary_table,
)


EXACT_COLORS = {
    "full": "#1f77b4",
    "sklansky": "#ff7f0e",
    "kogge": "#2ca02c",
    "carrysel": "#9467bd",
    "rbr": "#8c564b",
}

APPROX_COLORS = {
    "loa": "#e41a1c",
    "ccba": "#377eb8",
    "trua": "#984ea3",
    "gear": "#4daf4a",
    "csa": "#ff7f00",
}

EXACT_MARKERS = {
    "full": "o",
    "sklansky": "s",
    "kogge": "^",
    "carrysel": "D",
    "rbr": "v",
}

APPROX_MARKERS = {
    "loa": "o",
    "ccba": "s",
    "trua": "^",
    "gear": "D",
    "csa": "v",
}


def _label_map() -> dict[str, str]:
    return {spec.key: spec.label for spec in ALL_ADDERS}


def plot_comparison(
    bit_precisions: list[int],
    metrics: dict,
    output_path: str,
    size: int,
) -> None:
    labels = _label_map()
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    panels = [
        ("latency_ns", "Latency (ns)", False),
        ("energy_nj", f"Energy (nJ, size={size})", True),
        ("area_ge", "Area (gate-equivalent units)", False),
    ]

    for ax, (metric_key, ylabel, use_log) in zip(axes, panels):
        for spec in EXACT_ADDERS:
            key = spec.key
            ax.plot(
                bit_precisions,
                metrics[metric_key][key],
                label=labels[key],
                color=EXACT_COLORS[key],
                marker=EXACT_MARKERS[key],
                linewidth=2.0,
                markersize=5,
                linestyle="-",
            )

        for spec in APPROX_ADDERS:
            key = spec.key
            ax.plot(
                bit_precisions,
                metrics[metric_key][key],
                label=labels[key],
                color=APPROX_COLORS[key],
                marker=APPROX_MARKERS[key],
                linewidth=2.2,
                markersize=5,
                linestyle="--",
            )

        ax.set_xlabel("Bit precision (bits)", fontsize=12)
        ax.set_ylabel(ylabel, fontsize=12)
        ax.set_title(ylabel.split(" (")[0], fontsize=13, fontweight="bold", pad=10)
        ax.grid(True, linestyle="--", alpha=0.45)
        if use_log:
            ax.set_yscale("log")
        ax.set_xticks([bp for bp in bit_precisions if bp % 4 == 0 or bp == bit_precisions[0]])

    handles, legend_labels = axes[0].get_legend_handles_labels()
    style_handles = [
        plt.Line2D([0], [0], color="gray", linestyle="-", linewidth=2, label="Exact (solid)"),
        plt.Line2D([0], [0], color="gray", linestyle="--", linewidth=2, label="Approximate (dashed)"),
    ]
    fig.legend(
        handles + style_handles,
        legend_labels + ["Exact (solid)", "Approximate (dashed)"],
        loc="upper center",
        ncol=6,
        fontsize=8,
        frameon=True,
        bbox_to_anchor=(0.5, 1.06),
    )

    fig.suptitle(
        "Exact vs. Approximate Adders — DAFTPUM-LAT Cost Model",
        fontsize=15,
        fontweight="bold",
        y=1.12,
    )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    print(f"Saved plot to {output_path}")
    plt.close()


def write_csv(rows: list[dict], path: str) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved CSV to {path}")


def print_snapshot(bit_precisions: list[int], size: int) -> None:
    sample_bps = [bp for bp in (8, 16, 32) if bp in bit_precisions]
    print("\nSample comparison (latency ns / energy nJ / area GE):")
    print("-" * 78)
    for bp in sample_bps:
        print(f"\n  {bp}-bit:")
        for spec in ALL_ADDERS:
            from adder_cost_model import get_adder_metrics
            m = get_adder_metrics(bp, spec.key, size)
            family = "exact" if spec.family == AdderFamily.EXACT else "approx"
            print(
                f"    {spec.label:14s} [{family:6s}]  "
                f"lat={m.latency_ns:7.3f} ns  "
                f"E={m.energy_nj:8.5f} nJ  "
                f"area={m.area_ge:6.2f} GE"
            )


def parse_args() -> argparse.Namespace:
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Plot exact vs approximate adder cost metrics vs bit precision.",
    )
    parser.add_argument("--size", type=int, default=1024, help="Workload size (elements)")
    parser.add_argument("--bp-min", type=int, default=1, help="Minimum bit precision")
    parser.add_argument("--bp-max", type=int, default=32, help="Maximum bit precision")
    parser.add_argument(
        "--output",
        default=os.path.join(here, "adder_comparison.png"),
        help="Output PNG path",
    )
    parser.add_argument("--csv", default="", help="Optional CSV export path")
    parser.add_argument("--no-plot", action="store_true", help="Skip plot generation")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.bp_min < 1 or args.bp_max < args.bp_min or args.bp_max > 63:
        print("Error: invalid bit precision range", file=sys.stderr)
        return 1

    bit_precisions = list(range(args.bp_min, args.bp_max + 1))
    metrics = evaluate_all_adders(bit_precisions, size=args.size)

    print_snapshot(bit_precisions, args.size)

    rows = summary_table(bit_precisions, size=args.size)
    if args.csv:
        write_csv(rows, args.csv)

    if not args.no_plot:
        plot_comparison(bit_precisions, metrics, args.output, args.size)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
