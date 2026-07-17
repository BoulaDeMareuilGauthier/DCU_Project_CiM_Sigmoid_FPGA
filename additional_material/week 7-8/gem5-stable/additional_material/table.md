# Hardware Units Implementation Details

## Adders

| Name | Description | Implementation |
|---|---|---|
| Full (RCA) | Ripple-carry / full adder | Uses precise latency and energy values extracted directly from Proteus synthesis benchmark lookup tables (LUTs) based on exact bit-precision. |
| Sklansky | Brent-Kung / Sklansky prefix | Uses precise latency and energy values extracted directly from Proteus synthesis benchmark lookup tables (LUTs) based on exact bit-precision. |
| Kogge-Stone | Kogge-Stone prefix | Uses precise latency and energy values extracted directly from Proteus synthesis benchmark lookup tables (LUTs) based on exact bit-precision. |
| Carry-Select | Carry-select adder | Uses precise latency and energy values extracted directly from Proteus synthesis benchmark lookup tables (LUTs) based on exact bit-precision. |
| RBR | Reversed-biased ripple adder | Uses precise latency and energy values extracted directly from Proteus synthesis benchmark lookup tables (LUTs) based on exact bit-precision. |
| LOA | Lower-part-OR adder | Models approximation by applying established literature-derived scaling ratios to the exact Full Adder baseline costs. |
| CCBA | Carry cut-back adder | Models approximation by applying established literature-derived scaling ratios to the exact Full Adder baseline costs. |
| TruA | Truncated adder | Models approximation by applying established literature-derived scaling ratios to the exact Full Adder baseline costs. |
| GeAr | Generic accuracy-configurable adder | Models approximation by applying established literature-derived scaling ratios to the exact Full Adder baseline costs. |
| CSA | Carry speculative adder | Models approximation by applying established literature-derived scaling ratios to the exact Full Adder baseline costs. |

## Multipliers

| Name | Description | Implementation |
|---|---|---|
| Full (RC Array) | Ripple-carry array multiplier | Uses precise latency and energy values extracted directly from exact synthesis benchmark lookup tables based on bit-width. |
| Sklansky | Sklansky-tree multiplier | Uses precise latency and energy values extracted directly from exact synthesis benchmark lookup tables based on bit-width. |
| Carry-Select | Carry-save / carry-select multiplier | Uses precise latency and energy values extracted directly from exact synthesis benchmark lookup tables based on bit-width. |
| RBR | Reversed-biased ripple multiplier | Uses precise latency and energy values extracted directly from exact synthesis benchmark lookup tables based on bit-width. |
| Mitchell | Logarithmic approximate multiplier (shift + add) | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |
| ALM-SOA | Approximate logarithmic multiplier with set-one-adder | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |
| ILM-AA | Improved logarithmic multiplier with approximate adders | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |
| CGPM1 | CGP-generated approximate multiplier (1 sub-block) | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |
| TAM1 | Truncation with adaptive error compensation | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |
| HOCM (1StepTrunc) | High-order compressor multiplier, 1-step truncated | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |
| CGPM3 | CGP-generated approximate multiplier (3 sub-blocks) | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |
| BAM | Broken-array multiplier | Employs latency and energy reduction percentages derived from literature, applied against the Exact Array multiplier cost. |

## Dividers

| Name | Description | Implementation |
|---|---|---|
| Exact Array | Restoring array divider (n iterations of a partial-remainder step) | Base latency and energy are computed by scaling the optimal exact multiplier costs by a factor of 2.3 to represent the complex division logic overhead. |
| Exact Logarithmic | LNS/Mitchell-based logarithmic divider (subtraction in log domain) | Models the Logarithmic Number System (LNS) by simulating the cost of two RBR additions (latency 1.3x) and a total energy of 1.5x of a single RBR adder. |
| AAXD | Adaptive Approximate Divider | Calculates performance by scaling the exact array divider costs using specific ratios (e.g. -61% latency) derived from the updatetwo benchmark data. |
| INZeD | Inexact Zero-based Divider | Calculates performance by scaling the exact array divider costs using specific ratios derived from the updatetwo benchmark data. |
| AXDr1 | Approximate Restoring Divider v1, depth-8 approx subtractor | Calculates performance by scaling the exact array divider costs using specific ratios derived from the updatetwo benchmark data. |
| AXDr3 | Approximate Restoring Divider v3, higher-accuracy variant | Calculates performance by scaling the exact array divider costs using specific ratios derived from the updatetwo benchmark data. |
| SEERAD-4 | Rounding-based approximate divider, accuracy level 4 | Calculates performance by scaling the exact array divider costs using specific ratios derived from the updatetwo benchmark data. |
| DAXD | Dual-path Approximate Divider with bit-width reduction | Calculates performance by scaling the exact array divider costs using specific ratios derived from the updatetwo benchmark data. |
| SC Divider | Stochastic-Computing divider, bit-stream encoding | Models stochastic clocking behavior where latency strictly follows an exponential 2^BP (clock cycles) cost while maintaining exceptionally low energy per cycle. |
| RAPID | RAPID reconfigurable logarithmic approximate divider | Implements a reconfigurable logarithmic approach where both latency and energy costs scale logarithmically, proportional to log2(BP). |
| 3D-FPCA | 3D-FPCA RRAM reciprocal + multiply | Mimics reciprocal division (A * 1/B) by charging an average of 0.63 * BP iterative addition cycles followed by a single optimal multiplier operation. |
