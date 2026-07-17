#!/usr/bin/env python3
"""
Generate comparison graphs for adder-free vs traditional adders.

This script creates visualizations comparing the AFSRAM-CIM adder-free
approach against traditional adders across multiple metrics.
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import List, Dict
from adder_cost_model import ALL_ADDERS, get_adder_metrics
from adder_free_cost_model import get_adder_free_metrics


def plot_energy_comparison(
    bit_precisions: List[int],
    size: int = 1024,
    output_file: str = "adder_free_energy_comparison.png",
) -> None:
    """
    Plot energy comparison across bit precisions.
    """
    plt.figure(figsize=(12, 6))
    
    # Get adder-free data
    af_energy = [get_adder_free_metrics(bp, size).energy_nj for bp in bit_precisions]
    
    # Get traditional adder data
    adder_data = {}
    for adder_spec in ALL_ADDERS:
        energies = [get_adder_metrics(bp, adder_spec.key, size).energy_nj for bp in bit_precisions]
        adder_data[adder_spec.label] = energies
    
    # Plot adder-free
    plt.plot(bit_precisions, af_energy, 'o-', linewidth=3, markersize=10, 
             label='Adder-Free (AFSRAM)', color='#2ecc71', zorder=10)
    
    # Plot traditional adders (lighter colors, thinner lines)
    colors = ['#e74c3c', '#3498db', '#9b59b6', '#f39c12', '#1abc9c', 
              '#34495e', '#e67e22', '#95a5a6', '#16a085', '#c0392b']
    
    for i, (label, energies) in enumerate(adder_data.items()):
        plt.plot(bit_precisions, energies, '--', linewidth=1.5, alpha=0.6,
                 label=label, color=colors[i % len(colors)])
    
    plt.xlabel('Bit Precision', fontsize=12, fontweight='bold')
    plt.ylabel('Energy (nJ)', fontsize=12, fontweight='bold')
    plt.title('Energy Comparison: Adder-Free vs Traditional Adders', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved energy comparison to {output_file}")
    plt.close()


def plot_area_comparison(
    bit_precisions: List[int],
    size: int = 1024,
    output_file: str = "adder_free_area_comparison.png",
) -> None:
    """
    Plot area comparison across bit precisions.
    """
    plt.figure(figsize=(12, 6))
    
    # Get adder-free data
    af_area = [get_adder_free_metrics(bp, size).area_ge for bp in bit_precisions]
    
    # Get traditional adder data
    adder_data = {}
    for adder_spec in ALL_ADDERS:
        areas = [get_adder_metrics(bp, adder_spec.key, size).area_ge for bp in bit_precisions]
        adder_data[adder_spec.label] = areas
    
    # Plot adder-free
    plt.plot(bit_precisions, af_area, 'o-', linewidth=3, markersize=10,
             label='Adder-Free (AFSRAM)', color='#2ecc71', zorder=10)
    
    # Plot traditional adders
    colors = ['#e74c3c', '#3498db', '#9b59b6', '#f39c12', '#1abc9c',
              '#34495e', '#e67e22', '#95a5a6', '#16a085', '#c0392b']
    
    for i, (label, areas) in enumerate(adder_data.items()):
        plt.plot(bit_precisions, areas, '--', linewidth=1.5, alpha=0.6,
                 label=label, color=colors[i % len(colors)])
    
    plt.xlabel('Bit Precision', fontsize=12, fontweight='bold')
    plt.ylabel('Area (Gate Equivalents)', fontsize=12, fontweight='bold')
    plt.title('Area Comparison: Adder-Free vs Traditional Adders', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved area comparison to {output_file}")
    plt.close()


def plot_latency_comparison(
    bit_precisions: List[int],
    size: int = 1024,
    output_file: str = "adder_free_latency_comparison.png",
) -> None:
    """
    Plot latency comparison across bit precisions.
    """
    plt.figure(figsize=(12, 6))
    
    # Get adder-free data
    af_latency = [get_adder_free_metrics(bp, size).latency_ns for bp in bit_precisions]
    
    # Get traditional adder data
    adder_data = {}
    for adder_spec in ALL_ADDERS:
        latencies = [get_adder_metrics(bp, adder_spec.key, size).latency_ns for bp in bit_precisions]
        adder_data[adder_spec.label] = latencies
    
    # Plot adder-free
    plt.plot(bit_precisions, af_latency, 'o-', linewidth=3, markersize=10,
             label='Adder-Free (AFSRAM)', color='#2ecc71', zorder=10)
    
    # Plot traditional adders
    colors = ['#e74c3c', '#3498db', '#9b59b6', '#f39c12', '#1abc9c',
              '#34495e', '#e67e22', '#95a5a6', '#16a085', '#c0392b']
    
    for i, (label, latencies) in enumerate(adder_data.items()):
        plt.plot(bit_precisions, latencies, '--', linewidth=1.5, alpha=0.6,
                 label=label, color=colors[i % len(colors)])
    
    plt.xlabel('Bit Precision', fontsize=12, fontweight='bold')
    plt.ylabel('Latency (ns)', fontsize=12, fontweight='bold')
    plt.title('Latency Comparison: Adder-Free vs Traditional Adders', fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved latency comparison to {output_file}")
    plt.close()


def plot_savings_comparison(
    bit_precisions: List[int],
    size: int = 1024,
    output_file: str = "adder_free_savings_comparison.png",
) -> None:
    """
    Plot energy and area savings percentage vs Full adder.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Calculate savings
    energy_savings = []
    area_savings = []
    
    for bp in bit_precisions:
        af = get_adder_free_metrics(bp, size)
        full = get_adder_metrics(bp, "full", size)
        
        e_sav = (full.energy_nj - af.energy_nj) / full.energy_nj * 100
        a_sav = (full.area_ge - af.area_ge) / full.area_ge * 100
        
        energy_savings.append(e_sav)
        area_savings.append(a_sav)
    
    # Energy savings
    bars1 = ax1.bar(bit_precisions, energy_savings, color='#2ecc71', alpha=0.8, edgecolor='darkgreen')
    ax1.set_xlabel('Bit Precision', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Energy Savings (%)', fontsize=11, fontweight='bold')
    ax1.set_title('Energy Savings vs Full Adder', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    ax1.set_ylim([95, 100])
    
    # Add value labels on bars
    for bar, val in zip(bars1, energy_savings):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.1f}%', ha='center', va='bottom', fontsize=9)
    
    # Area savings
    bars2 = ax2.bar(bit_precisions, area_savings, color='#3498db', alpha=0.8, edgecolor='darkblue')
    ax2.set_xlabel('Bit Precision', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Area Savings (%)', fontsize=11, fontweight='bold')
    ax2.set_title('Area Savings vs Full Adder', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_ylim([90, 100])
    
    # Add value labels on bars
    for bar, val in zip(bars2, area_savings):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.1f}%', ha='center', va='bottom', fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved savings comparison to {output_file}")
    plt.close()


def plot_radar_comparison(
    bit_precision: int = 16,
    size: int = 1024,
    output_file: str = "adder_free_radar_comparison.png",
) -> None:
    """
    Create a radar chart comparing adder-free with best traditional adders at a specific precision.
    """
    from math import pi
    
    # Get metrics
    af = get_adder_free_metrics(bit_precision, size)
    
    # Get best traditional adders by category
    best_latency = min(ALL_ADDERS, key=lambda a: get_adder_metrics(bit_precision, a.key, size).latency_ns)
    best_energy = min(ALL_ADDERS, key=lambda a: get_adder_metrics(bit_precision, a.key, size).energy_nj)
    best_area = min(ALL_ADDERS, key=lambda a: get_adder_metrics(bit_precision, a.key, size).area_ge)
    
    best_latency_m = get_adder_metrics(bit_precision, best_latency.key, size)
    best_energy_m = get_adder_metrics(bit_precision, best_energy.key, size)
    best_area_m = get_adder_metrics(bit_precision, best_area.key, size)
    
    # Normalize metrics (lower is better, so we invert)
    def normalize(value, max_val):
        return (1 - value / max_val) * 100
    
    # Find max values for normalization
    max_latency = max(af.latency_ns, best_latency_m.latency_ns)
    max_energy = max(af.energy_nj, best_energy_m.energy_nj)
    max_area = max(af.area_ge, best_area_m.area_ge)
    
    # Categories
    categories = ['Latency', 'Energy', 'Area']
    N = len(categories)
    
    # Angles
    angles = [n / float(N) * 2 * pi for n in range(N)]
    angles += angles[:1]
    
    # Adder-free values
    af_values = [
        normalize(af.latency_ns, max_latency),
        normalize(af.energy_nj, max_energy),
        normalize(af.area_ge, max_area),
    ]
    af_values += af_values[:1]
    
    # Best traditional values (average of best in each category)
    trad_values = [
        normalize(best_latency_m.latency_ns, max_latency),
        normalize(best_energy_m.energy_nj, max_energy),
        normalize(best_area_m.area_ge, max_area),
    ]
    trad_values += trad_values[:1]
    
    # Plot
    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
    
    # Adder-free
    ax.plot(angles, af_values, 'o-', linewidth=3, color='#2ecc71', label='Adder-Free (AFSRAM)')
    ax.fill(angles, af_values, alpha=0.25, color='#2ecc71')
    
    # Traditional
    ax.plot(angles, trad_values, 'o-', linewidth=3, color='#e74c3c', label='Best Traditional')
    ax.fill(angles, trad_values, alpha=0.25, color='#e74c3c')
    
    # Labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=11, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(['20%', '40%', '60%', '80%', '100%'], fontsize=9)
    ax.grid(True, alpha=0.3)
    
    plt.title(f'Performance Comparison at {bit_precision}-bit Precision', 
              fontsize=14, fontweight='bold', pad=20)
    plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=11)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved radar comparison to {output_file}")
    plt.close()


def plot_paper_validation(
    output_file: str = "adder_free_paper_validation.png",
) -> None:
    """
    Create a validation plot comparing model results with paper claims.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Paper claims
    paper_energy = 11.86  # fJ
    paper_area = 74.91  # um^2
    
    # Model results at 128-bit
    af = get_adder_free_metrics(128)
    model_energy = af.energy_nj * 1000  # Convert to fJ
    model_area = af.area_um2
    
    # Energy comparison
    categories = ['Paper Claim', 'Model Result']
    energies = [paper_energy, model_energy]
    colors = ['#3498db', '#2ecc71']
    
    bars1 = ax1.bar(categories, energies, color=colors, alpha=0.8, edgecolor='black')
    ax1.set_ylabel('Energy (fJ)', fontsize=11, fontweight='bold')
    ax1.set_title('Energy per Operation (128-bit)', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bar, val in zip(bars1, energies):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.2f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # Area comparison
    areas = [paper_area, model_area]
    
    bars2 = ax2.bar(categories, areas, color=colors, alpha=0.8, edgecolor='black')
    ax2.set_ylabel('Area (um^2)', fontsize=11, fontweight='bold')
    ax2.set_title('Popcount Unit Area (128-bit)', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Add value labels
    for bar, val in zip(bars2, areas):
        height = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.2f}', ha='center', va='bottom', fontsize=11, fontweight='bold')
    
    # Add validation text
    fig.suptitle('AFSRAM-CIM Paper Validation (128-bit, 40nm)', 
                 fontsize=14, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"[OK] Saved paper validation to {output_file}")
    plt.close()


if __name__ == "__main__":
    # Set style
    plt.style.use('seaborn-v0_8-darkgrid')
    
    # Bit precisions to plot
    bit_precisions = [1, 2, 4, 8, 16, 32]
    
    print("Generating Adder-Free Comparison Graphs...")
    print("=" * 60)
    
    # Generate all plots
    plot_energy_comparison(bit_precisions)
    plot_area_comparison(bit_precisions)
    plot_latency_comparison(bit_precisions)
    plot_savings_comparison(bit_precisions)
    plot_radar_comparison(bit_precision=16)
    plot_paper_validation()
    
    print("=" * 60)
    print("All graphs generated successfully!")
