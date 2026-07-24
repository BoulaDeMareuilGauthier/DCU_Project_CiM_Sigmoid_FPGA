# ============================================================================
# Vivado TCL Project Creator for Truncated Adder (ADD_APPROX)
# Generates a GUI-openable Vivado Project (.xpr) for Zynq-7010 (Zybo Z7-10)
# Usage: vivado -mode batch -source create_project.tcl
# ============================================================================

set proj_root [file normalize [file dirname [info script]]]
set ::env(TEMP) [file join $proj_root tmp]
set ::env(TMP) [file join $proj_root tmp]
file mkdir [file join $proj_root tmp]
cd $proj_root

set project_name "truncated_adder_project"
set project_dir "./vivado_project"
set fpga_part "xc7z010clg400-1"

puts "=========================================================================="
puts "  Creating Vivado Project (.xpr): $project_name in $project_dir"
puts "=========================================================================="

# Create Vivado Project (.xpr) on disk
create_project $project_name $project_dir -part $fpga_part -force

# Add HDL Design Sources (sources_1)
add_files -norecurse {
    ./AdderIMPACTZeroApproxOneBit.v
    ./full_adder_1bit.v
    ./ADD_APPROX.v
    ./truncated_adder_top.v
}

# Add Simulation Testbench (sim_1)
add_files -fileset sim_1 -norecurse {
    ./tb_ADD_APPROX.v
}

# Set Top Module for Synthesis and Simulation
set_property top truncated_adder_top [current_fileset]
set_property top tb_ADD_APPROX [get_filesets sim_1]

# Update Compile Order
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1

puts "=========================================================================="
puts "  SUCCESS: Vivado Project Created!"
puts "  Project File: [file normalize $project_dir/$project_name.xpr]"
puts "  You can open this project directly in Vivado GUI."
puts "=========================================================================="
