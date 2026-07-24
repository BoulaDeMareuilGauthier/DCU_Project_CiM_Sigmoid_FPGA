// ============================================================================
// Module: tb_ADD_APPROX
// Description: Pong P. Chu Style Self-Checking Testbench for Truncated Adder.
// Reference: "FPGA Prototyping by Verilog Examples" (Pong P. Chu) &
//            "Truncated Adder Integration in a CNN Accelerator" (Lim Qi Yang et al., 2025)
// Features:
//   - Clock & Reset generation
//   - Parameterized sweeps across n = 0, 2, 4, 6, 8, 16 approximate bits
//   - Random vector stimulus generation loop (100+ vectors)
//   - Waveform dumping ($dumpfile / $dumpvars for GTKWave / Vivado)
//   - Self-checking pass/fail & error tolerance statistics
// ============================================================================

`timescale 1ns / 1ps

module tb_ADD_APPROX;

    // Clock and Reset Signals (Pong P. Chu standard testbench template)
    reg clk;
    reg reset;

    localparam DATA_WIDTH = 16;
    localparam CLK_PERIOD = 10; // 100 MHz clock

    // Clock Generator (10 ns period)
    always #(CLK_PERIOD / 2) clk = ~clk;

    // Testbench Stimulus Signals
    reg  [DATA_WIDTH-1:0] a;
    reg  [DATA_WIDTH-1:0] b;
    reg                   cin;

    // Outputs for various approximation bit configs
    wire [DATA_WIDTH-1:0] sum_n0, sum_n2, sum_n4, sum_n6, sum_n8, sum_n16;
    wire cout_n0, cout_n2, cout_n4, cout_n6, cout_n8, cout_n16;

    // Instantiate ADD_APPROX modules (0, 2, 4, 6, 8, 16 approx bits)
    ADD_APPROX #(.DATA_WIDTH(16), .APPROX_BITS(0))  u_n0  (.a(a), .b(b), .cin(cin), .sum(sum_n0),  .cout(cout_n0));
    ADD_APPROX #(.DATA_WIDTH(16), .APPROX_BITS(2))  u_n2  (.a(a), .b(b), .cin(cin), .sum(sum_n2),  .cout(cout_n2));
    ADD_APPROX #(.DATA_WIDTH(16), .APPROX_BITS(4))  u_n4  (.a(a), .b(b), .cin(cin), .sum(sum_n4),  .cout(cout_n4));
    ADD_APPROX #(.DATA_WIDTH(16), .APPROX_BITS(6))  u_n6  (.a(a), .b(b), .cin(cin), .sum(sum_n6),  .cout(cout_n6));
    ADD_APPROX #(.DATA_WIDTH(16), .APPROX_BITS(8))  u_n8  (.a(a), .b(b), .cin(cin), .sum(sum_n8),  .cout(cout_n8));
    ADD_APPROX #(.DATA_WIDTH(16), .APPROX_BITS(16)) u_n16 (.a(a), .b(b), .cin(cin), .sum(sum_n16), .cout(cout_n16));

    // Statistics Counters
    integer test_count;
    integer pass_n0_count;
    integer err_n4_total;
    integer err_n6_total;
    integer i;

    // Main Test Stimulus Process
    initial begin
        // Waveform Dumping for GTKWave / Vivado XSIM (Chu Example Standard)
        $dumpfile("tb_ADD_APPROX.vcd");
        $dumpvars(0, tb_ADD_APPROX);

        // Initialize signals
        clk = 0;
        reset = 1;
        a = 0;
        b = 0;
        cin = 0;
        test_count = 0;
        pass_n0_count = 0;
        err_n4_total = 0;
        err_n6_total = 0;

        // Reset Pulse
        #(CLK_PERIOD * 2);
        reset = 0;
        #(CLK_PERIOD);

        $display("==========================================================================");
        $display("  PONG P. CHU VERILOG SIMULATION METHODOLOGY: TRUNCATED ADDER TESTBENCH");
        $display("==========================================================================");

        // --------------------------------------------------------------------
        // Phase 1: Directed Test Cases
        // --------------------------------------------------------------------
        $display("\n--- Phase 1: Directed Fixed-Point Test Vectors (Q4.12) ---");

        // Case 1: Zero Addition
        a = 16'h0000; b = 16'h0000; #(CLK_PERIOD);
        check_result("Zero Addition", 16'h0000);

        // Case 2: Positive Addition (+1.5 + +2.25 = +3.75 in Q4.12)
        // 1.5 = 0x1800, 2.25 = 0x2400 -> Sum = 0x3C00
        a = 16'h1800; b = 16'h2400; #(CLK_PERIOD);
        check_result("Q4.12 Positive", 16'h3C00);

        // Case 3: Negative Addition (-2.0 + -3.0 = -5.0 in 2's complement Q4.12)
        // -2.0 = 0xE000, -3.0 = 0xD000 -> Sum = 0xB000
        a = 16'hE000; b = 16'hD000; #(CLK_PERIOD);
        check_result("Q4.12 Negative", 16'hB000);

        // Case 4: Max Boundary Value
        a = 16'h7FFF; b = 16'h0001; #(CLK_PERIOD);
        check_result("Max Boundary", 16'h8000);

        // --------------------------------------------------------------------
        // Phase 2: Random Vector Sweep (Pong P. Chu Random Testing)
        // --------------------------------------------------------------------
        $display("\n--- Phase 2: 100 Random Vector Verification Sweep ---");
        for (i = 0; i < 100; i = i + 1) begin
            a = $random;
            b = $random;
            cin = $random & 1'b1;
            #(CLK_PERIOD);

            test_count = test_count + 1;
            if (sum_n0 === (a + b + cin)) begin
                pass_n0_count = pass_n0_count + 1;
            end
            
            // Accumulate absolute bit error for n=4 and n=6
            if ((sum_n0 > sum_n4))
                err_n4_total = err_n4_total + (sum_n0 - sum_n4);
            else
                err_n4_total = err_n4_total + (sum_n4 - sum_n0);

            if ((sum_n0 > sum_n6))
                err_n6_total = err_n6_total + (sum_n6 - sum_n0);
            else
                err_n6_total = err_n6_total + (sum_n6 - sum_n0);
        end

        // --------------------------------------------------------------------
        // Phase 3: Final Test Report
        // --------------------------------------------------------------------
        $display("\n==========================================================================");
        $display("  SIMULATION SUMMARY REPORT (Chu Methodology)");
        $display("==========================================================================");
        $display("  Total Random Vectors Tested : %0d", test_count);
        $display("  n=0 Exact Adder Pass Count   : %0d / %0d (%s)", 
                 pass_n0_count, test_count, (pass_n0_count == test_count) ? "PASS" : "FAIL");
        $display("  n=4 Approx Avg LSB Bit Error : %0f LSBs", err_n4_total / (1.0 * test_count));
        $display("  n=6 Approx Avg LSB Bit Error : %0f LSBs", err_n6_total / (1.0 * test_count));
        $display("==========================================================================");
        $display("  Waveform file generated: tb_ADD_APPROX.vcd");
        $display("==========================================================================");

        $finish;
    end

    // Task to verify directed tests
    task check_result;
        input [128*8-1:0] test_name;
        input [DATA_WIDTH-1:0] expected_sum;
        begin
            test_count = test_count + 1;
            if (sum_n0 === expected_sum) begin
                pass_n0_count = pass_n0_count + 1;
                $display("[PASS] %-20s | A: 0x%04h, B: 0x%04h | Exact Sum: 0x%04h | n=4: 0x%04h | n=6: 0x%04h", 
                         test_name, a, b, sum_n0, sum_n4, sum_n6);
            end else begin
                $display("[FAIL] %-20s | A: 0x%04h, B: 0x%04h | Expected: 0x%04h, Got: 0x%04h", 
                         test_name, a, b, expected_sum, sum_n0);
            end
        end
    endtask

endmodule
