"""
plot_sigmoid_energy_latency.py

Generates a PNG comparing energy consumption and latency of:
  - Original sigmoid (Taylor expansion, 16 bbops)
  - f_6 rational polynomial approximation (11 bbops)

Both simulated through the Proteus PIM analytical model.

Produces: sigmoid_energy_latency_compare.png

Uses ONLY Python standard library (struct + zlib for raw PNG).
"""

import struct
import zlib

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
        '%': ['11001','11010','00100','00100','00100','01011','10011'],
        ',': ['00000','00000','00000','00000','00000','01100','00100'],
        ':': ['00000','01100','01100','00000','01100','01100','00000'],
        '_': ['00000','00000','00000','00000','00000','00000','11111'],
        'X': ['10001','10001','01010','00100','01010','10001','10001'],
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


def draw_hline(pixels, x0, x1, y, color):
    if 0 <= y < len(pixels):
        for x in range(max(0, x0), min(len(pixels[0]), x1)):
            pixels[y][x] = color


def draw_vline(pixels, x, y0, y1, color):
    if 0 <= x < len(pixels[0]):
        for y in range(max(0, y0), min(len(pixels), y1)):
            pixels[y][x] = color


# ============================================================================
# Parse CSV summaries
# ============================================================================

def parse_summary(csv_path):
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


# ============================================================================
# Main
# ============================================================================

