# ============================================================================
# Vivado TCL Synthesis & Bitstream Script for Truncated Adder (ADD_APPROX)
# Board: Digilent Zybo Z7-10 (xc7z010clg400-1)
# Usage: vivado -mode batch -source build.tcl
# Creates: vivado_project/truncated_adder_project.xpr
# Reference: "Truncated Adder Integration in a CNN Accelerator" (Lim Qi Yang et al., 2025)
# ============================================================================

set proj_root [file normalize [file dirname [info script]]]
set ::env(TEMP) [file join $proj_root tmp]
set ::env(TMP) [file join $proj_root tmp]
file mkdir [file join $proj_root tmp]
cd $proj_root

set project_name "truncated_adder_project"
set project_dir "./vivado_project"
set fpga_part "xc7z010clg400-1"
set output_dir "./build_output"

file mkdir $output_dir

puts "=========================================================================="
puts "  [1/5] Creating Vivado Project (.xpr)..."
puts "=========================================================================="

# Create disk-based Vivado project (.xpr)
create_project $project_name $project_dir -part $fpga_part -force

# Downgrade DRC NSTD-1 and UCIO-1 for standalone AXI module bitstream creation
set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
set_property SEVERITY {Warning} [get_drc_checks UCIO-1]

# Read Verilog source files
add_files -norecurse {
    ./AdderIMPACTZeroApproxOneBit.v
    ./full_adder_1bit.v
    ./ADD_APPROX.v
    ./truncated_adder_top.v
}

# Add simulation fileset
add_files -fileset sim_1 -norecurse {
    ./tb_ADD_APPROX.v
}

set_property top truncated_adder_top [current_fileset]
set_property top tb_ADD_APPROX [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

puts "=========================================================================="
puts "  [2/5] Synthesizing Design..."
puts "=========================================================================="

synth_design -top truncated_adder_top -part $fpga_part -mode out_of_context

# Create timing constraints (333 MHz clock target)
create_clock -period 3.000 -name s_axi_aclk [get_ports s_axi_aclk]

puts "=========================================================================="
puts "  [3/5] Optimizing, Placing & Routing..."
puts "=========================================================================="

opt_design
place_design
route_design

puts "=========================================================================="
puts "  [4/5] Generating Utilization & Power Reports..."
puts "=========================================================================="

report_utilization -file "$output_dir/utilization.rpt"
report_timing_summary -file "$output_dir/timing_summary.rpt"
report_power -file "$output_dir/power.rpt"

puts "=========================================================================="
puts "  [5/5] Generating Bitstream..."
puts "=========================================================================="

# Override DRC checks for bitstream generation
set_property SEVERITY {Warning} [get_drc_checks NSTD-1]
set_property SEVERITY {Warning} [get_drc_checks UCIO-1]

write_bitstream -force "$output_dir/truncated_adder_top.bit"

puts "=========================================================================="
puts "  BUILD & BITSTREAM COMPLETE!"
puts "  - Vivado Project File: [file normalize $project_dir/$project_name.xpr]"
puts "  - Bitstream Output   : [file normalize $output_dir/truncated_adder_top.bit]"
puts "  - Synthesis Reports  : [file normalize $output_dir]"
puts "=========================================================================="
