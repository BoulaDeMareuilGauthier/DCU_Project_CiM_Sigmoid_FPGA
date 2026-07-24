# ============================================================================
# Vivado TCL: Full Zynq System Block Design (PS7 + AXI Interconnect + truncated_adder_top)
# Board: Digilent Zybo Z7-10 (xc7z010clg400-1)
# Usage: vivado -mode batch -source build_system_bd.tcl
# ============================================================================

set proj_root [file normalize [file dirname [info script]]]
set ::env(TEMP) [file join $proj_root tmp]
set ::env(TMP) [file join $proj_root tmp]
file mkdir [file join $proj_root tmp]
cd $proj_root

set project_name "truncated_adder_system"
set project_dir "./vivado_system_project"
set fpga_part "xc7z010clg400-1"
set output_dir "./build_output"

file mkdir $output_dir

# Limit parallel synthesis threads to prevent memory/process collisions
set_param general.maxThreads 2

puts "=========================================================================="
puts "  [1/5] Creating Vivado Zynq System Project..."
puts "=========================================================================="

create_project $project_name $project_dir -part $fpga_part -force

add_files -norecurse {
    ./AdderIMPACTZeroApproxOneBit.v
    ./full_adder_1bit.v
    ./ADD_APPROX.v
    ./truncated_adder_top.v
}
update_compile_order -fileset sources_1

puts "=========================================================================="
puts "  [2/5] Creating Block Design with Zynq PS7 Processing System..."
puts "=========================================================================="

create_bd_design "system"

# Instantiate Zynq PS7
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:* ps7
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR"} [get_bd_cells ps7]

set_property -dict [list \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_UART0_PERIPHERAL_ENABLE {0} \
    CONFIG.PCW_UART1_PERIPHERAL_ENABLE {1} \
    CONFIG.PCW_UART1_UART1_IO {MIO 48 .. 49} \
    CONFIG.PCW_UART1_BAUD_RATE {115200} \
    CONFIG.PCW_PRESET_BANK0_VOLTAGE {LVCMOS 3.3V} \
    CONFIG.PCW_PRESET_BANK1_VOLTAGE {LVCMOS 1.8V} \
    CONFIG.PCW_GPIO_MIO_GPIO_ENABLE {1} \
    CONFIG.PCW_GPIO_MIO_GPIO_IO {MIO} \
] [get_bd_cells ps7]

# AXI Interconnect
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* axi_ic
set_property -dict [list CONFIG.NUM_MI {1}] [get_bd_cells axi_ic]
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins axi_ic/S00_AXI]

# Truncated Adder AXI Top Instance
create_bd_cell -type module -reference truncated_adder_top truncated_adder_top_0
connect_bd_intf_net [get_bd_intf_pins axi_ic/M00_AXI] [get_bd_intf_pins truncated_adder_top_0/s_axi]

# Processor System Reset
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* rst_ps7_100M
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins rst_ps7_100M/slowest_sync_clk]
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins rst_ps7_100M/ext_reset_in]

# Connect Clock & Reset Network
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_ic/ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_ic/S00_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_ic/M00_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7/M_AXI_GP0_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins truncated_adder_top_0/s_axi_aclk]

connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins axi_ic/ARESETN]
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins axi_ic/S00_ARESETN]
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins axi_ic/M00_ARESETN]
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins truncated_adder_top_0/s_axi_aresetn]

# Assign Memory Map Address
assign_bd_address [get_bd_addr_segs -of_objects [get_bd_intf_pins truncated_adder_top_0/s_axi]]

regenerate_bd_layout
validate_bd_design
save_bd_design

# Generate Block Design HDL Targets and Wrapper
generate_target all [get_files $project_dir/$project_name.srcs/sources_1/bd/system/system.bd]
set wrapper_file [make_wrapper -files [get_files $project_dir/$project_name.srcs/sources_1/bd/system/system.bd] -top]
add_files -norecurse $wrapper_file
update_compile_order -fileset sources_1
set_property top system_wrapper [current_fileset]

puts "=========================================================================="
puts "  [3/5] Running Full Zynq Synthesis & Implementation..."
puts "=========================================================================="

launch_runs synth_1 -jobs 1
wait_on_run synth_1

puts "=========================================================================="
puts "  [4/5] Running Implementation & Writing Bitstream..."
puts "=========================================================================="

launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1

puts "=========================================================================="
puts "  [5/5] Exporting System Bitstream & XSA Hardware Definition..."
puts "=========================================================================="

file copy -force "$project_dir/$project_name.runs/impl_1/system_wrapper.bit" "$output_dir/system_wrapper.bit"
write_hw_platform -fixed -include_bit -file "$output_dir/system_wrapper.xsa"

puts "=========================================================================="
puts "  ZYNQ SYSTEM BITSTREAM CREATED SUCCESSFULLY!"
puts "  - Bitstream: [file normalize $output_dir/system_wrapper.bit]"
puts "  - XSA Platform: [file normalize $output_dir/system_wrapper.xsa]"
puts "  - Project  : [file normalize $project_dir/$project_name.xpr]"
puts "=========================================================================="
