# Vivado TCL: fast_Vaisnav16 Sigmoid on Zybo Z7-10
# Usage: vivado -mode batch -source build.tcl

# Fix Windows sub-process journal path issue
set proj_root [file normalize [file dirname [info script]]]
set ::env(TEMP) [file join $proj_root tmp]
set ::env(TMP) [file join $proj_root tmp]
set ::env(VIVADO_TOP_JOURNAL_DIR) [file join $proj_root tmp]
set ::env(VIVADO_TOP_LOG_DIR) [file join $proj_root tmp]
file mkdir [file join $proj_root tmp]
cd $proj_root

set project_name "vaisnav16_project"
set project_dir "./vivado_project"
set fpga_part "xc7z010clg400-1"

create_project $project_name $project_dir -part $fpga_part -force

add_files -norecurse {
    ./pck_definitions.vhdl
    ./sigmoid.vhdl
    ./sigmoid_top.v
}
update_compile_order -fileset sources_1

create_bd_design "system"

# PS7
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
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1} \
] [get_bd_cells ps7]

# AXI Interconnect (1 master only)
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:* axi_ic
set_property -dict [list CONFIG.NUM_MI {1}] [get_bd_cells axi_ic]
connect_bd_intf_net [get_bd_intf_pins ps7/M_AXI_GP0] [get_bd_intf_pins axi_ic/S00_AXI]

# sigmoid_top (AXI slave)
create_bd_cell -type module -reference sigmoid_top sigmoid_top_0
set_property -dict [list CONFIG.NUM_POINTS {31}] [get_bd_cells sigmoid_top_0]

connect_bd_intf_net [get_bd_intf_pins axi_ic/M00_AXI] [get_bd_intf_pins sigmoid_top_0/S_AXI]

# Processor System Reset
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:* rst_ps7_100M
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins rst_ps7_100M/slowest_sync_clk]
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] [get_bd_pins rst_ps7_100M/ext_reset_in]

# Clocks
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_ic/ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_ic/S00_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins axi_ic/M00_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins ps7/M_AXI_GP0_ACLK]
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] [get_bd_pins sigmoid_top_0/clk]

# Resets
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins axi_ic/ARESETN]
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins axi_ic/S00_ARESETN]
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins axi_ic/M00_ARESETN]
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] [get_bd_pins sigmoid_top_0/rst_n]

# Interrupt
connect_bd_net [get_bd_pins sigmoid_top_0/irq] [get_bd_pins ps7/IRQ_F2P]

# Address
assign_bd_address [get_bd_addr_segs -of_objects [get_bd_intf_pins sigmoid_top_0/S_AXI]]

regenerate_bd_layout
validate_bd_design
save_bd_design

# Wrapper
set wrapper_file [make_wrapper -files [get_files $project_dir/$project_name.srcs/sources_1/bd/system/system.bd] -top]
add_files -norecurse $wrapper_file
update_compile_order -fileset sources_1
set_property top system_wrapper [current_fileset]

# Synth + Impl (reduced parallelism for 16 GB system)
set_param general.maxThreads 2
launch_runs synth_1 -jobs 1
wait_on_run synth_1

launch_runs impl_1 -to_step write_bitstream -jobs 1
wait_on_run impl_1

write_hw_platform -fixed -include_bit -file $project_dir/system_wrapper.xsa

puts "Build complete! Bitstream ready."
