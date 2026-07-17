// ============================================================================
// sigmoid_bench.c  –  DCC version (no COM port required)
//
// Bare-metal benchmark for sigmoid_top over AXI4-Lite on Zybo Z7-10.
// Uses 100 points from stimuli_points.h, compares against ideal_points.h.
// Output goes through DCC (JTAG) → visible in xsdb console.
// Timing via Cortex-A9 PMU cycle counter (CP15).
// ============================================================================
#include <stdint.h>
#include "xil_io.h"
#include "xparameters.h"
#include "stimuli_points.h"

#ifndef XPAR_SIGMOID_TOP_0_S_AXI_BASEADDR
#define XPAR_SIGMOID_TOP_0_S_AXI_BASEADDR 0x43C00000
#endif
#define SIGMOID_BASE XPAR_SIGMOID_TOP_0_S_AXI_BASEADDR

#ifndef XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ
#define XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ 666666687u
#endif

#define REG_X      0x00
#define REG_Y      0x04
#define REG_CTRL   0x08
#define REG_STATUS 0x0C
#define STATUS_DONE_MASK 0x2
#define CTRL_START        0x1

// ---- DCC output via JTAG ----
#define DCC_TX *((volatile uint32_t *)0xF800030C)

static void dcc_outchar(char c) {
    DCC_TX = (uint32_t)c;
}

static void dcc_str(const char *s) {
    while (*s) dcc_outchar(*s++);
}

static void dcc_int(int val) {
    char buf[12];
    int i = 0;
    int neg = 0;
    unsigned int v;
    if (val < 0) { neg = 1; v = (unsigned int)(-val); }
    else { v = (unsigned int)val; }
    if (v == 0) { buf[i++] = '0'; }
    else { while (v > 0) { buf[i++] = '0' + (v % 10); v /= 10; } }
    if (neg) dcc_outchar('-');
    while (i > 0) dcc_outchar(buf[--i]);
}

static void dcc_uint(unsigned int v) {
    char buf[12];
    int i = 0;
    if (v == 0) { buf[i++] = '0'; }
    else { while (v > 0) { buf[i++] = '0' + (v % 10); v /= 10; } }
    while (i > 0) dcc_outchar(buf[--i]);
}

static void dcc_float(float f, int decimals) {
    int d;
    if (f < 0.0f) { dcc_outchar('-'); f = -f; }
    dcc_int((int)f);
    dcc_outchar('.');
    unsigned int frac = (unsigned int)((f - (float)(int)f) * 10000.0f);
    char buf[5];
    for (d = 3; d >= 0; d--) { buf[d] = '0' + (frac % 10); frac /= 10; }
    for (d = 0; d < decimals && d < 4; d++) dcc_outchar(buf[d]);
}

// ---- PMU cycle counter ----
static inline void enable_ccnt(void) {
    uint32_t pmcr;
    __asm__ volatile ("mrc p15, 0, %0, c9, c12, 0" : "=r"(pmcr));
    pmcr |= 1u;
    __asm__ volatile ("mcr p15, 0, %0, c9, c12, 0" :: "r"(pmcr));
    uint32_t cnten = 1u << 31;
    __asm__ volatile ("mcr p15, 0, %0, c9, c12, 1" :: "r"(cnten));
}

static inline uint32_t read_ccnt(void) {
    uint32_t v;
    __asm__ volatile ("mrc p15, 0, %0, c9, c13, 0" : "=r"(v));
    return v;
}

int main(void) {
    enable_ccnt();

    uint32_t t0, t1;
    double lat_sum_ns = 0.0, lat_min_ns = 1e18, lat_max_ns = 0.0;
    double err_sum = 0.0, err_max = 0.0;

    dcc_str("\r\n=== sigmoid_bench: 100-point HW benchmark ===\r\n");
    dcc_str("Cycle counter enabled. Running...\r\n\r\n");

    int i;
    for (i = 0; i < N_POINTS; i++) {
        short x_raw = x_raw_points[i];
        float x_float = x_raw / 4096.0f;

        Xil_Out32(SIGMOID_BASE + REG_X, (uint32_t)(uint16_t)x_raw);

        t0 = read_ccnt();
        Xil_Out32(SIGMOID_BASE + REG_CTRL, CTRL_START);

        uint32_t status;
        do { status = Xil_In32(SIGMOID_BASE + REG_STATUS); }
        while (!(status & STATUS_DONE_MASK));
        t1 = read_ccnt();

        short y_raw = (short)Xil_In32(SIGMOID_BASE + REG_Y);
        float y_float = y_raw / 4096.0f;
        float ideal = ideal_points[i];
        float abs_err = y_float - ideal;
        if (abs_err < 0) abs_err = -abs_err;

        uint32_t cycles = t1 - t0;
        double lat_ns = 1.0e9 * (double)cycles /
                        (double)XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ;
        if (lat_ns < lat_min_ns) lat_min_ns = lat_ns;
        if (lat_ns > lat_max_ns) lat_max_ns = lat_ns;
        lat_sum_ns += lat_ns;
        err_sum += abs_err;
        if (abs_err > err_max) err_max = abs_err;

        /* Print: [idx] x=... hw=... ideal=... err=... lat=...ns */
        dcc_str("["); dcc_int(i); dcc_str("] ");
        dcc_str("x="); dcc_float(x_float, 4); dcc_str(" ");
        dcc_str("hw="); dcc_float(y_float, 6); dcc_str(" ");
        dcc_str("ideal="); dcc_float(ideal, 6); dcc_str(" ");
        dcc_str("err="); dcc_float(abs_err, 6); dcc_str(" ");
        dcc_int((int)cycles); dcc_str("cyc ");
        dcc_float((float)lat_ns, 1); dcc_str("ns\r\n");
    }

    dcc_str("\r\n=== Summary ===\r\n");
    dcc_str("Points: "); dcc_int(N_POINTS); dcc_str("\r\n");
    dcc_str("Latency (ns): min="); dcc_float((float)lat_min_ns, 1);
    dcc_str("  max="); dcc_float((float)lat_max_ns, 1);
    dcc_str("  avg="); dcc_float((float)(lat_sum_ns / N_POINTS), 1);
    dcc_str("\r\n");
    dcc_str("Abs error:    mean="); dcc_float((float)(err_sum / N_POINTS), 6);
    dcc_str("  max="); dcc_float((float)err_max, 6);
    dcc_str("\r\n");

    dcc_str("\r\nDone.\r\n");
    return 0;
}
