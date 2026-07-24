# ============================================================================
# Vivado XSIM Simulation TCL Script (Pong P. Chu Methodology)
# Reference: "FPGA Prototyping with Verilog Examples" (Pong P. Chu)
# ============================================================================

# Create work directory
file mkdir ./sim_workspace
cd ./sim_workspace

puts "--------------------------------------------------------------------------"
puts "  [1/3] Compiling Verilog Sources (xvlog)..."
puts "--------------------------------------------------------------------------"
exec xvlog -work work ../AdderIMPACTZeroApproxOneBit.v
exec xvlog -work work ../full_adder_1bit.v
exec xvlog -work work ../ADD_APPROX.v
exec xvlog -work work ../truncated_adder_top.v
exec xvlog -work work ../tb_ADD_APPROX.v

puts "--------------------------------------------------------------------------"
puts "  [2/3] Elaborating Design (xelab)..."
puts "--------------------------------------------------------------------------"
exec xelab -debug typical work.tb_ADD_APPROX -s tb_ADD_APPROX_snapshot

puts "--------------------------------------------------------------------------"
puts "  [3/3] Running Simulation (xsim)..."
puts "--------------------------------------------------------------------------"
exec xsim tb_ADD_APPROX_snapshot -runall

puts "--------------------------------------------------------------------------"
puts "  Simulation Completed. VCD file saved as tb_ADD_APPROX.vcd"
puts "--------------------------------------------------------------------------"
cd ..
