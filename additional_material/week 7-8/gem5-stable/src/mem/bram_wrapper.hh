/*
 * Copyright (c) 2024
 * All rights reserved
 *
 * BRAM wrapper for ZYNQ 7010 Block RAM model.
 * Inspired by DRAMsim3Wrapper architecture.
 */

#ifndef __MEM_BRAM_WRAPPER_HH__
#define __MEM_BRAM_WRAPPER_HH__

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

namespace gem5
{

namespace memory
{

/**
 * Wrapper class modeling ZYNQ 7010 Block RAM (BRAM) behavior.
 * Follows the same wrapper pattern as DRAMsim3Wrapper but implements
 * internal timing models instead of wrapping an external library.
 *
 * ZYNQ 7010 BRAM specs:
 * - Up to 63KB of on-chip BRAM (36Kb blocks)
 * - True dual-port with synchronous read/write
 * - Single-cycle access at operating frequency
 * - Byte-enable write support
 * - No refresh required
 * - Configurable latency (default: 1 cycle)
 */
class BRAMWrapper
{
  private:

    /**
     * BRAM timing parameters
     */
    double _clockPeriod;      // Clock period in ns
    unsigned int _sizeBytes;  // Total BRAM size in bytes
    unsigned int _widthBytes; // Data bus width in bytes
    unsigned int _depth;      // Number of addressable locations
    unsigned int _latency;    // Read/write latency in cycles
    unsigned int _queueSize;  // Transaction queue capacity
    unsigned int _burstSize;  // Burst size in bytes

    /**
     * Internal transaction queue to model pipeline behavior
     */
    struct BRAMTransaction {
        uint64_t addr;
        bool is_write;
        unsigned int cycles_remaining;
    };
    std::vector<BRAMTransaction> pendingTransactions;

  public:

    /**
     * Create a BRAM wrapper instance with ZYNQ 7010 specifications.
     *
     * @param size_kb BRAM size in kilobytes (default: 64KB)
     * @param clock_period_ns Clock period in nanoseconds (default: 4.0ns for 250MHz)
     * @param width_bytes Data bus width in bytes (default: 4 bytes / 32-bit)
     * @param latency_cycles Read/write latency in cycles (default: 1)
     * @param read_cb Read completion callback
     * @param write_cb Write completion callback
     */
    BRAMWrapper(unsigned int size_kb = 64,
                double clock_period_ns = 4.0,
                unsigned int width_bytes = 4,
                unsigned int latency_cycles = 1,
                std::function<void(uint64_t)> read_cb = nullptr,
                std::function<void(uint64_t)> write_cb = nullptr);

    ~BRAMWrapper();

    /**
     * Print BRAM statistics.
     */
    void printStats();

    /**
     * Reset statistics.
     */
    void resetStats();

    /**
     * Set callbacks for read and write completions.
     */
    void setCallbacks(std::function<void(uint64_t)> read_complete,
                      std::function<void(uint64_t)> write_complete);

    /**
     * Determine if the BRAM can accept a new transaction.
     *
     * @return true if the controller can accept transactions
     */
    bool canAccept(uint64_t addr, bool is_write) const;

    /**
     * Enqueue a transaction. Assumes canAccept returned true.
     *
     * @param addr Address of the transaction
     * @param is_write True for write, false for read
     */
    void enqueue(uint64_t addr, bool is_write);

    /**
     * Get the clock period in ns.
     */
    double clockPeriod() const;

    /**
     * Get the transaction queue size.
     */
    unsigned int queueSize() const;

    /**
     * Get the burst size in bytes.
     */
    unsigned int burstSize() const;

    /**
     * Get the total BRAM size in bytes.
     */
    unsigned int sizeBytes() const;

    /**
     * Get the data bus width in bytes.
     */
    unsigned int widthBytes() const;

    /**
     * Get the read/write latency in cycles.
     */
    unsigned int latency() const;

    /**
     * Progress the BRAM controller one cycle.
     */
    void tick();
};

} // namespace memory
} // namespace gem5

#endif // __MEM_BRAM_WRAPPER_HH__
