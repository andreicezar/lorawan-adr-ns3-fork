/*
 * Scenario 5: Traffic Pattern Variation
 * Tests channel saturation with different packet intervals: 600s, 300s, 60s
 * Measures PDR degradation, duty cycle utilization, and collision escalation
 * 
 * Purpose: Examine channel saturation, collision rate, and queue buildup under varying loads
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
#include <cmath>

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("Scenario05TrafficPatterns");

#include "common/position_loader.h"
// ==============================================================================
// GLOBAL VARIABLES
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Scenario-specific variables
std::map<uint32_t, std::vector<double>> g_transmissionTimesPerNode;
std::map<uint32_t, double> g_totalAirTimePerNode;
double g_totalChannelAirTime = 0.0;

// Store current packet interval for analysis
int g_currentPacketInterval = 600;

// ==============================================================================
// CALLBACK FUNCTIONS
// ==============================================================================

void OnPacketSent(Ptr<const Packet> packet) {
    uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
    
    // Track transmission times for traffic analysis
    double currentTime = Simulator::Now().GetSeconds();
    g_transmissionTimesPerNode[nodeId].push_back(currentTime);
    
    // Calculate airtime (assume SF10 for consistency)
    double airTime = lora::CalculateAirTime(10);
    g_totalAirTimePerNode[nodeId] += airTime;
    g_totalChannelAirTime += airTime;
    
    // NS_LOG_DEBUG("Node " << nodeId << " sent packet #" << g_sentPacketsPerNode[nodeId] 
    //            << " at " << std::fixed << std::setprecision(2) << currentTime << "s");
}

void OnGatewayReceive(Ptr<const Packet> packet)
{
    LorawanMacHeader macHeader;
    LoraFrameHeader frameHeader;
    
    Ptr<Packet> packetCopy = packet->Copy();
    packetCopy->RemoveHeader(macHeader);
    
    if (macHeader.GetMType() == LorawanMacHeader::UNCONFIRMED_DATA_UP)
    {
        packetCopy->RemoveHeader(frameHeader);
        LoraDeviceAddress deviceAddress = frameHeader.GetAddress();
        
        auto it = g_deviceToNodeMap.find(deviceAddress);
        if (it != g_deviceToNodeMap.end())
        {
            uint32_t nodeId = it->second;
            g_receivedPacketsPerNode[nodeId]++;
            g_totalReceived++;
            
            // double currentTime = Simulator::Now().GetSeconds();
            // NS_LOG_DEBUG("Gateway received packet from Node " << nodeId 
            //            << " at " << std::fixed << std::setprecision(2) << currentTime << "s");
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
        g_totalAirTimePerNode[nodeId] = 0.0;
        g_transmissionTimesPerNode[nodeId].clear();
    }
    
    std::cout << "✅ Traffic patterns device mapping built for " << endDevices.GetN() << " devices" << std::endl;
}

// ==============================================================================
// RESULTS EXPORT
// ==============================================================================

void ExportResults(const std::string& filename, NodeContainer endDevices, 
                  int simulationTime, int packetInterval)
{
    std::ofstream file(filename);
    WriteStandardHeader(file, "Scenario 5: Traffic Pattern Variation",
                       endDevices.GetN(), 1, simulationTime,
                       "Interval: " + std::to_string(packetInterval) + "s, saturation analysis");
    
    double simulationTimeSeconds = simulationTime * 60.0;
    double expectedPacketsPerDevice = simulationTimeSeconds / packetInterval;
    
    // Standardized Erlang calculation (1 channel assumption)
    double offeredLoad = lora::OfferedLoadErlangs(g_totalChannelAirTime, simulationTimeSeconds, 1);
    double channelUtilization = lora::ChannelUtilizationPercent(offeredLoad);
    
    uint32_t packetsDropped = g_totalSent - g_totalReceived;
    
    file << "OVERALL_STATS\n";
    file << "PacketInterval_s," << packetInterval << "\n";
    file << "ExpectedPacketsPerDevice," << std::fixed << std::setprecision(2) 
         << expectedPacketsPerDevice << "\n";
    file << "OfferedLoad_Erlangs," << std::fixed << std::setprecision(6) << offeredLoad << "\n";
    file << "ChannelUtilization_Percent," << std::fixed << std::setprecision(4) 
         << channelUtilization << "\n";
    file << "TotalSent," << g_totalSent << "\n";
    file << "TotalReceived," << g_totalReceived << "\n";
    file << "PDR_Percent," << std::fixed << std::setprecision(2) 
         << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";
    file << "PacketsDropped_SentMinusReceived," << packetsDropped << "\n";
    file << "DropRate_Percent," << std::fixed << std::setprecision(2) 
         << lora::DropRatePercent(packetsDropped, g_totalSent) << "\n";
    file << "TotalChannelAirTime_ms," << std::fixed << std::setprecision(2) 
         << g_totalChannelAirTime << "\n";
    
    // Duty cycle analysis (EU868 1% limit)
    double dutyCycleLimit = 0.01; // 1%
    double avgDutyCycleUsage = (g_totalChannelAirTime / 1000.0) / simulationTimeSeconds / endDevices.GetN();
    double avgDutyCycleHeadroom = std::max(0.0, (dutyCycleLimit - avgDutyCycleUsage) * 100.0);
    file << "AvgDutyCycleUsage_Percent," << std::fixed << std::setprecision(4) 
         << avgDutyCycleUsage * 100.0 << "\n";
    file << "AvgDutyCycleHeadroom_Percent," << std::fixed << std::setprecision(4) 
         << avgDutyCycleHeadroom << "\n";
    
    // Saturation analysis
    double theoreticalMaxUtilization = 100.0; // 100% channel usage
    double saturationLevel = channelUtilization / theoreticalMaxUtilization * 100.0;
    file << "SaturationLevel_Percent," << std::fixed << std::setprecision(2) 
         << saturationLevel << "\n\n";
    
    // Per-node stats
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,AirTime_ms,DutyCycleUsage_Percent,TransmissionCount\n";
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = g_sentPacketsPerNode[nodeId];
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        double airTime = g_totalAirTimePerNode[nodeId];
        double nodeDutyCycleUsage = (airTime / 1000.0) / simulationTimeSeconds * 100.0;
        uint32_t transmissionCount = g_transmissionTimesPerNode[nodeId].size();
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << "," 
             << airTime << "," << nodeDutyCycleUsage << "," << transmissionCount << "\n";
    }
    
    file.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}

// ==============================================================================
// MAIN FUNCTION
// ==============================================================================

int main(int argc, char* argv[])
{
    // Scenario 5 Parameters
    int nDevices = 100;
    int nGateways = 1;
    int simulationTime = 30; // minutes (longer to observe saturation effects)
    int packetInterval = 600; // Command line parameter: 600, 300, 60 seconds
    double sideLengthMeters = 5000; // 5km x 5km area
    double maxRandomLossDb = 5.0;
    std::string outputPrefix = "scenario05_traffic_patterns";
    std::string positionFile = "scenario_positions.csv";
    bool useFilePositions = true;

    CommandLine cmd(__FILE__);
    cmd.AddValue("packetInterval", "Packet interval in seconds (600, 300, 60)", packetInterval);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("nDevices", "Number of devices", nDevices);
    cmd.AddValue("positionFile", "CSV file with node positions", positionFile);
    cmd.AddValue("useFilePositions", "Use positions from file (vs random)", useFilePositions);
    cmd.Parse(argc, argv);

    // Store the current packet interval for analysis
    g_currentPacketInterval = packetInterval;

    // Logging
    LogComponentEnable("Scenario05TrafficPatterns", LOG_LEVEL_INFO);
    
    // Create node containers
    NodeContainer endDevices, gateways;
    endDevices.Create(nDevices);
    gateways.Create(nGateways);
    
    // Setup network using standardized functions
    Ptr<LoraChannel> channel = SetupStandardChannel(maxRandomLossDb);
    if (useFilePositions) {
        SetupMobilityFromFile(endDevices, gateways, sideLengthMeters,
                              "scenario_05_traffic", positionFile);
    } else {
        RngSeedManager::SetSeed(12349);
        RngSeedManager::SetRun(1);
        SetupStandardMobility(endDevices, gateways, sideLengthMeters);
    }
    SetupStandardLoRa(endDevices, gateways, channel, 2); // DR2 = SF10

    SetupStandardNetworkServer(gateways, endDevices, false); // No ADR
    
    // Setup timing and traces
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMapping);
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);

    // Run simulation
    Time totalSimulationTime = Seconds(simulationTime * 60);
    Simulator::Stop(totalSimulationTime);

    // Calculate expected traffic metrics
    double expectedPacketsPerDevice = (simulationTime * 60.0) / packetInterval;
    double theoreticalAirTime = lora::CalculateAirTime(10); // SF10
    double theoreticalChannelLoad = (nDevices * expectedPacketsPerDevice * theoreticalAirTime) / (simulationTime * 60 * 1000) * 100.0;

    std::cout << "\n=== Scenario 5: Traffic Pattern Variation ===" << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "Packet interval: " << packetInterval << "s" << std::endl;
    std::cout << "Expected packets per device: " << std::fixed << std::setprecision(1) << expectedPacketsPerDevice << std::endl;
    std::cout << "Theoretical channel utilization: " << std::fixed << std::setprecision(4) << theoreticalChannelLoad << "%" << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes" << std::endl;
    std::cout << "Starting simulation..." << std::endl;

    Simulator::Run();

    std::cout << "\n=== Simulation Complete ===" << std::endl;
    std::cout << "Total packets sent: " << g_totalSent << std::endl;
    std::cout << "Total packets received: " << g_totalReceived << std::endl;
    std::cout << "Total channel airtime: " << std::fixed << std::setprecision(2) << g_totalChannelAirTime << " ms" << std::endl;
    
    if (g_totalSent > 0) {
        double pdr = lora::PdrPercent(g_totalReceived, g_totalSent);
        double dropRate = lora::DropRatePercent(g_totalSent - g_totalReceived, g_totalSent);
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2) << pdr << "%" << std::endl;
        std::cout << "Drop rate: " << std::fixed << std::setprecision(2) << dropRate << "%" << std::endl;
    }
    
    // Calculate actual channel utilization
    double simulationTimeSeconds = simulationTime * 60.0;
    double actualChannelUtilization = (g_totalChannelAirTime / 1000.0) / simulationTimeSeconds * 100.0;
    std::cout << "Actual channel utilization: " << std::fixed << std::setprecision(4) << actualChannelUtilization << "%" << std::endl;

    // Validate and export results
    ValidateResults(endDevices);

    std::string outputFile = outputPrefix + "_interval" + std::to_string(packetInterval) + "s_results.csv";
    ExportResults(outputFile, endDevices, simulationTime, packetInterval);

    Simulator::Destroy();
    return 0;
}