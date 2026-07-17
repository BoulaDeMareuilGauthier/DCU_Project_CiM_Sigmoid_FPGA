#!/usr/bin/env python3
"""
ramulator_sweep_v21.py — Ramulator2 v2.1 DDR4 frequency sweep on the f6 trace.

Uses the Python-first API. Generates:
  1. f6_ramulator_dram_breakdown_v21.png — internal DRAM stats
  2. f6_ramulator_freq_sweep_v21.png — sweep across speed grades

Usage:
    cd <repo-root>
    PYTHONPATH=python python3 proteus_f6/ramulator_sweep_v21.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))
import ramulator
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

GRADES = ["DDR4_2133R", "DDR4_2400R", "DDR4_3200AA"]

def run_one(grade):
    frontend = ramulator.frontend.LoadStoreTrace(
        clock_ratio=8, path="proteus_f6/f6_ramulator.trace")
    dram = ramulator.dram.DDR4(
        org_preset="DDR4_8Gb_x8", timing_preset=grade, rank=2)
    ctrl = ramulator.controller.GenericDDR(
        dram=dram,
        scheduler=ramulator.scheduler.FRFCFS(),
        refresh_manager=ramulator.refresh_manager.AllBank(),
        row_policy=ramulator.row_policy.ClosedCAP(cap=4),
        addr_mapper=ramulator.addr_mapper.RoBaRaCoCh(),
    )
    mem = ramulator.memory_system.GenericDRAM(
        clock_ratio=3, controllers=[ctrl],
        channel_mapper=ramulator.channel_mapper.CacheLineInterleave())
    sim = ramulator.Simulation(frontend, mem)
    sim.run()
    return sim.stats["memory_system"]["controller"]

results = {}
for g in GRADES:
    print(f"Running @ {g} ...")
    results[g] = run_one(g)

base = results["DDR4_2400R"]

# ---- Chart 1: DRAM behaviour breakdown ------------------------------------
fig, ax = plt.subplots(2, 2, figsize=(14, 10))

# derive per-group breakdown
rh = base["read_row_hits"]
rm = base["read_row_misses"]
wh = base["row_hits"] - rh
wm = base["row_misses"] - rm
write_q = base["queue_len_avg"] - base["read_queue_len_avg"]
total_cycles = base["cycles"]

# top-left: request mix
ax[0][0].bar(["reads", "writes"],
    [base["num_read_reqs"], base["num_write_reqs"]],
    color=["#2e86c1", "#e67e22"], edgecolor="white", linewidth=0.6)
ax[0][0].set_title("Memory requests issued (f6 trace)", fontsize=11, fontweight="bold")
ax[0][0].set_ylabel("count", fontsize=10)
rsum = base["num_read_reqs"] + base["num_write_reqs"]
ax[0][0].text(0.5, base["num_read_reqs"]*0.97, f"{base['num_read_reqs']:,}",
    ha="center", va="top", fontsize=11, fontweight="bold", color="white")
ax[0][0].text(1, base["num_write_reqs"]*0.97, f"{base['num_write_reqs']:,}",
    ha="center", va="top", fontsize=11, fontweight="bold", color="white")
ax[0][0].text(0.5, max(base["num_read_reqs"], base["num_write_reqs"])*1.02,
    f"total = {rsum:,}", ha="center", fontsize=10, style="italic")

# top-right: read/write row hits vs misses
vals = [rh, rm, wh, wm]
ax[0][1].bar([0, 1, 2, 3], vals,
    color=["#27ae60", "#c0392b", "#7dcea0", "#e6786c"],
    edgecolor="white", linewidth=0.6)
ax[0][1].set_xticks([0, 1, 2, 3])
ax[0][1].set_xticklabels(["read\nhits", "read\nmisses", "write\nhits", "write\nmisses"],
    fontsize=9)
ax[0][1].set_title("DRAM row buffer hits vs misses", fontsize=11, fontweight="bold")
ax[0][1].set_ylabel("count", fontsize=10)
for i, v in enumerate(vals):
    ax[0][1].text(i, v*1.02, f"{v:,}\n({100*v/(v+(rm if i==0 else rh if i==1 else wm if i==2 else wh)):.1f}%)",
        ha="center", va="bottom", fontsize=9, fontweight="bold")

# bottom-left: overall hit rate pie (annotated with totals)
hits = base["row_hits"]
miss = base["row_misses"]
if hits + miss <= 0:
    hits, miss = 1, 0
wedges, texts, autotexts = ax[1][0].pie([hits, miss],
    labels=[f"hits\n{hits:,}", f"misses\n{miss:,}"],
    autopct="%1.1f%%", colors=["#27ae60", "#c0392b"],
    startangle=90, textprops={"fontsize": 10})
for t in autotexts:
    t.set_fontweight("bold")
ax[1][0].set_title("Row-buffer hit rate", fontsize=11, fontweight="bold")
ax[1][0].text(0, -1.4, f"total: {hits+miss:,} activations",
    ha="center", fontsize=9, style="italic")
ax[1][0].text(0, -1.6, f"(including {base['num_maintenance_reqs']} refresh activations)",
    ha="center", fontsize=8, style="italic")

# bottom-right: avg queue lengths
ax[1][1].bar(["read queue", "write queue"],
    [base["read_queue_len_avg"], write_q],
    color=["#2e86c1", "#e67e22"], edgecolor="white", linewidth=0.6)
ax[1][1].set_title("Average controller queue occupancy", fontsize=11, fontweight="bold")
ax[1][1].set_ylabel("avg #requests", fontsize=10)
for i, v in enumerate([base["read_queue_len_avg"], write_q]):
    ax[1][1].text(i, v*1.03, f"{v:.1f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
tot_q = base["queue_len_avg"]
ax[1][1].text(0.5, max(base["read_queue_len_avg"], write_q)*1.13,
    f"= {tot_q:.1f} total", ha="center", fontsize=10, style="italic")

fig.suptitle("Ramulator2 v2.1 DDR4 simulation of the f6 workload\n"
             f"DDR4_2400R — 10000 f6 elems → 30000 refs — {total_cycles:,} controller cycles",
             fontsize=13, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
out1 = os.path.join(os.path.dirname(__file__), "f6_ramulator_dram_breakdown_v21.png")
fig.savefig(out1, dpi=130)
print(f"Saved: {out1}")

# ---- Chart 2: frequency sweep ----------------------------------------------
fig2, (axA, axB) = plt.subplots(1, 2, figsize=(13, 5))

cycles = [results[g]["cycles"] for g in GRADES]
lats = [results[g]["avg_read_latency"] for g in GRADES]

axA.bar(GRADES, cycles, color=["#85929e", "#5b8db8", "#1f618d"])
axA.set_title("Controller cycles vs DDR4 speed grade")
axA.set_ylabel("cycles")
axA.tick_params(axis="x", rotation=15)
for i, v in enumerate(cycles):
    axA.text(i, v, f"{int(v)}", ha="center", va="bottom", fontsize=9)

axB.bar(GRADES, lats, color=["#d7bde2", "#a569bd", "#6c3483"])
axB.set_title("Avg read latency (cycles) vs DDR4 speed grade")
axB.set_ylabel("avg read latency (cycles)")
axB.tick_params(axis="x", rotation=15)
for i, v in enumerate(lats):
    axB.text(i, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9)

fig2.suptitle("Ramulator2 v2.1 frequency sweep on the f6 workload",
              fontsize=13, fontweight="bold")
fig2.tight_layout(rect=[0, 0, 1, 0.94])
out2 = os.path.join(os.path.dirname(__file__), "f6_ramulator_freq_sweep_v21.png")
fig2.savefig(out2, dpi=130)
print(f"Saved: {out2}")

print("\n=== Ramulator2 v2.1 sweep summary ===")
for g in GRADES:
    r = results[g]
    tot = r["row_hits"] + r["row_misses"]
    hr = 100 * r["row_hits"] / tot if tot > 0 else 0.0
    print(f"{g:12s}  cycles={int(r['cycles']):>8d}  "
          f"avg_read_lat={r['avg_read_latency']:.2f}  "
          f"row_hit_rate={hr:.1f}%")

with open("proteus_f6/sweep_results_v21.json", "w") as f:
    json.dump({g: dict(results[g]) for g in GRADES}, f, indent=2)
print("Sweep results saved to sweep_results_v21.json")
