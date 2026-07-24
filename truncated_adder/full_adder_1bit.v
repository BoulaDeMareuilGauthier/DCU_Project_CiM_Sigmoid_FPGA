// ============================================================================
// Module: full_adder_1bit
// Description: Standard 1-bit accurate full adder logic block.
// Reference: "Truncated Adder Integration in a CNN Accelerator" (Lim Qi Yang et al., 2025)
// ============================================================================

`timescale 1ns / 1ps

module full_adder_1bit (
    input  wire a,
    input  wire b,
    input  wire cin,
    output wire sum,
    output wire cout
);

    assign sum  = a ^ b ^ cin;
    assign cout = (a & b) | (b & cin) | (a & cin);

endmodule
