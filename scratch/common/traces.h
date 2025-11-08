#ifndef TRACES_H
#define TRACES_H

#include "ns3/packet.h"
#include "ns3/node-container.h"
#include <vector>
#include <map>

namespace ns3 { 
    namespace lorawan { 
        class LoraTag; 
    } 
}

namespace scenario {

class DetailedPropagationLossModel;

class TraceCallbacks {
public:
    static void SetPropagationModel(
        ns3::Ptr<DetailedPropagationLossModel> model,
        const ns3::NodeContainer& gateways,
        const ns3::NodeContainer& endDevices);
    
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
    
    // NEW: Latency tracking
    static void RecordTxTime(uint32_t nodeId, uint32_t seqNum, double txTime);
    static void RecordRxTime(uint32_t nodeId, uint32_t seqNum, double rxTime);
    static std::vector<double> GetLatencies();
    static double CalculatePercentile(const std::vector<double>& data, double percentile);

private:
    static ns3::Ptr<DetailedPropagationLossModel> s_propagationModel;
    static ns3::NodeContainer s_gateways;
    static ns3::NodeContainer s_endDevices;
    static std::map<uint32_t, double> s_txTimes;
    static std::vector<double> s_latencies;
};

} // namespace scenario

#endif // TRACES_H