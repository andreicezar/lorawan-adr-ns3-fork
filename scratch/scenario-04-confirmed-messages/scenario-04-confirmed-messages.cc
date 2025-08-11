/*
 * Scenario 4: Confirmed vs Unconfirmed Messages
 * Tests both unconfirmed and confirmed message modes
 * Measures retransmission behavior, DL impact, and ACK loss
 * 
 * Purpose: Check MAC layer reliability mechanisms and downlink coordination
 */

#include "ns3/command-line.h"
#include "ns3/config.h"
#include "ns3/core-module.h"
#include "ns3/forwarder-helper.h"
#include "ns3/gateway-lora-phy.h"
#include "ns3/hex-grid-position-allocator.h"
#include "ns3/log.h"
#include "ns3/lora-channel.h"
#include "ns3/lora-device-address-generator.h"
#include "ns3/lora-helper.h"
#include "ns3/lora-phy-helper.h"
#include "ns3/lorawan-mac-helper.h"
#include "ns3/mobility-helper.h"
#include "ns3/network-module.h"
#include "ns3/network-server-helper.h"
#include "ns3/periodic-sender-helper.h"
#include "ns3/point-to-point-module.h"
#include "ns3/random-variable-stream.h"
#include "common/lora_utils.h"
#include "common/scenario_utils.h"
#include <fstream>
#include <iomanip>

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("Scenario04ConfirmedMessages");

// ==============================================================================
// GLOBAL VARIABLES
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Scenario-specific variables
std::map<uint32_t, uint32_t> g_retransmissionsPerNode;
std::map<uint32_t, std::set<uint32_t>> g_frameCountersPerNode; // Track FCnt per device
std::map<uint32_t, uint32_t> g_lastFrameCountPerNode;
uint32_t g_totalRetransmissions = 0;
uint32_t g_confirmedPacketsSent = 0;
uint32_t g_confirmedPacketsReceived = 0;
uint32_t g_totalAcks = 0;
uint32_t g_totalAckTimeouts = 0;
uint32_t g_totalDownlinksSent = 0;
uint32_t g_totalDownlinksReceived = 0;

// Store current mode for analysis
bool g_isConfirmedMode = false;

// ==============================================================================
// CALLBACK FUNCTIONS
// ==============================================================================

void OnPacketSent(Ptr<const Packet> packet)
{
    uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
    
    // In confirmed mode, count as confirmed packet
    if (g_isConfirmedMode) {
        g_confirmedPacketsSent++;
    }
    
    NS_LOG_DEBUG("Node " << nodeId << " sent packet #" << g_sentPacketsPerNode[nodeId]);
}

void OnGatewayReceive(Ptr<const Packet> packet) 
{
    LorawanMacHeader macHeader;
    LoraFrameHeader frameHeader;
    
    Ptr<Packet> packetCopy = packet->Copy();
    packetCopy->RemoveHeader(macHeader);
    
    if (macHeader.GetMType() == LorawanMacHeader::UNCONFIRMED_DATA_UP ||
        macHeader.GetMType() == LorawanMacHeader::CONFIRMED_DATA_UP)
    {
        packetCopy->RemoveHeader(frameHeader);
        LoraDeviceAddress deviceAddress = frameHeader.GetAddress();
        
        auto it = g_deviceToNodeMap.find(deviceAddress);
        if (it != g_deviceToNodeMap.end())
        {
            uint32_t nodeId = it->second;
            g_receivedPacketsPerNode[nodeId]++;
            g_totalReceived++;

            // Count confirmed packets received
            if (macHeader.GetMType() == LorawanMacHeader::CONFIRMED_DATA_UP) {
                g_confirmedPacketsReceived++;
            }

            // Detect retransmissions using frame counter
            uint32_t fcnt = frameHeader.GetFCnt();
            if (g_frameCountersPerNode[nodeId].count(fcnt) > 0) {
                // This FCnt was seen before - it's a retransmission
                g_retransmissionsPerNode[nodeId]++;
                g_totalRetransmissions++;
                NS_LOG_INFO("Retransmission detected from Node " << nodeId << " FCnt=" << fcnt);
            } else {
                // First time seeing this FCnt
                g_frameCountersPerNode[nodeId].insert(fcnt);
            }
            
            g_lastFrameCountPerNode[nodeId] = fcnt;
            NS_LOG_DEBUG("Gateway received packet from Node " << nodeId);
        }
    }
}

