#!/usr/bin/env python3
"""
plot_results.py
Reads the Proteus model output (bbop_statistics.csv) produced by the
f6_daftpum_wrapper and renders a comparison chart of DAFTPUM_LAT vs the
SIMDRAM baselines for the f6-generated workload.

Pure stdlib + matplotlib (no pandas needed).
"""
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CSV = "bbop_statistics.csv"
OUT = "f6_daftpum_vs_simdram.png"

# Mechanisms we want to compare (in plotting order).
MECHS = [
    "SIMDRAM_1",
    "SIMDRAM_64",
    "SIMDRAM_64_DYNAMIC",
    "DAFTPUM_STATIC_LAT",
    "DAFTPUM_LAT",
    "DAFTPUM_ENE",
    "DAFTPUM_TFAW",
]
HILITE = {"DAFTPUM_LAT"}

# per-operation latency/energy: data[op][mech] = (lat_ms, ene_mj)
data = {}
summary = {}

with open(CSV, newline="") as f:
    reader = csv.reader(f)
    next(reader)  # header
    for row in reader:
        row = [c.strip() for c in row if c.strip() != ""]
        if not row:
            continue
        if row[0] == "Summary":
            if len(row) < 4:
                continue
            mech, lat, ene = row[1], float(row[2]), float(row[3])
            summary[mech] = (lat, ene)
        elif len(row) >= 7:
            op, mech = row[1], row[4]
            lat, ene = float(row[5]), float(row[6])
            data.setdefault(op, {})[mech] = (lat, ene)

ops = list(data.keys())

fig, axes = plt.subplots(1, 3, figsize=(18, 6))

def bars(ax, labels, values, title, ylabel):
    colors = ["#c0392b" if l in HILITE else "#5b8db8" for l in labels]
    bp = ax.bar(range(len(labels)), values, color=colors)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=9)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    for i, v in enumerate(values):
        ax.text(i, v, f"{v:.4g}", ha="center", va="bottom", fontsize=8)

# Panel 1+2: per-operation latency
for ax, op in zip(axes[:len(ops)], ops):
    labels = [m for m in MECHS if m in data[op]]
    vals = [data[op][m][0] for m in labels]
    bars(ax, labels, vals, f"{op}: latency (f6 data, 10000 elems)", "latency (ms)")

# Panel 3: total summary latency
ax = axes[2]
labels = [m for m in MECHS if m in summary]
vals = [summary[m][0] for m in labels]
bars(ax, labels, vals, "Total latency (ADD+MUL)", "latency (ms)")

fig.suptitle(
    "Proteus DAFTPUM_LAT vs SIMDRAM on f6(x)-generated workload (10000 points)\n"
    "f6(x)=min(max((128+64x+16x^2+2x^3)/(256+32x^2),0),1)  |  DAFTPUM_LAT highlighted in red",
    fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.93])
fig.savefig(OUT, dpi=130)
print(f"Saved chart: {OUT}")

# Print a small speedup table to stdout.
print("\n=== DAFTPUM_LAT speedup over SIMDRAM (total) ===")
base = summary.get("SIMDRAM_1", (0, 0))[0]
dl = summary.get("DAFTPUM_LAT", (0, 0))[0]
if dl:
    print(f"SIMDRAM_1 total latency : {base:.6f} ms")
    print(f"DAFTPUM_LAT total       : {dl:.6f} ms")
    print(f"Speedup                 : {base/dl:.2f}x")
