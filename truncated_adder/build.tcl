# ============================================================================
# Vivado TCL Build Script for Truncated Adder (ADD_APPROX / truncated_adder_top)
# Board: Digilent Zybo Z7-10 (xc7z010clg400-1)
# Clock Target: 333 MHz (3.0 ns period)
# Reference: "Truncated Adder Integration in a CNN Accelerator" (Lim Qi Yang et al., 2025)
# ============================================================================

set project_name "truncated_adder_synth"
set part_number "xc7z010clg400-1"
set output_dir "./build_output"

# Create build output directory
file mkdir $output_dir

# Create in-memory project
create_project -in_memory -part $part_number

# Read Verilog source files
read_verilog [file normalize "./AdderIMPACTZeroApproxOneBit.v"]
read_verilog [file normalize "./full_adder_1bit.v"]
read_verilog [file normalize "./ADD_APPROX.v"]
read_verilog [file normalize "./truncated_adder_top.v"]

# Set top module
set_property top truncated_adder_top [current_fileset]

# Synthesize design
synth_design -top truncated_adder_top -part $part_number -mode out_of_context

# Create timing constraints (333 MHz clock target)
create_clock -period 3.000 -name s_axi_aclk [get_ports s_axi_aclk]

# Opt design and Place & Route
opt_design
place_design
route_design

# Write utilization and timing reports
report_utilization -file "$output_dir/utilization.rpt"
report_timing_summary -file "$output_dir/timing_summary.rpt"
report_power -file "$output_dir/power.rpt"

puts "=========================================================================="
puts "  Synthesis & Implementation Complete for Truncated Adder Module"
puts "  Reports saved in $output_dir/"
puts "=========================================================================="
