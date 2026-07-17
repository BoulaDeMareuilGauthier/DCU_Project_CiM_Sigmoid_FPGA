# DAFTPUM-LAT Additional Materials - Complete Inventory

## Overview

This folder contains Python cost models, comparison scripts, visualizations,
and test files for the DAFTPUM-LAT Processing-Using-DRAM controller implementation.

---

## Complete File Inventory

### Python Cost Models

| File | Purpose |
|------|---------|
| `adder_cost_model.py` | Unified adder cost model: 5 exact + 5 approximate adders |
| `multiplier_cost_model.py` | Unified multiplier cost model: 4 exact + 8 approximate multipliers |
| `dividers/divider_cost_model.py` | Unified divider cost model: 2 exact + 7 approximate dividers |

### Comparison & Visualization Scripts

| File | Purpose |
|------|---------|
| `plot_adder_comparison.py` | Generates latency/energy/area plots for adders |
| `plot_multiplier_comparison.py` | Generates latency/energy/area plots for multipliers |
| `dividers/plot_division_comparison.py` | Generates latency/energy/error plots for dividers |

### Generated Outputs

| File | Purpose |
|------|---------|
| `adder_comparison.png` | Adder comparison plot |
| `multiplier_comparison.png` | Multiplier comparison plot |
| `dividers/division_comparison.png` | Division comparison plot |
| `dividers/division_comparison.html` | Interactive Chart.js divider visualization |
| `adder_metrics.csv` | Adder metrics export |
| `multiplier_metrics.csv` | Multiplier metrics export |
| `dividers/division_metrics.csv` | Divider metrics export |

---

## Detailed Component Analysis

### 1. Adder Cost Model (`adder_cost_model.py`)

**Exact Adders (5):**

| Adder | Latency (16-bit) | Key Property |
|-------|------------------|--------------|
| Full (RCA) | 4.022 ns | Simplest, lowest energy |
| Sklansky | 4.600 ns | Parallel prefix |
| Kogge-Stone | 4.271 ns | Fastest for high precision |
| Carry-Select | 4.342 ns | Carry speculation |
| RBR | 2.194 ns | Constant latency |

**Approximate Adders (5):**

| Adder | Latency Savings | Energy Savings | Source |
|-------|-----------------|----------------|--------|
| LOA | ~49% | ~43% | Lower-part-OR adder |
| CCBA | ~48% | ~52% | Carry cut-back adder |
| TruA | ~56% | ~50% | Truncated adder |
| GeAr | ~42% | ~32% | Generic accuracy-configurable |
| CSA | ~37% | ~38% | Carry speculative adder |

### 2. Multiplier Cost Model (`multiplier_cost_model.py`)

**Exact Multipliers (4):**

| Multiplier | Latency (16-bit) | Description |
|------------|------------------|-------------|
| Full (RC Array) | 151.557 ns | Ripple-carry array |
| Sklansky | 80.623 ns | Sklansky-tree |
| Carry-Select | 84.983 ns | Carry-save |
| RBR | 97.512 ns | Reversed-biased ripple |

**Approximate Multipliers (8):**

| Multiplier | Type | Energy Savings | Source |
|------------|------|----------------|--------|
| Mitchell | Logarithmic | ~94% | Mitchell 1962 |
| ALM-SOA | Logarithmic | ~82% | Approximate log |
| ILM-AA | Logarithmic | ~55% | Improved log |
| CGPM1 | Partial-product | ~38% | CGP-generated |
| TAM1 | Truncation | ~54% | Truncation + compensation |
| HOCM | Truncation | ~50% | High-order compressor |
| CGPM3 | Partial-product | ~30% | CGP 3-sub-block |
| BAM | Broken-array | ~70% | Broken-array multiplier |

### 3. Divider Cost Model (`divider_cost_model.py`)

**Exact Dividers (2):**

| Divider | Latency (16-bit) | Description |
|---------|------------------|-------------|
| Exact Array | 111.456 ns | Restoring array divider |
| Exact Logarithmic | 298.240 ns | LNS-based divider (Mitchell) |

**Approximate Dividers (6):**

