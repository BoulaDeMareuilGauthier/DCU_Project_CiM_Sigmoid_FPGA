# Copyright (c) 2024
# All rights reserved
#
# BRAM SimObject definition for ZYNQ 7010 Block RAM model.
# Follows the DRAMsim3.py pattern.

from m5.objects.AbstractMemory import *
from m5.params import *


class BRAM(AbstractMemory):
    type = "BRAM"
    cxx_header = "mem/bram.hh"
    cxx_class = "gem5::memory::BRAM"

    port = ResponsePort(
        "port for receiving requests from the CPU or other requestor"
    )

    sizeKB = Param.Unsigned(
        64,
        "BRAM size in kilobytes (ZYNQ 7010: up to 64KB)",
    )
    clockPeriod = Param.Float(
        4.0,
        "Clock period in nanoseconds (default: 4.0ns = 250MHz)",
    )
    widthBytes = Param.Unsigned(
        4,
        "Data bus width in bytes (default: 4 bytes = 32-bit)",
    )
    latencyCycles = Param.Unsigned(
        1,
        "Read/write latency in clock cycles (default: 1 cycle)",
    )
