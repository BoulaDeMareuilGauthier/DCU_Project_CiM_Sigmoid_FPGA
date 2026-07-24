// ============================================================================
// Module: AdderIMPACTZeroApproxOneBit
// Description: 1-bit zero truncation approximate adder cell.
//              Replaces standard 5-gate full adder with zero-cost wire/constant logic.
// Reference: "Truncated Adder Integration in a CNN Accelerator" (Lim Qi Yang et al., 2025)
// ============================================================================

`timescale 1ns / 1ps

module AdderIMPACTZeroApproxOneBit (
    input  wire a,
    input  wire b,
    input  wire cin,
    output wire sum,
    output wire cout
);

    // Zero-truncation: sum and cout are set to zero (using no combinational gates)
    assign sum  = 1'b0;
    assign cout = 1'b0;

endmodule
