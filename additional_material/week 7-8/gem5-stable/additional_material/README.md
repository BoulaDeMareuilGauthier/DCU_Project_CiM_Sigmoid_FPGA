# DAFTPUM-LAT Controller for gem5

A gem5 memory controller implementing the **DAFTPUM-LAT** (Latency-Optimized)
configuration of the Proteus Processing-Using-DRAM architecture.

## Overview

DAFTPUM-LAT enables computation directly within DRAM subarrays by exploiting
dynamic bit-precision and latency-optimized circuit selection:

- **Dynamic bit-precision**: Scans actual data to find narrow values at runtime,
  reducing bit-width from static 32/64-bit to the minimum needed
- **Latency-optimized circuits**: Auto-selects the fastest adder/multiplier
  from full-adder, Sklansky, Kogge-Stone, carry-select, and RBR designs
- **64-subarray parallelism**: Partitions bulk operations across all DRAM
  subarrays for maximum throughput
- **No TFAW constraints**: This configuration does not enforce
  Timing-FAW limitations

## Project Structure

### Controller Source (C++)

| File | Location | Description |
|------|----------|-------------|
| `daftpum_types.hh` | Controller dir | Shared enums, structs, constants |
| `daftpum_subarray_unit.hh/cc` | Controller dir | Per-subarray execution unit |
| `daftpum_lat_controller.hh/cc` | Controller dir | Main controller implementation |
| `DaftpumLatController.py` | Controller dir | gem5 SimObject configuration |

### Additional Materials (this folder)

| File | Description |
|------|-------------|
| `config_example.py` | Example gem5 configuration using the controller |
| `example_f6_nearest.cc` | Demonstrates decomposing `f_6_nearest(x)` into BBOP operations |
| `test_cost_model.cc` | Standalone test driver for the cost model |
| `daftpum_results.py` | Python parser/display for gem5 simulation output |
| `daftpum_results.html` | Interactive Chart.js visualization (open in browser) |
| `sample_stats.txt` | Sample gem5 stats output (DAFTPUM-LAT configuration) |
| `sample_stats_static.txt` | Sample gem5 stats output (DAFTPUM-STATIC configuration) |
| `sample_output.json` | Sample JSON export from results parser |
| `README.md` | This file |

## Supported BBOP Operations

| Operation | Description | Circuit Used |
|-----------|-------------|--------------|
| `BBOP_ADD` | Element-wise addition | Adder (auto-selected per precision) |
| `BBOP_SUB` | Element-wise subtraction | Adder |
| `BBOP_MUL` | Element-wise multiplication | Multiplier (auto-selected per precision) |
| `BBOP_DIV` | Element-wise division | Multiplier (modeled as multiply) |
| `BBOP_RELU` | Rectified linear unit | ReLU unit |
| `BBOP_CPY` | Element-wise copy | Passthrough |
| `BBOP_RED` | Array reduction (sum) | Adder (pipelined) |

## Verified Circuit Selection

Circuit selection was verified by the test driver against Proteus lookup tables:

### Adder Selection (fastest at each precision)

| Bit-precision | Full | Sklansky | Kogge-Stone | Carry-Select | RBR | Selected |
|---------------|------|----------|-------------|--------------|-----|----------|
| 8-bit | 2,110 ps | 3,152 ps | 2,823 ps | 2,398 ps | 2,194 ps | **Full** |
| 16-bit | 4,022 ps | 4,600 ps | 4,271 ps | 4,342 ps | 2,194 ps | **RBR** |
| 32-bit | 14,161 ps | 5,644 ps | 5,315 ps | 6,934 ps | 2,194 ps | **RBR** |

### Multiplier Selection (fastest at each precision)

| Bit-precision | Full | Sklansky | Carry-Select | RBR | Selected |
|---------------|------|----------|--------------|-----|----------|
| 8-bit | 24,647 ps | 25,911 ps | 22,953 ps | 39,592 ps | **Carry-Select** |
| 16-bit | 151,557 ps | 80,623 ps | 84,983 ps | 97,512 ps | **Sklansky** |

### Energy Scaling

Energy scales linearly with element count (verified: 2.0x ratio at 65k vs 131k elements).

## Cost Model

Latency lookup tables are ported from `util/bbop_manager.c` in the Proteus
repository. Energy formulas match the Proteus cost model.

### Adder Energy Formulas

| Circuit | Formula (nJ) |
|---------|--------------|
| Full | `8.1075 * bp * ceil(size/SIMD) * 0.871` |
| Kogge-Stone | `(0.025*bp^3 + 0.1*bp^2 + 5.5*log2(bp)*log(bp) - 5.5*log(bp) + 18.875*bp - 19) * 0.871 * ceil(size/SIMD)` |
| Sklansky | `(19.5*bp - 10.8*log2(bp) - 0.125) * 0.871 * ceil(size/SIMD)` |
| Carry-Select | `22.1465 * bp * ceil(size/SIMD) * 0.871` |
| RBR | `35.075 * bp * ceil(size/SIMD) * 0.871` |

### Multiplier Energy Formulas

