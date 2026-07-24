"""
plot_f6_benchmark.py

Generates a PNG bar chart from bbop_statistics.csv using ONLY Python standard
library (struct + zlib for raw PNG encoding). No matplotlib/pillow needed.

Produces: f6_sigmoid_benchmark.png

Usage:
    python plot_f6_benchmark.py
"""

import struct
import zlib
import csv
import math

# ============================================================================
# Minimal PNG writer (standard library only)
# ============================================================================

def write_png(filename, pixels, width, height):
    """Write an RGB pixel array to a PNG file."""
    def make_chunk(chunk_type, data):
        chunk = chunk_type + data
        return struct.pack('>I', len(data)) + chunk + struct.pack('>I', zlib.crc32(chunk) & 0xffffffff)

    # PNG signature
    sig = b'\x89PNG\r\n\x1a\n'

    # IHDR
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    ihdr = make_chunk(b'IHDR', ihdr_data)

    # IDAT - raw pixel data with filter byte 0 per row
    raw = b''
    for y in range(height):
        raw += b'\x00'  # filter: none
        for x in range(width):
            r, g, b = pixels[y][x]
            raw += struct.pack('BBB', r, g, b)
    compressed = zlib.compress(raw)
    idat = make_chunk(b'IDAT', compressed)

    # IEND
    iend = make_chunk(b'IEND', b'')

    with open(filename, 'wb') as f:
        f.write(sig + ihdr + idat + iend)


def fill_rect(pixels, x0, y0, x1, y1, color):
    """Fill a rectangle in the pixel buffer."""
    for y in range(max(0, y0), min(len(pixels), y1)):
        for x in range(max(0, x0), min(len(pixels[0]), x1)):
            pixels[y][x] = color


def draw_text_5x7(pixels, x0, y0, text, color):
    """Draw text using a minimal 5x7 bitmap font (digits, letters, '.', '-', ' ')."""
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
        '(': ['00010','00100','01000','01000','01000','00100','00010'],
        ')': ['01000','00100','00010','00010','00010','00100','01000'],
        '/': ['00001','00010','00010','00100','01000','01000','10000'],
        ':': ['00000','01100','01100','00000','01100','01100','00000'],
    }
    cx = x0
    for ch in text:
        glyph = font.get(ch.upper(), font[' '])
        for row in range(7):
            for col in range(5):
                if glyph[row][col] == '1':
                    px = cx + col
                    py = y0 + row
                    if 0 <= py < len(pixels) and 0 <= px < len(pixels[0]):
                        pixels[py][px] = color
        cx += 6  # 5 pixels + 1 spacing


def draw_hline(pixels, x0, x1, y, color):
    if 0 <= y < len(pixels):
        for x in range(max(0, x0), min(len(pixels[0]), x1)):
            pixels[y][x] = color


def draw_vline(pixels, x, y0, y1, color):
    if 0 <= x < len(pixels[0]):
        for y in range(max(0, y0), min(len(pixels), y1)):
            pixels[y][x] = color


# ============================================================================
# Parse CSV and generate chart
# ============================================================================

def parse_summary(csv_path):
    """Parse the Summary rows from bbop_statistics.csv."""
    summaries = {}
    with open(csv_path, 'r') as f:
        for line in f:
            parts = [p.strip() for p in line.split(',')]
            if parts[0] == 'Summary' and len(parts) >= 7:
                mechanism = parts[4]
                latency = float(parts[5])
                energy = float(parts[6])
                summaries[mechanism] = {'latency': latency, 'energy': energy}
    return summaries


