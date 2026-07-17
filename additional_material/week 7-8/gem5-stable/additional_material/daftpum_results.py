#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DAFTPUM-LAT gem5 Output Parser and Display

Parses gem5 simulation output (stats.txt, stderr) and displays
DAFTPUM-LAT controller statistics including:
  - BBOP execution counts and types
  - Dynamic bit-precision distribution
  - Circuit selection statistics
  - Latency and energy breakdowns
  - Subarray utilization
  - Comparison across mechanism configurations

Usage:
  python daftpum_results.py stats.txt
  python daftpum_results.py stats.txt --plot
  python daftpum_results.py stats.txt --json output.json
  python daftpum_results.py --compare stats1.txt stats2.txt stats3.txt
"""

import re
import sys
import json
import argparse
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Data structures
# ============================================================================

@dataclass
class AdderStats:
    full: int = 0
    sklansky: int = 0
    kogge_stone: int = 0
    carry_select: int = 0
    rbr: int = 0

    def total(self) -> int:
        return self.full + self.sklansky + self.kogge_stone + \
               self.carry_select + self.rbr

    def as_dict(self) -> dict:
        return {
            "full": self.full,
            "sklansky": self.sklansky,
            "kogge_stone": self.kogge_stone,
            "carry_select": self.carry_select,
            "rbr": self.rbr,
            "total": self.total(),
        }


@dataclass
class MultiplierStats:
    full: int = 0
    sklansky: int = 0
    carry_select: int = 0
    rbr: int = 0

    def total(self) -> int:
        return self.full + self.sklansky + self.carry_select + self.rbr

    def as_dict(self) -> dict:
        return {
            "full": self.full,
            "sklansky": self.sklansky,
            "carry_select": self.carry_select,
            "rbr": self.rbr,
            "total": self.total(),
        }


@dataclass
class DaftpumStats:
    total_bbops: int = 0
    total_latency_ns: float = 0.0
    total_energy_nj: float = 0.0
    avg_parallelism: float = 0.0
    bit_precision_dist: Dict[int, int] = field(default_factory=dict)
    adder_selection: AdderStats = field(default_factory=AdderStats)
    multiplier_selection: MultiplierStats = field(default_factory=MultiplierStats)

    def as_dict(self) -> dict:
        return {
            "total_bbops": self.total_bbops,
            "total_latency_ns": self.total_latency_ns,
            "total_energy_nj": self.total_energy_nj,
            "avg_parallelism": self.avg_parallelism,
            "bit_precision_dist": self.bit_precision_dist,
            "adder_selection": self.adder_selection.as_dict(),
            "multiplier_selection": self.multiplier_selection.as_dict(),
        }


# ============================================================================
# Parser
# ============================================================================

class Gem5StatsParser:
    """Parse gem5 stats.txt and extract DAFTPUM-LAT statistics."""

    # Pattern for DAFTPUM-LAT stats in gem5 stats.txt
    STAT_PATTERNS = {
        "total_bbops": r"daftpum_lat\.total_bbops\s+(\d+)",
        "total_latency_ns": r"daftpum_lat\.total_latency_ns\s+([\d.]+)",
        "total_energy_nj": r"daftpum_lat\.total_energy_nj\s+([\d.]+)",
        "avg_parallelism": r"daftpum_lat\.avg_parallelism\s+([\d.]+)",
    }

    DIST_PATTERN = re.compile(
        r"daftpum_lat\.bit_precision_distribution\.bucket_(\d+)\s+(\d+)"
    )

    ADDER_PATTERNS = {
        "full": r"daftpum_lat\.adder_selection\.bucket_0\s+(\d+)",
        "sklansky": r"daftpum_lat\.adder_selection\.bucket_1\s+(\d+)",
        "kogge_stone": r"daftpum_lat\.adder_selection\.bucket_2\s+(\d+)",
        "carry_select": r"daftpum_lat\.adder_selection\.bucket_3\s+(\d+)",
        "rbr": r"daftpum_lat\.adder_selection\.bucket_4\s+(\d+)",
    }

    MULT_PATTERNS = {
        "full": r"daftpum_lat\.multiplier_selection\.bucket_0\s+(\d+)",
        "sklansky": r"daftpum_lat\.multiplier_selection\.bucket_1\s+(\d+)",
        "carry_select": r"daftpum_lat\.multiplier_selection\.bucket_2\s+(\d+)",
        "rbr": r"daftpum_lat\.multiplier_selection\.bucket_3\s+(\d+)",
    }

    def __init__(self):
        self.stats = DaftpumStats()

    def parse_file(self, filepath: str) -> DaftpumStats:
        """Parse a gem5 stats.txt file."""
        with open(filepath, "r") as f:
            content = f.read()
        return self.parse_content(content)

    def parse_content(self, content: str) -> DaftpumStats:
        """Parse stats content string."""
        self.stats = DaftpumStats()

        # Scalar stats
        for key, pattern in self.STAT_PATTERNS.items():
            m = re.search(pattern, content)
            if m:
                val = m.group(1)
                if "." in val:
                    setattr(self.stats, key, float(val))
                else:
                    setattr(self.stats, key, int(val))

        # Bit-precision distribution
        for m in self.DIST_PATTERN.finditer(content):
            bp = int(m.group(1))
            count = int(m.group(2))
            self.stats.bit_precision_dist[bp] = count

        # Adder selection
        for key, pattern in self.ADDER_PATTERNS.items():
            m = re.search(pattern, content)
            if m:
                setattr(self.stats.adder_selection, key, int(m.group(1)))

        # Multiplier selection
        for key, pattern in self.MULT_PATTERNS.items():
            m = re.search(pattern, content)
            if m:
                setattr(self.stats.multiplier_selection, key, int(m.group(1)))

        return self.stats

    def parse_stderr(self, filepath: str) -> DaftpumStats:
        """Parse DAFTPUM-LAT debug output from gem5 stderr."""
        self.stats = DaftpumStats()

        bbop_pattern = re.compile(
            r"bbop_(\d+) completed: (\w+), dynamicBP=(\d+), "
            r"latency=([\d.]+) ns, energy=([\d.]+) nJ"
        )
        parallel_pattern = re.compile(
            r"subarrays=(\d+), repFactor=(\d+)"
        )

        with open(filepath, "r") as f:
            for line in f:
                m = bbop_pattern.search(line)
                if m:
                    self.stats.total_bbops += 1
                    self.stats.total_latency_ns += float(m.group(4))
                    self.stats.total_energy_nj += float(m.group(5))
                    bp = int(m.group(3))
                    self.stats.bit_precision_dist[bp] = \
                        self.stats.bit_precision_dist.get(bp, 0) + 1

                m = parallel_pattern.search(line)
                if m:
                    subs = int(m.group(1))
                    self.stats.avg_parallelism = (
                        (self.stats.avg_parallelism * (self.stats.total_bbops - 1)
                         + subs) / self.stats.total_bbops
                        if self.stats.total_bbops > 0 else subs
                    )

        return self.stats


# ============================================================================
# Display
# ============================================================================

class StatsDisplay:
    """Display DAFTPUM-LAT statistics in formatted output."""

    HEADER_WIDTH = 70
    SEPARATOR = "=" * HEADER_WIDTH

    def __init__(self, stats: DaftpumStats, source_file: str = ""):
        self.stats = stats
        self.source = source_file

    def print_all(self):
        """Print all statistics."""
        self._print_header()
        self._print_summary()
        self._print_bit_precision_distribution()
        self._print_circuit_selection()
        self._print_energy_breakdown()
        self._print_footer()

    def _print_header(self):
        print(self.SEPARATOR)
        print("  DAFTPUM-LAT Controller Results")
        if self.source:
            print(f"  Source: {self.source}")
        print(self.SEPARATOR)
        print()

    def _print_footer(self):
        print()
        print(self.SEPARATOR)

    def _print_summary(self):
        s = self.stats
        print("  EXECUTION SUMMARY")
        print("  " + "-" * 40)
        print(f"  Total BBOPs executed:    {s.total_bbops:>12}")
        print(f"  Total latency:           {s.total_latency_ns:>12.2f} ns")
        print(f"  Total energy:            {s.total_energy_nj:>12.3f} nJ")
        print(f"  Average parallelism:     {s.avg_parallelism:>12.1f} subarrays")
        if s.total_bbops > 0:
            avg_lat = s.total_latency_ns / s.total_bbops
            avg_nj = s.total_energy_nj / s.total_bbops
            print(f"  Avg latency/bbop:        {avg_lat:>12.2f} ns")
            print(f"  Avg energy/bbop:         {avg_nj:>12.3f} nJ")
        print()

    def _print_bit_precision_distribution(self):
        dist = self.stats.bit_precision_dist
        if not dist:
            print("  BIT PRECISION DISTRIBUTION: (no data)")
            print()
            return

        print("  BIT PRECISION DISTRIBUTION")
        print("  " + "-" * 40)

        total = sum(dist.values())
        max_count = max(dist.values()) if dist else 1

        # Sort by bit precision
        sorted_bps = sorted(dist.keys())

        # Find bar width
        bar_max = 30

        for bp in sorted_bps:
            count = dist[bp]
            pct = (count / total * 100) if total > 0 else 0
            bar_len = int((count / max_count) * bar_max) if max_count > 0 else 0
            bar = "#" * bar_len
            print(f"  {bp:>2}-bit: {count:>6} ({pct:>5.1f}%) {bar}")

        print(f"  {'Total':>6}: {total:>6}")
        print()

    def _print_circuit_selection(self):
        adders = self.stats.adder_selection
        mults = self.stats.multiplier_selection

        print("  CIRCUIT SELECTION")
        print("  " + "-" * 40)

        # Adders
        adder_total = adders.total()
        if adder_total > 0:
            print(f"  Adders ({adder_total} total):")
            circuits = [
                ("Full", adders.full),
                ("Sklansky", adders.sklansky),
                ("Kogge-Stone", adders.kogge_stone),
                ("Carry-Select", adders.carry_select),
                ("RBR", adders.rbr),
            ]
            for name, count in circuits:
                if count > 0:
                    pct = count / adder_total * 100
                    bar_len = int(pct / 100 * 30)
                    bar = "#" * bar_len
                    print(f"    {name:<14}: {count:>6} ({pct:>5.1f}%) {bar}")
        else:
            print("  Adders: (none recorded)")

        print()

        # Multipliers
        mult_total = mults.total()
        if mult_total > 0:
            print(f"  Multipliers ({mult_total} total):")
            circuits = [
                ("Full", mults.full),
                ("Sklansky", mults.sklansky),
                ("Carry-Select", mults.carry_select),
                ("RBR", mults.rbr),
            ]
            for name, count in circuits:
                if count > 0:
                    pct = count / mult_total * 100
                    bar_len = int(pct / 100 * 30)
                    bar = "#" * bar_len
                    print(f"    {name:<14}: {count:>6} ({pct:>5.1f}%) {bar}")
        else:
            print("  Multipliers: (none recorded)")

        print()

    def _print_energy_breakdown(self):
        s = self.stats
        if s.total_bbops == 0:
            return

        print("  ENERGY BREAKDOWN")
        print("  " + "-" * 40)

        # Estimate energy per operation type
        avg_energy = s.total_energy_nj / s.total_bbops
        avg_latency = s.total_latency_ns / s.total_bbops

        print(f"  Average energy per BBOP:  {avg_energy:.3f} nJ")
        print(f"  Average latency per BBOP: {avg_latency:.2f} ns")
        print(f"  Energy-delay product:     {avg_energy * avg_latency:.3f} nJ*ns")

        # Throughput
        if s.total_latency_ns > 0:
            throughput = s.total_bbops / (s.total_latency_ns / 1e9)
            print(f"  Throughput:               {throughput:.0f} BBOPs/sec")

        print()


# ============================================================================
# Comparison
# ============================================================================

class StatsComparator:
    """Compare DAFTPUM-LAT statistics across multiple runs."""

    def __init__(self, labels: List[str], stats_list: List[DaftpumStats]):
        assert len(labels) == len(stats_list)
        self.labels = labels
        self.stats_list = stats_list

    def print_comparison(self):
        """Print a side-by-side comparison table."""
        n = len(self.labels)
        col_width = max(16, max(len(l) for l in self.labels) + 2)

        print("=" * (col_width * (n + 1) + 10))
        print("  DAFTPUM-LAT Comparison")
        print("=" * (col_width * (n + 1) + 10))

        # Header
        header = f"  {'Metric':<24}"
        for label in self.labels:
            header += f"{label:>{col_width}}"
        print(header)
        print("  " + "-" * (col_width * n + 24))

        # Rows
        rows = [
            ("Total BBOPs", "total_bbops", "d"),
            ("Total latency (ns)", "total_latency_ns", ".2f"),
            ("Total energy (nJ)", "total_energy_nj", ".3f"),
            ("Avg parallelism", "avg_parallelism", ".1f"),
        ]

        for name, attr, fmt in rows:
            row = f"  {name:<24}"
            for s in self.stats_list:
                val = getattr(s, attr)
                row += f"{val:>{col_width}{fmt}}"
            print(row)

        # Avg per-bbop
        row = f"  {'Avg latency/bbop (ns)':<24}"
        for s in self.stats_list:
            val = s.total_latency_ns / s.total_bbops if s.total_bbops > 0 else 0
            row += f"{val:>{col_width}.2f}"
        print(row)

        row = f"  {'Avg energy/bbop (nJ)':<24}"
        for s in self.stats_list:
            val = s.total_energy_nj / s.total_bbops if s.total_bbops > 0 else 0
            row += f"{val:>{col_width}.3f}"
        print(row)

        print()

        # Circuit selection comparison
        print("  CIRCUIT SELECTION")
        print("  " + "-" * (col_width * n + 24))

        circuit_rows = [
            ("Adder: Full", lambda s: s.adder_selection.full),
            ("Adder: Sklansky", lambda s: s.adder_selection.sklansky),
            ("Adder: Kogge-Stone", lambda s: s.adder_selection.kogge_stone),
            ("Adder: Carry-Select", lambda s: s.adder_selection.carry_select),
            ("Adder: RBR", lambda s: s.adder_selection.rbr),
            ("Mult: Full", lambda s: s.multiplier_selection.full),
            ("Mult: Sklansky", lambda s: s.multiplier_selection.sklansky),
            ("Mult: Carry-Select", lambda s: s.multiplier_selection.carry_select),
            ("Mult: RBR", lambda s: s.multiplier_selection.rbr),
        ]

        for name, getter in circuit_rows:
            row = f"  {name:<24}"
            for s in self.stats_list:
                val = getter(s)
                row += f"{val:>{col_width}d}"
            print(row)

        print("=" * (col_width * (n + 1) + 10))


# ============================================================================
# Plotting (optional)
# ============================================================================

def plot_results(stats: DaftpumStats, output_prefix: str = "daftpum_results"):
    """Generate matplotlib plots of DAFTPUM-LAT results."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
        HAS_MPL = True
    except ImportError:
        HAS_MPL = False

    if not HAS_MPL:
        # Generate ASCII SVG-like plots as a simple HTML file
        _plot_html(stats, output_prefix)
        return

    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle("DAFTPUM-LAT Controller Results", fontsize=14, fontweight="bold")

    # 1. Bit-precision distribution
    ax = axes[0, 0]
    dist = stats.bit_precision_dist
    if dist:
        bps = sorted(dist.keys())
        counts = [dist[bp] for bp in bps]
        ax.bar(bps, counts, color="#4C72B0", edgecolor="black", linewidth=0.5)
        ax.set_xlabel("Bit Precision")
        ax.set_ylabel("Count")
        ax.set_title("Bit-Precision Distribution")
        ax.grid(axis="y", alpha=0.3)

    # 2. Adder selection pie chart
    ax = axes[0, 1]
    adders = stats.adder_selection
    adder_data = {
        "Full": adders.full,
        "Sklansky": adders.sklansky,
        "Kogge-Stone": adders.kogge_stone,
        "Carry-Select": adders.carry_select,
        "RBR": adders.rbr,
    }
    adder_data = {k: v for k, v in adder_data.items() if v > 0}
    if adder_data:
        colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974"]
        ax.pie(adder_data.values(), labels=adder_data.keys(),
               autopct="%1.1f%%", colors=colors[:len(adder_data)])
        ax.set_title("Adder Circuit Selection")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_title("Adder Circuit Selection")

    # 3. Multiplier selection pie chart
    ax = axes[1, 0]
    mults = stats.multiplier_selection
    mult_data = {
        "Full": mults.full,
        "Sklansky": mults.sklansky,
        "Carry-Select": mults.carry_select,
        "RBR": mults.rbr,
    }
    mult_data = {k: v for k, v in mult_data.items() if v > 0}
    if mult_data:
        colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2"]
        ax.pie(mult_data.values(), labels=mult_data.keys(),
               autopct="%1.1f%%", colors=colors[:len(mult_data)])
        ax.set_title("Multiplier Circuit Selection")
    else:
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_title("Multiplier Circuit Selection")

    # 4. Summary text
    ax = axes[1, 1]
    ax.axis("off")
    summary_lines = [
        f"Total BBOPs:        {stats.total_bbops}",
        f"Total Latency:      {stats.total_latency_ns:.2f} ns",
        f"Total Energy:       {stats.total_energy_nj:.3f} nJ",
        f"Avg Parallelism:    {stats.avg_parallelism:.1f} subarrays",
    ]
    if stats.total_bbops > 0:
        summary_lines.extend([
            "",
            f"Avg Latency/BBOP:   {stats.total_latency_ns / stats.total_bbops:.2f} ns",
            f"Avg Energy/BBOP:    {stats.total_energy_nj / stats.total_bbops:.3f} nJ",
            f"Energy-Delay:       {stats.total_energy_nj * stats.total_latency_ns / stats.total_bbops:.3f} nJ*ns",
        ])
    ax.text(0.1, 0.9, "\n".join(summary_lines), transform=ax.transAxes,
            fontsize=11, verticalalignment="top", fontfamily="monospace",
            bbox=dict(boxstyle="round", facecolor="#f0f0f0", alpha=0.8))
    ax.set_title("Summary")

    plt.tight_layout()
    outfile = f"{output_prefix}.png"
    plt.savefig(outfile, dpi=150, bbox_inches="tight")
    print(f"  Plot saved to: {outfile}")
    plt.close()


