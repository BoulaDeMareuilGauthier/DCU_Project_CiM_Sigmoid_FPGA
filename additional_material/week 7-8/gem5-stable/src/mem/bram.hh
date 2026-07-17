/*
 * Copyright (c) 2024
 * All rights reserved
 *
 * BRAM SimObject for ZYNQ 7010 Block RAM model.
 * Follows the DRAMsim3 SimObject pattern.
 */

#ifndef __MEM_BRAM_HH__
#define __MEM_BRAM_HH__

#include <functional>
#include <queue>
#include <unordered_map>

#include "mem/abstract_mem.hh"
#include "mem/bram_wrapper.hh"
#include "mem/qport.hh"
#include "params/BRAM.hh"

namespace gem5
{

namespace memory
{

class BRAM : public AbstractMemory
{
  private:

    /**
     * The memory port has to deal with its own flow control.
     */
    class MemoryPort : public ResponsePort
    {

      private:

        BRAM& mem;

      public:

        MemoryPort(const std::string& _name, BRAM& _memory);

      protected:

        Tick recvAtomic(PacketPtr pkt);

        void recvFunctional(PacketPtr pkt);

        bool recvTimingReq(PacketPtr pkt);

        void recvRespRetry();

        AddrRangeList getAddrRanges() const;

    };

    MemoryPort port;

    /**
     * Callback functions
     */
    std::function<void(uint64_t)> read_cb;
    std::function<void(uint64_t)> write_cb;

    /**
     * The actual BRAM wrapper
     */
    BRAMWrapper wrapper;

    /**
     * Is the connected port waiting for a retry from us
     */
    bool retryReq;

    /**
     * Are we waiting for a retry for sending a response.
     */
    bool retryResp;

    /**
     * Keep track of when the wrapper is started.
     */
    Tick startTick;

    /**
     * Keep track of what packets are outstanding per address.
     */
    std::unordered_map<Addr, std::queue<PacketPtr>> outstandingReads;
    std::unordered_map<Addr, std::queue<PacketPtr>> outstandingWrites;

    /**
     * Count the number of outstanding transactions.
     */
    unsigned int nbrOutstandingReads;
    unsigned int nbrOutstandingWrites;

    /**
     * Queue to hold response packets until we can send them back.
     */
    std::deque<PacketPtr> responseQueue;

    unsigned int nbrOutstanding() const;

    /**
     * When a packet is ready, use the "access()" method in
     * AbstractMemory to actually create the response packet.
     */
    void accessAndRespond(PacketPtr pkt);

    void sendResponse();

    /**
     * Event to schedule sending of responses
     */
    EventFunctionWrapper sendResponseEvent;

    /**
     * Progress the controller one clock cycle.
     */
    void tick();

    /**
     * Event to schedule clock ticks
     */
    EventFunctionWrapper tickEvent;

    /**
     * Upstream caches need this packet until true is returned.
     */
    std::unique_ptr<Packet> pendingDelete;

  public:

    typedef BRAMParams Params;
    BRAM(const Params &p);

    /**
     * Read completion callback.
     */
    void readComplete(uint64_t addr);

    /**
     * Write completion callback.
     */
    void writeComplete(uint64_t addr);

    DrainState drain() override;

    virtual Port& getPort(const std::string& if_name,
                          PortID idx = InvalidPortID) override;

    void init() override;
    void startup() override;

    void resetStats() override;

  protected:

    Tick recvAtomic(PacketPtr pkt);
    void recvFunctional(PacketPtr pkt);
    bool recvTimingReq(PacketPtr pkt);
    void recvRespRetry();

};

} // namespace memory
} // namespace gem5

#endif // __MEM_BRAM_HH__
