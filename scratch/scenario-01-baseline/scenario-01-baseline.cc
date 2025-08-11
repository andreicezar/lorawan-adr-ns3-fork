/*
 * Scenario 1: Baseline Reference Case
 * 100 end devices, 1 gateway, SF10 fixed, 125 kHz, 51B payload
 * Packet interval: 600s, TX power: 14 dBm, uplink only, unconfirmed
 * 
 * Purpose: Control case to normalize other experiments
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

NS_LOG_COMPONENT_DEFINE("Scenario01Baseline");

// ==============================================================================
// GLOBAL VARIABLES
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Scenario-specific variables
std::map<uint32_t, uint32_t> g_adrChangesPerNode;

// ==============================================================================
// CALLBACK FUNCTIONS
// ==============================================================================

void OnPacketSent(Ptr<const Packet> packet) {
    uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
    NS_LOG_DEBUG("Node " << nodeId << " sent packet #" << g_sentPacketsPerNode[nodeId]);
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
            NS_LOG_DEBUG("Gateway received packet from Node " << nodeId);
        }
    }
}

void OnDataRateChange(uint8_t oldDr, uint8_t newDr) {
    uint32_t nodeId = Simulator::GetContext();
    g_adrChangesPerNode[nodeId]++;
    NS_LOG_INFO("Node " << nodeId << " DR change: " << (int)oldDr << " -> " << (int)newDr);
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
        g_adrChangesPerNode[nodeId] = 0;
    }
    
    std::cout << "✅ Baseline device mapping built for " << endDevices.GetN() << " devices" << std::endl;
}

// ==============================================================================
// RESULTS EXPORT
// ==============================================================================

void ExportResults(const std::string& filename, NodeContainer endDevices, int simulationTime) {
    std::ofstream file(filename);
    
    WriteStandardHeader(file, "Scenario 1: Baseline Reference Case", 
                       endDevices.GetN(), 1, simulationTime,
                       "SF10 fixed, 600s interval, unconfirmed uplink only, ADR disabled");
    
    // Overall stats
    file << "OVERALL_STATS\n";
    file << "TotalSent," << g_totalSent << "\n";
    file << "TotalReceived," << g_totalReceived << "\n";
    file << "PDR_Percent," << std::fixed << std::setprecision(2) 
         << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";
    
    // Calculate drops and utilization
    uint32_t drops = (g_totalSent >= g_totalReceived) ? (g_totalSent - g_totalReceived) : 0;
    file << "Drops_SentMinusReceived," << drops << "\n";
    file << "DropRate_Percent," << std::fixed << std::setprecision(2) 
         << lora::DropRatePercent(drops, g_totalSent) << "\n";
    
    // Airtime and utilization calculations
    double toa_ms = lora::CalculateAirTime(10); // SF10
    double sim_s = simulationTime * 60.0;
    double totalAirtime = g_totalSent * toa_ms;
    double offered = lora::OfferedLoadErlangs(totalAirtime, sim_s, 1);
    
    file << "TheoreticalToA_ms_SF10," << std::fixed << std::setprecision(2) << toa_ms << "\n";
    file << "TotalAirTime_ms," << std::fixed << std::setprecision(2) << totalAirtime << "\n";
    file << "ChannelUtilization_Percent," << std::fixed << std::setprecision(4) 
         << lora::ChannelUtilizationPercent(offered) << "\n";
    file << "AvgHearingsPerUplink,1\n\n"; // Single GW baseline
    
    // Per-node stats
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,Drops,ADR_Changes\n";
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = g_sentPacketsPerNode[nodeId];
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        uint32_t nodeDrops = sent >= received ? sent - received : 0;
        uint32_t adrChanges = g_adrChangesPerNode[nodeId];
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << "," 
             << nodeDrops << "," << adrChanges << "\n";
    }
    
    file.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}

// ==============================================================================
// MAIN FUNCTION
// ==============================================================================

int main(int argc, char* argv[]) {
    // Scenario 1 Parameters
    int nDevices = 100;
    int nGateways = 1;
    int simulationTime = 10; // minutes
    int packetInterval = 600; // seconds
    std::string outputPrefix = "scenario01_baseline";
    
    CommandLine cmd(__FILE__);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.Parse(argc, argv);

    // Logging
    LogComponentEnable("Scenario01Baseline", LOG_LEVEL_INFO);
    
    // Create node containers
    NodeContainer endDevices, gateways;
    endDevices.Create(nDevices);
    gateways.Create(nGateways);
    
    // Setup network using standardized functions
    Ptr<LoraChannel> channel = SetupStandardChannel();
    SetupStandardMobility(endDevices, gateways);
    SetupStandardLoRa(endDevices, gateways, channel, 2); // DR2 = SF10
    SetupStandardNetworkServer(gateways, endDevices, false); // No ADR
    
    // Setup timing and traces
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMapping);
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);
    
    // Connect ADR trace (for completeness, though not used in baseline)
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/DataRate",
        MakeCallback(&OnDataRateChange));

    // Run simulation
    Time totalSimulationTime = Seconds(simulationTime * 60);
    Simulator::Stop(totalSimulationTime);

    std::cout << "\n=== Scenario 1: Baseline Reference Case ===" << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "SF: Fixed SF10 | ADR: Disabled" << std::endl;
    std::cout << "Packet interval: " << packetInterval << "s" << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes" << std::endl;
    std::cout << "Starting simulation..." << std::endl;

    Simulator::Run();

    std::cout << "\n=== Simulation Complete ===" << std::endl;
    std::cout << "Total packets sent: " << g_totalSent << std::endl;
    std::cout << "Total packets received: " << g_totalReceived << std::endl;
    
    if (g_totalSent > 0) {
        double pdr = lora::PdrPercent(g_totalReceived, g_totalSent);
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2) << pdr << "%" << std::endl;
    }

    // Validate and export results
    ValidateResults(endDevices);

    std::string outputFile = outputPrefix + "_results.csv";
    ExportResults(outputFile, endDevices, simulationTime);

    Simulator::Destroy();
    return 0;
}