def main():
    taylor_data = parse_summary('bbop_statistics_taylor.csv')
    f6_data = parse_summary('bbop_statistics_f6.csv')

    if not taylor_data or not f6_data:
        print("ERROR: Missing CSV files. Run sigmoid_taylor_pim.exe and sigmoid_f6_pim.exe first.")
        return

    # Mechanisms to compare
    mechanisms = ['SIMDRAM_1', 'SIMDRAM_64', 'SIMDRAM_64_DYNAMIC',
                  'DAFTPUM_STATIC_LAT', 'DAFTPUM_STATIC_ENE',
                  'DAFTPUM_LAT', 'DAFTPUM_ENE', 'DAFTPUM_TFAW']

    short_labels = ['SIM 1', 'SIM 64', 'S64 DYN', 'P ST.L', 'P ST.E', 'P DY.L', 'P DY.E', 'P TFAW']

    taylor_lat = [taylor_data.get(m, {}).get('latency', 0) for m in mechanisms]
    taylor_ene = [taylor_data.get(m, {}).get('energy', 0) for m in mechanisms]
    f6_lat = [f6_data.get(m, {}).get('latency', 0) for m in mechanisms]
    f6_ene = [f6_data.get(m, {}).get('energy', 0) for m in mechanisms]

    n = len(mechanisms)

    # Image dimensions
    W = 1000
    H = 700
    margin_left = 90
    margin_right = 40
    margin_top = 55
    margin_bottom = 50
    chart_w = W - margin_left - margin_right

    # Two charts: top = latency, bottom = energy
    gap = 70
    chart_h = (H - margin_top - margin_bottom - gap) // 2

    # Colors
    BG = (255, 255, 255)
    BLACK = (0, 0, 0)
    GRAY = (200, 200, 200)
    TAYLOR_COLOR = (66, 133, 244)    # blue - original sigmoid
    F6_COLOR = (234, 67, 53)         # red - f6 approximation
    SPEEDUP_COLOR = (52, 168, 83)    # green - speedup annotation

    pixels = [[BG for _ in range(W)] for _ in range(H)]

    # --- Title ---
    draw_text_5x7(pixels, W // 2 - 220, 10,
                  'PIM LATENCY AND ENERGY: ORIGINAL SIGMOID VS F6 APPROXIMATION', BLACK)
    draw_text_5x7(pixels, W // 2 - 100, 25, '(65536 ELEMENTS, PROTEUS MODEL)', BLACK)

    # ===== TOP CHART: LATENCY =====
    chart1_top = margin_top
    chart1_bot = chart1_top + chart_h

    # Axes
    draw_vline(pixels, margin_left, chart1_top, chart1_bot, BLACK)
    draw_hline(pixels, margin_left, margin_left + chart_w, chart1_bot, BLACK)

    # Y-axis label
    draw_text_5x7(pixels, 5, chart1_top + chart_h // 2 - 10, 'LATENCY', BLACK)
    draw_text_5x7(pixels, 5, chart1_top + chart_h // 2 + 2, '(MS)', BLACK)

    max_lat = max(max(taylor_lat), max(f6_lat))
    if max_lat == 0:
        max_lat = 1

    # Bar width and spacing
    group_w = chart_w // n
    bar_w = group_w // 3

    for i in range(n):
        group_x = margin_left + i * group_w + group_w // 6

        # Taylor bar (blue)
        h1 = int((taylor_lat[i] / max_lat) * (chart_h - 20))
        x0 = group_x
        fill_rect(pixels, x0, chart1_bot - h1, x0 + bar_w, chart1_bot, TAYLOR_COLOR)

        # f6 bar (red)
        h2 = int((f6_lat[i] / max_lat) * (chart_h - 20))
        x1 = group_x + bar_w + 2
        fill_rect(pixels, x1, chart1_bot - h2, x1 + bar_w, chart1_bot, F6_COLOR)

        # Value labels
        draw_text_5x7(pixels, x0, chart1_bot - h1 - 10,
                      '{:.3f}'.format(taylor_lat[i]), TAYLOR_COLOR)
        draw_text_5x7(pixels, x1, chart1_bot - h2 - 10,
                      '{:.3f}'.format(f6_lat[i]), F6_COLOR)

        # Speedup annotation
        if f6_lat[i] > 0:
            speedup = taylor_lat[i] / f6_lat[i]
            draw_text_5x7(pixels, group_x + bar_w // 2 - 5, chart1_bot - h1 - 22,
                          '{:.1f}X'.format(speedup), SPEEDUP_COLOR)

        # X label
        draw_text_5x7(pixels, group_x, chart1_bot + 4, short_labels[i], BLACK)

    # Grid lines
    for frac in [0.25, 0.5, 0.75]:
        gy = chart1_bot - int(frac * (chart_h - 20))
        for x in range(margin_left + 1, margin_left + chart_w):
            if x % 4 == 0:
                pixels[gy][x] = GRAY

    # ===== BOTTOM CHART: ENERGY =====
    chart2_top = chart1_bot + gap
    chart2_bot = chart2_top + chart_h

    draw_vline(pixels, margin_left, chart2_top, chart2_bot, BLACK)
    draw_hline(pixels, margin_left, margin_left + chart_w, chart2_bot, BLACK)

    draw_text_5x7(pixels, 5, chart2_top + chart_h // 2 - 10, 'ENERGY', BLACK)
    draw_text_5x7(pixels, 5, chart2_top + chart_h // 2 + 2, '(MJ)', BLACK)

    max_ene = max(max(taylor_ene), max(f6_ene))
    if max_ene == 0:
        max_ene = 1

    for i in range(n):
        group_x = margin_left + i * group_w + group_w // 6

        # Taylor bar (blue)
        h1 = int((taylor_ene[i] / max_ene) * (chart_h - 20))
        x0 = group_x
        fill_rect(pixels, x0, chart2_bot - h1, x0 + bar_w, chart2_bot, TAYLOR_COLOR)

        # f6 bar (red)
        h2 = int((f6_ene[i] / max_ene) * (chart_h - 20))
        x1 = group_x + bar_w + 2
        fill_rect(pixels, x1, chart2_bot - h2, x1 + bar_w, chart2_bot, F6_COLOR)

        # Value labels
        draw_text_5x7(pixels, x0, chart2_bot - h1 - 10,
                      '{:.4f}'.format(taylor_ene[i]), TAYLOR_COLOR)
        draw_text_5x7(pixels, x1, chart2_bot - h2 - 10,
                      '{:.4f}'.format(f6_ene[i]), F6_COLOR)

        # Savings annotation
        if f6_ene[i] > 0:
            savings = taylor_ene[i] / f6_ene[i]
            draw_text_5x7(pixels, group_x + bar_w // 2 - 5, chart2_bot - h1 - 22,
                          '{:.1f}X'.format(savings), SPEEDUP_COLOR)

        # X label
        draw_text_5x7(pixels, group_x, chart2_bot + 4, short_labels[i], BLACK)

    # Grid lines
    for frac in [0.25, 0.5, 0.75]:
        gy = chart2_bot - int(frac * (chart_h - 20))
        for x in range(margin_left + 1, margin_left + chart_w):
            if x % 4 == 0:
                pixels[gy][x] = GRAY

    # ===== LEGEND =====
    legend_y = H - 40
    fill_rect(pixels, margin_left + 20, legend_y, margin_left + 50, legend_y + 8, TAYLOR_COLOR)
    draw_text_5x7(pixels, margin_left + 55, legend_y,
                  'ORIGINAL SIGMOID (TAYLOR 5TH ORDER, 16 BBOPS)', BLACK)

    fill_rect(pixels, margin_left + 400, legend_y, margin_left + 430, legend_y + 8, F6_COLOR)
    draw_text_5x7(pixels, margin_left + 435, legend_y,
                  'F6 APPROXIMATION (RATIONAL POLY, 11 BBOPS)', BLACK)

    draw_text_5x7(pixels, margin_left + 20, legend_y + 14,
                  'GREEN = SPEEDUP/SAVINGS FACTOR (HIGHER IS BETTER FOR F6)', SPEEDUP_COLOR)

    # Write PNG
    out_path = 'sigmoid_energy_latency_compare.png'
    write_png(out_path, pixels, W, H)
    print(f'PNG written to: {out_path}')
    print(f'Image size: {W}x{H}')
    print()
    print('Comparison summary:')
    print(f'{"Mechanism":<22} {"Taylor Lat":>10} {"F6 Lat":>10} {"Speedup":>8} {"Taylor Ene":>11} {"F6 Ene":>10} {"Savings":>8}')
    print('-' * 82)
    for i, m in enumerate(mechanisms):
        sp = taylor_lat[i] / f6_lat[i] if f6_lat[i] > 0 else 0
        sv = taylor_ene[i] / f6_ene[i] if f6_ene[i] > 0 else 0
        print(f'{m:<22} {taylor_lat[i]:>10.4f} {f6_lat[i]:>10.4f} {sp:>7.2f}x {taylor_ene[i]:>11.6f} {f6_ene[i]:>10.6f} {sv:>7.2f}x')


if __name__ == '__main__':
    main()