def _plot_html(stats: DaftpumStats, output_prefix: str):
    """Generate self-contained HTML chart (no dependencies)."""
    dist = stats.bit_precision_dist
    adders = stats.adder_selection
    mults = stats.multiplier_selection

    dist_labels = json.dumps([f"{bp}-bit" for bp in sorted(dist.keys())])
    dist_values = json.dumps([dist[bp] for bp in sorted(dist.keys())])

    adder_labels = json.dumps(["Full", "Sklansky", "Kogge-Stone", "Carry-Select", "RBR"])
    adder_values = json.dumps([adders.full, adders.sklansky, adders.kogge_stone,
                               adders.carry_select, adders.rbr])

    mult_labels = json.dumps(["Full", "Sklansky", "Carry-Select", "RBR"])
    mult_values = json.dumps([mults.full, mults.sklansky, mults.carry_select, mults.rbr])

    avg_lat = stats.total_latency_ns / stats.total_bbops if stats.total_bbops > 0 else 0
    avg_nj = stats.total_energy_nj / stats.total_bbops if stats.total_bbops > 0 else 0

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>DAFTPUM-LAT Results</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
body {{ font-family: sans-serif; max-width: 960px; margin: 20px auto; }}
.card {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin: 16px 0; box-shadow: 0 2px 4px rgba(0,0,0,.1); }}
h1 {{ color: #333; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
canvas {{ max-height: 300px; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #4C72B0; color: white; }}
</style></head><body>
<h1>DAFTPUM-LAT Controller Results</h1>

<div class="card">
<h2>Execution Summary</h2>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Total BBOPs</td><td>{stats.total_bbops}</td></tr>
<tr><td>Total Latency</td><td>{stats.total_latency_ns:.2f} ns</td></tr>
<tr><td>Total Energy</td><td>{stats.total_energy_nj:.3f} nJ</td></tr>
<tr><td>Avg Parallelism</td><td>{stats.avg_parallelism:.1f} subarrays</td></tr>
<tr><td>Avg Latency/BBOP</td><td>{avg_lat:.2f} ns</td></tr>
<tr><td>Avg Energy/BBOP</td><td>{avg_nj:.3f} nJ</td></tr>
</table></div>

<div class="grid">
<div class="card">
<h3>Bit-Precision Distribution</h3>
<canvas id="bpChart"></canvas></div>
<div class="card">
<h3>Adder Circuit Selection</h3>
<canvas id="adderChart"></canvas></div>
<div class="card">
<h3>Multiplier Circuit Selection</h3>
<canvas id="multChart"></canvas></div>
</div>

<script>
new Chart(document.getElementById("bpChart"), {{
  type: "bar",
  data: {{
    labels: {dist_labels},
    datasets: [{{ label: "Count", data: {dist_values},
      backgroundColor: "#4C72B0" }}]
  }},
  options: {{ responsive: true, plugins: {{ legend: {{ display: false }} }} }}
}});
new Chart(document.getElementById("adderChart"), {{
  type: "doughnut",
  data: {{
    labels: {adder_labels},
    datasets: [{{ data: {adder_values},
      backgroundColor: ["#4C72B0","#55A868","#C44E52","#8172B2","#CCB974"] }}]
  }},
  options: {{ responsive: true }}
}});
new Chart(document.getElementById("multChart"), {{
  type: "doughnut",
  data: {{
    labels: {mult_labels},
    datasets: [{{ data: {mult_values},
      backgroundColor: ["#4C72B0","#55A868","#C44E52","#8172B2"] }}]
  }},
  options: {{ responsive: true }}
}});
</script></body></html>"""

    outfile = f"{output_prefix}.html"
    with open(outfile, "w") as f:
        f.write(html)
    print(f"  Interactive chart saved to: {outfile}")
    print(f"  Open in browser: file:///{outfile.replace(chr(92), '/')}")



# ============================================================================
# JSON export
# ============================================================================

def export_json(stats: DaftpumStats, output_file: str):
    """Export statistics to JSON."""
    data = stats.as_dict()
    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  JSON exported to: {output_file}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="DAFTPUM-LAT gem5 Results Parser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s stats.txt
  %(prog)s stats.txt --plot
  %(prog)s stats.txt --json results.json
  %(prog)s --compare run1.txt run2.txt run3.txt
  %(prog)s --stderr gem5.log
        """,
    )

    parser.add_argument("stats_file", nargs="?", help="gem5 stats.txt file")
    parser.add_argument("--stderr", help="Parse gem5 stderr/log instead of stats.txt")
    parser.add_argument("--plot", action="store_true", help="Generate matplotlib plots")
    parser.add_argument("--json", metavar="FILE", help="Export statistics to JSON")
    parser.add_argument("--compare", nargs="+", metavar="FILE",
                        help="Compare multiple stats files side-by-side")
    parser.add_argument("--compare-labels", nargs="+", metavar="LABEL",
                        help="Labels for --compare files")
    parser.add_argument("--output-prefix", default="daftpum_results",
                        help="Output file prefix for plots")

    args = parser.parse_args()

    if args.compare:
        # Comparison mode
        labels = args.compare_labels or [
            f"Run {i+1}" for i in range(len(args.compare))
        ]
        stats_list = []
        parser_obj = Gem5StatsParser()
        for filepath in args.compare:
            try:
                s = parser_obj.parse_file(filepath)
                stats_list.append(s)
                print(f"  Loaded: {filepath}")
            except Exception as e:
                print(f"  Error loading {filepath}: {e}")
                sys.exit(1)

        comparator = StatsComparator(labels, stats_list)
        comparator.print_comparison()

        if args.json:
            data = [s.as_dict() for s in stats_list]
            with open(args.json, "w") as f:
                json.dump(dict(zip(labels, data)), f, indent=2)
            print(f"  JSON exported to: {args.json}")

    elif args.stderr:
        # Parse stderr
        p = Gem5StatsParser()
        stats = p.parse_stderr(args.stderr)
        display = StatsDisplay(stats, args.stderr)
        display.print_all()

        if args.plot:
            plot_results(stats, args.output_prefix)
        if args.json:
            export_json(stats, args.json)

    elif args.stats_file:
        # Single file mode
        p = Gem5StatsParser()
        try:
            stats = p.parse_file(args.stats_file)
        except Exception as e:
            print(f"  Error: {e}")
            sys.exit(1)

        display = StatsDisplay(stats, args.stats_file)
        display.print_all()

        if args.plot:
            plot_results(stats, args.output_prefix)
        if args.json:
            export_json(stats, args.json)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