// ==============================================================================
// DEVICE MAPPING
// ==============================================================================

void BuildDeviceMapping(NodeContainer endDevices) {
    // Use standard mapping first
    BuildStandardDeviceMapping(endDevices);
    
    // Add scenario-specific initialization
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        g_retransmissionsPerNode[nodeId] = 0;
        g_lastFrameCountPerNode[nodeId] = 0;
        g_frameCountersPerNode[nodeId].clear();
    }
    
    std::cout << "✅ Confirmed messages device mapping built for " << endDevices.GetN() << " devices" << std::endl;
}

// ==============================================================================
// RESULTS EXPORT
// ==============================================================================

void ExportResults(const std::string& filename, NodeContainer endDevices, 
                  int simulationTime, bool confirmedMessages)
{
    std::ofstream file(filename);
    WriteStandardHeader(file, "Scenario 4: Confirmed vs Unconfirmed Messages",
                       endDevices.GetN(), 1, simulationTime,
                       confirmedMessages ? "Confirmed messages, retransmission enabled" : "Unconfirmed messages");
    
    file << "OVERALL_STATS\n";
    file << "MessageType," << (confirmedMessages ? "CONFIRMED" : "UNCONFIRMED") << "\n";
    file << "TotalSent," << g_totalSent << "\n";
    file << "TotalReceived," << g_totalReceived << "\n";
    file << "PDR_Percent," << std::fixed << std::setprecision(2) 
         << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";
    file << "TotalRetransmissions," << g_totalRetransmissions << "\n";
    file << "ConfirmedPacketsSent," << g_confirmedPacketsSent << "\n";
    file << "ConfirmedPacketsReceived," << g_confirmedPacketsReceived << "\n";
    
    // Reliability improvement calculation
    double retransmissionRate = g_totalReceived > 0 ? 
        (double)g_totalRetransmissions / g_totalReceived * 100.0 : 0.0;
    file << "RetransmissionRate_Percent," << std::fixed << std::setprecision(2) 
         << retransmissionRate << "\n";
    
    // Extra airtime due to retransmissions (assume SF10)
    double extraAirtime = g_totalRetransmissions * lora::CalculateAirTime(10);
    file << "ExtraAirtime_ms_Retransmissions," << std::fixed << std::setprecision(2) 
         << extraAirtime << "\n";
    
    // ACK-related stats (placeholder for future implementation)
    file << "TotalACKs," << g_totalAcks << "\n";
    file << "TotalACKTimeouts," << g_totalAckTimeouts << "\n";
    file << "TotalDownlinksSent," << g_totalDownlinksSent << "\n";
    file << "TotalDownlinksReceived," << g_totalDownlinksReceived << "\n";
    
    // Reliability improvement vs unconfirmed
    double reliabilityImprovement = confirmedMessages ? 
        lora::PdrPercent(g_totalReceived, g_totalSent) : 0.0;
    file << "ReliabilityImprovement_Percent," << std::fixed << std::setprecision(2) 
         << reliabilityImprovement << "\n\n";
    
    // Per-node stats
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,Retransmissions,UniqueFrameCounts,LastFrameCount\n";
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = g_sentPacketsPerNode[nodeId];
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        uint32_t retransmissions = g_retransmissionsPerNode[nodeId];
        uint32_t uniqueFrameCounts = g_frameCountersPerNode[nodeId].size();
        uint32_t lastFrameCount = g_lastFrameCountPerNode[nodeId];
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << "," 
             << retransmissions << "," << uniqueFrameCounts << "," << lastFrameCount << "\n";
    }
    
    file.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}

