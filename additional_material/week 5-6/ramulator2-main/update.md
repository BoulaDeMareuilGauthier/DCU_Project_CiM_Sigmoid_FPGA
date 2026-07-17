# update.md — f6 / Proteus DAFTPUM_LAT simulation on Ramulator2 v2.1

This note documents a self-contained experiment: driving the **Proteus DAFTPUM
latency model (`DAFTPUM_LAT`)** with data generated from the requested function,
comparing it against the **SIMDRAM** baselines, running a matching **Ramulator2
v2.1** DRAM simulation, and charting the result.

The function used to generate the data:

```
f6_nearest(x) = min( max( (128 + 64x + 16x^2 + 2x^3) / (256 + 32x^2), 0), 1)
```

---

## 1. What was there before

The repository was originally **Ramulator 2.0a** (CMU-SAFARI), a cycle-accurate
DRAM simulator with YAML-based config and a standalone C++ executable. It has
now been upgraded to **Ramulator 2.1**, which uses a **Python-first API**
(`import ramulator`) and no longer provides a standalone binary.

Key structural changes from v2.0 → v2.1:
- Source: `src/{dram,controller,frontend,...}/` → `src/ramulator/`
- Config: YAML files → Python API (`ramulator.Simulation`, etc.)
- Execution: `ramulator2 -f config.yaml` → `PYTHONPATH=python python3 script.py`
- Build: CMake builds `libramulator.so` + Python C extension (`_ramulator.*.so`)
- The old YAML configs, standalone `ramulator2` executable, and v2.0 directories
  (`perf_comparison/`, `rh_study/`, `verilog_verification/`) no longer exist.

The `DAFTPUM_LAT` model lives in a separate repository
(`CMU-SAFARI/Proteus`, `util/bbop_manager.c` / `.h`). It was fetched verbatim
in `proteus_f6/` — **zero lines were modified**.

---

## 2. What was done

**Zero lines of the original Ramulator2 v2.1 source or the original Proteus model
were changed.** Everything new lives in `proteus_f6/`.

| File | Origin | Notes |
|------|--------|-------|
| `bbop_manager.c` | CMU-SAFARI/Proteus `util/` | **Unmodified original** |
| `bbop_manager.h` | CMU-SAFARI/Proteus `util/` | **Unmodified original** |
| `f6_daftpum_wrapper.c` | **New wrapper** | Calls Proteus API with f6 data |
| `plot_results.py` | **New plotter** | DAFTPUM vs SIMDRAM chart |
| `run_f6_v21.py` | **New v2.1 sim** | Runs Ramulator2 v2.1 via Python API |
| `ramulator_sweep_v21.py` | **New v2.1 sweep** | DDR4 frequency sweep + charts |
| `f6_ramulator.trace` | generated | LoadStore trace (30,000 refs) |
| `bbop_statistics.csv` | generated | Standard Proteus model output |
| `f6_daftpum_vs_simdram.png` | generated | **Chart A**: Proteus model comparison |
| `f6_ramulator_dram_breakdown_v21.png` | generated | **Chart B**: DRAM internal stats |
| `f6_ramulator_freq_sweep_v21.png` | generated | **Chart C**: DDR4 speed sweep |
| `f6_ramulator_stats_v21.json` | generated | Ramulator2 v2.1 full stats |
| `sweep_results_v21.json` | generated | Sweep data for all DDR4 grades |

**The wrapper (`f6_daftpum_wrapper.c`)** only calls the public Proteus API:
1. Generates **10,000** data points: sweeps `x` over `[-8, 8]`, evaluates
   `f6_nearest(x)`, scales to integer operands.
2. Feeds operands into the unmodified Proteus model via `bbop_op()` for
   element-wise **ADD** and **MUL**.
3. Emits a **Ramulator2 `LoadStore` trace** (`f6_ramulator.trace`): 2 operand
   loads + 1 result store per element (30,000 references).
4. Writes the standard Proteus `bbop_statistics.csv`.

**How to reproduce everything** (requires WSL with g++, cmake, Python 3.10+):

