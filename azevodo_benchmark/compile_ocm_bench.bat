@echo off
setlocal

set GCC=D:\2026.1\Vitis\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe
set SIZE=D:\2026.1\Vitis\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-size.exe

set BSP=D:\azevodo\vitis_test\platform\export\platform\sw\standalone_ps7_cortexa9_0
set HW=D:\azevodo\vitis_test\platform\export\platform\hw
set SRC=D:\azevodo\vitis_test\app_component\src
set OUT=D:\azevodo

set FLAGS=-DSDT -mcpu=cortex-a9 -mfloat-abi=soft -O2 -g -U__clang__
set INCLUDES=-I%BSP%\include -I%SRC% -I%HW%

echo Compiling startup...
%GCC% -mcpu=cortex-a9 -c "%OUT%\ocm_startup.S" -o "%OUT%\ocm_startup.o"
if errorlevel 1 goto :fail

echo Compiling ps7_init.c...
%GCC% %FLAGS% %INCLUDES% -c "%HW%\ps7_init.c" -o "%OUT%\ocm_ps7_init.o"
if errorlevel 1 goto :fail

echo Compiling combined_main.c...
%GCC% %FLAGS% %INCLUDES% -c "%OUT%\combined_main.c" -o "%OUT%\combined_main.o"
if errorlevel 1 goto :fail

echo Compiling azevodo_bench_ddr.c...
%GCC% %FLAGS% %INCLUDES% -c "%OUT%\azevodo_bench_ddr.c" -o "%OUT%\azevodo_bench_ddr.o"
if errorlevel 1 goto :fail

echo Linking OCM benchmark binary...
%GCC% %FLAGS% -Wl,--build-id=none -T "%OUT%\lscript_ocm.ld" -nostartfiles "%OUT%\ocm_startup.o" "%OUT%\ocm_ps7_init.o" "%OUT%\combined_main.o" "%OUT%\azevodo_bench_ddr.o" -lgcc -lc -o "%OUT%\azevodo_ocm.elf"
if errorlevel 1 goto :fail

%SIZE% "%OUT%\azevodo_ocm.elf"
echo.
echo Build OK: %OUT%\azevodo_ocm.elf
goto :end

:fail
echo BUILD FAILED
:end
