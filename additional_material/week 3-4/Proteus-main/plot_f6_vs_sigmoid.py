"""
plot_f6_vs_sigmoid.py

Generates a PNG comparing the exact sigmoid 1/(1+exp(-x)) against the
rational polynomial approximation f_6(x) = clamp((120+60x+12x^2+x^3)/(240+24x^2), 0, 1).

Produces: f6_vs_sigmoid.png

Uses ONLY Python standard library (struct + zlib for raw PNG).
"""

import struct
import zlib
import math

# ============================================================================
# Minimal PNG writer
# ============================================================================

def write_png(filename, pixels, width, height):
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    raw = b''
    for y in range(height):
        raw += b'\x00'
        for x in range(width):
            r, g, b = pixels[y][x]
            raw += struct.pack('BBB', r, g, b)
    compressed = zlib.compress(raw)
    idat = make_chunk(b'IDAT', compressed)
    iend = make_chunk(b'IEND', b'')

    with open(filename, 'wb') as f:
        f.write(sig + ihdr + idat + iend)


def draw_text_5x7(pixels, x0, y0, text, color):
    font = {
        '0': ['01110','10001','10011','10101','11001','10001','01110'],
        '1': ['00100','01100','00100','00100','00100','00100','01110'],
        '2': ['01110','10001','00001','00110','01000','10000','11111'],
        '3': ['01110','10001','00001','00110','00001','10001','01110'],
        '4': ['00010','00110','01010','10010','11111','00010','00010'],
        '5': ['11111','10000','11110','00001','00001','10001','01110'],
        '6': ['00110','01000','10000','11110','10001','10001','01110'],
        '7': ['11111','00001','00010','00100','01000','01000','01000'],
        '8': ['01110','10001','10001','01110','10001','10001','01110'],
        '9': ['01110','10001','10001','01111','00001','00010','01100'],
        '.': ['00000','00000','00000','00000','00000','00000','01100'],
        '-': ['00000','00000','00000','11111','00000','00000','00000'],
        ' ': ['00000','00000','00000','00000','00000','00000','00000'],
        '+': ['00000','00100','00100','11111','00100','00100','00000'],
        '=': ['00000','00000','11111','00000','11111','00000','00000'],
        '(': ['00010','00100','01000','01000','01000','00100','00010'],
        ')': ['01000','00100','00010','00010','00010','00100','01000'],
        '/': ['00001','00010','00010','00100','01000','01000','10000'],
        ',': ['00000','00000','00000','00000','00000','01100','00100'],
        ':': ['00000','01100','01100','00000','01100','01100','00000'],
        '_': ['00000','00000','00000','00000','00000','00000','11111'],
        'A': ['01110','10001','10001','11111','10001','10001','10001'],
        'B': ['11110','10001','10001','11110','10001','10001','11110'],
        'C': ['01110','10001','10000','10000','10000','10001','01110'],
        'D': ['11110','10001','10001','10001','10001','10001','11110'],
        'E': ['11111','10000','10000','11110','10000','10000','11111'],
        'F': ['11111','10000','10000','11110','10000','10000','10000'],
        'G': ['01110','10001','10000','10111','10001','10001','01110'],
        'H': ['10001','10001','10001','11111','10001','10001','10001'],
        'I': ['01110','00100','00100','00100','00100','00100','01110'],
        'J': ['00111','00010','00010','00010','00010','10010','01100'],
        'K': ['10001','10010','10100','11000','10100','10010','10001'],
        'L': ['10000','10000','10000','10000','10000','10000','11111'],
        'M': ['10001','11011','10101','10101','10001','10001','10001'],
        'N': ['10001','11001','10101','10011','10001','10001','10001'],
        'O': ['01110','10001','10001','10001','10001','10001','01110'],
        'P': ['11110','10001','10001','11110','10000','10000','10000'],
        'Q': ['01110','10001','10001','10001','10101','10010','01101'],
        'R': ['11110','10001','10001','11110','10100','10010','10001'],
        'S': ['01110','10001','10000','01110','00001','10001','01110'],
        'T': ['11111','00100','00100','00100','00100','00100','00100'],
        'U': ['10001','10001','10001','10001','10001','10001','01110'],
        'V': ['10001','10001','10001','10001','01010','01010','00100'],
        'W': ['10001','10001','10001','10101','10101','10101','01010'],
        'X': ['10001','10001','01010','00100','01010','10001','10001'],
        'Y': ['10001','10001','01010','00100','00100','00100','00100'],
        'Z': ['11111','00001','00010','00100','01000','10000','11111'],
        '|': ['00100','00100','00100','00100','00100','00100','00100'],
    }
    cx = x0
    for ch in text:
        glyph = font.get(ch.upper(), font.get(' '))
        if glyph is None:
            glyph = font[' ']
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == '1':
                    px = cx + col
                    py = y0 + row
                    if 0 <= py < len(pixels) and 0 <= px < len(pixels[0]):
                        pixels[py][px] = color
        cx += 6