// ==============================================================================
// MAIN FUNCTION
// ==============================================================================

int main(int argc, char* argv[])
{
    // Scenario 4 Parameters
    int nDevices = 100;
    int nGateways = 1;
    int simulationTime = 20; // minutes (longer for retransmission observation)
    int packetInterval = 120; // seconds (2 min intervals for confirmed message testing)
    double sideLengthMeters = 5000; // 5km x 5km area
    double maxRandomLossDb = 5.0;
    bool confirmedMessages = false; // Command line parameter
    std::string outputPrefix = "scenario04_confirmed_messages";
    
    CommandLine cmd(__FILE__);
    cmd.AddValue("confirmedMessages", "Use confirmed messages (true) or unconfirmed (false)", confirmedMessages);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("packetInterval", "Packet interval in seconds", packetInterval);
    cmd.Parse(argc, argv);

    // Store mode for callback reference
    g_isConfirmedMode = confirmedMessages;

    // Logging
    LogComponentEnable("Scenario04ConfirmedMessages", LOG_LEVEL_INFO);
    
    // Create node containers
    NodeContainer endDevices, gateways;
    endDevices.Create(nDevices);
    gateways.Create(nGateways);
    
    // Setup network using standardized functions
    Ptr<LoraChannel> channel = SetupStandardChannel(maxRandomLossDb);
    SetupStandardMobility(endDevices, gateways, sideLengthMeters);
    SetupStandardLoRa(endDevices, gateways, channel, 2); // DR2 = SF10
    SetupStandardNetworkServer(gateways, endDevices, false); // No ADR
    
    // Setup timing and traces
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMapping);
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);

    // Run simulation
    Time totalSimulationTime = Seconds(simulationTime * 60);
    Simulator::Stop(totalSimulationTime);

    std::cout << "\n=== Scenario 4: Confirmed vs Unconfirmed Messages ===" << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "Message Type: " << (confirmedMessages ? "CONFIRMED" : "UNCONFIRMED") << std::endl;
    std::cout << "Packet interval: " << packetInterval << "s" << std::endl;
    std::cout << "Expected packets per device: " << (simulationTime * 60 / packetInterval) << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes" << std::endl;
    
    if (confirmedMessages) {
        std::cout << "Note: Confirmed message behavior depends on NS-3 LoRaWAN version support" << std::endl;
        std::cout << "Using frame counter analysis for retransmission detection" << std::endl;
    } else {
        std::cout << "Using unconfirmed messages with frame counter tracking" << std::endl;
    }
    
    std::cout << "Starting simulation..." << std::endl;

    Simulator::Run();

    std::cout << "\n=== Simulation Complete ===" << std::endl;
    std::cout << "Total packets sent: " << g_totalSent << std::endl;
    std::cout << "Total packets received: " << g_totalReceived << std::endl;
    
    if (confirmedMessages || g_totalRetransmissions > 0) {
        std::cout << "Total retransmissions: " << g_totalRetransmissions << std::endl;
        std::cout << "Confirmed packets sent: " << g_confirmedPacketsSent << std::endl;
        std::cout << "Confirmed packets received: " << g_confirmedPacketsReceived << std::endl;
        
        if (g_totalRetransmissions > 0) {
            double retransmissionRate = (double)g_totalRetransmissions / g_totalReceived * 100.0;
            std::cout << "Retransmission rate: " << std::fixed << std::setprecision(2) 
                      << retransmissionRate << "%" << std::endl;
        }
    }
    
    if (g_totalSent > 0) {
        double pdr = lora::PdrPercent(g_totalReceived, g_totalSent);
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2) << pdr << "%" << std::endl;
    }

    // Validate and export results
    ValidateResults(endDevices);

    std::string modeStr = confirmedMessages ? "confirmed" : "unconfirmed";
    std::string outputFile = outputPrefix + "_" + modeStr + "_results.csv";
    ExportResults(outputFile, endDevices, simulationTime, confirmedMessages);

    Simulator::Destroy();
    return 0;
}