import sys
import numpy as np
import matplotlib.pyplot as plt

sys.path.append('.')
from adder_cost_model import get_adder_metrics
from multiplier_cost_model import get_multiplier_metrics
from divider_cost_model import get_divider_metrics

bit_precisions = list(range(8, 33, 4))
size = 1024

f6_area, f6_energy, f6_latency = [], [], []
f6n_area, f6n_energy, f6n_latency = [], [], []

# Note: The exact keys depend on the script variables, 
# 'trua' for adder, 'mitchell' for multiplier, 'rapid' for divider.
adder_key = 'trua'
mul_key = 'mitchell'
div_key = 'rapid'

for bp in bit_precisions:
    am = get_adder_metrics(bp, adder_key, size)
    mm = get_multiplier_metrics(bp, mul_key, size)
    dm = get_divider_metrics(bp, div_key, size)
    
    d_lat = dm.latency_ns
    d_ene = dm.energy_nj
    d_area = dm.area_ge
    
    # f6 costs (2 Mul, 7 Add, 1 Div)
    # Critical Path Latency: 2 Mul + 4 Add + 1 Div
    f6_area.append(2 * mm.area_ge + 7 * am.area_ge + 1 * d_area)
    f6_energy.append(2 * mm.energy_nj + 7 * am.energy_nj + 1 * d_ene)
    f6_latency.append(2 * mm.latency_ns + 4 * am.latency_ns + 1 * d_lat)
    
    # f6_nearest costs (2 Mul, 4 Add, 1 Div)
    # Critical Path Latency: 2 Mul + 3 Add + 1 Div
    f6n_area.append(2 * mm.area_ge + 4 * am.area_ge + 1 * d_area)
    f6n_energy.append(2 * mm.energy_nj + 4 * am.energy_nj + 1 * d_ene)
    f6n_latency.append(2 * mm.latency_ns + 3 * am.latency_ns + 1 * d_lat)

fig, axes = plt.subplots(1, 3, figsize=(18, 5.5))
fig.suptitle('Cost Comparison: $f_6(x)$ vs $f_{6, nearest}(x)$ \n(Using TruA Adder, Mitchell Multiplier, RAPID Divider)', fontsize=15, fontweight='bold', y=1.05)

ax = axes[0]
ax.plot(bit_precisions, f6_area, label='$f_6(x)$ (7 Adders)', marker='o', linewidth=2, color='#4c72b0')
ax.plot(bit_precisions, f6n_area, label='$f_{6, nearest}(x)$ (4 Adders)', marker='s', linestyle='--', linewidth=2, color='#dd8452')
ax.set_title('Area vs Bit Precision', fontsize=14)
ax.set_xlabel('Bit Precision (bits)', fontsize=12)
ax.set_ylabel('Area (Gate Equivalents)', fontsize=12)
ax.legend(fontsize=11)
ax.grid(True, linestyle='--', alpha=0.6)

ax = axes[1]
ax.plot(bit_precisions, f6_latency, label='$f_6(x)$ (4 Adder Stages)', marker='o', linewidth=2, color='#4c72b0')
ax.plot(bit_precisions, f6n_latency, label='$f_{6, nearest}(x)$ (3 Adder Stages)', marker='s', linestyle='--', linewidth=2, color='#dd8452')
ax.set_title('Latency vs Bit Precision', fontsize=14)
ax.set_xlabel('Bit Precision (bits)', fontsize=12)
ax.set_ylabel('Latency (ns)', fontsize=12)
ax.legend(fontsize=11)
ax.grid(True, linestyle='--', alpha=0.6)

ax = axes[2]
ax.plot(bit_precisions, f6_energy, label='$f_6(x)$', marker='o', linewidth=2, color='#4c72b0')
ax.plot(bit_precisions, f6n_energy, label='$f_{6, nearest}(x)$', marker='s', linestyle='--', linewidth=2, color='#dd8452')
ax.set_title('Energy vs Bit Precision', fontsize=14)
ax.set_xlabel('Bit Precision (bits)', fontsize=12)
ax.set_ylabel('Energy (nJ)', fontsize=12)
ax.legend(fontsize=11)
ax.grid(True, linestyle='--', alpha=0.6)

plt.tight_layout()
plt.savefig('formula_cost_comparison.png', dpi=300, bbox_inches='tight')
print("Saved to formula_cost_comparison.png")
