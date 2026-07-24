@echo off
REM ============================================================================
REM Windows Batch Launcher for Vivado / Python Simulation of Truncated Adder
REM Reference: "FPGA Prototyping with Verilog Examples" (Pong P. Chu)
REM ============================================================================

echo ==========================================================================
echo  Truncated Adder Simulation Launcher (Pong P. Chu Methodology)
echo ==========================================================================

where vivado >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Vivado detected on PATH. Launching Vivado XSIM simulation...
    vivado -mode batch -source run_sim.tcl
    goto END
)

where iverilog >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Icarus Verilog detected. Running iverilog simulation...
    iverilog -o sim_tb.vvp AdderIMPACTZeroApproxOneBit.v full_adder_1bit.v ADD_APPROX.v truncated_adder_top.v tb_ADD_APPROX.v
    vvp sim_tb.vvp
    goto END
)

echo [INFO] Running standalone Python simulation runner...
python simulate_python.py

:END
echo ==========================================================================
echo  Simulation process complete.
echo ==========================================================================
pause
