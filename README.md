# DCU Project: FPGA-Accelerated Sigmoid Approximation for Compute-in-Memory

This project implements and benchmarks hardware-accelerated sigmoid function approximations and approximate arithmetic units on the Xilinx Zynq-7010 (Digilent Zybo Z7-10) FPGA platform. The work explores hardware approximation algorithms (Verilog and VHDL) with comprehensive benchmarking infrastructure for evaluating latency, accuracy, power, area, and throughput.

## Overview

The sigmoid function is a fundamental activation function in neural networks and machine learning. This project implements hardware-efficient approximations suitable for FPGA deployment and CNN accelerators:

1. **Azevodo Approximation** (16-bit fixed-point): A piecewise polynomial approximation using Q4.12 fixed-point arithmetic
2. **Vaiṣṇav Approximation** (fast piecewise-linear): A fast, shift-based piecewise-linear approximation using Q4.12 fixed-point arithmetic
3. **Truncated Adder (`ADD_APPROX`)**: Parameterized approximate adder for energy-efficient CNN/Sigmoid compute engines

All implementations are wrapped with AXI4-Lite interfaces and driven by the ARM Cortex-A9 processor on the Zynq SoC, enabling comprehensive performance evaluation.

## Project Structure

```
DCU_Project_CiM_Sigmoid_FPGA/
├── 16 bit Azevedo/              # Azevodo polynomial approximation (Verilog)
│   ├── sigmoid.v                # Core sigmoid datapath (piecewise polynomial)
│   ├── sigmoid_top.v            # AXI4-Lite wrapper
│   ├── main.c                   # Software driver (31-point test)
│   └── build.tcl                # Vivado build script
│
├── fast_Vaisnav16/              # Vaiṣṇav piecewise-linear approximation (VHDL)
│   ├── sigmoid.vhdl             # Core sigmoid datapath (piecewise-linear)
│   ├── pck_definitions.vhdl     # VHDL package with constants
│   ├── sigmoid_top.v            # AXI4-Lite wrapper (Verilog)
│   ├── main.c                   # Software driver (31-point test)
│   ├── sigmoid_bench.c          # Extended benchmark (100-point, DCC output)
│   ├── stimuli_points.h         # Test point definitions
│   └── build.tcl                # Vivado build script
│
├── truncated_adder/             # Parameterized Truncated Adder Module (Verilog)
│   ├── AdderIMPACTZeroApproxOneBit.v # 1-bit zero truncation cell
│   ├── full_adder_1bit.v        # 1-bit accurate full adder cell
│   ├── ADD_APPROX.v             # Parameterized m-bit truncated adder
│   ├── truncated_adder_top.v    # AXI4-Lite slave top wrapper
│   ├── tb_ADD_APPROX.v          # Self-checking testbench (Pong P. Chu methodology)
│   ├── simulate_python.py       # Standalone testbench runner (VCD waveforms)
│   ├── verify_truncated_adder.py# Python MPE & PPA error analysis suite
│   ├── build.tcl                # Vivado 333 MHz synthesis script
│   ├── run_sim.tcl / .bat       # Vivado XSIM simulation scripts
│   └── README.md                # Comprehensive documentation
│
├── azevodo_benchmark/           # Comprehensive benchmark for Azevodo implementation
│   ├── azevodo_bench_ddr.c      # 100-point DDR-based benchmark
│   ├── combined_main.c          # Main with ps7_init + enable_pl + benchmark
│   ├── stimuli_points.h         # 100 test points with ideal values
│   ├── run_benchmark.py         # Python automation script
│   ├── compile_ocm_bench.bat    # Build script (OCM, soft-float)
│   ├── test_azevodo.tcl         # xsdb automation script
│   └── hw/                      # Hardware platform files
│
├── vaisnav_benchmark/           # Comprehensive benchmark for Vaiṣṇav implementation
│   ├── sigmoid_bench_ddr.c     # 100-point DDR-based benchmark
│   ├── combined_main.c          # Main with ps7_init + enable_pl + benchmark
│   ├── stimuli_points.h         # 100 test points with ideal values
│   ├── run_benchmark.py         # Python automation script
│   ├── compile_ocm_bench.bat    # Build script (OCM, soft-float)
│   ├── test_sigmoid.tcl         # xsdb automation script
│   └── hw/                      # Hardware platform files
│
└── additional_material/         # Research materials and references
    ├── week 1-2/                # Initial exploration notebooks
    ├── week 3-4/                # AritPIM simulator (PIM arithmetic research)
    ├── week 5-6/                # Extended analysis notebooks
    └── week 7-8/                # Extended PIM/gem5 simulator exploration
```