| Circuit | Formula (nJ) |
|---------|--------------|
| Full | `(11*bp^2 - 5*bp - 1) * ceil(size/SIMD) * 0.871` |
| Sklansky/CS | `(4*bp + 0.0075*bp*(bp-1) + 0.0015*bp + bp*(19.15*2*bp + log2(2*bp) - 19)) * ceil(size/SIMD) * 0.871` |
| RBR | `(18.0325*bp^2 + 70.218*bp) * ceil(size/SIMD) * 0.871` |

### ReLU

| Component | Formula |
|-----------|---------|
| Latency | `LAT_SIMDRAM_RELU[bp]` (ps) |
| Energy | `(3*bp + (bp-1) mod 2) * ceil(size/SIMD) * 0.871` |

## Test Driver

Compile and run the standalone cost model tests:

```bash
g++ -std=c++17 -o test_cost_model test_cost_model.cc -lm
./test_cost_model
```

**Test results** (all 5 suites pass):
1. Adder latency: verifies correct circuit selection at 8/16/32-bit
2. Multiplier latency: verifies correct circuit selection at 8/16-bit
3. Energy scaling: verifies linear scaling with element count (2.0x ratio)
4. ReLU latency: verifies 2,401 ps at 16-bit
5. Energy formula: verifies manual calculation matches code

## Results Parser

Parse and display DAFTPUM-LAT statistics from gem5 simulation output:

```bash
# Parse gem5 stats.txt
python daftpum_results.py stats.txt

# Parse gem5 stderr/debug output
python daftpum_results.py --stderr gem5.log

# Generate interactive HTML charts
python daftpum_results.py stats.txt --plot

# Export to JSON
python daftpum_results.py stats.txt --json results.json

# Compare multiple runs side-by-side
python daftpum_results.py --compare run1.txt run2.txt --compare-labels "LAT" "STATIC"
```

### Interactive Visualization

The `--plot` flag generates `daftpum_results.html` with interactive Chart.js charts:
- Bit-precision distribution (bar chart)
- Adder circuit selection (doughnut chart)
- Multiplier circuit selection (doughnut chart)
- Execution summary table

Open in browser: `file:///C:/Users/croqu/Downloads/DCU PROJECT/Implementation/search/week 5-6/gem5-stable/gem5-stable/additional_material/daftpum_results.html`

### Sample Terminal Output

```
======================================================================
  DAFTPUM-LAT Controller Results
  Source: stats.txt
======================================================================

  EXECUTION SUMMARY
  ----------------------------------------
  Total BBOPs executed:             150
  Total latency:               45231.67 ns
  Total energy:                2341.567 nJ
  Average parallelism:             48.3 subarrays

  BIT PRECISION DISTRIBUTION
  ----------------------------------------
   1-bit:     12 (  8.0%) ########
   4-bit:     28 ( 18.7%) ##################
   8-bit:     45 ( 30.0%) ##############################
  12-bit:     32 ( 21.3%) #####################
  16-bit:     21 ( 14.0%) ##############
  32-bit:      4 (  2.7%) ##

  CIRCUIT SELECTION
  ----------------------------------------
  Adders (150 total):
    RBR           :     95 ( 63.3%) ###################
  Multipliers (97 total):
    Sklansky      :     42 ( 43.3%) ############
```

## Integration with gem5

1. Copy C++ files to `gem5/src/mem/daftpum_lat/`
2. Add to `gem5/src/mem/SConscript`:
   ```python
   Source('daftpum_lat/daftpum_lat_controller.cc')
   Source('daftpum_lat/daftpum_subarray_unit.cc')
   SimObject('DaftpumLatController.py')
   ```
3. Build gem5: `scons build/ARM/gem5.opt`
4. Use in configuration script (see `config_example.py`)

## Architecture Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_subarrays` | 64 | Number of DAFTPUM subarrays |
| `simd_width` | 65536 | Elements processed per subarray per cycle |
| `tfaw_enabled` | false | Enable TFAW constraints |
| `aap_latency_ns` | 49.0 | AAP unit latency (ns) |
| `aap_energy_nj` | 0.871 | AAP unit energy (nJ) |
| `max_bit_precision` | 63 | Maximum bit precision |
| `bbop_budget_ns` | 0.0 | Per-bbop latency budget (0=unlimited) |
| `bbop_budget_nj` | 0.0 | Per-bbop energy budget (0=unlimited) |

## Example: f_6_nearest Decomposition

The function `f_6_nearest(x) = min(max((128 + 64x + 16x^2 + 2x^3) / (256 + 32x^2), 0), 1)`
decomposes into 13 BBOP operations (see `example_f6_nearest.cc`):

- 5 BBOP_MUL (x^2, x^3, 64x, 16x^2, 2x^3)
- 4 BBOP_ADD (accumulate numerator terms)
- 1 BBOP_DIV (numerator / denominator)
- 2 BBOP_RELU (clamping to [0, 1])
- 1 BBOP_CPY (output)

## References

- Proteus: [Paper](https://doi.org/10.1145/3579371)
- Proteus repository: `util/bbop_manager.c`, `util/bbop_manager.h`
