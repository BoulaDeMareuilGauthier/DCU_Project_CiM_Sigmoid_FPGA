# azevodo_benchmark — FPGA-Accelerated Sigmoid Approximation (Zybo Z7-10)

Hardware-accelerated sigmoid function using a fast approximation (Azevodo) on the Xilinx Zynq-7010 (Zybo Z7-10). The PL (FPGA) implements the sigmoid datapath in Verilog; the PS (ARM Cortex-A9) drives it via AXI4-Lite and measures latency/accuracy across 100 test points.

## File Structure

```
azevodo_benchmark/
├── README.md                            # This file
├── ocm_startup.S                        # CPU startup: disable MMU, set SP, jump to main
├── combined_main.c                      # main(): ps7_init() + enable_pl() + benchmark_main()
├── azevodo_bench_ddr.c                  # Benchmark: 100-point sweep, results to DDR
├── stimuli_points.h                     # 100 test points (x_raw + ideal values)
├── compile_ocm_bench.bat                # Build script (soft-float, OCM-only binary)
├── compile_soft_test.bat                # Build script (DDR, soft-float ELF test binary)
├── lscript_ocm.ld                       # Linker script (OCM 0x0–0x30000)
├── ddr_init_startup.S                   # Startup for DDR-based test binary
├── test_azevodo.tcl                     # xsdb Tcl script for automated testing
├── azevodo_top.v                        # AXI4-Lite wrapper (top-level Verilog)
├── azevodo.v                            # Sigmoid approximation datapath (Verilog)
├── hw/
│   ├── system_wrapper.bit               # PL bitstream
│   ├── system_wrapper.xsa               # Hardware platform descriptor
│   ├── ps7_init.c                       # PS initialization (DDR, PLLs, clocks)
│   └── ps7_init.h                       # PS init header
```

## Requirements

- **Board:** Digilent Zybo Z7-10 (xc7z010clg400-1)
- **Tools:** Vivado 2026.1 (for bitstream), Vitis 2026.1 ARM GCC toolchain (for software)
- **Connection:** JTAG (USB cable) — no UART needed

## How to Build

### 1. Bitstream (Vivado)

Open the Vivado project, generate bitstream, export to `hw/system_wrapper.bit` and `hw/system_wrapper.xsa`.

### 2. Software Binary

Run `compile_ocm_bench.bat` from a Visual Studio Command Prompt or any shell with `arm-none-eabi-gcc` in PATH:

```
compile_ocm_bench.bat
```

This produces `azevodo_ocm.elf` — a combined binary running from OCM.

## How to Run (xsdb)

1. Connect the board via USB and launch xsdb.
2. Run the test script:
   ```
   source test_azevodo.tcl
   ```
3. Read results via `mrd 0x10E000 410`.

See `vaisnav_benchmark/README.md` for detailed register layout and troubleshooting.