def main():
    csv_path = 'bbop_statistics.csv'
    summaries = parse_summary(csv_path)

    if not summaries:
        print("ERROR: No summary data found in", csv_path)
        return

    # Mechanisms to plot (ordered)
    mechanisms = ['SIMDRAM_1', 'SIMDRAM_64', 'SIMDRAM_64_DYNAMIC',
                  'DAFTPUM_STATIC_LAT', 'DAFTPUM_STATIC_ENE',
                  'DAFTPUM_LAT', 'DAFTPUM_ENE', 'DAFTPUM_TFAW']

    # Short labels for display
    labels = ['SIMDRAM\n1 SA', 'SIMDRAM\n64 SA', 'SIMDRAM\n64 DYN',
              'PROTEUS\nST LAT', 'PROTEUS\nST ENE',
              'PROTEUS\nDY LAT', 'PROTEUS\nDY ENE', 'PROTEUS\nTFAW']
    short_labels = ['SIM 1', 'SIM 64', 'S64 DYN', 'P ST.L', 'P ST.E', 'P DY.L', 'P DY.E', 'P TFAW']

    latencies = [summaries.get(m, {}).get('latency', 0) for m in mechanisms]
    energies = [summaries.get(m, {}).get('energy', 0) for m in mechanisms]

    n = len(mechanisms)

    # Image dimensions
    W = 900
    H = 520
    margin_left = 80
    margin_right = 30
    margin_top = 50
    margin_bottom = 100
    chart_w = W - margin_left - margin_right
    chart_h_half = (H - margin_top - margin_bottom - 30) // 2  # two charts stacked

    # Colors
    BG = (255, 255, 255)
    BLACK = (0, 0, 0)
    GRAY = (200, 200, 200)
    BAR_LAT = (66, 133, 244)   # blue
    BAR_ENE = (234, 67, 53)    # red

    # Create pixel buffer
    pixels = [[BG for _ in range(W)] for _ in range(H)]

    # --- Title ---
    draw_text_5x7(pixels, W//2 - 180, 10, 'F6 SIGMOID PIM BENCHMARK: LATENCY AND ENERGY', BLACK)

    # --- Top chart: Latency ---
    chart_top_y = margin_top
    chart_bot_y = chart_top_y + chart_h_half

    # Y-axis
    draw_vline(pixels, margin_left, chart_top_y, chart_bot_y, BLACK)
    draw_hline(pixels, margin_left, margin_left + chart_w, chart_bot_y, BLACK)

    max_lat = max(latencies) if max(latencies) > 0 else 1
    bar_w = chart_w // (n * 2)

    draw_text_5x7(pixels, 5, chart_top_y + chart_h_half // 2 - 4, 'LAT MS', BLACK)

    for i in range(n):
        bar_h = int((latencies[i] / max_lat) * (chart_h_half - 10))
        x0 = margin_left + 10 + i * (bar_w + bar_w // 2)
        y0 = chart_bot_y - bar_h
        fill_rect(pixels, x0, y0, x0 + bar_w, chart_bot_y, BAR_LAT)
        # Value label
        val_str = '{:.3f}'.format(latencies[i])
        draw_text_5x7(pixels, x0, y0 - 10, val_str, BLACK)
        # X label
        draw_text_5x7(pixels, x0, chart_bot_y + 3, short_labels[i], BLACK)

    # --- Bottom chart: Energy ---
    chart_top_y2 = chart_bot_y + 60
    chart_bot_y2 = chart_top_y2 + chart_h_half

    draw_vline(pixels, margin_left, chart_top_y2, chart_bot_y2, BLACK)
    draw_hline(pixels, margin_left, margin_left + chart_w, chart_bot_y2, BLACK)

    max_ene = max(energies) if max(energies) > 0 else 1

    draw_text_5x7(pixels, 5, chart_top_y2 + chart_h_half // 2 - 4, 'ENE MJ', BLACK)

    for i in range(n):
        bar_h = int((energies[i] / max_ene) * (chart_h_half - 10))
        x0 = margin_left + 10 + i * (bar_w + bar_w // 2)
        y0 = chart_bot_y2 - bar_h
        fill_rect(pixels, x0, y0, x0 + bar_w, chart_bot_y2, BAR_ENE)
        # Value label
        val_str = '{:.4f}'.format(energies[i])
        draw_text_5x7(pixels, x0, y0 - 10, val_str, BLACK)
        # X label
        draw_text_5x7(pixels, x0, chart_bot_y2 + 3, short_labels[i], BLACK)

    # --- Subtitle ---
    draw_text_5x7(pixels, margin_left, H - 20,
                  'F6(X) = MIN(MAX((120 + 60X + 12X2 + X3) / (240 + 24X2), 0), 1)  SIZE=65536', BLACK)

    # Write PNG
    out_path = 'f6_sigmoid_benchmark.png'
    write_png(out_path, pixels, W, H)
    print(f'PNG written to: {out_path}')
    print(f'Image size: {W}x{H}')
    print(f'\nSummary (Total latency / energy for f_6 over 65536 elements):')
    print(f'{"Mechanism":<22} {"Latency (ms)":>14} {"Energy (mJ)":>14}')
    print('-' * 52)
    for i, m in enumerate(mechanisms):
        print(f'{m:<22} {latencies[i]:>14.6f} {energies[i]:>14.6f}')


if __name__ == '__main__':
    main()
