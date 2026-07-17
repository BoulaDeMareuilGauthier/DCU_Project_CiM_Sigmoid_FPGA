#include <stdint.h>
#include "xil_printf.h"
#include "xil_types.h"
#include "xil_io.h"
#include "xparameters.h"

#define SIGMOID_BASEADDR XPAR_SIGMOID_TOP_0_BASEADDR

#define X_REG      (SIGMOID_BASEADDR + 0x00)
#define Y_REG      (SIGMOID_BASEADDR + 0x04)
#define CTRL_REG   (SIGMOID_BASEADDR + 0x08)
#define STATUS_REG (SIGMOID_BASEADDR + 0x0C)

#define NUM_POINTS 31
#define Q4_12_ONE 4096

static int16_t float_to_q4_12(float val) {
    if (val > 7.999f)  val = 7.999f;
    if (val < -8.0f)   val = -8.0f;
    return (int16_t)(val * (float)Q4_12_ONE);
}

static float q4_12_to_float(int16_t val) {
    return (float)val / (float)Q4_12_ONE;
}

static void reg_write(uint32_t addr, uint32_t val) {
    *(volatile uint32_t *)addr = val;
}

static uint32_t reg_read(uint32_t addr) {
    return *(volatile uint32_t *)addr;
}

/* Simple exp(x) using Taylor series (no math.h needed) */
static float fast_exp(float x) {
    if (x < -8.0f) return 0.000335f;
    if (x > 8.0f)  return 2980.0f;
    float term = 1.0f;
    float sum  = 1.0f;
    int i;
    for (i = 1; i <= 16; i++) {
        term *= x / (float)i;
        sum  += term;
    }
    return sum;
}

static float fast_sigmoid_ref(float x) {
    return 1.0f / (1.0f + fast_exp(-x));
}

static float fast_fabsf(float x) {
    return (x < 0.0f) ? -x : x;
}

static const float test_points[NUM_POINTS] = {
    -4.8320f, -4.2170f, -3.6510f, -3.1080f, -2.5430f,
    -2.0120f, -1.4870f, -1.0320f, -0.5780f, -0.1950f,
     0.1230f,  0.5670f,  1.0120f,  1.5430f,  2.0980f,
     2.4320f,  2.8760f,  3.2140f,  3.6870f,  4.0230f,
     4.3450f,  4.6780f,  4.9120f,  3.1560f,  1.7890f,
    -0.3450f, -1.6780f, -2.9120f, -3.5670f, -4.1230f,
     0.0000f
};

int main(void) {
    xil_printf("\r\n=== fast_Vaisnav16 Sigmoid HW Accelerator ===\r\n");
    xil_printf("Processing %d points | Q4.12 | Zybo Z7-10\r\n", NUM_POINTS);

    xil_printf("\r\n%-4s  %9s  %6s  %6s  %9s  %9s  %7s\r\n",
               "i", "x(float)", "x(Q12)", "y(Q12)", "hw_y", "ref_y", "error");
    xil_printf("----  ---------  ------  ------  ---------  ---------  -------\r\n");

    float max_err = 0.0f;
    int err_count = 0;

    int i;
    for (i = 0; i < NUM_POINTS; i++) {
        int16_t x_q = float_to_q4_12(test_points[i]);

        /* Write x and start HW */
        reg_write(X_REG, (uint32_t)(uint16_t)x_q);
        reg_write(CTRL_REG, 0x01);

        /* Wait for done (bit 1 of STATUS) */
        while ((reg_read(STATUS_REG) & 0x02) == 0);

        /* Read result */
        int16_t y_hw = (int16_t)(reg_read(Y_REG) & 0xFFFF);
        float y_f    = q4_12_to_float(y_hw);
        float y_ref  = fast_sigmoid_ref(test_points[i]);
        float err    = y_f - y_ref;
        if (err < 0.0f) err = -err;

        if (err > max_err) max_err = err;
        if (err > 0.01f) err_count++;

        xil_printf("[%2d]  %7.4f   %6d  %6d  %7.4f   %7.4f   %.5f\r\n",
                   i, test_points[i], x_q, y_hw, y_f, y_ref, err);
    }

    xil_printf("\r\n=== Summary ===\r\n");
    xil_printf("Points: %d | Max error: %.6f | Errors > 0.01: %d\r\n",
               NUM_POINTS, max_err, err_count);

    return 0;
}
