#include <stdint.h>
#include "ps7_init.h"

#define SLCR_UNLOCK      0xF8000008u
#define SLCR_LOCK        0xF8000004u
#define FCLK_CLK0_CTRL   0xF8000150u
#define FPGA_RST_CTRL    0xF8000240u
#define LVL_SHFTR_EN     0xF8000900u

static void enable_pl(void) {
    *(volatile uint32_t *)SLCR_UNLOCK = 0xDF0Du;

    *(volatile uint32_t *)FCLK_CLK0_CTRL = 0x00000007u;

    *(volatile uint32_t *)FPGA_RST_CTRL = 0x00000000u;

    *(volatile uint32_t *)LVL_SHFTR_EN = 0x0000000Fu;

    *(volatile uint32_t *)SLCR_LOCK = 0x767Bu;
}

extern int benchmark_main(void);

int main(void) {
    ps7_init();
    enable_pl();
    return benchmark_main();
}
