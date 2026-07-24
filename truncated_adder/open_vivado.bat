@echo off
REM ============================================================================
REM Windows Batch script to generate .xpr project and open it in Vivado GUI
REM ============================================================================

echo ==========================================================================
echo  Creating Vivado Project (.xpr) and Launching GUI...
echo ==========================================================================

cd /d "%~dp0"

where vivado >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Vivado not found on system PATH.
    echo Please run this script inside the Vivado Design Suite Command Prompt.
    pause
    exit /b 1
)

echo [1/2] Creating Vivado Project (.xpr)...
vivado -mode batch -source create_project.tcl

echo [2/2] Opening Vivado GUI with project...
start vivado vivado_project\truncated_adder_project.xpr

echo Done.