## Hardware Implementations

### Azevodo Approximation (16-bit Q4.12 Fixed-Point)

**File**: `16 bit Azevedo/sigmoid.v`

The Azevodo implementation uses a piecewise polynomial approximation with 5 regions:
- Region 1 (x ≤ -5.44): Output = 0
- Region 2 (-5.44 < x ≤ -3.25): Linear approximation
- Region 3 (-3.25 < x ≤ 0): Quadratic approximation
- Region 4 (0 < x ≤ 3.25): Quadratic approximation
- Region 5 (3.25 < x ≤ 5.44): Linear approximation
- Region 6 (x > 5.44): Output = 1

**Key Parameters**:
- Fixed-point format: Q4.12 (4 integer bits, 12 fractional bits)
- Input range: -8.0 to +8.0
- Output range: 0.0 to 1.0
- Polynomial coefficients optimized for minimal error

### Vaiṣṇav Approximation (Fast Piecewise-Linear)

**File**: `fast_Vaisnav16/sigmoid.vhdl`

The Vaiṣṇav implementation uses a fast piecewise-linear approximation based on the absolute value of the input:
- For |x| ≥ 5.0: Output saturates to 0 or 1
- For 2.375 ≤ |x| < 5.0: y = |x|/32 + 0.84375
- For 1.0 ≤ |x| < 2.375: y = |x|/8 + 0.625
- For |x| < 1.0: y = |x|/4 + 0.5

The sign is then applied: if x ≥ 0, y = result; else y = 1 - result.

**Key Parameters**:
- Fixed-point format: Q4.12 (4 integer bits, 12 fractional bits)
- Input range: -8.0 to +8.0
- Output range: 0.0 to 1.0
- Uses only shift operations for efficiency

### Truncated Adder (`ADD_APPROX`)

**File**: `truncated_adder/ADD_APPROX.v`

The Truncated Adder combines $n$ zero-truncation approximate adder cells (`AdderIMPACTZeroApproxOneBit`) at the lower LSBs with $(m-n)$ standard full adders (`full_adder_1bit`) at the upper MSBs:
- Replaces standard 5-gate 1-bit full adders in the LSB section with zero-cost wire/constant logic.
- Preserves signed 2's complement sign extension and carry chaining between stages.
- Parameterized operand width $m$ (default 16) and approximation bits $n$ ($0 \le n \le m$).

---

## Performance Results

### Vaiṣṇav Implementation (100 points, -8.0..+8.0 input range)

| Metric | Value |
|---|---|
| Min latency | 390.5 ns (260 cycles @ 666.7 MHz) |
| Max latency | 1522 ns (1015 cycles) |
| Avg latency | 396.4 ns (264 cycles avg) |
| Avg absolute error | 0.00913 (0.91%) |
| Max absolute error | 0.0179 (1.79%) |

Throughput: ~2.52 Msps (Mega-samples per second)

### Truncated Adder (`ADD_APPROX`) Trade-Off Results

| Approx Bits ($n$) | Cell Count Saved (%) | Area Saved (%) | Power Saved (%) | Mean Percentage Error (%) |
|---|---|---|---|---|
| **2** | 5.26% | 5.46% | 6.32% | **0.83%** |
| **4** | 10.91% | 12.13% | 14.95% | **1.74%** |
| **6** | 16.87% | 18.90% | 23.67% | **2.90%** |
| **8** | 22.12% | 24.58% | 32.22% | **6.89%** |
| **10** | 27.96% | 30.99% | 40.83% | **22.76%** |
| **12** | 35.27% | 36.97% | 49.37% | **82.14%** |
| **14** | 53.40% | 50.58% | 58.41% | **365.00%** |
| **16** | 73.83% | 75.24% | 72.05% | **100.00%** |