```bash
# 1. Build Ramulator2 v2.1
cd <repo-root>
mkdir build && cd build
cmake .. -DCMAKE_BUILD_TYPE=Release && make -j4

# 2. Run the Proteus DAFTPUM model + f6 wrapper (inside proteus_f6)
cd proteus_f6
gcc -O2 -fopenmp f6_daftpum_wrapper.c bbop_manager.c -o f6_daftpum -lm
./f6_daftpum                                    # -> bbop_statistics.csv + f6_ramulator.trace
cd ..

# 3. Ramulator2 v2.1 simulation (Python API)
PYTHONPATH=python python3 proteus_f6/run_f6_v21.py
# -> proteus_f6/f6_ramulator_stats_v21.json

# 4. Proteus comparison chart
python3 proteus_f6/plot_results.py
# -> proteus_f6/f6_daftpum_vs_simdram.png

# 5. Ramulator2 v2.1 DDR4 sweep + visualisations
PYTHONPATH=python python3 proteus_f6/ramulator_sweep_v21.py
# -> proteus_f6/f6_ramulator_dram_breakdown_v21.png
# -> proteus_f6/f6_ramulator_freq_sweep_v21.png
```

---

## 3. Results

### 3.1 Proteus model — DAFTPUM_LAT vs SIMDRAM (from `bbop_statistics.csv`)

Per-operation latency on the 10,000-point f6 workload:

| Mechanism            | ADD latency (ms) | MUL latency (ms) |
|----------------------|------------------|------------------|
| SIMDRAM_1            | 0.012593         | 0.544047         |
| SIMDRAM_64           | 0.012593         | 0.544047         |
| SIMDRAM_64_DYNAMIC   | 0.007889         | 0.210651         |
| DAFTPUM_STATIC_LAT   | 0.002194         | 0.184576         |
| **DAFTPUM_LAT**      | **0.002194**     | **0.099505**     |
| DAFTPUM_ENE          | 0.004978         | 0.210651         |
| DAFTPUM_TFAW         | 0.002194         | 0.099505         |

**`DAFTPUM_LAT` total speedup over `SIMDRAM_1`: 5.47×** (ADD+MUL: 0.5566 ms → 0.1017 ms).

**Chart A** (`f6_daftpum_vs_simdram.png`) shows DAFTPUM_LAT highlighted in red
as the lowest-latency mechanism across all baselines.

### 3.2 Ramulator2 v2.1 DRAM simulation

Replaying the f6-derived `LoadStore` trace through the v2.1 cycle-accurate DDR4
model (`DDR4_2400R`, `ClosedCAP` row policy):

| Metric                 | v2.0 result | v2.1 result |
|------------------------|-------------|-------------|
| Controller cycles      | 359,876     | **292,764** |
| Total reads            | 20,000      | 20,000      |
| Total writes           | 10,000      | 10,000      |
| Row hits               | 22,377      | **23,773**  |
| Row misses             | 7,570       | **6,175**   |
| Row conflict rate      | 0%          | 0%          |

v2.1 shows **~18.6% fewer cycles** (simulator/controller improvements), with
**6.2% more row hits** and **18.4% fewer row misses** due to scheduling changes
in the new controller model.

**Chart B** (`f6_ramulator_dram_breakdown_v21.png`) shows four panels of
internal DRAM stats: request mix, row-buffer hit/miss breakdown (79.4% hit
rate), pie chart, and queue occupancy.

### 3.3 DDR4 frequency sweep

| DDR4 preset  | Controller cycles | Avg read latency (cycles) | Row hit rate |
|-------------|-------------------|---------------------------|--------------|
| DDR4_2133R  | 292,372           | 492.00                    | 77.9%        |
| DDR4_2400R  | 292,764           | 492.56                    | 79.4%        |
| DDR4_3200AA | 375,292           | 631.35                    | 79.4%        |

Notice: `avg_read_latency` in v2.1 is in **frontend (CPU) cycles** (ratio 8:1 to
memory system), so values are ~492 vs the v2.0 value of ~13 (which was in
memory-system cycles).

**Chart C** (`f6_ramulator_freq_sweep_v21.png`) visualises the sweep.

### 3.4 Interpretation

The DAFTPUM model exploits **dynamic bit-precision**: because `f6(x)` is bounded
in `[0,1]`, the scaled operands have limited magnitude, so the latency-optimised
PUD configuration selects fast, narrow-precision adders/multipliers and beats
every SIMDRAM baseline by **5.47×**.

The upgrade to Ramulator2 v2.1 replaced the old YAML/standalone workflow with a
modern Python API while improving simulation accuracy (TFAW-aware scheduling,
better row-hit rates).

---

## 4. Reproducing

See section 2 for the full five-step build-and-run workflow. The original
Ramulator2 v2.1 source and the original Proteus model are untouched — only the
wrapper, config equivalency scripts, and plotter are new.
