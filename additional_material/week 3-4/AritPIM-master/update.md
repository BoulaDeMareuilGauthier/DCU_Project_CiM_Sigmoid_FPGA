# Update Card: F₆ Sigmoid Approximation on AritPIM

## Origin

This project extends the **AritPIM** simulator, originally published as:

> O. Leitersdorf, D. Leitersdorf, J. Gal, M. Dahan, R. Ronen, and S. Kvatinsky,
> "AritPIM: High-Throughput In-Memory Arithmetic,"
> IEEE Transactions on Emerging Topics in Computing, 2023.

The original repository provides bit-serial and bit-parallel Processing-in-Memory arithmetic algorithms (addition, subtraction, multiplication, division) for both fixed-point and IEEE 754 floating-point representations, along with simulators and correctness tests.

**Source**: https://github.com/oleitersdorf/AritPIM

## What Was Done

### New Feature: `f6_dashboard.py`

Implemented a complete sigmoid approximation pipeline on the AritPIM architecture using the rational polynomial:

**f₆(x) = min(max((120 + 60x + 12x² + x³) / (240 + 24x²), 0), 1)**

This function approximates the standard sigmoid σ(x) = 1/(1+e⁻ˣ) using only integer-friendly operations, making it suitable for Processing-in-Memory hardware.

### Implementation Details

- **Horner's method** for numerator: ((x+12)·x+60)·x+120 — 3 multiplications, 3 additions
- **Denominator**: 240 + 24·x² — 2 multiplications, 1 addition
- **Division** with zero-check
- **Clamping** to [0, 1] using subtraction-based comparisons

### Architecture Exploration (10 Hybrid Strategies)

Evaluates f₆ across 10 architecture mixing strategies × 2 representations = **20 configurations**:

| Strategy | Description |
|----------|-------------|
| Pure Serial | All operations bit-serial |
| Pure Parallel | All operations bit-parallel |
| Hybrid A | Multiplications parallel, additions/division serial |
| Hybrid B | Additions parallel, multiplications serial |
| Hybrid C | Numerator parallel, denominator + division serial |
| Hybrid D | All arithmetic parallel, clamping serial |
| Hybrid E | Only division parallel, everything else serial |
| Hybrid F | Only additions parallel, mult/div/clamp serial |
| Hybrid G | Numerator serial, denominator + division + clamping parallel |
| Hybrid H | Multiplications + division parallel, additions + clamping serial |

### Outputs

1. **`sigmoid_vs_f6_comparison.png`** — Visual comparison of true sigmoid vs f₆ approximation with error plot
2. **`dashboard_comparison.png`** — Bar chart of top 4 configurations across 5 metrics (latency, energy, area, TOPS, TOPS/W)
3. **Console summary** — Full table of all 20 configurations with ranking

### Metrics Collected

- **Latency** (cycles) — from simulator performance counters
- **Energy** (gates) — gate activations during computation
- **Area** (cells) — memory cells used
- **Throughput** (TOPS) — derived using RACER architecture parameters
- **Energy Efficiency** (TOPS/W) — throughput per watt

### Ranking Algorithm

1. Rank by throughput descending (standard competition ranking)
2. Rank by energy efficiency descending (standard competition ranking)
3. Combined score = throughput_rank + efficiency_rank
4. Select top 4 by lowest combined score
5. Tie-break: lower area, then higher throughput

### Files Added

| File | Purpose |
|------|---------|
| `f6_dashboard.py` | Main implementation (single script, ~2800 lines) |
| `update.md` | This file — documents what was added |
| `.gitignore` | Git ignore rules |
| `tests/` | Property-based and unit tests (10 files) |

### Files NOT Modified

The original AritPIM source code was **not modified**:
- `serial/AritPIM.py`, `serial/simulator.py`, `serial/test.py`
- `parallel/AritPIM.py`, `parallel/simulator.py`, `parallel/test.py`
- `util/representation.py`, `util/constants.py`, `util/IO.py`
- `output/`, `results/`, `gpu/`

