import numpy as np
import matplotlib.pyplot as plt

def f6(x):
    val = (120 + 60*x + 12*x**2 + x**3) / (240 + 24*x**2)
    return np.clip(val, 0, 1)

def f6_nearest(x):
    val = (128 + 64*x + 16*x**2 + 2*x**3) / (256 + 32*x**2)
    return np.clip(val, 0, 1)

x = np.linspace(-10, 10, 2000)
y1 = f6(x)
y2 = f6_nearest(x)

plt.figure(figsize=(10, 6))
plt.plot(x, y1, label='$f_6(x) = \min(\max(\\frac{120 + 60x + 12x^2 + x^3}{240 + 24x^2}, 0), 1)$', linewidth=2)
plt.plot(x, y2, label='$f_{6,nearest}(x) = \min(\max(\\frac{128 + 64x + 16x^2 + 2x^3}{256 + 32x^2}, 0), 1)$', linestyle='--', linewidth=2)

plt.title('Comparison of $f_6(x)$ and its nearest hardware-friendly approximation', fontsize=14)
plt.xlabel('x', fontsize=12)
plt.ylabel('f(x)', fontsize=12)
plt.legend(fontsize=10)
plt.grid(True, linestyle='--', alpha=0.7)

# Highlight the difference
diff = np.abs(y1 - y2)
plt.fill_between(x, y1, y2, color='red', alpha=0.1, label='Difference')

plt.tight_layout()
plt.savefig('function_comparison.png', dpi=300)
print("Plot saved to function_comparison.png")
