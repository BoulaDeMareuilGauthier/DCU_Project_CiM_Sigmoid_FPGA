// ============================================================================
// Module: ADD_APPROX
// Description: Parameterized m-bit Truncated Adder with n approximation bits.
//              - n LSBs: Zero-truncation 1-bit approximate adders (AdderIMPACTZeroApproxOneBit)
//              - (m-n) MSBs: Accurate 1-bit full adders (full_adder_1bit)
//              - Supports signed 2's complement sign extension and carry chaining.
// Reference: "Truncated Adder Integration in a CNN Accelerator" (Lim Qi Yang et al., 2025)
// ============================================================================

`timescale 1ns / 1ps

module ADD_APPROX #(
    parameter DATA_WIDTH  = 16, // m: total data width
    parameter APPROX_BITS = 4   // n: number of approximate bits (0 <= n <= DATA_WIDTH)
)(
    input  wire [DATA_WIDTH-1:0] a,
    input  wire [DATA_WIDTH-1:0] b,
    input  wire                  cin,
    output wire [DATA_WIDTH-1:0] sum,
    output wire                  cout
);

    wire [DATA_WIDTH:0] carry;
    assign carry[0] = cin;

    genvar i;
    generate
        for (i = 0; i < DATA_WIDTH; i = i + 1) begin : adder_stage
            if (i < APPROX_BITS) begin : approx_bit
                // LSB approximate stage (zero truncation)
                AdderIMPACTZeroApproxOneBit u_approx_adder (
                    .a   (a[i]),
                    .b   (b[i]),
                    .cin (carry[i]),
                    .sum (sum[i]),
                    .cout(carry[i+1])
                );
            end else begin : accurate_bit
                // MSB accurate stage
                full_adder_1bit u_accurate_adder (
                    .a   (a[i]),
                    .b   (b[i]),
                    .cin (carry[i]),
                    .sum (sum[i]),
                    .cout(carry[i+1])
                );
            end
        end
    endgenerate

    assign cout = carry[DATA_WIDTH];

endmodule
