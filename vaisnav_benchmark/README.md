# fast_Vaisnav16 — FPGA-Accelerated Sigmoid Approximation (Zybo Z7-10)

Hardware-accelerated sigmoid function using a fast, piecewise-linear approximation on the Xilinx Zynq-7010 (Zybo Z7-10). The PL (FPGA) implements the sigmoid datapath; the PS (ARM Cortex-A9) drives it via AXI4-Lite and measures latency/accuracy across 100 test points.

## Results (100 points, -8.0..+8.0 input range)

| Metric | Value |
|---|---|
| Min latency | 390.5 ns (260 cycles @ 666.7 MHz) |
| Max latency | 1522 ns (1015 cycles) |
| Avg latency | 396.4 ns (264 cycles avg) |
| Avg absolute error | 0.00913 (0.91%) |
| Max absolute error | 0.0179 (1.79%) |

## Requirements

- **Board:** Digilent Zybo Z7-10 (xc7z010clg400-1)
- **Tools:** Vivado 2026.1 (for bitstream), Vitis 2026.1 ARM GCC toolchain (for software)
- **Connection:** JTAG (USB cable) — no UART needed

## File Structure

```
final_git/
├── README.md                        # This file
├── ocm_startup.S                    # CPU startup: disable MMU, set SP, jump to main
├── combined_main.c                  # main(): ps7_init() + enable_pl() + benchmark_main()
├── sigmoid_bench_ddr.c              # Benchmark: 100-point sweep, results to DDR
├── stimuli_points.h                 # 100 test points (x_raw + ideal values)
├── compile_ocm_bench.bat            # Build script (soft-float, OCM-only binary)
├── lscript_ocm.ld                   # Linker script (OCM 0x0–0x30000)
├── test_sigmoid.tcl                 # xsdb Tcl script for automated testing
├── sigmoid_top.v                    # AXI4-Lite wrapper (top-level Verilog)
├── sigmoid.vhdl                     # Sigmoid approximation datapath (VHDL)
├── pck_definitions.vhdl             # Package with constants/types
├── hw/
│   ├── system_wrapper.bit           # PL bitstream
│   ├── system_wrapper.xsa           # Hardware platform descriptor
│   ├── ps7_init.c                   # PS initialization (DDR, PLLs, clocks)
│   └── ps7_init.h                   # PS init header
```

## How to Build

### 1. Bitstream (Vivado)

Open the Vivado project, generate bitstream, export to `hw/system_wrapper.bit` and `hw/system_wrapper.xsa`.

### 2. Software Binary

Run `compile_ocm_bench.bat` from a Visual Studio Command Prompt or any shell with `arm-none-eabi-gcc` in PATH:

```
compile_ocm_bench.bat
```

This produces `sigmoid_ocm.elf` — a combined binary containing ps7_init, enable_pl, and the benchmark, all running from OCM (on-chip memory, 0x0–0x30000).

**Note:** The build uses `-mfloat-abi=soft` because the FPU (VFP) is not enabled in the startup code. Enabling the VFP in startup (CPACR write + ISB) causes ps7_init's DDR poll loop to hang. See [FPU Caveat](#fpu-caveat) below.

## How to Run (xsdb)

1. Connect the board via USB and launch xsdb:
   ```
   xsdb
   ```

2. Run the test script or type commands manually:

   **Script:**
   ```
   source test_sigmoid.tcl
   ```

   **Manual:**
   ```
   connect
   targets -set -filter {name =~ "ARM*#0"}
   rst -system
   fpga -file hw/system_wrapper.bit
   dow sigmoid_ocm.elf
   con
   ```

3. Wait ~5 seconds for the benchmark to complete (100 iterations at 666 MHz), then stop:

   ```
   stop
   ```

4. Read results:

   ```
   mrd 0x10E000 410
   mrd 0x10E640 5    # summary statistics
   ```

### Results Format

#### Per-point results (0x10E000–0x10E63F, 400 words = 100 points × 4)

For point `i` (0-based), four 32-bit words:

| Offset | Content |
|---|---|
| `0x10E000 + i*16 + 0` | cycles_buf[i] (raw CPU cycle count) |
| `0x10E000 + i*16 + 4` | y_f (measured sigmoid output, IEEE 754 float) |
| `0x10E000 + i*16 + 8` | ideal (expected output, IEEE 754 float) |
| `0x10E000 + i*16 + 12` | abs_error (float) |

