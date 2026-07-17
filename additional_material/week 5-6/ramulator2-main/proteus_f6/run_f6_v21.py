#!/usr/bin/env python3
"""
run_f6_v21.py — Ramulator2 v2.1 simulation of the f6 workload.

Uses the new Python-first API (import ramulator).
Replaces the old YAML-based f6_ramulator_config.yaml from v2.0.

Usage:
    cd <repo-root>
    PYTHONPATH=python python3 proteus_f6/run_f6_v21.py
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))
import ramulator

FRONTEND = ramulator.frontend.LoadStoreTrace(
    clock_ratio=8,
    path="proteus_f6/f6_ramulator.trace",
)

DDR4 = ramulator.dram.DDR4(
    org_preset="DDR4_8Gb_x8",
    timing_preset="DDR4_2400R",
    rank=2,
)

CTRL = ramulator.controller.GenericDDR(
    dram=DDR4,
    scheduler=ramulator.scheduler.FRFCFS(),
    refresh_manager=ramulator.refresh_manager.AllBank(),
    row_policy=ramulator.row_policy.ClosedCAP(cap=4),
    addr_mapper=ramulator.addr_mapper.RoBaRaCoCh(),
)

MEM = ramulator.memory_system.GenericDRAM(
    clock_ratio=3,
    controllers=[CTRL],
    channel_mapper=ramulator.channel_mapper.CacheLineInterleave(),
)

sim = ramulator.Simulation(FRONTEND, MEM)
sim.run()

stats = sim.stats
if not stats:
    print("No stats returned.")
    sys.exit(1)

ctrl = stats["memory_system"]["controller"]
print(f"Controller cycles:      {ctrl['cycles']}")
print(f"Total read requests:    {ctrl['num_read_reqs']}")
print(f"Total write requests:   {ctrl['num_write_reqs']}")
print(f"Avg read latency:       {ctrl['avg_read_latency']:.4f} cycles")
print(f"Row hits:               {ctrl['row_hits']}")
print(f"Row misses:             {ctrl['row_misses']}")
print(f"Row conflicts:          {ctrl['row_conflicts']}")

with open("proteus_f6/f6_ramulator_stats_v21.json", "w") as f:
    json.dump(stats, f, indent=2)
print("Stats saved to proteus_f6/f6_ramulator_stats_v21.json")
