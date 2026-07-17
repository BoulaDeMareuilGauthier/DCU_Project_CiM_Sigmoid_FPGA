#!/usr/bin/env python3
"""
Comparison script: Adder-free vs Traditional Adders

This script compares the AFSRAM-CIM adder-free approach against all
traditional adders (exact and approximate) implemented in adder_cost_model.py.
"""

import csv
from typing import List, Dict
from adder_cost_model import (
    ALL_ADDERS,
    get_adder_metrics,
    evaluate_all_adders,
    summary_table as adder_summary_table,
)
from adder_free_cost_model import (
    get_adder_free_metrics,
    compare_with_adder_tree,
    summary_table as adder_free_summary_table,
)


def generate_comparison_csv(
    bit_precisions: List[int],
    size: int = 1024,
    output_file: str = "adder_free_comparison.csv",
) -> None:
    """
    Generate a comprehensive CSV comparing adder-free with all traditional adders.
    """
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        header = [
            "bit_precision",
            "approach",
            "adder_type",
            "family",
            "latency_ns",
            "energy_nj",
            "area_ge",
            "energy_savings_vs_full_adder",
            "area_savings_vs_full_adder",
        ]
        writer.writerow(header)
        
        # Get Full adder baseline for each precision
        full_adder_baseline = {}
        for bp in bit_precisions:
            full_adder_baseline[bp] = get_adder_metrics(bp, "full", size)
        
        # Write adder-free rows
        for bp in bit_precisions:
            af_metrics = get_adder_free_metrics(bp, size)
            baseline = full_adder_baseline[bp]
            
            energy_savings = (baseline.energy_nj - af_metrics.energy_nj) / baseline.energy_nj
            area_savings = (baseline.area_ge - af_metrics.area_ge) / baseline.area_ge
            
            writer.writerow([
                bp,
                "adder_free",
                "AFSRAM-CIM",
                "digital_cim",
                round(af_metrics.latency_ns, 4),
                round(af_metrics.energy_nj, 6),
                round(af_metrics.area_ge, 3),
                round(energy_savings, 4),
                round(area_savings, 4),
            ])
        
        # Write traditional adder rows
        for bp in bit_precisions:
            baseline = full_adder_baseline[bp]
            for adder_spec in ALL_ADDERS:
                metrics = get_adder_metrics(bp, adder_spec.key, size)
                
                energy_savings = (baseline.energy_nj - metrics.energy_nj) / baseline.energy_nj
                area_savings = (baseline.area_ge - metrics.area_ge) / baseline.area_ge
                
                writer.writerow([
                    bp,
                    "traditional",
                    adder_spec.label,
                    adder_spec.family.value,
                    round(metrics.latency_ns, 4),
                    round(metrics.energy_nj, 6),
                    round(metrics.area_ge, 3),
                    round(energy_savings, 4),
                    round(area_savings, 4),
                ])


