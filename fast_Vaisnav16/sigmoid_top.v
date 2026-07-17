module sigmoid_top #(
    parameter NUM_POINTS = 31
)(
    input  wire        clk,
    input  wire        rst_n,

    // AXI4-Lite slave
    input  wire [4:0]  s_axi_awaddr,
    input  wire        s_axi_awvalid,
    output wire        s_axi_awready,
    input  wire [31:0] s_axi_wdata,
    input  wire [3:0]  s_axi_wstrb,
    input  wire        s_axi_wvalid,
    output wire        s_axi_wready,
    output wire [1:0]  s_axi_bresp,
    output wire        s_axi_bvalid,
    input  wire        s_axi_bready,
    input  wire [4:0]  s_axi_araddr,
    input  wire        s_axi_arvalid,
    output wire        s_axi_arready,
    output wire [31:0] s_axi_rdata,
    output wire [1:0]  s_axi_rresp,
    output wire        s_axi_rvalid,
    input  wire        s_axi_rready,

    output wire        irq
);

    localparam ADDR_X      = 5'h00;
    localparam ADDR_Y      = 5'h04;
    localparam ADDR_CTRL   = 5'h08;
    localparam ADDR_STATUS = 5'h0C;

    reg signed [15:0] x_reg;
    reg signed [15:0] y_reg;
    reg        start_reg;
    reg        busy;
    reg        done;

    reg signed [15:0] sigmoid_x;
    wire signed [15:0] sigmoid_y;

    // VHDL sigmoide entity (from fast_Vaisnav16)
    sigmoide u_sigmoid (
        .ck(clk),
        .x(sigmoid_x),
        .y(sigmoid_y)
    );

    // AXI4-Lite write channel
    reg        aw_ready, w_ready;
    reg [1:0]  b_resp;
    reg        b_valid;

    assign s_axi_awready = aw_ready;
    assign s_axi_wready  = w_ready;
    assign s_axi_bresp   = b_resp;
    assign s_axi_bvalid  = b_valid;

    always @(posedge clk) begin
        if (!rst_n) begin
            aw_ready   <= 1'b0;
            w_ready    <= 1'b0;
            b_resp     <= 2'b00;
            b_valid    <= 1'b0;
            x_reg      <= 16'd0;
            start_reg  <= 1'b0;
        end else begin
            start_reg <= 1'b0;

            if (s_axi_awvalid && s_axi_wvalid && !b_valid) begin
                aw_ready <= 1'b1;
                w_ready  <= 1'b1;
                b_resp   <= 2'b00;
                b_valid  <= 1'b1;
                case (s_axi_awaddr)
                    ADDR_X: if (s_axi_wstrb[0]) x_reg <= s_axi_wdata[15:0];
                    ADDR_CTRL: begin
                        if (s_axi_wdata[0]) start_reg <= 1'b1;
                    end
                    default: ;
                endcase
            end else begin
                aw_ready <= 1'b0;
                w_ready  <= 1'b0;
            end

            if (b_valid && s_axi_bready)
                b_valid <= 1'b0;
        end
    end

    // AXI4-Lite read channel
    reg        ar_ready;
    reg [1:0]  r_resp;
    reg [31:0] r_data;
    reg        r_valid;

    assign s_axi_arready = ar_ready;
    assign s_axi_rdata   = r_data;
    assign s_axi_rresp   = r_resp;
    assign s_axi_rvalid  = r_valid;

    always @(posedge clk) begin
        if (!rst_n) begin
            ar_ready <= 1'b0;
            r_resp   <= 2'b00;
            r_data   <= 32'd0;
            r_valid  <= 1'b0;
        end else begin
            if (s_axi_arvalid && !r_valid) begin
                ar_ready <= 1'b1;
                r_resp   <= 2'b00;
                r_valid  <= 1'b1;
                case (s_axi_araddr)
                    ADDR_X:      r_data <= {16'd0, x_reg};
                    ADDR_Y:      r_data <= {16'd0, y_reg};
                    ADDR_CTRL:   r_data <= {31'd0, start_reg};
                    ADDR_STATUS: r_data <= {30'd0, done, busy};
                    default:     r_data <= 32'd0;
                endcase
            end else begin
                ar_ready <= 1'b0;
            end

            if (r_valid && s_axi_rready)
                r_valid <= 1'b0;
        end
    end

    // Processing FSM: LOAD -> WAIT_SIGMOID -> STORE
    localparam S_IDLE  = 2'd0;
    localparam S_LOAD  = 2'd1;
    localparam S_WAIT  = 2'd2;
    localparam S_STORE = 2'd3;

    reg [1:0] state;

    always @(posedge clk) begin
        if (!rst_n) begin
            state     <= S_IDLE;
            busy      <= 1'b0;
            done      <= 1'b0;
            sigmoid_x <= 16'd0;
            y_reg     <= 16'd0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0;
                    if (start_reg && !busy) begin
                        busy <= 1'b1;
                        state <= S_LOAD;
                    end
                end

                S_LOAD: begin
                    sigmoid_x <= x_reg;
                    state     <= S_WAIT;
                end

                S_WAIT: begin
                    y_reg <= sigmoid_y;
                    state <= S_STORE;
                end

                S_STORE: begin
                    busy <= 1'b0;
                    done <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

    assign irq = done;

endmodule