---

## Requirements

### Hardware
- **Board**: Digilent Zybo Z7-10 (xc7z010clg400-1)
- **FPGA**: Xilinx Zynq-7010 (ARM Cortex-A9 + Artix-7 FPGA fabric)

### Software Tools
- **Vivado 2026.1**: For FPGA bitstream generation & XSIM simulation
- **Vitis 2026.1**: ARM GCC toolchain for software compilation
- **Python 3**: For benchmark automation and verification
- **xsdb**: Xilinx System Debugger for JTAG communication

### Connection
- JTAG (USB cable) — no UART required for benchmarking

---

## Building and Running

### Quick Start (Truncated Adder Simulation)

```bash
# Run standalone Python testbench runner & VCD waveform generator
python truncated_adder/simulate_python.py

# Run error metrics reproduction script
python truncated_adder/verify_truncated_adder.py

# Run Vivado XSIM simulation (if Vivado is installed)
vivado -mode batch -source truncated_adder/run_sim.tcl
```

### Quick Start (Vaiṣṇav Benchmark)

1. **Generate Bitstream**:
   ```bash
   cd vaisnav_benchmark
   # Open Vivado project, generate bitstream, export to hw/system_wrapper.bit
   ```

2. **Compile Software**:
   ```bash
   compile_ocm_bench.bat
   ```
   This produces `sigmoid_ocm.elf` — a combined binary running from OCM (on-chip memory).

3. **Run Benchmark**:
   ```bash
   xsdb
   source test_sigmoid.tcl
   ```

4. **Analyze Results** (optional):
   ```bash
   python run_benchmark.py
   ```
   This generates CSV output and latency graphs.

### Detailed Instructions

See individual README files in each subdirectory:
- `truncated_adder/README.md` — Detailed Truncated Adder guide and architectural documentation
- `vaisnav_benchmark/README.md` — Detailed Vaiṣṇav benchmark guide
- `azevodo_benchmark/README.md` — Detailed Azevodo benchmark guide

---

## Key Technical Details

### AXI4-Lite Interface

Both sigmoid implementations and the truncated adder top module use standard AXI4-Lite slave interfaces:

| Offset | Register | Direction | Description |
|---|---|---|---|
| 0x00 | X_REG / A_REG | R/W | Input value A (Q4.12) |
| 0x04 | Y_REG / B_REG | R/W | Input value B (Q4.12) |
| 0x08 | CTRL | W | Bit 0 = start computation |
| 0x0C | STATUS | R | Bit 0 = busy, Bit 1 = done |
| 0x10 | SUM_REG | R | Truncated Sum Output |

### Processing Pipeline

The hardware uses a simple 4-stage FSM:
1. **IDLE**: Wait for start command
2. **LOAD**: Load input to sigmoid / adder core
3. **WAIT**: Wait for computation (1 cycle)
4. **STORE**: Store result and assert done

### PS7 Initialization and PL Enable

The benchmark uses bare-metal code that:
1. Calls `ps7_init()` to initialize DDR, PLLs, and clocks
2. Manually enables the PL (FPGA fabric) via `enable_pl()`:
   - Unlocks SLCR registers
   - Configures FCLK_CLK0 to ~47.6 MHz
   - Releases FPGA resets
   - Enables level shifters
3. Runs the benchmark loop

### FPU Caveat

The benchmark compiles with `-mfloat-abi=soft` (software floating-point) because enabling the VFP in startup code causes `ps7_init()` to hang in a DDR poll loop. This is a known issue with the specific startup code configuration.

---

## Sources and Citations

### Primary Algorithm Sources

1. **Truncated Adder Integration in CNN Accelerator**:
   - Lim Qi Yang, Lim Yang Wei, Fakhrul Zaman Rokhani, Noor Ain Kamsani, *"Truncated Adder Integration in a Convolutional Neural Network Approximate Accelerator"*, IEEE ICSyS, 2025.
   - Implemented in `truncated_adder/ADD_APPROX.v`