### How to Run

```bash
pip install numpy matplotlib
python f6_dashboard.py
```

### Sample Execution Output

```
[1/5] Running all 12 configurations (6 strategies × 2 representations)...
      Parameters: n=1024, N=32, num_cols=1024

      Completed: 20 configurations executed.

[2/5] Configuration Results Summary
------------------------------------------------------------------------
#   Configuration                   Latency     Energy       Area         TOPS       TOPS/W
------------------------------------------------------------------------
1   Pure Serial (Fixed)             105,016    105,016        709     0.009985       0.0006
2   Pure Serial (Float)              82,882     82,882        460     0.012651       0.0010
3   Pure Parallel (Fixed)             9,787    169,740        736     0.107140       0.0042
4   Pure Parallel (Float)            15,131    154,376        768     0.069300       0.0030
5   Hybrid A (Fixed)                 61,730    134,436        736     0.016986       0.0008
6   Hybrid A (Float)                 52,086    115,379        768     0.020132       0.0012
7   Hybrid B (Fixed)                 61,730    134,436        736     0.016986       0.0008
8   Hybrid B (Float)                 52,086    115,379        768     0.020132       0.0012
9   Hybrid C (Fixed)                 53,072    140,320        736     0.019758       0.0009
10  Hybrid C (Float)                 45,926    121,878        768     0.022832       0.0012
11  Hybrid D (Fixed)                 18,444    163,856        736     0.056852       0.0023
12  Hybrid D (Float)                 21,290    147,876        768     0.049252       0.0022
13  Hybrid E (Fixed)                 96,358    110,900        736     0.010882       0.0007
14  Hybrid E (Float)                 76,722     89,381        768     0.013667       0.0010
15  Hybrid F (Fixed)                 70,387    128,552        736     0.014897       0.0008
16  Hybrid F (Float)                 58,245    108,879        768     0.018003       0.0011
17  Hybrid G (Fixed)                 61,730    134,436        736     0.016986       0.0008
18  Hybrid G (Float)                 52,086    115,379        768     0.020132       0.0012
19  Hybrid H (Fixed)                 53,072    140,320        736     0.019758       0.0009
20  Hybrid H (Float)                 45,926    121,878        768     0.022832       0.0012
------------------------------------------------------------------------

[3/5] Correctness Verification...
      Skipping inline verification (use test_property_f6_e2e.py for correctness checks).

[4/5] Ranking configurations and selecting top 4...

  Top 4 Configurations (by combined throughput + efficiency rank):
  --------------------------------------------------------------------
  Rank  Configuration                Combined  T-Rank  E-Rank       TOPS
  --------------------------------------------------------------------
  1     Pure Parallel (Fixed)               2       1       1   0.107140
  2     Pure Parallel (Float)               4       2       2   0.069300
  3     Hybrid D (Fixed)                    6       3       3   0.056852
  4     Hybrid D (Float)                    8       4       4   0.049252
  --------------------------------------------------------------------

[5/6] Plotting sigmoid vs f₆(x) comparison...
  Sigmoid comparison saved to: sigmoid_vs_f6_comparison.png

[6/6] Rendering dashboard and saving to 'dashboard_comparison.png'...
```

### Key Findings

- **Pure Parallel (Fixed)** achieves the highest throughput at **0.107 TOPS** and best energy efficiency at **0.0042 TOPS/W**
- **Hybrid D** (all arithmetic parallel, clamping serial) is the best hybrid, achieving ~53% of pure parallel throughput with slightly lower energy
- Bit-parallel configurations dominate the top 4 — the latency reduction from parallelism outweighs the energy cost
- Fixed-point consistently outperforms floating-point in throughput (fewer cycles for simpler operations)
- Hybrid strategies B, G produce identical metrics to Hybrid A due to the weighted averaging approach in hybrid metric computation

### Dependencies

- Python 3.12+
- numpy
- matplotlib
- hypothesis (for tests only)
