/*
 * Scenario 3: Spreading Factor Impact Analysis
 * Tests SF7 through SF12 with 50 devices per run
 * Measures PDR, ToA (Time on Air), and Collision Rate
 * 
 * Purpose: Assess PHY layer impact and airtime growth across SFs
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

NS_LOG_COMPONENT_DEFINE("Scenario03SfImpact");

// ==============================================================================
// GLOBAL VARIABLES
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Scenario-specific variables
std::map<uint32_t, double> g_totalAirTimePerNode;
std::map<uint32_t, double> g_rssiPerNode;
std::map<uint32_t, double> g_snrPerNode;
double g_totalAirTime = 0.0;

// Store current SF for airtime calculations
uint8_t g_currentSpreadingFactor = 10;

// ==============================================================================
// CALLBACK FUNCTIONS
// ==============================================================================

void OnPacketSent(Ptr<const Packet> packet) {
    uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
    
    // Calculate airtime for fixed SF
    double airTime = lora::CalculateAirTime(g_currentSpreadingFactor);
    g_totalAirTimePerNode[nodeId] += airTime;
    g_totalAirTime += airTime;
    
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

            // Calculate RSSI and SNR for analysis
            Ptr<Node> node = NodeList::GetNode(nodeId);
            Ptr<MobilityModel> mob = node->GetObject<MobilityModel>();
            if (mob) {
                Vector pos = mob->GetPosition();
                double distance = lora::Distance2D(pos.x, pos.y, 0.0, 0.0);
                distance = std::max(1.0, distance);

                double rssiDbm = lora::Rssi_dBm_fromDistance(14.0, distance, 7.7, 3.76);
                double noiseDbm = lora::NoiseFloor_dBm(125000.0, 6.0);
                double snrDb = lora::Snr_dB(rssiDbm, noiseDbm);

                // Running averages
                uint32_t count = g_receivedPacketsPerNode[nodeId];
                if (count == 1) {
                    g_rssiPerNode[nodeId] = rssiDbm;
                    g_snrPerNode[nodeId] = snrDb;
                } else {
                    g_rssiPerNode[nodeId] = (g_rssiPerNode[nodeId] * (count - 1) + rssiDbm) / count;
                    g_snrPerNode[nodeId] = (g_snrPerNode[nodeId] * (count - 1) + snrDb) / count;
                }
            }
            
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
        g_totalAirTimePerNode[nodeId] = 0.0;
        g_rssiPerNode[nodeId] = 0.0;
        g_snrPerNode[nodeId] = 0.0;
    }
    
    std::cout << "✅ SF Impact device mapping built for " << endDevices.GetN() << " devices" << std::endl;
}

// ==============================================================================
// RESULTS EXPORT
// ==============================================================================

void ExportResults(const std::string& filename, NodeContainer endDevices, 
                  int simulationTime, uint8_t spreadingFactor)
{
    std::ofstream file(filename);
    WriteStandardHeader(file, "Scenario 3: Spreading Factor Impact Analysis",
                       endDevices.GetN(), 1, simulationTime,
                       "SF" + std::to_string(spreadingFactor) + " fixed, 300s interval");
    
    double theoreticalAirTime = lora::CalculateAirTime(spreadingFactor);
    uint32_t packetsDropped = g_totalSent - g_totalReceived;
    
    file << "OVERALL_STATS\n";
    file << "SpreadingFactor," << (int)spreadingFactor << "\n";
    file << "TotalSent," << g_totalSent << "\n";
    file << "TotalReceived," << g_totalReceived << "\n";
    file << "PDR_Percent," << std::fixed << std::setprecision(2) 
         << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";
    file << "PacketsDropped_SentMinusReceived," << packetsDropped << "\n";
    file << "DropRate_Percent," << std::fixed << std::setprecision(2) 
         << lora::DropRatePercent(packetsDropped, g_totalSent) << "\n";
    file << "TotalAirTime_ms," << std::fixed << std::setprecision(2) << g_totalAirTime << "\n";
    file << "TheoreticalAirTimePerPacket_ms," << std::fixed << std::setprecision(2) 
         << theoreticalAirTime << "\n";
    
    // Channel utilization
    double simSeconds = simulationTime * 60.0;
    double offered = lora::OfferedLoadErlangs(g_totalAirTime, simSeconds, 1);
    file << "ChannelUtilization_Percent," << std::fixed << std::setprecision(4) 
         << lora::ChannelUtilizationPercent(offered) << "\n";
    
    // Airtime scaling analysis
    double sf7AirTime = lora::CalculateAirTime(7);
    double airtimeScale = theoreticalAirTime / sf7AirTime;
    file << "AirtimeScale_vs_SF7," << std::fixed << std::setprecision(2) << airtimeScale << "\n\n";
    
    // Per-node stats with RF analysis
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,AirTime_ms,AvgRSSI_dBm,AvgSNR_dB,Distance_m\n";
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = g_sentPacketsPerNode[nodeId];
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        double airTime = g_totalAirTimePerNode[nodeId];
        double avgRssi = g_rssiPerNode[nodeId];
        double avgSnr = g_snrPerNode[nodeId];
        
        // Calculate distance for analysis
        Ptr<Node> node = NodeList::GetNode(nodeId);
        Vector pos = node->GetObject<MobilityModel>()->GetPosition();
        double distance = lora::Distance2D(pos.x, pos.y, 0.0, 0.0);
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << "," 
             << airTime << "," << avgRssi << "," << avgSnr << "," 
             << std::setprecision(0) << distance << "\n";
    }
    
    file.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}

// ==============================================================================
// MAIN FUNCTION
// ==============================================================================

int main(int argc, char* argv[])
{
    // Scenario 3 Parameters
    int nDevices = 50; // Reduced for clearer SF impact analysis
    int nGateways = 1;
    int simulationTime = 15; // minutes
    int packetInterval = 300; // seconds (faster than baseline for more data points)
    double sideLengthMeters = 3000; // 3km x 3km area (smaller for better coverage)
    double maxRandomLossDb = 3.0;
    uint8_t spreadingFactor = 10; // Default SF10, can be overridden
    std::string outputPrefix = "scenario03_sf_impact";
    
    CommandLine cmd(__FILE__);
    cmd.AddValue("spreadingFactor", "Spreading Factor to test (7-12)", spreadingFactor);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("nDevices", "Number of devices", nDevices);
    cmd.AddValue("packetInterval", "Packet interval in seconds", packetInterval);
    cmd.Parse(argc, argv);

    // Validate SF range
    if (spreadingFactor < 7 || spreadingFactor > 12) {
        std::cerr << "Error: Spreading Factor must be between 7 and 12" << std::endl;
        return 1;
    }

    // Store the current SF for airtime calculations
    g_currentSpreadingFactor = spreadingFactor;

    // Logging
    LogComponentEnable("Scenario03SfImpact", LOG_LEVEL_INFO);
    
    // Create node containers
    NodeContainer endDevices, gateways;
    endDevices.Create(nDevices);
    gateways.Create(nGateways);
    
    // Setup network using standardized functions
    Ptr<LoraChannel> channel = SetupStandardChannel(maxRandomLossDb);
    SetupStandardMobility(endDevices, gateways, sideLengthMeters);
    
    // Convert SF to DR for EU868
    uint8_t dataRate = lora::DrFromSfEu868(spreadingFactor);
    SetupStandardLoRa(endDevices, gateways, channel, dataRate);
    SetupStandardNetworkServer(gateways, endDevices, false); // No ADR
    
    // Setup timing and traces
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMapping);
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);

    // Run simulation
    Time totalSimulationTime = Seconds(simulationTime * 60);
    Simulator::Stop(totalSimulationTime);

    double theoreticalAirTime = lora::CalculateAirTime(spreadingFactor);
    std::cout << "\n=== Scenario 3: SF Impact Analysis ===" << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "Spreading Factor: SF" << (int)spreadingFactor << std::endl;
    std::cout << "Theoretical packet airtime: " << std::fixed << std::setprecision(2) 
              << theoreticalAirTime << " ms" << std::endl;
    std::cout << "Packet interval: " << packetInterval << "s" << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes" << std::endl;
    std::cout << "Starting simulation..." << std::endl;

    Simulator::Run();

    std::cout << "\n=== Simulation Complete ===" << std::endl;
    std::cout << "Total packets sent: " << g_totalSent << std::endl;
    std::cout << "Total packets received: " << g_totalReceived << std::endl;
    
    uint32_t packetsLost = g_totalSent - g_totalReceived;
    std::cout << "Total packets lost: " << packetsLost << std::endl;
    std::cout << "Total airtime: " << std::fixed << std::setprecision(2) << g_totalAirTime << " ms" << std::endl;
    
    if (g_totalSent > 0) {
        double pdr = lora::PdrPercent(g_totalReceived, g_totalSent);
        double lossRate = lora::DropRatePercent(packetsLost, g_totalSent);
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2) << pdr << "%" << std::endl;
        std::cout << "Loss rate: " << std::fixed << std::setprecision(2) << lossRate << "%" << std::endl;
    }

    // Validate and export results
    ValidateResults(endDevices);

    std::string outputFile = outputPrefix + "_sf" + std::to_string(spreadingFactor) + "_results.csv";
    ExportResults(outputFile, endDevices, simulationTime, spreadingFactor);

    Simulator::Destroy();
    return 0;
}