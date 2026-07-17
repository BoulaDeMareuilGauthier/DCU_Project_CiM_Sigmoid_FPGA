/*
 * Copyright (c) 2025 CMU SAFARI Group
 * Licensed under the MIT License.
 *
 * Standalone test driver for the DAFTPUM-LAT cost model.
 * Verifies that the latency/energy computations match the Proteus
 * bbop_manager.c reference implementation.
 *
 * Compile: g++ -std=c++17 -o test_cost_model test_cost_model.cc
 * Run:     ./test_cost_model
 */

#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <algorithm>

using namespace std;

// ---- Constants from Proteus ----
static constexpr double AAP_ENERGY_PJ = 0.871;
static constexpr double AAP_LATENCY_NS = 49.0;
static constexpr int SIMD_WIDTH = 65536;

// ---- Lookup tables (ps) from bbop_manager.c ----

static const int LAT_DAFTPUM_FULL_ADDER[64] = {
    -1, 676, 676, 915, 1154, 1393, 1632, 1871, 2110, 2349,
    2588, 2827, 3066, 3305, 3544, 3783, 4022, 4261, 4500, 4739,
    4978, 5217, 5456, 5695, 5934, 6173, 6412, 6651, 6890, 7129,
    7368, 7607, 7846, 8085, 8324, 8563, 8802, 9041, 9280, 9519,
    9758, 9997, 10236, 10475, 10714, 10953, 11192, 11431, 11670, 11909,
    12148, 12387, 12626, 12865, 13104, 13343, 13582, 13821, 14060, 14299,
    14538, 14777, 15016, 15255
};

static const int LAT_DAFTPUM_SKLANSKY_ADDER[64] = {
    -1, 1757, 1757, 2556, 2556, 3152, 3152, 3152, 3152, 3812,
    3812, 3812, 3812, 3812, 3812, 3812, 3812, 4600, 4600, 4600,
    4600, 4600, 4600, 4600, 4600, 4600, 4600, 4600, 4600, 4600,
    4600, 4600, 4600, 5644, 5644, 5644, 5644, 5644, 5644, 5644,
    5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644,
    5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644, 5644,
    5644, 5644, 5644, 5644
};

static const int LAT_DAFTPUM_KOGGE_ADDER[64] = {
    -1, 1663, 1663, 2227, 2227, 2823, 2823, 2823, 2823, 3483,
    3483, 3483, 3483, 3483, 3483, 3483, 3483, 4271, 4271, 4271,
    4271, 4271, 4271, 4271, 4271, 4271, 4271, 4271, 4271, 4271,
    4271, 4271, 4271, 5315, 5315, 5315, 5315, 5315, 5315, 5315,
    5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315,
    5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315, 5315,
    5315, 5315, 5315, 5315
};

static const int LAT_DAFTPUM_CARRYSEL_ADDER[64] = {
    -1, 676, 676, 915, 1154, 2398, 2398, 2398, 2398, 3046,
    3046, 3046, 3046, 3046, 3046, 3046, 3046, 4342, 4342, 4342,
    4342, 4342, 4342, 4342, 4342, 4342, 4342, 4342, 4342, 4342,
    4342, 4342, 4342, 6934, 6934, 6934, 6934, 6934, 6934, 6934,
    6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934,
    6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934, 6934,
    6934, 6934, 6934, 6934
};

static const int LAT_DAFTPUM_RBR_ADDER[64] = {
    -1, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194, 2194,
    2194, 2194, 2194, 2194
};

static const int LAT_SIMDRAM_RC_MULT[64] = {
    -1, 1617, 1617, 4067, 7595, 12201, 17885, 24647, 32487, 41405,
    51401, 62475, 74627, 87857, 102165, 117551, 134015, 151557, 170177,
    189875, 210651, 232505, 255437, 279447, 304535, 330701, 357945, 386267,
    415667, 446145, 477701, 510335, 544047, 578837, 614705, 651651, 689675,
    728777, 768957, 810215, 852551, 895965, 940457, 986027, 1032675, 1080401,
    1129205, 1179087, 1230047, 1282085, 1335201, 1389395, 1444667, 1501017,
    1558445, 1616951, 1676535, 1737197, 1798937, 1861755, 1925651, 1990625,
    2056677, 2123807
};

