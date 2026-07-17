#!/usr/bin/env python3
"""
run_benchmark.py — Execute sigmoid benchmark on Zybo Z7-10, parse results,
generate CSV with per-point data and a latency graph.

Usage:
  python run_benchmark.py                          # run test from final_git/
  python run_benchmark.py --offline raw_output.txt # re-parse existing mrd dump

Dependencies: matplotlib (for latency graph)
"""

import re
import csv
import os
import sys
import struct
import subprocess
from pathlib import Path
from collections import OrderedDict

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False
    print("WARNING: matplotlib not installed. Graphs will not be generated.", file=sys.stderr)


def find_xsdb():
    candidates = [
        Path(r"D:\2026.1\Vitis\bin\xsdb.bat"),
        Path(r"C:\Xilinx\Vitis\2026.1\bin\xsdb.bat"),
        Path(r"C:\Xilinx\Vivado\2026.1\bin\xsdb.bat"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    from shutil import which
    xsdb = which("xsdb") or which("xsdb.bat")
    return xsdb


def run_test(xsdb_path, bit_path, elf_path, timeout=45):
    cmds = "\n".join([
        "connect",
        'targets -set -filter {name =~ "ARM*#0"}',
        "rst -system",
        "fpga -file [file nativename {%s}]" % bit_path,
        "dow [file nativename {%s}]" % elf_path,
        "con",
        "after 10000",
        "stop",
        "mrd 0x10E000 410",
        "exit",
    ]) + "\n"
    p = subprocess.Popen(
        [xsdb_path, "-interactive"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=str(Path.cwd().resolve()),
    )
    p.stdin.write(cmds.encode())
    p.stdin.flush()
    out, err = p.communicate(timeout=timeout)
    return (out or b"").decode(errors="replace")


def parse_mrd_values(text):
    values = []
    for line in text.splitlines():
        if ':' not in line:
            continue
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        addr_idx = None
        for i, p in enumerate(parts):
            if re.match(r'^[0-9A-Fa-f]+:$', p):
                addr_idx = i
                break
        if addr_idx is None:
            continue
        for p in parts[addr_idx + 1:]:
            try:
                values.append(int(p, 16))
            except ValueError:
                pass
    return values


def u32_to_float(v):
    return struct.unpack('f', struct.pack('I', v))[0]


def q4_12_to_float(v):
    v = v & 0xFFFF
    if v & 0x8000:
        v -= 0x10000
    return v / 4096.0


def parse_x_raw_points(path):
    with open(path) as f:
        text = f.read()
    m = re.search(r'x_raw_points\[N_POINTS\]\s*=\s*\{(.*?)\};', text, re.DOTALL)
    if not m:
        return []
    return [int(n) for n in re.findall(r'-?\d+', m.group(1))]


def compute_throughput(avg_latency_s):
    return 1.0 / avg_latency_s if avg_latency_s > 0 else 0.0


def write_csv(rows, summary, path):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow([
            'point', 'x_raw', 'x_float', 'cycles', 'latency_ns',
            'y_measured', 'y_ideal', 'abs_error'
        ])
        for r in rows:
            w.writerow([
                r['point'], r['x_raw'], f"{r['x_float']:.6f}",
                r['cycles'], f"{r['latency_ns']:.3f}",
                f"{r['y_measured']:.6f}", f"{r['y_ideal']:.6f}",
                f"{r['abs_error']:.8f}",
            ])
        w.writerow([])
        w.writerow(['=== SUMMARY ==='])
        for k, v in summary.items():
            w.writerow([k, v])


def generate_latency_graph(rows, summary, output_prefix):
    if not HAS_MPL:
        return

    x_vals = [r['x_float'] for r in rows]
    lat_ns = [r['latency_ns'] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(x_vals, lat_ns, 'b.', markersize=4)
    ax.axhline(y=summary.get('lat_avg_ns', 0), color='orange', linestyle='--',
               linewidth=1, label=f"Avg = {summary.get('lat_avg_ns', 0):.1f} ns")
    ax.axhline(y=summary.get('lat_min_ns', 0), color='g', linestyle=':',
               linewidth=1, label=f"Min = {summary.get('lat_min_ns', 0):.1f} ns")
    ax.axhline(y=summary.get('lat_max_ns', 0), color='r', linestyle=':',
               linewidth=1, label=f"Max = {summary.get('lat_max_ns', 0):.1f} ns")
    ax.set_xlabel('Input x')
    ax.set_ylabel('Latency (ns)')
    ax.set_title('Sigmoid Computation Latency vs Input')
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.savefig(f'{output_prefix}_latency.png', dpi=150, bbox_inches='tight')
    plt.close(fig)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Run sigmoid benchmark on Zybo Z7-10 and analyze results')
    parser.add_argument('--offline', metavar='RAW_TXT',
                        help='Skip hardware test; parse existing mrd dump file')
    parser.add_argument('--xsdb', help='Path to xsdb.bat (auto-detected if omitted)')
    parser.add_argument('--bit', help='Path to system_wrapper.bit')
    parser.add_argument('--elf', help='Path to sigmoid_ocm.elf')
    parser.add_argument('--stimuli', help='Path to stimuli_points.h')
    parser.add_argument('--output', default='results',
                        help='Output prefix for CSV and graphs (default: results')
    parser.add_argument('--outdir', default='.',
                        help='Output directory for CSV and graphs (default: cwd)')
    parser.add_argument('--timeout', type=int, default=45,
                        help='Timeout in seconds for xsdb (default: 45)')
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    cwd = Path.cwd().resolve()
    outdir = Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    output_prefix = str(outdir / args.output)

    stim_path = Path(args.stimuli) if args.stimuli else None

    raw_text = None
    if args.offline:
        offline_path = Path(args.offline).resolve()
        if not offline_path.exists():
            print(f"Error: offline file not found: {offline_path}")
            sys.exit(1)
        with open(offline_path) as f:
            raw_text = f.read()
        print(f"Parsing offline dump: {offline_path}")
    else:
        xsdb_path = args.xsdb or find_xsdb()
        if not xsdb_path:
            print("Error: xsdb not found. Use --xsdb PATH or install Vitis.")
            sys.exit(1)

        if args.bit:
            bit_path = Path(args.bit).resolve()
        else:
            bit_path = cwd / 'vitis_test' / 'platform' / 'export' / 'platform' / 'hw' / 'system_wrapper.bit'
            if not bit_path.exists():
                bit_path = cwd / 'hw' / 'system_wrapper.bit'
            if not bit_path.exists():
                bit_path = script_dir / 'hw' / 'system_wrapper.bit'

        if args.elf:
            elf_path = Path(args.elf).resolve()
        else:
            elf_path = cwd / 'sigmoid_ocm.elf'
            if not elf_path.exists():
                elf_path = script_dir / 'sigmoid_ocm.elf'

        if stim_path is None:
            stim_path = script_dir / 'stimuli_points.h'
            if not stim_path.exists():
                stim_path = cwd / 'stimuli_points.h'

        if not bit_path.exists():
            print(f"Error: bitstream not found. Check --bit or run from correct directory.")
            print(f"  Tried: {bit_path}")
            sys.exit(1)
        if not elf_path.exists():
            print(f"Error: ELF not found. Run compile_ocm_bench.bat first or use --elf.")
            print(f"  Tried: {elf_path}")
            sys.exit(1)

        print(f"xsdb:   {xsdb_path}")
        print(f"bit:    {bit_path}")
        print(f"elf:    {elf_path}")
        print("Running benchmark (wait ~10s)...")
        try:
            raw_text = run_test(xsdb_path, str(bit_path), str(elf_path),
                                timeout=args.timeout)
        except subprocess.TimeoutExpired:
            print("Error: xsdb timed out. Board connected?")
            sys.exit(1)

        raw_path = outdir / f'{args.output}_raw.txt'
        with open(raw_path, 'w') as f:
            f.write(raw_text)
        print(f"Raw output saved: {raw_path}")

    values = parse_mrd_values(raw_text)
    print(f"Parsed {len(values)} words from mrd output")

    if len(values) < 400:
        print(f"Error: expected >=400 words, got {len(values)}")
        print("Raw output may be incomplete. Check *_raw.txt")
        sys.exit(1)

    if stim_path and stim_path.exists():
        x_raw = parse_x_raw_points(stim_path)
    else:
        print("Warning: stimuli_points.h not found; x_float will be 0")
        x_raw = []

    n_points = min(100, min(len(values) // 4, len(x_raw) if x_raw else 100))

    CPU_FREQ = 666666687.0
    rows = []
    for i in range(n_points):
        raw_cycles = values[i * 4 + 0]
        cycles = raw_cycles if raw_cycles < 0xFFFF0000 else None
        y_meas = u32_to_float(values[i * 4 + 1])
        y_ideal = u32_to_float(values[i * 4 + 2])
        err = u32_to_float(values[i * 4 + 3])
        xr = x_raw[i] if i < len(x_raw) else 0
        xf = q4_12_to_float(xr)
        lat_ns = (cycles / CPU_FREQ * 1e9) if cycles is not None else 0

        rows.append(OrderedDict([
            ('point', i), ('x_raw', xr), ('x_float', xf),
            ('cycles', cycles if cycles is not None else 0),
            ('latency_ns', lat_ns),
            ('y_measured', y_meas), ('y_ideal', y_ideal),
            ('abs_error', err),
        ]))

    valid_lat = [r['latency_ns'] for r in rows if r['cycles'] > 0]
    valid_err = [r['abs_error'] for r in rows]
    if valid_lat:
        lat_min_ns = min(valid_lat)
        lat_max_ns = max(valid_lat)
        lat_avg_ns = sum(valid_lat) / len(valid_lat)
    else:
        lat_min_ns = lat_max_ns = lat_avg_ns = 0.0
    if valid_err:
        err_avg = sum(valid_err) / len(valid_err)
        err_max = max(valid_err)
    else:
        err_avg = err_max = 0.0

    avg_lat_s = lat_avg_ns * 1e-9
    throughput = compute_throughput(avg_lat_s)

    summary = OrderedDict([
        ('lat_min_ns', lat_min_ns),
        ('lat_max_ns', lat_max_ns),
        ('lat_avg_ns', lat_avg_ns),
        ('err_avg', err_avg),
        ('err_max', err_max),
        ('throughput_msps', throughput / 1e6),
        ('throughput_ksps', throughput / 1e3),
    ])

    print(f"\n--- Summary ---")
    print(f"  Latency:  min={lat_min_ns:.1f}  max={lat_max_ns:.1f}  avg={lat_avg_ns:.1f} ns")
    print(f"  Error:    avg={err_avg*1e6:.2f}  max={err_max*1e6:.2f} µ")
    print(f"  Throughput: {throughput/1e6:.3f} Msps ({throughput/1e3:.1f} Ksps)")

    csv_path = outdir / f'{args.output}.csv'
    write_csv(rows, summary, csv_path)
    print(f"\nCSV saved: {csv_path}")

    generate_latency_graph(rows, summary, output_prefix)
    p = Path(f'{output_prefix}_latency.png')
    if p.exists():
        print(f"Graph saved: {p}")

    print("\nDone.")


if __name__ == '__main__':
    main()