2. **FPGA Prototyping by Verilog Examples**:
   - Pong P. Chu, *"FPGA Prototyping by Verilog Examples: Xilinx Spartan-3 Version / Artix-7 Version"*, Wiley.
   - Testbench architecture and simulation methodology implemented in `truncated_adder/tb_ADD_APPROX.v` and `run_sim.tcl`

3. **Vaiṣṇav Approximation**:
   - Vaiṣṇav, "Fast Approximate Sigmoid Function for FPGA Implementation"
   - Implemented in `fast_Vaisnav16/sigmoid.vhdl`
   - This work provides a fast, shift-based piecewise-linear approximation suitable for FPGA implementation
   - **Source Repository**: https://github.com/AngeloIFSP/FPGA-implementation-of-sigmoid-approximation-for-neural-networks

4. **Azevodo Approximation**:
   - Azevodo polynomial approximation method
   - Implemented in `16 bit Azevedo/sigmoid.v`
   - Piecewise polynomial approximation with optimized coefficients for Q4.12 fixed-point arithmetic
   - **Source Repository**: https://github.com/AngeloIFSP/FPGA-implementation-of-sigmoid-approximation-for-neural-networks

### Hardware Platform Documentation

5. **Xilinx Zynq-7000 Technical Reference Manual**:
   - Xilinx UG585: Zynq-7000 SoC TRM
   - Referenced for PS7 initialization, SLCR configuration, and AXI4-Lite interface details

6. **Digilent Zybo Z7-10 Reference Manual**:
   - Board-specific documentation for the Zybo Z7-10 platform
   - Hardware specifications and pin mappings

### Related Research

7. **AritPIM: High-Throughput In-Memory Arithmetic**:
   - O. Leitersdorf, D. Leitersdorf, J. Gal, M. Dahan, R. Ronen, and S. Kvatinsky, "AritPIM: High-Throughput In-Memory Arithmetic," IEEE Transactions on Emerging Topics in Computing, 2023.
   - Simulator included in `additional_material/week 3-4/AritPIM-master/`
   - This work explores in-memory arithmetic operations, providing context for compute-in-memory architectures
   - **Source Repository**: https://github.com/oleitersdorf/AritPIM

8. **Proteus: High-Performance Processing-Using-DRAM**:
   - G. F. Oliveira, M. Kabra, Y. Guo, K. Chen, A. G. Yaglikci, M. Soysal, M. Sadrosadati, J. Olivares, S. Ghose, J. Gomez-Luna, and O. Mutlu, "Proteus: Achieving High-Performance Processing-Using-DRAM via Dynamic Precision Bit-Serial Arithmetic," Proceedings of the 37th ACM International Conference on Supercomputing (ICS), 2025.
   - Simulator included in `additional_material/week 3-4/Proteus-main/`
   - This work addresses PUD latency through dynamic bit-precision, adaptive data representation, and flexible arithmetic
   - **Source Repository**: https://github.com/CMU-SAFARI/Proteus

9. **MIMDRAM: End-to-End Processing-Using-DRAM System**:
   - MIMDRAM simulator referenced by Proteus for cycle-level simulation
   - Provides gem5-based simulator infrastructure for PUD systems
   - **Source Repository**: https://github.com/CMU-SAFARI/MIMDRAM

### Development Tools

10. **Xilinx Vivado Design Suite**:
    - Version 2026.1 used for FPGA synthesis and bitstream generation
    - AXI4-Lite IP integration and hardware platform export

11. **Xilinx Vitis Unified Software Platform**:
    - Version 2026.1 ARM GCC toolchain for bare-metal software compilation
    - PS7 initialization libraries and drivers

---

## What Was Done

### Main FPGA Implementation

This project accomplished the following:

1. **Algorithm Implementation**:
   - Translated two sigmoid approximation algorithms (Azevodo and Vaiṣṇav) from literature to hardware description languages (Verilog and VHDL)
   - Implemented parameterized **Truncated Adder** (`ADD_APPROX`) with configurable zero-truncation bits ($n \in \{0..16\}$) based on IEEE ICSyS 2025.
   - Optimized all implementations for 16-bit Q4.12 fixed-point arithmetic
   - Designed AXI4-Lite wrapper modules for processor integration