static const int LAT_DAFTPUM_SKLANSKY_MULT[64] = {
    -1, 5120, 5120, 8722, 12656, 16856, 21283, 25911, 30720, 35698,
    40833, 46117, 51542, 57104, 62797, 68617, 74560, 80623, 86803,
    93098, 99505, 106023, 112649, 119382, 126221, 133163, 140208,
    147355, 154602, 161949, 169394, 176937, 184576, 192311, 200142,
    208067, 216086, 224199, 232404, 240702, 249091, 257571, 266142,
    274803, 283554, 292395, 301325, 310343, 319450, 328644, 337927,
    347296, 356753, 366296, 375926, 385643, 395445, 405333, 415306,
    425364, 435508, 445736, 456049, 466447
};

static const int LAT_DAFTPUM_CSA_MULT[64] = {
    -1, 2974, 2974, 7773, 11052, 14675, 18642, 22953, 27608, 32607,
    37950, 43637, 49668, 56043, 62762, 69825, 77232, 84983, 93078,
    101517, 110300, 119427, 128898, 138713, 148872, 159375, 170222,
    181413, 192948, 204827, 217050, 229617, 242528, 255783, 269382,
    283325, 297612, 312243, 327218, 342537, 358200, 374207, 390558,
    407253, 424292, 441675, 459402, 477473, 495888, 514647, 533750,
    553197, 572988, 593123, 613602, 634425, 655592, 677103, 698958,
    721157, 743700, 766587, 789818, 813393
};

static const int LAT_DAFTPUM_RBR_MULT[64] = {
    -1, 11232, 11232, 16872, 22528, 28200, 33888, 39592, 45312, 51048,
    56800, 62568, 68352, 74152, 79968, 85800, 91648, 97512, 103392,
    109288, 115200, 121128, 127072, 133032, 139008, 145000, 151008,
    157032, 163072, 169128, 175200, 181288, 187392, 193512, 199648,
    205800, 211968, 218152, 224352, 230568, 236800, 243048, 249312,
    255592, 261888, 268200, 274528, 280872, 287232, 293608, 300000,
    306408, 312832, 319272, 325728, 332200, 338688, 345192, 351712,
    358248, 364800, 371368, 377952, 384552
};

static const int LAT_SIMDRAM_RELU[64] = {
    -1, 196, 343, 490, 637, 784, 931, 1078, 1225, 1372,
    1519, 1666, 1813, 1960, 2107, 2254, 2401, 2548, 2695, 2842,
    2989, 3136, 3283, 3430, 3577, 3724, 3871, 4018, 4165, 4312,
    4459, 4606, 4753, 4900, 5047, 5194, 5341, 5488, 5635, 5782,
    5929, 6076, 6223, 6370, 6517, 6664, 6811, 6958, 7105, 7252,
    7399, 7546, 7693, 7840, 7987, 8134, 8281, 8428, 8575, 8722,
    8869, 9016, 9163, 9310
};


// ---- Cost model functions ----

enum class AdderType { FULL=0, SKLANSKY, KOGGE, CARRYSEL, RBR, NUM };
enum class MultType  { FULL=0, SKLANSKY, CARRYSEL, RBR, NUM };

struct CostResult {
    int bitPrecision;
    AdderType adder;
    MultType mult;
    double latAdderNs;
    double latMultNs;
    double energyAdderNj;
    double energyMultNj;
};

int bestAdderLatency(int bp) {
    int vals[] = {
        LAT_DAFTPUM_FULL_ADDER[bp],
        LAT_DAFTPUM_SKLANSKY_ADDER[bp],
        LAT_DAFTPUM_KOGGE_ADDER[bp],
        LAT_DAFTPUM_CARRYSEL_ADDER[bp],
        LAT_DAFTPUM_RBR_ADDER[bp]
    };
    int minV = vals[0];
    for (int i = 1; i < 5; i++)
        if (vals[i] < minV) minV = vals[i];
    return minV;
}

int bestMultLatency(int bp) {
    int vals[] = {
        LAT_SIMDRAM_RC_MULT[bp],
        LAT_DAFTPUM_SKLANSKY_MULT[bp],
        LAT_DAFTPUM_CSA_MULT[bp],
        LAT_DAFTPUM_RBR_MULT[bp]
    };
    int minV = vals[0];
    for (int i = 1; i < 4; i++)
        if (vals[i] < minV) minV = vals[i];
    return minV;
}