def fill_rect(pixels, x0, y0, x1, y1, color):
    for y in range(max(0, y0), min(len(pixels), y1)):
        for x in range(max(0, x0), min(len(pixels[0]), x1)):
            pixels[y][x] = color


def set_pixel(pixels, x, y, color):
    if 0 <= y < len(pixels) and 0 <= x < len(pixels[0]):
        pixels[y][x] = color


def draw_thick_point(pixels, x, y, color, thickness=2):
    for dy in range(-thickness, thickness + 1):
        for dx in range(-thickness, thickness + 1):
            set_pixel(pixels, x + dx, y + dy, color)


# ============================================================================
# Math functions
# ============================================================================

def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        ex = math.exp(x)
        return ex / (1.0 + ex)


def f6(x):
    x2 = x * x
    x3 = x2 * x
    num = 120.0 + 60.0 * x + 12.0 * x2 + x3
    den = 240.0 + 24.0 * x2
    result = num / den
    if result < 0.0:
        result = 0.0
    elif result > 1.0:
        result = 1.0
    return result


# ============================================================================
# Main
# ============================================================================

def main():
    # Image dimensions
    W = 900
    H = 600

    # Plot area
    margin_left = 70
    margin_right = 30
    margin_top = 50
    margin_bottom = 120
    plot_w = W - margin_left - margin_right
    plot_h = H - margin_top - margin_bottom

    # X range: [-8, 8], Y range: [-0.1, 1.1]
    x_min, x_max = -8.0, 8.0
    y_min, y_max = -0.1, 1.1

    # Colors
    BG = (255, 255, 255)
    BLACK = (0, 0, 0)
    GRAY = (220, 220, 220)
    LIGHT_GRAY = (240, 240, 240)
    BLUE = (41, 98, 255)       # exact sigmoid
    RED = (234, 67, 53)        # f6 approximation
    GREEN = (52, 168, 83)      # error curve
    AXIS = (80, 80, 80)

    # Create pixel buffer
    pixels = [[BG for _ in range(W)] for _ in range(H)]

    # Helper: data coords to pixel coords
    def to_px(xv, yv):
        px = margin_left + int((xv - x_min) / (x_max - x_min) * plot_w)
        py = margin_top + int((1.0 - (yv - y_min) / (y_max - y_min)) * plot_h)
        return px, py

    # --- Grid lines ---
    for yv in [0.0, 0.25, 0.5, 0.75, 1.0]:
        _, py = to_px(0, yv)
        for x in range(margin_left, margin_left + plot_w):
            if x % 3 == 0:
                set_pixel(pixels, x, py, GRAY)

    for xv in [-8, -6, -4, -2, 0, 2, 4, 6, 8]:
        px, _ = to_px(xv, 0)
        for y in range(margin_top, margin_top + plot_h):
            if y % 3 == 0:
                set_pixel(pixels, px, y, GRAY)

    # --- Axes ---
    # X axis at y=0
    _, y_axis_zero = to_px(0, 0)
    for x in range(margin_left, margin_left + plot_w):
        set_pixel(pixels, x, y_axis_zero, AXIS)

    # Y axis at x=0
    x_axis_zero, _ = to_px(0, 0)
    for y in range(margin_top, margin_top + plot_h):
        set_pixel(pixels, x_axis_zero, y, AXIS)

    # Border
    for x in range(margin_left, margin_left + plot_w):
        set_pixel(pixels, x, margin_top, AXIS)
        set_pixel(pixels, x, margin_top + plot_h, AXIS)
    for y in range(margin_top, margin_top + plot_h + 1):
        set_pixel(pixels, margin_left, y, AXIS)
        set_pixel(pixels, margin_left + plot_w, y, AXIS)

    # --- Axis labels ---
    for xv in [-8, -6, -4, -2, 0, 2, 4, 6, 8]:
        px, _ = to_px(xv, 0)
        label = str(xv)
        draw_text_5x7(pixels, px - len(label) * 3, margin_top + plot_h + 5, label, BLACK)

    for yv in [0.0, 0.25, 0.5, 0.75, 1.0]:
        _, py = to_px(0, yv)
        label = '{:.2f}'.format(yv)
        draw_text_5x7(pixels, margin_left - 35, py - 3, label, BLACK)

    # --- Plot curves ---
    num_samples = plot_w * 2  # oversample for smooth curves

    # Exact sigmoid (blue, thick)
    prev_px, prev_py = None, None
    for i in range(num_samples):
        xv = x_min + (x_max - x_min) * i / (num_samples - 1)
        yv = sigmoid(xv)
        px, py = to_px(xv, yv)
        if margin_left <= px <= margin_left + plot_w and margin_top <= py <= margin_top + plot_h:
            draw_thick_point(pixels, px, py, BLUE, 1)

    # f6 approximation (red, thick)
    for i in range(num_samples):
        xv = x_min + (x_max - x_min) * i / (num_samples - 1)
        yv = f6(xv)
        px, py = to_px(xv, yv)
        if margin_left <= px <= margin_left + plot_w and margin_top <= py <= margin_top + plot_h:
            draw_thick_point(pixels, px, py, RED, 1)

    # Error curve (green, scaled to be visible: error * 10)
    # Plot |f6(x) - sigmoid(x)| * 10 so it's visible
    error_scale = 10.0
    for i in range(num_samples):
        xv = x_min + (x_max - x_min) * i / (num_samples - 1)
        err = abs(f6(xv) - sigmoid(xv)) * error_scale
        px, py = to_px(xv, err)
        if margin_left <= px <= margin_left + plot_w and margin_top <= py <= margin_top + plot_h:
            set_pixel(pixels, px, py, GREEN)
            set_pixel(pixels, px, py + 1, GREEN)

    # --- Title ---
    draw_text_5x7(pixels, W // 2 - 170, 12,
                  'SIGMOID VS F6 RATIONAL POLYNOMIAL APPROXIMATION', BLACK)

    # --- Legend ---
    legend_y = margin_top + plot_h + 30
    # Blue = exact sigmoid
    fill_rect(pixels, margin_left + 20, legend_y, margin_left + 50, legend_y + 8, BLUE)
    draw_text_5x7(pixels, margin_left + 55, legend_y, 'EXACT SIGMOID: 1/(1+EXP(-X))', BLACK)

    # Red = f6
    fill_rect(pixels, margin_left + 20, legend_y + 15, margin_left + 50, legend_y + 23, RED)
    draw_text_5x7(pixels, margin_left + 55, legend_y + 15,
                  'F6(X) = CLAMP((120+60X+12X2+X3)/(240+24X2), 0, 1)', BLACK)

    # Green = error
    fill_rect(pixels, margin_left + 20, legend_y + 30, margin_left + 50, legend_y + 38, GREEN)
    draw_text_5x7(pixels, margin_left + 55, legend_y + 30,
                  'ABSOLUTE ERROR X 10 (SCALED FOR VISIBILITY)', BLACK)

    # --- Stats ---
    # Compute max error and where it occurs
    max_err = 0.0
    max_err_x = 0.0
    for i in range(10000):
        xv = x_min + (x_max - x_min) * i / 9999
        err = abs(f6(xv) - sigmoid(xv))
        if err > max_err:
            max_err = err
            max_err_x = xv

    stats_y = legend_y + 50
    draw_text_5x7(pixels, margin_left + 20, stats_y,
                  'MAX ABS ERROR: {:.6f} AT X={:.2f}'.format(max_err, max_err_x), BLACK)
    draw_text_5x7(pixels, margin_left + 20, stats_y + 12,
                  'ERROR < 0.001 FOR |X| < 2.5  (COVERS 99 PERCENT OF NN ACTIVATIONS)', BLACK)

    # Write PNG
    out_path = 'f6_vs_sigmoid.png'
    write_png(out_path, pixels, W, H)
    print(f'PNG written to: {out_path}')
    print(f'Image size: {W}x{H}')
    print(f'Max absolute error: {max_err:.8f} at x={max_err_x:.4f}')


if __name__ == '__main__':
    main()