def print_comparison_summary(bit_precisions: List[int], size: int = 1024) -> None:
    """
    Print a formatted summary comparison.
    """
    print("=" * 80)
    print("ADDER-FREE VS TRADITIONAL ADDERS COMPARISON")
    print("=" * 80)
    print(f"\nSize: {size} elements")
    print(f"Bit precisions: {bit_precisions}")
    print()
    
    # Get Full adder baseline
    full_baseline = {bp: get_adder_metrics(bp, "full", size) for bp in bit_precisions}
    
    print("ADDER-FREE METRICS")
    print("-" * 80)
    print(f"{'Precision':>10} | {'Latency (ns)':>12} | {'Energy (nJ)':>12} | {'Area (GE)':>10} | {'E Savings':>10} | {'A Savings':>10}")
    print("-" * 80)
    
    for bp in bit_precisions:
        af = get_adder_free_metrics(bp, size)
        baseline = full_baseline[bp]
        
        e_savings = (baseline.energy_nj - af.energy_nj) / baseline.energy_nj * 100
        a_savings = (baseline.area_ge - af.area_ge) / baseline.area_ge * 100
        
        print(f"{bp:>10} | {af.latency_ns:>12.4f} | {af.energy_nj:>12.6f} | {af.area_ge:>10.3f} | {e_savings:>9.1f}% | {a_savings:>9.1f}%")
    
    print("\nTRADITIONAL ADDERS (Best at each precision)")
    print("-" * 80)
    print(f"{'Precision':>10} | {'Best Adder':>15} | {'Latency (ns)':>12} | {'Energy (nJ)':>12} | {'Area (GE)':>10}")
    print("-" * 80)
    
    for bp in bit_precisions:
        best_latency = None
        best_energy = None
        best_area = None
        
        for adder_spec in ALL_ADDERS:
            m = get_adder_metrics(bp, adder_spec.key, size)
            
            if best_latency is None or m.latency_ns < best_latency[1].latency_ns:
                best_latency = (adder_spec.label, m)
            if best_energy is None or m.energy_nj < best_energy[1].energy_nj:
                best_energy = (adder_spec.label, m)
            if best_area is None or m.area_ge < best_area[1].area_ge:
                best_area = (adder_spec.label, m)
        
        print(f"{bp:>10} | {best_latency[0]:>15} | {best_latency[1].latency_ns:>12.4f} | {best_energy[1].energy_nj:>12.6f} | {best_area[1].area_ge:>10.3f}")
    
    print("\nDETAILED COMPARISON AT KEY PRECISIONS")
    print("-" * 80)
    
    for bp in [8, 16, 32]:
        if bp not in bit_precisions:
            continue
        
        print(f"\n{bp}-bit precision:")
        print(f"{'Adder':>20} | {'Latency (ns)':>12} | {'Energy (nJ)':>12} | {'Area (GE)':>10}")
        print("-" * 80)
        
        # Adder-free
        af = get_adder_free_metrics(bp, size)
        print(f"{'Adder-Free (AFSRAM)':>20} | {af.latency_ns:>12.4f} | {af.energy_nj:>12.6f} | {af.area_ge:>10.3f}")
        
        # Traditional adders
        for adder_spec in ALL_ADDERS:
            m = get_adder_metrics(bp, adder_spec.key, size)
            print(f"{adder_spec.label:>20} | {m.latency_ns:>12.4f} | {m.energy_nj:>12.6f} | {m.area_ge:>10.3f}")


def generate_paper_comparison() -> None:
    """
    Generate comparison specifically matching the paper's claims.
    """
    print("\n" + "=" * 80)
    print("PAPER VALIDATION: AFSRAM-CIM CLAIMS")
    print("=" * 80)
    print("\nPaper claims (128-bit, 40nm):")
    print("  - Energy: 11.86 fJ per operation")
    print("  - Area: 74.91 um^2 for popcount unit")
    print("  - Energy savings: >3x vs adder-tree")
    print("  - Area savings: ~17x vs adder-tree")
    print()
    
    # Model results at 128-bit
    af = get_adder_free_metrics(128)
    
    print("Model results (128-bit):")
    print(f"  - Energy: {af.energy_nj * 1000:.3f} fJ per operation")
    print(f"  - Area: {af.area_um2:.3f} um^2")
    print()
    
    # Comparison with adder-tree
    comp = compare_with_adder_tree(128)
    
    print("Comparison with Full adder (adder-tree baseline):")
    print(f"  - Energy savings: {comp['energy_savings'] * 100:.1f}% ({comp['energy_savings']:.2f}x)")
    print(f"  - Area savings: {comp['area_savings'] * 100:.1f}% ({1/(1-comp['area_savings']):.1f}x)")
    print()
    
    # Validate against paper claims
    energy_factor = 1 / (1 - comp['energy_savings'])
    area_factor = 1 / (1 - comp['area_savings'])
    
    print("Validation:")
    print(f"  - Energy: Model shows {energy_factor:.1f}x savings (paper claims >3x) {'[PASS]' if energy_factor >= 3 else '[FAIL]'}")
    print(f"  - Area: Model shows {area_factor:.1f}x savings (paper claims ~17x) {'[PASS]' if 15 <= area_factor <= 20 else '[FAIL]'}")


if __name__ == "__main__":
    # Test with common bit precisions (limited to 63 by adder_cost_model.py)
    bit_precisions = [1, 2, 4, 8, 16, 32]
    
    # Generate comparison CSV
    print("Generating comparison CSV...")
    generate_comparison_csv(bit_precisions)
    print("[OK] Saved to adder_free_comparison.csv")
    
    # Print summary
    print_comparison_summary(bit_precisions)
    
    # Validate against paper
    generate_paper_comparison()
