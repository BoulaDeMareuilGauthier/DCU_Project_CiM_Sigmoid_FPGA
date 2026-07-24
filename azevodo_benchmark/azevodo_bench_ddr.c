#include <stdint.h>
#include "xil_io.h"
#include "stimuli_points.h"

#define SIGMOID_BASE 0x43C00000u
#define REG_X      0x00
#define REG_Y      0x04
#define REG_CTRL   0x08
#define REG_STATUS 0x0C
#define CTRL_START 0x1

#define RESULTS_BASE 0x10E000u
#define MARKER_ADDR  0x10E020u

#ifndef XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ
#define XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ 666666687u
#endif

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

int benchmark_main(void)
{
    volatile uint32_t *marker = (volatile uint32_t *)MARKER_ADDR;
    volatile uint32_t *results = (volatile uint32_t *)RESULTS_BASE;

    *marker = 0xDEADBEEF;

    enable_ccnt();

    uint32_t cycles_buf[N_POINTS];
    short y_raw_buf[N_POINTS];
    int i;
    for (i = 0; i < N_POINTS; i++) {
        Xil_Out32(SIGMOID_BASE + REG_X, (uint32_t)(uint16_t)x_raw_points[i]);

        uint32_t t0 = read_ccnt();
        Xil_Out32(SIGMOID_BASE + REG_CTRL, CTRL_START);
        __asm__ volatile("dsb" ::: "memory");
        uint32_t t1 = read_ccnt();

        cycles_buf[i] = t1 - t0;
        y_raw_buf[i] = (short)Xil_In32(SIGMOID_BASE + REG_Y);
    }

    float cpu_freq = (float)XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ;
    double lat_sum = 0.0, lat_min = 1e18, lat_max = 0.0;
    double err_sum = 0.0, err_max = 0.0;

    for (i = 0; i < N_POINTS; i++) {
        float x_f   = x_raw_points[i] / 4096.0f;
        float y_f   = y_raw_buf[i] / 4096.0f;
        float ideal = ideal_points[i];
        float e = y_f - ideal;
        if (e < 0) e = -e;
        float lat_ns = (float)cycles_buf[i] / cpu_freq * 1.0e9f;

        if (lat_ns < lat_min) lat_min = lat_ns;
        if (lat_ns > lat_max) lat_max = lat_ns;
        lat_sum += lat_ns;
        err_sum += e;
        if (e > err_max) err_max = e;

        results[i * 4 + 0] = cycles_buf[i];
        results[i * 4 + 1] = *(uint32_t *)&y_f;
        results[i * 4 + 2] = *(uint32_t *)&ideal;
        results[i * 4 + 3] = *(uint32_t *)&e;
    }

    results[400] = (uint32_t)(lat_min * 1000.0f);
    results[401] = (uint32_t)(lat_max * 1000.0f);
    results[402] = (uint32_t)(lat_sum / N_POINTS * 1000.0f);
    results[403] = (uint32_t)(err_sum / N_POINTS * 1000000.0f);
    results[404] = (uint32_t)(err_max * 1000000.0f);

    *marker = 0xFFFFFFFF;

    while (1);
    return 0;
}