void computeCost(int bitPrecision, uint64_t size, CostResult &r) {
    r.bitPrecision = bitPrecision;

    // Find best adder
    int adderLats[] = {
        LAT_DAFTPUM_FULL_ADDER[bitPrecision],
        LAT_DAFTPUM_SKLANSKY_ADDER[bitPrecision],
        LAT_DAFTPUM_KOGGE_ADDER[bitPrecision],
        LAT_DAFTPUM_CARRYSEL_ADDER[bitPrecision],
        LAT_DAFTPUM_RBR_ADDER[bitPrecision]
    };
    int minA = adderLats[0];
    r.adder = AdderType::FULL;
    for (int i = 1; i < 5; i++) {
        if (adderLats[i] < minA) {
            minA = adderLats[i];
            r.adder = (AdderType)i;
        }
    }

    // Find best multiplier
    int multLats[] = {
        LAT_SIMDRAM_RC_MULT[bitPrecision],
        LAT_DAFTPUM_SKLANSKY_MULT[bitPrecision],
        LAT_DAFTPUM_CSA_MULT[bitPrecision],
        LAT_DAFTPUM_RBR_MULT[bitPrecision]
    };
    int minM = multLats[0];
    r.mult = MultType::FULL;
    for (int i = 1; i < 4; i++) {
        if (multLats[i] < minM) {
            minM = multLats[i];
            r.mult = (MultType)i;
        }
    }

    double ceilSimd = ceil((double)size / SIMD_WIDTH);
    double bp = bitPrecision;

    r.latAdderNs = (double)minA / 1000.0;
    r.latMultNs = (double)minM / 1000.0;

    // Adder energy
    switch (r.adder) {
      case AdderType::FULL:
        r.energyAdderNj = 8.1075 * bp * ceilSimd * AAP_ENERGY_PJ / 1000.0;
        break;
      case AdderType::KOGGE:
        r.energyAdderNj = (0.025*bp*bp*bp + 0.1*bp*bp
            + 5.5*log2(bp)*log(bp) - 5.5*log(bp) + 18.875*bp - 19)
            * AAP_ENERGY_PJ * ceilSimd / 1000.0;
        break;
      case AdderType::SKLANSKY:
        r.energyAdderNj = (19.5*bp - 10.8*log2(bp) - 0.125)
            * AAP_ENERGY_PJ * ceilSimd / 1000.0;
        break;
      case AdderType::CARRYSEL:
        r.energyAdderNj = 22.1465 * bp * ceilSimd * AAP_ENERGY_PJ / 1000.0;
        break;
      case AdderType::RBR:
        r.energyAdderNj = 35.075 * bp * ceilSimd * AAP_ENERGY_PJ / 1000.0;
        break;
      default:
        r.energyAdderNj = 0.0;
    }

    // Multiplier energy
    switch (r.mult) {
      case MultType::FULL:
        r.energyMultNj = (11*bp*bp - 5*bp - 1) * ceilSimd
            * AAP_ENERGY_PJ / 1000.0;
        break;
      case MultType::SKLANSKY:
      case MultType::CARRYSEL:
        r.energyMultNj = (4*bp + 0.0075*bp*(bp-1) + 0.0075*2*0.1*bp
            + bp*(19.15*2*bp + log2(2*bp) - 19))
            * ceilSimd * AAP_ENERGY_PJ / 1000.0;
        break;
      case MultType::RBR:
        r.energyMultNj = (18.0325*bp*bp + 70.218*bp) * ceilSimd
            * AAP_ENERGY_PJ / 1000.0;
        break;
      default:
        r.energyMultNj = 0.0;
    }
}


// ---- Test cases ----

void test_adder_latency_8bit() {
    CostResult r;
    computeCost(8, 1024, r);
    int v = (int)r.adder;
    fprintf(stderr, "  Adder latency at 8-bit, 1024 elems: %.2f ns (circuit=%d, v=%d)\n",
           r.latAdderNs, (int)r.adder, v);
    fprintf(stderr, "  FULL=%d, SKL=%d, KOG=%d, CS=%d, RBR=%d\n",
        LAT_DAFTPUM_FULL_ADDER[8], LAT_DAFTPUM_SKLANSKY_ADDER[8],
        LAT_DAFTPUM_KOGGE_ADDER[8], LAT_DAFTPUM_CARRYSEL_ADDER[8],
        LAT_DAFTPUM_RBR_ADDER[8]);
    assert(v == 0);
    assert(r.latAdderNs > 0.0);
}

