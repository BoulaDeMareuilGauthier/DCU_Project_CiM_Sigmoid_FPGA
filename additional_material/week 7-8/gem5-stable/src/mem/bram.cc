/*
 * Copyright (c) 2024
 * All rights reserved
 *
 * BRAM SimObject implementation for ZYNQ 7010 Block RAM model.
 * Follows the DRAMsim3 SimObject pattern.
 */

#include "mem/bram.hh"

#include "base/callback.hh"
#include "base/trace.hh"
#include "debug/BRAM.hh"
#include "debug/Drain.hh"
#include "sim/system.hh"

namespace gem5
{

namespace memory
{

BRAM::BRAM(const Params &p) :
    AbstractMemory(p),
    port(name() + ".port", *this),
    read_cb(std::bind(&BRAM::readComplete,
                      this, std::placeholders::_1)),
    write_cb(std::bind(&BRAM::writeComplete,
                       this, std::placeholders::_1)),
    wrapper(p.sizeKB, p.clockPeriod, p.widthBytes, p.latencyCycles),
    retryReq(false), retryResp(false), startTick(0),
    nbrOutstandingReads(0), nbrOutstandingWrites(0),
    sendResponseEvent([this]{ sendResponse(); }, name()),
    tickEvent([this]{ tick(); }, name())
{
    DPRINTF(BRAM,
            "Instantiated BRAM with %d KB, clock %.1f ns, "
            "width %d bytes, latency %d cycles, queue size %d\n",
            p.sizeKB, p.clockPeriod, p.widthBytes,
            p.latencyCycles, wrapper.queueSize());

    registerExitCallback([this]() { wrapper.printStats(); });
}

void
BRAM::init()
{
    AbstractMemory::init();

    if (!port.isConnected()) {
        fatal("BRAM %s is unconnected!\n", name());
    } else {
        port.sendRangeChange();
    }

    if (system()->cacheLineSize() != wrapper.burstSize())
        fatal("BRAM burst size %d does not match cache line size %d\n",
              wrapper.burstSize(), system()->cacheLineSize());
}

void
BRAM::startup()
{
    startTick = curTick();
    schedule(tickEvent, clockEdge());
}

void
BRAM::resetStats() {
    wrapper.resetStats();
}

void
BRAM::sendResponse()
{
    assert(!retryResp);
    assert(!responseQueue.empty());

    DPRINTF(BRAM, "Attempting to send response\n");

    bool success = port.sendTimingResp(responseQueue.front());
    if (success) {
        responseQueue.pop_front();

        DPRINTF(BRAM, "Have %d read, %d write, %d responses outstanding\n",
                nbrOutstandingReads, nbrOutstandingWrites,
                responseQueue.size());

        if (!responseQueue.empty() && !sendResponseEvent.scheduled())
            schedule(sendResponseEvent, curTick());

        if (nbrOutstanding() == 0)
            signalDrainDone();
    } else {
        retryResp = true;

        DPRINTF(BRAM, "Waiting for response retry\n");

        assert(!sendResponseEvent.scheduled());
    }
}

unsigned int
BRAM::nbrOutstanding() const
{
    return nbrOutstandingReads + nbrOutstandingWrites + responseQueue.size();
}

void
BRAM::tick()
{
    if (system()->isTimingMode()) {
        wrapper.tick();

        if (retryReq && nbrOutstanding() < wrapper.queueSize()) {
            retryReq = false;
            port.sendRetryReq();
        }
    }

    schedule(tickEvent,
        curTick() + wrapper.clockPeriod() * sim_clock::as_int::ns);
}

Tick
BRAM::recvAtomic(PacketPtr pkt)
{
    access(pkt);
    // BRAM has very low latency - 1 cycle at 250MHz = 4ns
    return pkt->cacheResponding() ? 0 :
           wrapper.clockPeriod() * sim_clock::as_int::ns;
}

void
BRAM::recvFunctional(PacketPtr pkt)
{
    pkt->pushLabel(name());

    functionalAccess(pkt);

    for (auto i = responseQueue.begin(); i != responseQueue.end(); ++i)
        pkt->trySatisfyFunctional(*i);

    pkt->popLabel();
}

bool
BRAM::recvTimingReq(PacketPtr pkt)
{
    if (pkt->cacheResponding()) {
        pendingDelete.reset(pkt);
        return true;
    }

    if (retryReq)
        return false;

    bool can_accept = nbrOutstanding() < wrapper.queueSize();

    if (pkt->isRead()) {
        if (can_accept) {
            outstandingReads[pkt->getAddr()].push(pkt);
            ++nbrOutstandingReads;
        }
    } else if (pkt->isWrite()) {
        if (can_accept) {
            outstandingWrites[pkt->getAddr()].push(pkt);
            ++nbrOutstandingWrites;
            accessAndRespond(pkt);
        }
    } else {
        accessAndRespond(pkt);
        return true;
    }

    if (can_accept) {
        assert(wrapper.canAccept(pkt->getAddr(), pkt->isWrite()));

        DPRINTF(BRAM, "Enqueueing address %lld\n", pkt->getAddr());

        wrapper.enqueue(pkt->getAddr(), pkt->isWrite());

        return true;
    } else {
        retryReq = true;
        return false;
    }
}

void
BRAM::recvRespRetry()
{
    DPRINTF(BRAM, "Retrying\n");

    assert(retryResp);
    retryResp = false;
    sendResponse();
}

void
BRAM::accessAndRespond(PacketPtr pkt)
{
    DPRINTF(BRAM, "Access for address %lld\n", pkt->getAddr());

    bool needsResponse = pkt->needsResponse();

    access(pkt);

    if (needsResponse) {
        assert(pkt->isResponse());
        Tick time = curTick() + pkt->headerDelay + pkt->payloadDelay;
        pkt->headerDelay = pkt->payloadDelay = 0;

        DPRINTF(BRAM, "Queuing response for address %lld\n",
                pkt->getAddr());

        responseQueue.push_back(pkt);

        if (!retryResp && !sendResponseEvent.scheduled())
            schedule(sendResponseEvent, time);
    } else {
        pendingDelete.reset(pkt);
    }
}

void
BRAM::readComplete(uint64_t addr)
{
    DPRINTF(BRAM, "Read to address %llu complete\n", addr);

    auto p = outstandingReads.find(addr);
    assert(p != outstandingReads.end());

    PacketPtr pkt = p->second.front();
    p->second.pop();

    if (p->second.empty())
        outstandingReads.erase(p);

    assert(nbrOutstandingReads != 0);
    --nbrOutstandingReads;

    accessAndRespond(pkt);
}

void
BRAM::writeComplete(uint64_t addr)
{
    DPRINTF(BRAM, "Write to address %llu complete\n", addr);

    auto p = outstandingWrites.find(addr);
    assert(p != outstandingWrites.end());

    p->second.pop();
    if (p->second.empty())
        outstandingWrites.erase(p);

    assert(nbrOutstandingWrites != 0);
    --nbrOutstandingWrites;

    if (nbrOutstanding() == 0)
        signalDrainDone();
}

Port&
BRAM::getPort(const std::string &if_name, PortID idx)
{
    if (if_name != "port") {
        return ClockedObject::getPort(if_name, idx);
    } else {
        return port;
    }
}

DrainState
BRAM::drain()
{
    return nbrOutstanding() != 0 ? DrainState::Draining : DrainState::Drained;
}

BRAM::MemoryPort::MemoryPort(const std::string& _name,
                             BRAM& _memory)
    : ResponsePort(_name), mem(_memory)
{ }

AddrRangeList
BRAM::MemoryPort::getAddrRanges() const
{
    AddrRangeList ranges;
    ranges.push_back(mem.getAddrRange());
    return ranges;
}

Tick
BRAM::MemoryPort::recvAtomic(PacketPtr pkt)
{
    return mem.recvAtomic(pkt);
}

void
BRAM::MemoryPort::recvFunctional(PacketPtr pkt)
{
    mem.recvFunctional(pkt);
}

bool
BRAM::MemoryPort::recvTimingReq(PacketPtr pkt)
{
    return mem.recvTimingReq(pkt);
}

void
BRAM::MemoryPort::recvRespRetry()
{
    mem.recvRespRetry();
}

} // namespace memory
} // namespace gem5