2. **Simulation & Verification Infrastructure**:
   - Developed self-checking testbenches following Pong P. Chu's *FPGA Prototyping by Verilog Examples* methodology.
   - Created standalone Python testbench runner generating GTKWave VCD waveforms (`simulate_python.py`).
   - Built automated Python error evaluation tools reproducing PPA and MPE metrics from IEEE ICSyS 2025 (`verify_truncated_adder.py`).

3. **Software Development**:
   - Implemented bare-metal drivers for the ARM Cortex-A9 processor
   - Created comprehensive benchmark frameworks with 100-point test suites
   - Developed automated testing infrastructure using xsdb Tcl scripts
   - Built Python automation scripts for result analysis and visualization

4. **Performance Evaluation**:
   - Measured latency (min/max/avg) across input range -8.0 to +8.0
   - Calculated accuracy metrics (absolute error, percentage error)
   - Computed throughput in samples per second
   - Generated latency vs. input graphs for analysis

5. **Build Infrastructure**:
   - Created Vivado build scripts for automated bitstream generation
   - Developed compile scripts for software (both OCM and DDR configurations)
   - Integrated PS7 initialization and PL enable sequences
   - Handled FPU/soft-float compilation issues

6. **Documentation**:
   - Created detailed README files for each implementation
   - Documented register maps, memory layouts, and result formats
   - Provided troubleshooting guides for common issues
   - Maintained comprehensive build and run instructions

### Additional Material Research

The `additional_material/` directory contains research and exploration work related to compute-in-memory architectures and alternative sigmoid implementations:

#### Week 1-2: Initial Exploration
- **master_project_functions.ipynb**: Jupyter notebook for initial function exploration and analysis
- Early-stage investigation of sigmoid approximation methods and their properties

#### Week 3-4: PIM Architecture Research

**AritPIM Extension** (`additional_material/week 3-4/AritPIM-master/`):
- Extended the AritPIM simulator with F6 sigmoid approximation implementation
- Created `f6_dashboard.py` (~2800 lines) implementing rational polynomial approximation:
  - f₆(x) = min(max((120 + 60x + 12x² + x³) / (240 + 24x²), 0), 1)
- Evaluated 10 hybrid architecture strategies (pure serial, pure parallel, and 8 hybrid configurations)
- Tested both fixed-point and floating-point representations (20 total configurations)
- Generated performance metrics: latency, energy, area, throughput (TOPS), energy efficiency (TOPS/W)
- Key findings: Pure Parallel (Fixed) achieved 0.107 TOPS throughput and 0.0042 TOPS/W efficiency
- Created visualization tools: `sigmoid_vs_f6_comparison.png`, `dashboard_comparison.png`

**Proteus Extension** (`additional_material/week 3-4/Proteus-main/`):
- Implemented f₆ sigmoid approximation for Processing-Using-DRAM (PUD) systems
- Compared Taylor series expansion (16 bbop operations) vs f₆ approximation (11 bbop operations)
- Key improvement: Reduced divisions from 5 to 1 (80% reduction), eliminating the most expensive PUD operation
- Achieved 1.3–1.6× improvement in both latency and energy consumption over Taylor sigmoid
- Files added: `f6_sigmoid.c`, `sigmoid_compare_pim.c`, `Makefile.f6`, and plotting scripts
- Generated comparison plots: `f6_sigmoid_benchmark.png`, `f6_vs_sigmoid.png`, `sigmoid_energy_latency_compare.png`
- Accuracy trade-off: Maximum absolute error < 0.01 across full range, < 0.001 for |x| < 2.5

#### Week 5-6: Extended Analysis
- **master_project_functions(1).ipynb**: Extended Jupyter notebook for further analysis
- **ramulator2-main/**: Memory simulator with proteus_f6 integration
  - Contains Ramulator2 memory system simulator
  - Includes proteus_f6 directory with PIM-specific implementations
  - Provides infrastructure for memory system evaluation
