@echo off
setlocal

set GCC=D:\2026.1\Vitis\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe
set SIZE=D:\2026.1\Vitis\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-size.exe

set BSP=D:\azevodo\vitis_test\platform\export\platform\sw\standalone_ps7_cortexa9_0
set HW=D:\azevodo\vitis_test\platform\export\platform\hw
set OUT=D:\azevodo

set FLAGS=-DSDT -mcpu=cortex-a9 -mfloat-abi=soft -O2 -g -U__clang__
set INCLUDES=-I%BSP%\include -I%HW%

echo Compiling startup (ddr_init version)...
%GCC% -mcpu=cortex-a9 -c "%OUT%\ddr_init_startup.S" -o "%OUT%\test_startup.o"
if errorlevel 1 goto :fail

echo Compiling ps7_init.c...
%GCC% %FLAGS% %INCLUDES% -c "%HW%\ps7_init.c" -o "%OUT%\test_ps7_init.o"
if errorlevel 1 goto :fail

echo Compiling combined_main.c...
%GCC% %FLAGS% %INCLUDES% -c "%OUT%\combined_main.c" -o "%OUT%\test_main.o"
if errorlevel 1 goto :fail

echo Linking...
%GCC% %FLAGS% -Wl,--build-id=none -T "%OUT%\lscript_ocm.ld" -nostartfiles "%OUT%\test_startup.o" "%OUT%\test_ps7_init.o" "%OUT%\test_main.o" -lgcc -lc -o "%OUT%\testSoft.elf"
if errorlevel 1 goto :fail

%SIZE% "%OUT%\testSoft.elf"
echo.
echo Build OK: %OUT%\testSoft.elf
goto :end

:fail
echo BUILD FAILED
:end
