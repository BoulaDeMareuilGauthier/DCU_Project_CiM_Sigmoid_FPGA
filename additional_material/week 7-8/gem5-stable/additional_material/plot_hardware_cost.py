import matplotlib.pyplot as plt
import numpy as np

# Data representing hardware logic units
labels = ['Multipliers\n(Generic)', 'Adders & \nSubtractors', 'Dividers\n(Generic)', 'Shifts\n(Free Wiring)']
f6_counts = [2, 7, 1, 6]
f6_nearest_counts = [2, 4, 1, 4]

x = np.arange(len(labels))
width = 0.35

fig, ax = plt.subplots(figsize=(9, 6))

# Plot bars
rects1 = ax.bar(x - width/2, f6_counts, width, label='$f_6(x)$ (Original)', color='#4c72b0', edgecolor='black')
rects2 = ax.bar(x + width/2, f6_nearest_counts, width, label='$f_{6, nearest}(x)$ (Hardware-Friendly)', color='#dd8452', edgecolor='black')

# Formatting
ax.set_ylabel('Number of Operations', fontsize=12, fontweight='bold')
ax.set_title('Hardware Logic Requirements Comparison', fontsize=15, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=12)
ax.legend(fontsize=12, loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=2)
ax.set_ylim(0, max(f6_counts) + 3.5)

# Add text labels on top of bars
def autolabel(rects):
    for rect in rects:
        height = rect.get_height()
        ax.annotate(f'{height}',
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 4),  # 4 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=12, fontweight='bold')

autolabel(rects1)
autolabel(rects2)

# Subplot for Estimated Area & Latency Savings visualization
savings_text = (
    "Estimated Hardware Savings (e.g. @ 16-bit):\n"
    "• Area: ~300 - 450 GE saved (Eliminated 3 Adders)\n"
    "• Latency: Removed 1 sequential addition stage from the\n"
    "  critical path (Bypassed generic constant multipliers)"
)
ax.text(0.5, 0.95, savings_text, 
        transform=ax.transAxes, fontsize=12, fontweight='bold',
        verticalalignment='top', horizontalalignment='center',
        bbox=dict(boxstyle='round,pad=0.8', facecolor='#f0f9e8', edgecolor='#2b8cbe', alpha=0.95))

plt.grid(axis='y', linestyle='--', alpha=0.6)
plt.tight_layout()
plt.savefig('hardware_comparison.png', dpi=300, bbox_inches='tight')
print("Saved to hardware_comparison.png")
