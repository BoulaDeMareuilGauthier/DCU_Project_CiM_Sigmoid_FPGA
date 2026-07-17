/*
 * Copyright (c) 2024
 * All rights reserved
 *
 * BRAM wrapper implementation for ZYNQ 7010 Block RAM model.
 * Inspired by DRAMsim3Wrapper architecture.
 */

#include "mem/bram_wrapper.hh"

#include <algorithm>
#include <cassert>

#include "base/logging.hh"

namespace gem5
{

namespace memory
{

BRAMWrapper::BRAMWrapper(unsigned int size_kb,
                         double clock_period_ns,
                         unsigned int width_bytes,
                         unsigned int latency_cycles,
                         std::function<void(uint64_t)> read_cb,
                         std::function<void(uint64_t)> write_cb) :
    _clockPeriod(clock_period_ns),
    _sizeBytes(size_kb * 1024),
    _widthBytes(width_bytes),
    _depth((size_kb * 1024) / width_bytes),
    _latency(latency_cycles),
    _queueSize(16),   // BRAM has small internal FIFO
    _burstSize(width_bytes)
{
    if (!_clockPeriod)
        fatal("BRAM wrapper: clock period must be > 0\n");

    if (!_sizeBytes)
        fatal("BRAM wrapper: size must be > 0\n");

    if (!_widthBytes || (_widthBytes & (_widthBytes - 1)) != 0)
        fatal("BRAM wrapper: width must be a power of 2\n");

    pendingTransactions.reserve(_queueSize);

    DPRINTF(BRAM, "BRAM initialized: %dKB, %dns clock, %d-byte width, "
            "%d-cycle latency, %d-byte burst\n",
            size_kb, clock_period_ns, width_bytes,
            latency_cycles, _burstSize);
}

BRAMWrapper::~BRAMWrapper()
{
}

void
BRAMWrapper::printStats()
{
    DPRINTF(BRAM, "BRAM Stats: size=%d bytes, clock=%.1f ns, "
            "width=%d bytes, latency=%d cycles\n",
            _sizeBytes, _clockPeriod, _widthBytes, _latency);
}

void
BRAMWrapper::resetStats()
{
    pendingTransactions.clear();
}

void
BRAMWrapper::setCallbacks(std::function<void(uint64_t)> read_complete,
                           std::function<void(uint64_t)> write_complete)
{
    // BRAM is purely timing-based, callbacks are stored externally
    // in the SimObject layer (BRAM class) - same pattern as DRAMsim3
}

bool
BRAMWrapper::canAccept(uint64_t addr, bool is_write) const
{
    // BRAM can accept if queue has space and address is in range
    if (pendingTransactions.size() >= _queueSize)
        return false;

    // Check address is within BRAM range
    uint64_t offset = addr / _widthBytes;
    return offset < _depth;
}

void
BRAMWrapper::enqueue(uint64_t addr, bool is_write)
{
    assert(canAccept(addr, is_write));

    BRAMTransaction txn;
    txn.addr = addr;
    txn.is_write = is_write;
    txn.cycles_remaining = _latency;

    pendingTransactions.push_back(txn);

    DPRINTF(BRAM, "Enqueued %s at addr %llu, %d cycles remaining\n",
            is_write ? "write" : "read", addr, _latency);
}

double
BRAMWrapper::clockPeriod() const
{
    return _clockPeriod;
}

unsigned int
BRAMWrapper::queueSize() const
{
    return _queueSize;
}

unsigned int
BRAMWrapper::burstSize() const
{
    return _burstSize;
}

unsigned int
BRAMWrapper::sizeBytes() const
{
    return _sizeBytes;
}

unsigned int
BRAMWrapper::widthBytes() const
{
    return _widthBytes;
}

unsigned int
BRAMWrapper::latency() const
{
    return _latency;
}

void
BRAMWrapper::tick()
{
    // Progress all pending transactions
    for (auto it = pendingTransactions.begin();
         it != pendingTransactions.end(); ) {
        if (it->cycles_remaining > 0) {
            it->cycles_remaining--;
        }

        if (it->cycles_remaining == 0) {
            DPRINTF(BRAM, "Transaction complete at addr %llu\n", it->addr);
            it = pendingTransactions.erase(it);
        } else {
            ++it;
        }
    }
}

} // namespace memory
} // namespace gem5
