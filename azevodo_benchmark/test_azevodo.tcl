# Test script for azevodo_ocm.elf on Zybo Z7-10
connect
targets -set -filter {name =~ "ARM*#0"}
rst -system
fpga -file hw/system_wrapper.bit
dow azevodo_ocm.elf
puts "Running benchmark (waiting 10 seconds)..."
con
after 10000
stop
puts "Results:"
mrd 0x10E000 20
mrd 0x10E640 5
puts "Marker:"
mrd 0x10E020 1
puts "Done."
exit
