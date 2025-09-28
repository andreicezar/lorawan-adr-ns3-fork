#ifndef TRACES_H
#define TRACES_H

#include "ns3/packet.h"
namespace ns3 { namespace lorawan { class LoraTag; } }
namespace scenario {

class TraceCallbacks {
public:
    // Energy traces
    static void OnEdEnergyTotal(double oldJ, double newJ);
    static void OnRemainingEnergy(double oldJ, double newJ);
    
    // Gateway PHY traces
    static void OnGwPhyRxOk(ns3::Ptr<const ns3::Packet> p, unsigned int antennaId);
    static void OnGwPhyRxLost(ns3::Ptr<const ns3::Packet> p, uint32_t reason);
    static void OnGwPhyRxUnderSensitivity(ns3::Ptr<const ns3::Packet> p, unsigned int reason);
    
    // Gateway MAC traces
    static void OnGwMacRxOk(ns3::Ptr<const ns3::Packet> p);
    
    // End Device traces
    static void OnEdPhyTxBegin(ns3::Ptr<const ns3::Packet> p, unsigned int channelId);
    static void OnEdMacTx(ns3::Ptr<const ns3::Packet> p);
    
    // Network Server traces
    static void OnNsRxFromGw(ns3::Ptr<const ns3::Packet> p);
    
    // Helper functions
    static void LogSnrCsv(const ns3::lorawan::LoraTag& tag);
    static void PrintLoraParams(const char* who, unsigned id, ns3::Ptr<const ns3::Packet> p);
};

} // namespace scenario

#endif // TRACES_H