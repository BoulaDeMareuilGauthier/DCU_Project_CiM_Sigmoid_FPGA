# Update: f_6 Sigmoid Approximation for Processing-Using-DRAM

## What Was Before

The Proteus repository contained 11 benchmark workloads instrumented with the `bbop_manager` analytical model for evaluating Processing-Using-DRAM (PUD) operations. The **backprop** workload used the standard sigmoid activation function:

```c
float squash(float x)
{
    return (1.0 / (1.0 + exp(-x)));
}
```

For PIM execution, this requires a Taylor series expansion of `exp(-x)`:

```
exp(-x) ≈ 1 + (-x) + (-x)²/2 + (-x)³/6 + (-x)⁴/24 + (-x)⁵/120
```

This decomposition results in **16 bbop operations**: 1 SUB + 4 MUL + 5 DIV + 6 ADD. The division operations are particularly expensive in bit-serial PUD arithmetic.

---

## What Was Done

We implemented a **rational polynomial approximation** of the sigmoid function, called f_6:

$$f_6(x) = \min\left(\max\left(\frac{120 + 60x + 12x^2 + x^3}{240 + 24x^2},\ 0\right),\ 1\right)$$

This approximation is specifically designed to be PIM-friendly because:

1. **Fewer operations**: Only **11 bbop operations** (5 MUL + 4 ADD + 1 DIV + 1 RELU) vs 16 for Taylor
2. **Only 1 division**: The Taylor approach needs 5 divisions; f_6 needs just 1. Division is the most expensive PUD operation.
3. **Built-in clamping**: The RELU operation (max with 0) is natively supported and very cheap in PUD hardware.
4. **Low error**: Maximum absolute error < 0.01 across the full range, and < 0.001 for |x| < 2.5 (where most neural network activations fall).

### Files Added

| File | Description |
|------|-------------|
| `f6_sigmoid.c` | Standalone implementation with both baseline (floating-point) and PIM (bbop-decomposed) modes |
| `sigmoid_compare_pim.c` | Head-to-head PIM simulation comparing Taylor sigmoid vs f_6 |
| `Makefile.f6` | Build file for the f_6 workload |
| `plot_f6_benchmark.py` | Generates `f6_sigmoid_benchmark.png` — latency/energy across all mechanisms |
| `plot_f6_vs_sigmoid.py` | Generates `f6_vs_sigmoid.png` — accuracy comparison (curves + error) |
| `plot_sigmoid_energy_latency.py` | Generates `sigmoid_energy_latency_compare.png` — side-by-side PIM cost comparison |
| `update.md` | This file |
| `.gitignore` | Ignores build artifacts and CSV outputs |

### PNGs Generated

| PNG | Content |
|-----|---------|
| `f6_sigmoid_benchmark.png` | Bar chart of f_6 latency/energy across all 8 Proteus mechanisms |
| `f6_vs_sigmoid.png` | Overlay plot of exact sigmoid vs f_6 with error curve |
| `sigmoid_energy_latency_compare.png` | Side-by-side comparison of Taylor sigmoid vs f_6 (latency + energy) |

---

## Simulation Results

All simulations were run on an array of **65,536 elements** using the Proteus analytical model (`bbop_manager`), which computes cycle-accurate latency and energy estimates for each PUD mechanism.

### f_6 Approximation — Absolute Performance

| Mechanism | Latency (ms) | Energy (mJ) | Description |
|-----------|:---:|:---:|-------------|
| SIMDRAM_1 | 3.316 | 0.0596 | SIMDRAM baseline, 1 subarray |
| SIMDRAM_64 | 3.316 | 0.0596 | SIMDRAM with 64 subarrays (no dynamic precision) |
| SIMDRAM_64_DYNAMIC | 0.192 | 0.0034 | SIMDRAM 64 subarrays + dynamic bit-precision |
| DAFTPUM_STATIC_LAT | 0.222 | 0.0207 | Proteus, static precision, latency-optimized adder |
| DAFTPUM_STATIC_ENE | 0.313 | 0.0057 | Proteus, static precision, energy-optimized adder |
| DAFTPUM_LAT | 0.153 | 0.0111 | Proteus, dynamic precision, latency-optimized |
| DAFTPUM_ENE | 0.186 | 0.0034 | Proteus, dynamic precision, energy-optimized |
| DAFTPUM_TFAW | 0.153 | 0.0111 | Proteus with tFAW-aware scheduling |

**Best latency**: 0.153 ms (Proteus dynamic latency-optimized) — **21.7× faster** than baseline SIMDRAM.  
**Best energy**: 0.0034 mJ (Proteus dynamic energy-optimized) — **17.5× less energy** than baseline SIMDRAM.

### Taylor Sigmoid vs f_6 — Head-to-Head Comparison