#### Summary at 0x10E640 (5 words)

| Offset | Content | Scaling |
|---|---|---|
| `0x10E640` | lat_min × 1000 | picoseconds |
| `0x10E644` | lat_max × 1000 | picoseconds |
| `0x10E648` | lat_avg × 1000 | picoseconds |
| `0x10E64C` | err_avg × 1,000,000 | micro-units (1e-6) |
| `0x10E650` | err_max × 1,000,000 | micro-units (1e-6) |

#### Marker at 0x10E020

- `0xDEADBEEF` = benchmark started
- `0xFFFFFFFF` = benchmark completed

## Key Technical Details

### Enable PL (FCLK, Resets, Level Shifters)

`ps7_init()` does **not** call `ps7_post_config()`. After `ps7_init()`, the FPGA fabric has no clock, resets are asserted, and level shifters are disabled. Function `enable_pl()` in `combined_main.c` manually:

1. Unlocks SLCR (0xF8000008 ← 0xDF0D)
2. Sets FCLK_CLK0_CTRL.DIVISOR0 = 7 → ~47.6 MHz from ARM PLL
3. Releases FPGA resets (FPGA_RST_CTRL = 0x0)
4. Enables level shifters (LVL_SHFTR_EN = 0xF)
5. Relocks SLCR (0xF8000004 ← 0x767B)

### STATUS_DONE is a One-Cycle Pulse

The PL's STATUS register bit 1 (DONE) asserts for exactly one clock cycle when computation completes. The CPU cannot poll it reliably. Instead, after writing CTRL_START, execute a DSB barrier then read Y directly:

```c
Xil_Out32(SIGMOID_BASE + REG_CTRL, CTRL_START);
__asm__ volatile("dsb" ::: "memory");
uint32_t y = Xil_In32(SIGMOID_BASE + REG_Y);
```

### D-Cache Coherency

JTAG `dow -data` writes bypass the D-cache. After `ps7_init()` enables D-cache, JTAG writes to DDR may not be visible to the CPU. The startup code disables the MMU but does not explicitly disable D-cache. For this project, results are written to DDR by the CPU, so coherency is not an issue.

### No DDR Before ps7_init

Writing to any DDR address (including the marker at 0x10E020) before `ps7_init()` completes causes a bus lock because the DDR controller is uninitialized.

### FPU Caveat

The benchmark uses `float` for post-processing statistics. Compiling with `-mfloat-abi=hard -mfpu=vfpv3` and enabling the VFP in startup (CPACR bits 20–23 = 0xF) causes `ps7_init()` to hang in a DDR poll loop. The root cause is unclear but reproducible. Workaround: compile with `-mfloat-abi=soft` (software float via libgcc) and do **not** enable CP10/CP11 in the startup code.

## Expected Output (Example)

```
xsdb% mrd 0x10E000 410
  10E000: 00000140   3E95E000   3E9B0E1B   3C35C360
  ... (400 words of per-point data)
  10E640: 0005F94B   001752FF   00060A8D   000023AA
  10E650: 000045EB
xsdb% mrd 0x10E020 1
  10E020: FFFFFFFF
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| JTAG connection lost (DAP error 0xF0000021) | Bus hang from accessing PL without bitstream, or DDR write before ps7_init | `rst -system`, reload bitstream, ensure DDR writes only after ps7_init |
| CPU at address > 0x3FFFF in OCM range | CPU executing uninitialised OCM high mirror (0xFFFC0000+) | Check startup code — MMU must be disabled before any branch |
| Marker shows 0xCCCC0002 or 0xBBBB0001 but not 0xDEADBEEF | ps7_init completed but benchmark didn't start | Check ps7_init return value, verify enable_pl() runs |
| Benchmark stuck at 0x18c (subs r3,r3,#1) | ps7_config DDR poll loop — hardware condition not met | Usually benign timeout; wait longer or check hardware reset sequence |
| Marker shows 0xCAFEBABE (or residual data) | DDR retains data from previous run across `rst -system` | Not an error; data is valid for the current run |

## References

- Vaiṣṇav, "Fast Approximate Sigmoid Function for FPGA Implementation"
- Xilinx UG585: Zynq-7000 TRM
- Digilent Zybo Z7-10 Reference Manual
