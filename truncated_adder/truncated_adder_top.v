// ============================================================================
// Module: truncated_adder_top
// Description: Top-level AXI4-Lite wrapper for the Truncated Adder (ADD_APPROX).
//              Connects the hardware adder to Zynq PS7 via 32-bit memory-mapped registers.
// Register Map:
//   0x00: A_REG      [15:0] Input Operand A (Q4.12 Fixed-Point)
//   0x04: B_REG      [15:0] Input Operand B (Q4.12 Fixed-Point)
//   0x08: CTRL_REG   [0]    Start Computation
//   0x0C: STATUS_REG [0]=Busy, [1]=Done
//   0x10: SUM_REG    [15:0] Truncated Addition Result (Q4.12 Fixed-Point)
// Reference: "Truncated Adder Integration in a CNN Accelerator" (Lim Qi Yang et al., 2025)
// ============================================================================

`timescale 1ns / 1ps

module truncated_adder_top #(
    parameter C_S_AXI_DATA_WIDTH = 32,
    parameter C_S_AXI_ADDR_WIDTH = 5,
    parameter DATA_WIDTH         = 16,
    parameter APPROX_BITS        = 4
)(
    // AXI Clock and Reset
    input  wire                          s_axi_aclk,
    input  wire                          s_axi_aresetn,

    // AXI Write Address Channel
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] s_axi_awaddr,
    input  wire                          s_axi_awvalid,
    output reg                           s_axi_awready,

    // AXI Write Data Channel
    input  wire [C_S_AXI_DATA_WIDTH-1:0] s_axi_wdata,
    input  wire [C_S_AXI_DATA_WIDTH/8-1:0] s_axi_wstrb,
    input  wire                          s_axi_wvalid,
    output reg                           s_axi_wready,

    // AXI Write Response Channel
    output reg  [1:0]                    s_axi_bresp,
    output reg                           s_axi_bvalid,
    input  wire                          s_axi_bready,

    // AXI Read Address Channel
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] s_axi_araddr,
    input  wire                          s_axi_arvalid,
    output reg                           s_axi_arready,

    // AXI Read Data Channel
    output reg  [C_S_AXI_DATA_WIDTH-1:0] s_axi_rdata,
    output reg  [1:0]                    s_axi_rresp,
    output reg                           s_axi_rvalid,
    input  wire                          s_axi_rready
);

    // Internal Registers
    reg  [DATA_WIDTH-1:0] reg_a;
    reg  [DATA_WIDTH-1:0] reg_b;
    reg                   reg_ctrl_start;
    reg                   reg_status_busy;
    reg                   reg_status_done;
    wire [DATA_WIDTH-1:0] wire_sum;
    wire                  wire_cout;

    // Instantiate Core Parameterized Truncated Adder
    ADD_APPROX #(
        .DATA_WIDTH (DATA_WIDTH),
        .APPROX_BITS(APPROX_BITS)
    ) u_add_approx (
        .a   (reg_a),
        .b   (reg_b),
        .cin (1'b0),
        .sum (wire_sum),
        .cout(wire_cout)
    );

    // AXI4-Lite Write Handshake & Register Write
    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            s_axi_awready  <= 1'b0;
            s_axi_wready   <= 1'b0;
            s_axi_bvalid   <= 1'b0;
            s_axi_bresp    <= 2'b00;
            reg_a          <= {DATA_WIDTH{1'b0}};
            reg_b          <= {DATA_WIDTH{1'b0}};
            reg_ctrl_start <= 1'b0;
        end else begin
            // Address Ready
            if (!s_axi_awready && s_axi_awvalid && s_axi_wvalid) begin
                s_axi_awready <= 1'b1;
                s_axi_wready  <= 1'b1;
            end else begin
                s_axi_awready <= 1'b0;
                s_axi_wready  <= 1'b0;
            end

            // Write Execution
            if (s_axi_awready && s_axi_awvalid && s_axi_wready && s_axi_wvalid) begin
                case (s_axi_awaddr[4:2])
                    3'b000: reg_a          <= s_axi_wdata[DATA_WIDTH-1:0];
                    3'b001: reg_b          <= s_axi_wdata[DATA_WIDTH-1:0];
                    3'b010: reg_ctrl_start <= s_axi_wdata[0];
                    default: ;
                endcase
                s_axi_bvalid <= 1'b1; // Response Valid
                s_axi_bresp  <= 2'b00; // OKAY
            end else if (s_axi_bvalid && s_axi_bready) begin
                s_axi_bvalid <= 1'b0;
            end
        end
    end

    // FSM Control State Machine
    localparam STATE_IDLE  = 2'b00;
    localparam STATE_CALC  = 2'b01;
    localparam STATE_DONE  = 2'b10;

    reg [1:0] state;
    reg [DATA_WIDTH-1:0] reg_sum;

    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            state           <= STATE_IDLE;
            reg_status_busy <= 1'b0;
            reg_status_done <= 1'b0;
            reg_sum         <= {DATA_WIDTH{1'b0}};
        end else begin
            case (state)
                STATE_IDLE: begin
                    reg_status_done <= 1'b0;
                    if (reg_ctrl_start) begin
                        reg_status_busy <= 1'b1;
                        state           <= STATE_CALC;
                    end
                end

                STATE_CALC: begin
                    reg_sum         <= wire_sum;
                    reg_status_busy <= 1'b0;
                    reg_status_done <= 1'b1;
                    state           <= STATE_DONE;
                end

                STATE_DONE: begin
                    state <= STATE_IDLE;
                end

                default: state <= STATE_IDLE;
            endcase
        end
    end

    // AXI4-Lite Read Channel
    always @(posedge s_axi_aclk) begin
        if (!s_axi_aresetn) begin
            s_axi_arready <= 1'b0;
            s_axi_rvalid  <= 1'b0;
            s_axi_rresp   <= 2'b00;
            s_axi_rdata   <= 32'b0;
        end else begin
            if (!s_axi_arready && s_axi_arvalid) begin
                s_axi_arready <= 1'b1;
            end else begin
                s_axi_arready <= 1'b0;
            end

            if (s_axi_arready && s_axi_arvalid && !s_axi_rvalid) begin
                s_axi_rvalid <= 1'b1;
                s_axi_rresp  <= 2'b00;
                case (s_axi_araddr[4:2])
                    3'b000: s_axi_rdata <= {{32-DATA_WIDTH{1'b0}}, reg_a};
                    3'b001: s_axi_rdata <= {{32-DATA_WIDTH{1'b0}}, reg_b};
                    3'b010: s_axi_rdata <= {31'b0, reg_ctrl_start};
                    3'b011: s_axi_rdata <= {30'b0, reg_status_done, reg_status_busy};
                    3'b100: s_axi_rdata <= {{32-DATA_WIDTH{1'b0}}, reg_sum};
                    default: s_axi_rdata <= 32'b0;
                endcase
            end else if (s_axi_rvalid && s_axi_rready) begin
                s_axi_rvalid <= 1'b0;
            end
        end
    end

endmodule
