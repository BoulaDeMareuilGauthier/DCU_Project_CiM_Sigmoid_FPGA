# Truncated Adder Module (`truncated_adder`)

This directory contains the Verilog HDL implementation, AXI4-Lite top wrapper, Python verification suite, Vivado synthesis scripts, and theoretical model for the **Truncated Adder** (`ADD_APPROX`), as presented in the paper:

> **"Truncated Adder Integration in a Convolutional Neural Network Approximate Accelerator"**  
> *Lim Qi Yang, Lim Yang Wei, Fakhrul Zaman Rokhani, Noor Ain Kamsani* (2025 IEEE ICSyS)

---

## 1. Overview & Architecture

Approximate computing deliberately introduces controlled arithmetic inaccuracies to achieve substantial hardware power, area, and latency savings with minimal degradation in neural network output accuracy.

The `ADD_APPROX` module combines **$n$ 1-bit approximate adders** at the least significant bit (LSB) positions with **$(m-n)$ 1-bit accurate full adders** at the most significant bit (MSB) positions.

### Structural Diagram
```
        [ A[m-1:n] , B[m-1:n] ]                [ A[n-1:0] , B[n-1:0] ]
                   |                                       |
                   v                                       v
     +---------------------------+           +---------------------------+
     |   (m-n) Accurate Adders   |  <-----   |   n Approximate Adders    |
     |   (full_adder_1bit.v)     |   Carry   |  (AdderIMPACTZeroApprox)  |
     +---------------------------+           +---------------------------+
                   |                                       |
                   v                                       v
            [ Sum[m-1:n] ]                          [ Sum[n-1:0] = 0 ]
```

---

## 2. Directory Structure

```
truncated_adder/
├── AdderIMPACTZeroApproxOneBit.v   # 1-bit zero-truncation approximate adder cell
├── full_adder_1bit.v               # 1-bit accurate full adder cell
├── ADD_APPROX.v                    # Core parameterized m-bit truncated adder module
├── truncated_adder_top.v           # AXI4-Lite slave wrapper for Zynq-7010 FPGA integration
├── tb_ADD_APPROX.v                 # Verilog testbench
├── create_project.tcl              # TCL script to generate Vivado .xpr project file
├── build.tcl                       # Vivado TCL build script (.xpr + synthesis + PPA reports)
├── open_vivado.bat                 # Windows batch launcher for Vivado GUI
├── verify_truncated_adder.py       # Python error analysis & benchmark reproduction script
├── simulate_python.py              # Testbench simulator generating VCD waveforms
└── README.md                       # Documentation (this file)
```

---

## 3. Creating & Opening Vivado Project (`.xpr`)

### Option A: Create `.xpr` Project File via Command Line
Run the following command in Vivado Command Prompt or terminal:
```bash
vivado -mode batch -source truncated_adder/create_project.tcl
```
This generates the Vivado project file at:  
`truncated_adder/vivado_project/truncated_adder_project.xpr`

### Option B: Build Project & Perform Full Synthesis
```bash
vivado -mode batch -source truncated_adder/build.tcl
```
This creates the `.xpr` project, runs synthesis, placement, routing, and exports PPA reports into `truncated_adder/build_output/`.

### Option C: Double-Click Launcher (Windows)
Double-click `truncated_adder/open_vivado.bat` to build the `.xpr` file and launch the Vivado GUI automatically.

---

## 4. Register Map (AXI4-Lite)

| Address Offset | Register Name | Access | Description |
|---|---|---|---|
| `0x00` | `A_REG` | R/W | Input Operand A (Bits `[DATA_WIDTH-1:0]`, Q4.12 Fixed-Point) |
| `0x04` | `B_REG` | R/W | Input Operand B (Bits `[DATA_WIDTH-1:0]`, Q4.12 Fixed-Point) |
| `0x08` | `CTRL_REG` | W | Bit 0 = Start calculation |
| `0x0C` | `STATUS_REG` | R | Bit 0 = Busy, Bit 1 = Done |
| `0x10` | `SUM_REG` | R | Truncated Sum Result (`[DATA_WIDTH-1:0]`) |

---

## 5. Benchmark Performance & PPA Trade-Offs

| Approx Bits ($n$) | Cell Saved (%) | Area Saved (%) | Power Saved (%) | Paper Mean Error (%) | Python Sim Mean Error (%) |
|---|---|---|---|---|---|
| **2** | 5.26% | 5.46% | 6.32% | **0.83%** | 0.16% |
| **4** | 10.91% | 12.13% | 14.95% | **1.74%** | 1.42% |
| **6** | 16.87% | 18.90% | 23.67% | **2.90%** | 3.33% |
| **8** | 22.12% | 24.58% | 32.22% | **6.89%** | 13.14% |
| **10** | 27.96% | 30.99% | 40.83% | **22.76%** | 74.06% |
| **12** | 35.27% | 36.97% | 49.37% | **82.14%** | 225.19% |
| **14** | 53.40% | 50.58% | 58.41% | **365.00%** | 1174.83% |
| **16** | 73.83% | 75.24% | 72.05% | **100.00%** | 99.96% |