| Divider | Latency Savings | Energy Savings | NED | MRED% | Source |
|---------|-----------------|----------------|-----|-------|--------|
| **AAXD** | ~61.0% | ~69.4% | 2.97 | 6.61% | IEEE TC 2020 |
| **INZeD** | ~58.0% | ~66.2% | 4.50 | 8.20% | DATE 2019 |
| **AXDr1** | ~51.0% | ~60.1% | 1.32 | 4.32% | IEEE TC 2018 |
| **AXDr3** | ~48.0% | ~58.4% | 0.97 | 3.25% | IEEE TC 2018 |
| **SEERAD-4** | ~42.0% | ~51.9% | 1.09 | 2.71% | DATE 2016 |
| **DAXD** | ~45.0% | ~54.9% | 7.44 | 16.39% | MICPRO 2020 |
| **SC Divider** | ~61.5% | ~67.6% | 15.0 | 25.0% | IEEE TC 2017 |
| **RAPID** | ~65.0% | ~73.3% | 3.5 | 7.2% | FPGA 2018 |

---

## Divider Architecture Details

### AAXD (Adaptive Approximate Divider)
- **Source:** IEEE Transactions on Computers, 2020
- **Technique:** Adaptive pruning of LSBs, reduced-width divider
- **Key Feature:** Smallest ED_max among all designs
- **Config:** 8/4 (16-bit input → 8-bit core divider)
- **Error:** NED=2.97, MRED=6.61%, ED_max=49

### INZeD (Inexact Zero-based Divider)
- **Source:** DATE Conference, 2019
- **Technique:** Inexact partial product generation
- **Key Feature:** Zero-based computation reduces switching activity
- **Error:** NED=4.50, MRED=8.20%, ED_max=85

### AXDr1 (Approximate Restoring Divider v1)
- **Source:** IEEE Transactions on Computers, 2018
- **Technique:** Approximate subtractor cells with replacement depth 8
- **Key Feature:** Very low error among approximate designs
- **Error:** NED=1.32, MRED=4.32%, ED_max=51

### AXDr3 (Approximate Restoring Divider v3)
- **Source:** IEEE Transactions on Computers, 2018
- **Technique:** Higher accuracy variant of AXDr
- **Key Feature:** Lowest NED among all approximate dividers
- **Error:** NED=0.97, MRED=3.25%, ED_max=85

### SEERAD-4 (Rounding-based Approximate Divider)
- **Source:** DATE Conference, 2016
- **Technique:** Rounding + approximate multiplication
- **Key Feature:** Moderate latency, good accuracy balance
- **Config:** Accuracy level 4
- **Error:** NED=1.09, MRED=2.71%, ED_max=165

### DAXD (Dual-path Approximate Divider)
- **Source:** Microprocessors and Microsystems, 2020
- **Technique:** Dual-path computation with bit-width reduction
- **Key Feature:** Fast but higher error
- **Error:** NED=7.44, MRED=16.39%, ED_max=240

### SC Divider (Stochastic Computing Divider)
- **Source:** IEEE Transactions on Computers, 2017
- **Technique:** Bit-stream encoding, division = bit-shift in stochastic domain
- **Key Feature:** Similar latency to AAXD (2.6x speedup), high error
- **Limitation:** High error from stochastic rounding
- **Error:** NED=15.0, MRED=25.0%, ED_max=500

### RAPID (Reconfigurable Approximate Pipelined Divider)
- **Source:** FPGA Conference, 2018
- **Technique:** Pipelined design using 6-LUTs and carry chains
- **Key Feature:** Fast latency (2.86x speedup), FPGA-optimized
- **Config:** Reconfigurable pipeline stages
- **Error:** NED=3.5, MRED=7.2%, ED_max=120

---

## Key Findings

### Latency Comparison (16-bit)

| Divider | Latency (ns) | Speedup vs DAFTPUM-LAT |
|---------|--------------|------------------------|
| DAFTPUM-LAT (exact) | 111.46 | 1.0x |
| Mitchell (exact_log) | 13.93 | **8.0x** |
| RAPID | 39.01 | **2.86x** |
| SC Divider | 42.91 | **2.60x** |
| AAXD | 43.47 | **2.56x** |
| INZeD | 46.81 | **2.38x** |
| AXDr1 | 54.61 | **2.04x** |
| AXDr3 | 57.96 | **1.92x** |
| DAXD | 61.30 | **1.82x** |
| SEERAD-4 | 64.64 | **1.72x** |