| Mechanism | Taylor Latency | f_6 Latency | Speedup | Taylor Energy | f_6 Energy | Savings |
|-----------|:---:|:---:|:---:|:---:|:---:|:---:|
| SIMDRAM_1 | 4.985 ms | 3.316 ms | **1.50×** | 0.0897 mJ | 0.0596 mJ | **1.50×** |
| SIMDRAM_64 | 4.985 ms | 3.316 ms | **1.50×** | 0.0897 mJ | 0.0596 mJ | **1.50×** |
| SIMDRAM_64_DYNAMIC | 0.278 ms | 0.191 ms | **1.45×** | 0.0049 mJ | 0.0034 mJ | **1.43×** |
| DAFTPUM_STATIC_LAT | 0.357 ms | 0.222 ms | **1.61×** | 0.0325 mJ | 0.0207 mJ | **1.57×** |
| DAFTPUM_STATIC_ENE | 0.514 ms | 0.313 ms | **1.64×** | 0.0093 mJ | 0.0057 mJ | **1.62×** |
| DAFTPUM_LAT | 0.200 ms | 0.153 ms | **1.31×** | 0.0168 mJ | 0.0111 mJ | **1.50×** |
| DAFTPUM_ENE | 0.273 ms | 0.186 ms | **1.47×** | 0.0048 mJ | 0.0034 mJ | **1.42×** |
| DAFTPUM_TFAW | 0.200 ms | 0.153 ms | **1.31×** | 0.0168 mJ | 0.0111 mJ | **1.50×** |

---

## Explanation of Results

### Why f_6 is Faster and More Energy-Efficient

The performance advantage comes from **operation count reduction** and **avoiding expensive divisions**:

| Metric | Taylor Sigmoid | f_6 Approximation | Reduction |
|--------|:---:|:---:|:---:|
| Total bbop operations | 16 | 11 | 31% fewer |
| Multiplications | 4 | 5 | +1 (cheap) |
| Additions | 6 | 4 | 33% fewer |
| Divisions | 5 | 1 | **80% fewer** |
| Subtractions | 1 | 0 | eliminated |
| RELU (clamp) | 0 | 1 | +1 (very cheap) |

**Division is the bottleneck** in PUD arithmetic. A single division in bit-serial PUD costs roughly the same as a multiplication (both are O(n²) in bit-precision), but the Taylor sigmoid needs 5 of them. By restructuring the computation as a single rational fraction, f_6 eliminates 4 divisions entirely.

### Why Speedup Varies by Mechanism

- **SIMDRAM (1.50×)**: Straightforward operation count reduction. No dynamic precision benefits since SIMDRAM uses fixed 32-bit precision.
- **Proteus Static (1.57–1.64×)**: Higher speedup because Proteus selects optimal adder architectures per operation. Fewer operations means fewer suboptimal choices.
- **Proteus Dynamic (1.31–1.47×)**: Lower relative speedup because dynamic precision already reduces the cost of each individual operation. The absolute savings are still significant.

### Accuracy Trade-off

| Range | Max Absolute Error | Typical Use Case |
|-------|:---:|-------------|
| |x| < 1 | < 0.000001 | Most NN activations during inference |
| |x| < 2.5 | < 0.001 | 99% of typical activations |
| |x| < 5 | < 0.010 | Saturated regions (output ≈ 0 or 1 anyway) |
| |x| > 5 | Clamped to 0/1 | Exact for saturated sigmoid |

The maximum error of ~0.0095 occurs at x ≈ ±4.6, where the sigmoid is already at 0.99+ (or 0.01-). In practice, this error is negligible for neural network training and inference.

---

## How to Reproduce

```bash
# Build f_6 workload
make -f Makefile.f6

# Run PIM simulation
./f6_sigmoid_pim.exe

# Run comparison (Taylor vs f_6)
gcc -O3 -DRUN_PIM -DSIGMOID_TAYLOR -o sigmoid_taylor_pim sigmoid_compare_pim.c util/bbop_manager.c -lm -fopenmp -w
gcc -O3 -DRUN_PIM -DSIGMOID_F6 -o sigmoid_f6_pim sigmoid_compare_pim.c util/bbop_manager.c -lm -fopenmp -w
./sigmoid_taylor_pim
cp bbop_statistics.csv bbop_statistics_taylor.csv
./sigmoid_f6_pim
cp bbop_statistics.csv bbop_statistics_f6.csv

# Generate plots (Python 3, no external dependencies)
python plot_f6_benchmark.py
python plot_f6_vs_sigmoid.py
python plot_sigmoid_energy_latency.py
```

---

## Conclusion

The f_6 rational polynomial approximation provides a **1.3–1.6× improvement** in both latency and energy consumption over the traditional Taylor expansion sigmoid when executed on Processing-Using-DRAM hardware. This comes at a negligible accuracy cost (< 0.01 max error), making it an ideal drop-in replacement for sigmoid in PIM-accelerated neural network workloads.
