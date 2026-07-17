# Copyright (c) 2024
# All rights reserved
#
# BRAM convenience wrappers for ZYNQ 7010 Block RAM model.
# Follows the dramsim_3.py pattern.

from typing import (
    List,
    Optional,
    Sequence,
    Tuple,
)

import m5
from m5.objects import (
    BRAM,
    MemCtrl,
)
from m5.params import (
    AddrRange,
    Port,
)
from m5.util.convert import toMemorySize

from ...utils.override import overrides
from ..boards.abstract_board import AbstractBoard
from .abstract_memory_system import AbstractMemorySystem


class BRAMMemCtrl(BRAM):
    """
    A ZYNQ 7010 BRAM Memory Controller.

    The class serves as a SimObject wrapper for the on-chip Block RAM,
    modeling the ZYNQ 7010 PS BRAM with configurable timing parameters.
    """

    def __init__(
        self,
        size_kb: int = 64,
        clock_period_ns: float = 4.0,
        width_bytes: int = 4,
        latency_cycles: int = 1,
    ) -> None:
        """
        :param size_kb: BRAM size in kilobytes (ZYNQ 7010: up to 64KB).
        :param clock_period_ns: Clock period in nanoseconds.
        :param width_bytes: Data bus width in bytes.
        :param latency_cycles: Read/write latency in clock cycles.
        """
        super().__init__()
        self.sizeKB = size_kb
        self.clockPeriod = clock_period_ns
        self.widthBytes = width_bytes
        self.latencyCycles = latency_cycles


class SingleChannelBRAM(AbstractMemorySystem):
    """
    A Single Channel BRAM memory system.
    """

    def __init__(
        self,
        size_kb: int = 64,
        clock_period_ns: float = 4.0,
        width_bytes: int = 4,
        latency_cycles: int = 1,
    ):
        """
        :param size_kb: BRAM size in kilobytes.
        :param clock_period_ns: Clock period in nanoseconds.
        :param width_bytes: Data bus width in bytes.
        :param latency_cycles: Read/write latency in clock cycles.
        """
        super().__init__()
        self.mem_ctrl = BRAMMemCtrl(size_kb, clock_period_ns,
                                     width_bytes, latency_cycles)
        self._size = size_kb * 1024

    @overrides(AbstractMemorySystem)
    def incorporate_memory(self, board: AbstractBoard) -> None:
        pass

    @overrides(AbstractMemorySystem)
    def get_mem_ports(self) -> Tuple[Sequence[AddrRange], Port]:
        return [(self.mem_ctrl.range, self.mem_ctrl.port)]

    @overrides(AbstractMemorySystem)
    def get_memory_controllers(self) -> List[MemCtrl]:
        return [self.mem_ctrl]

    @overrides(AbstractMemorySystem)
    def get_size(self) -> int:
        return self._size

    @overrides(AbstractMemorySystem)
    def set_memory_range(self, ranges: List[AddrRange]) -> None:
        if len(ranges) != 1 or ranges[0].size() != self._size:
            raise Exception(
                "Single channel BRAM requires a single "
                "range which matches the memory's size."
            )
        self.mem_ctrl.range = ranges[0]


def ZYNQ7010_BRAM(
    size_kb: int = 64,
    clock_period_ns: float = 4.0,
) -> SingleChannelBRAM:
    """
    ZYNQ 7010 on-chip Block RAM configuration.

    The ZYNQ 7010 PS contains up to 63KB of BRAM organized as
    36Kb block RAM tiles. BRAM provides single-cycle synchronous
    read/write access at the PS clock frequency.

    :param size_kb: BRAM size in kilobytes (default: 64KB).
    :param clock_period_ns: Clock period in nanoseconds (default: 4.0ns = 250MHz).
    """
    return SingleChannelBRAM(size_kb, clock_period_ns, 4, 1)


def ZYNQ7010_BRAM_Fast(
    size_kb: int = 64,
) -> SingleChannelBRAM:
    """
    ZYNQ 7010 BRAM at maximum PS clock (667MHz).

    :param size_kb: BRAM size in kilobytes (default: 64KB).
    """
    return SingleChannelBRAM(size_kb, 1.5, 4, 1)  # 1.5ns = ~667MHz
