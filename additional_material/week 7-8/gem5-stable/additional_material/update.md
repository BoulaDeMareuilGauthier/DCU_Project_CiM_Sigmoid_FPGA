# DAFTPUM-LAT Controller - Implementation Update

## Project Summary

Implementation of the DAFTPUM-LAT (Latency-Optimized) configuration from the
Proteus Processing-Using-DRAM architecture for gem5 simulator.

## What Was Implemented

### 1. C++ Controller Source Files

| File | Purpose |
|------|---------|
| `daftpum_types.hh` | Shared enums (BbopOp, AdderType, MultiplierType), structs (AapParams, BbopCostResult), constants |
| `daftpum_subarray_unit.hh/cc` | Per-subarray execution unit with local precision detection and circuit selection |
| `daftpum_lat_controller.hh/cc` | Main controller: BRAM read/write, cost model, parallel execution, completion events |
| `DaftpumLatController.py` | gem5 SimObject Python configuration |

**Location**: `C:\Users\croqu\daftpum_lat_controller\`

### 2. Additional Materials (this folder)

| File | Purpose |
|------|---------|
| `config_example.py` | Example gem5 configuration using the controller |
| `example_f6_nearest.cc` | BBOP decomposition of f_6_nearest(x) into 13 operations |
| `test_cost_model.cc` | Standalone test driver verifying cost model against Proteus data |
| `daftpum_results.py` | Python parser/display for gem5 simulation output |
| `daftpum_results.html` | Interactive Chart.js visualization |
| `sample_stats.txt` | Sample gem5 stats (DAFTPUM-LAT configuration) |
| `sample_stats_static.txt` | Sample gem5 stats (DAFTPUM-STATIC configuration) |
| `sample_output.json` | Sample JSON export |

## DAFTPUM-LAT Key Properties

- **Dynamic bit-precision**: Scans data at runtime to find narrow values (e.g., 8-bit vs 32-bit)
- **Latency-optimized circuits**: Auto-selects fastest adder/multiplier per precision
- **64-subarray parallelism**: Partitions bulk operations across all DRAM subarrays
- **No TFAW constraints**: This configuration does not enforce Timing-FAW

## Verified Circuit Selection

### Adders

| Precision | Full | Sklansky | Kogge-Stone | Carry-Select | RBR | Winner |
|-----------|------|----------|-------------|--------------|-----|--------|
| 8-bit | 2,110 ps | 3,152 ps | 2,823 ps | 2,398 ps | 2,194 ps | **Full** |
| 16-bit | 4,022 ps | 4,600 ps | 4,271 ps | 4,342 ps | 2,194 ps | **RBR** |
| 32-bit | 14,161 ps | 5,644 ps | 5,315 ps | 6,934 ps | 2,194 ps | **RBR** |

### Multipliers

| Precision | Full | Sklansky | Carry-Select | RBR | Winner |
|-----------|------|----------|--------------|-----|--------|
| 8-bit | 24,647 ps | 25,911 ps | 22,953 ps | 39,592 ps | **Carry-Select** |
| 16-bit | 151,557 ps | 80,623 ps | 84,983 ps | 97,512 ps | **Sklansky** |

## Test Results

All 5 test suites pass:
1. Adder latency at 8/16/32-bit
2. Multiplier latency at 8/16-bit
3. Energy scaling (2.0x ratio verified)
4. ReLU latency (2,401 ps at 16-bit)
5. Energy formula verification

## Usage

### Compile and run tests
```bash
cd C:\Users\croqu\daftpum_lat_controller
g++ -std=c++17 -o test_cost_model.exe test_cost_model.cc -lm
test_cost_model.exe
```

### Parse gem5 results
```bash
python daftpum_results.py stats.txt
python daftpum_results.py stats.txt --plot
python daftpum_results.py stats.txt --json results.json
python daftpum_results.py --compare run1.txt run2.txt
```

### Open interactive visualization
```
file:///C:/Users/croqu/Downloads/DCU PROJECT/Implementation/search/week 5-6/gem5-stable/gem5-stable/additional_material/daftpum_results.html
```

## Integration with gem5

1. Copy C++ files to `gem5/src/mem/daftpum_lat/`
2. Add to `gem5/src/mem/SConscript`:
   ```python
   Source('daftpum_lat/daftpum_lat_controller.cc')
   Source('daftpum_lat/daftpum_subarray_unit.cc')
   SimObject('DaftpumLatController.py')
   ```
3. Build: `scons build/ARM/gem5.opt`
4. Use `config_example.py` as reference

## Cost Model Data Sources

- Latency tables: `util/bbop_manager.c` in Proteus repository
- Energy formulas: Match Proteus cost model
- AAP constants: `AAP_ENERGY = 0.871 pJ`, `AAP_LATENCY = 49 ns`
- Architecture: `SIMD_WIDTH = 65536`, `SUBARRAYS = 64`

## Mitchell's Approximate Method vs DAFTPUM-LAT

Comparison of Mitchell's logarithmic approximate multiplier/divider with
DAFTPUM-LAT exact multipliers.

### Key Results

| Metric | Mitchell | DAFTPUM-LAT | Ratio |
|--------|----------|-------------|-------|
| Latency (16-bit) | 13.93 ns | 77.23 ns | **5.5x faster** |
| Energy (16-bit) | 0.452 nJ | 8.402 nJ | **94.6% savings** |
| Max error (mul) | 11.10% | 0% | - |
| Avg error (mul) | 3.88% | 0% | - |
| Hardware | Shift + add | Full multiplier array | Simpler |

### When to Use Each

**Mitchell's Method:**
- Error-tolerant applications (ML inference, image processing)
- Ultra-low-power constraints
- When ~10% error is acceptable

**DAFTPUM-LAT Exact Multipliers:**
- Precision-critical applications
- When exact results are required
- Dynamic data with varying precision needs

### Files

- `mitchell_vs_daftpumlat.cc` - Comparison implementation and tests