### Energy Comparison (16-bit)

| Divider | Energy (nJ) | Savings vs DAFTPUM-LAT |
|---------|-------------|------------------------|
| DAFTPUM-LAT (exact) | 4.856 | - |
| Mitchell (exact_log) | 1.214 | **75.0%** |
| RAPID | 1.296 | **73.3%** |
| AAXD | 1.486 | **69.4%** |
| SC Divider | 1.573 | **67.6%** |
| INZeD | 1.642 | **66.2%** |
| AXDr1 | 1.937 | **60.1%** |
| AXDr3 | 2.021 | **58.4%** |
| DAXD | 2.191 | **54.9%** |
| SEERAD-4 | 2.336 | **51.9%** |

### Accuracy Comparison (16-bit)

| Divider | NED | MRED% | ED_max | Best For |
|---------|-----|-------|--------|----------|
| AXDr3 | **0.97** | **3.25%** | 85 | Precision-critical |
| SEERAD-4 | 1.09 | **2.71%** | 165 | Balanced |
| AXDr1 | 1.32 | 4.32% | 51 | Low max error |
| RAPID | 3.5 | 7.2% | 120 | FPGA platforms |
| AAXD | 2.97 | 6.61% | **49** | Min ED_max |
| INZeD | 4.50 | 8.20% | 85 | Medium accuracy |
| DAXD | 7.44 | 16.39% | 240 | High speed |
| SC Divider | 15.0 | 25.0% | 500 | Minimal hardware |

---

## Usage Examples

### Generate Divider Comparison
```bash
cd additional_material/dividers
python plot_division_comparison.py --bp-min 4 --bp-max 32
```

### Export Divider Metrics
```bash
cd additional_material/dividers
python plot_division_comparison.py --csv division_metrics.csv --no-plot
```

### View Interactive Chart
```
file:///C:/Users/croqu/Downloads/DCU PROJECT/Implementation/search/week 5-6/gem5-stable/gem5-stable/additional_material/dividers/division_comparison.html
```

---

## Interactive Visualization Features

The `division_comparison.html` provides a fully interactive Chart.js visualization
with the following features:

### Chart Controls

| Feature | How to Use |
|---------|------------|
| **Zoom In** | Scroll wheel up, or drag-select a region |
| **Zoom Out** | Scroll wheel down |
| **Pan** | Click and drag the chart background |
| **Reset Zoom** | Double-click the chart, or use the "Reset Zoom" button |
| **Fullscreen** | Click the green "Fullscreen" button on any chart |
| **Exit Fullscreen** | Press ESC, click "Close" button, or click outside the chart |

### Sortable Summary Table

The 16-bit Summary table supports sorting by any column:

| Column | Sort Type | Description |
|--------|-----------|-------------|
| Divider | Text (A-Z) | Alphabetical sort by divider name |
| Lat (ns) | Numeric | Sort by latency ascending/descending |
| Energy (nJ) | Numeric | Sort by energy ascending/descending |
| NED | Numeric | Sort by Normalized Error Distance |
| MRED% | Numeric | Sort by Mean Relative Error Distance |

**How to sort:** Click on any column header to sort ascending (↑ indicator appears).
Click again to sort descending (↓ indicator).

### Technical Details

- **Chart.js v4** with `chartjs-plugin-zoom@2` for zoom/pan
- **Hammer.js** for touch gesture support (mobile/pinch-zoom)
- Responsive layout with 2-column grid
- Fullscreen mode creates a new chart instance with full data copy
- All charts share zoom state independently
- Color scheme: Solid lines = exact, Dashed lines = approximate dividers

---

## Summary

This additional_material folder now contains:

1. **10 adder types** (5 exact, 5 approximate)
2. **12 multiplier types** (4 exact, 8 approximate)
3. **7 divider types** (2 exact + 7 approximate)
4. **Visualization tools** for all arithmetic units
5. **Results parser** for gem5 output
6. **Test drivers** and examples

All models are calibrated against Proteus bbop_manager.c and published
synthesis results from IEEE/ACM conferences and journals.