void test_adder_latency_16bit() {
    CostResult r;
    computeCost(16, 1024, r);
    fprintf(stderr, "  Adder latency at 16-bit, 1024 elems: %.2f ns (circuit=%d)\n",
           r.latAdderNs, (int)r.adder);
    // At 16-bit: Full=4022, Sklansky=4600, Kogge=4271, CS=4342, RBR=2194
    assert((int)r.adder == 4);  // RBR is fastest
}

void test_adder_latency_32bit() {
    CostResult r;
    computeCost(32, 1024, r);
    fprintf(stderr, "  Adder latency at 32-bit, 1024 elems: %.2f ns (circuit=%d)\n",
           r.latAdderNs, (int)r.adder);
    // At 32-bit: full=14161, Skl=5644, Kogge=5315, CS=6934, RBR=2194
    assert((int)r.adder == 4);  // RBR is fastest
}

void test_multiplier_latency_8bit() {
    CostResult r;
    computeCost(8, 1024, r);
    fprintf(stderr, "  Mult latency at 8-bit, 1024 elems: %.2f ns (circuit=%d)\n",
           r.latMultNs, (int)r.mult);
    assert((int)r.mult == 2);  // CarrySelect
}

void test_multiplier_latency_16bit() {
    CostResult r;
    computeCost(16, 1024, r);
    fprintf(stderr, "  Mult latency at 16-bit, 1024 elems: %.2f ns (circuit=%d)\n",
           r.latMultNs, (int)r.mult);
    assert((int)r.mult == 1);  // Sklansky
}

void test_energy_scales_with_size() {
    CostResult r1, r2;
    computeCost(16, 65536, r1);
    computeCost(16, 131072, r2);
    fprintf(stderr, "  Energy at 65536 elems: adder=%.3f nJ, mult=%.3f nJ\n",
           r1.energyAdderNj, r1.energyMultNj);
    fprintf(stderr, "  Energy at 131072 elems: adder=%.3f nJ, mult=%.3f nJ\n",
           r2.energyAdderNj, r2.energyMultNj);
    double ratioA = r2.energyAdderNj / r1.energyAdderNj;
    double ratioM = r2.energyMultNj / r1.energyMultNj;
    fprintf(stderr, "  Ratios: adder=%.2f, mult=%.2f\n", ratioA, ratioM);
    assert(ratioA > 1.8 && ratioA < 2.2);
    assert(ratioM > 1.8 && ratioM < 2.2);
}

void test_relu_latency() {
    int bp = 16;
    int lat = LAT_SIMDRAM_RELU[bp];
    printf("  ReLU latency at 16-bit: %d ps = %.2f ns\n", lat, lat/1000.0);
    assert(lat == 2401);
}

void test_energy_adder_formula() {
    // Manually verify full adder energy at 8-bit, size=1024
    double bp = 8.0;
    double ceilSimd = ceil(1024.0 / SIMD_WIDTH);  // = 1.0
    double energy = 8.1075 * bp * ceilSimd * AAP_ENERGY_PJ / 1000.0;
    fprintf(stderr, "  Full adder energy (8-bit, 1024): %.6f nJ\n", energy);
    assert(energy > 0.05 && energy < 0.06);
}

int main() {
    printf("DAFTPUM-LAT Cost Model Tests\n");
    printf("============================\n\n");

    printf("1. Adder latency tests:\n");
    test_adder_latency_8bit();
    test_adder_latency_16bit();
    test_adder_latency_32bit();
    printf("  PASS\n\n");

    printf("2. Multiplier latency tests:\n");
    test_multiplier_latency_8bit();
    test_multiplier_latency_16bit();
    printf("  PASS\n\n");

    printf("3. Energy scaling test:\n");
    test_energy_scales_with_size();
    printf("  PASS\n\n");

    printf("4. ReLU latency test:\n");
    test_relu_latency();
    printf("  PASS\n\n");

    printf("5. Energy formula verification:\n");
    test_energy_adder_formula();
    printf("  PASS\n\n");

    printf("All tests passed.\n");
    return 0;
}
