/*
 * Scenario 1: Baseline Reference Case
 * 100 end devices, 1 gateway, configurable SF/TP initialization, 125 kHz, 51B payload
 * Packet interval: 600s, uplink only, unconfirmed
 * 
 * Configurable parameters:
 * - initSF: Initialize spreading factor (default: true, SF10)
 * - initTP: Initialize transmit power (default: true, 14 dBm)
 * - enableADR: Enable adaptive data rate (default: false)
 * 
 * Uses MAC layer methods for both SF and TP configuration:
 * - SF via SetDataRate()/GetDataRate()
 * - TP via SetTransmissionPowerDbm()/GetTransmissionPowerDbm()
 * 
 * Purpose: Flexible control case to test different initialization strategies
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
#include "ns3/end-device-lorawan-mac.h"
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

#include "common/position_loader.h"

// ==============================================================================
// GLOBAL VARIABLES
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Enhanced tracking variables
std::map<uint32_t, uint32_t> g_adrChangesPerNode;
std::map<uint32_t, uint8_t> g_initialSFPerNode;
std::map<uint32_t, uint8_t> g_initialTPPerNode;
std::map<uint32_t, uint8_t> g_finalSFPerNode;
std::map<uint32_t, uint8_t> g_finalTPPerNode;

// Configuration flags
bool g_initSF = true;
bool g_initTP = true;
bool g_enableADR = false;

std::map<uint32_t, std::vector<std::pair<double, uint8_t>>> g_adrHistory; 
uint32_t g_totalAdrRequests = 0;
uint32_t g_totalAdrResponses = 0;

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

// Enhanced callback functions - replace your existing ones
void OnDataRateChange(uint8_t oldDr, uint8_t newDr) {
    uint32_t nodeId = Simulator::GetContext();
    double time = Simulator::Now().GetSeconds();
    
    g_adrChangesPerNode[nodeId]++;
    g_adrHistory[nodeId].push_back(std::make_pair(time, newDr));
    g_totalAdrResponses++;
    
    NS_LOG_INFO("Node " << nodeId << " DR change: " << (int)oldDr << " -> " << (int)newDr 
                << " (SF" << (12-oldDr) << " -> SF" << (12-newDr) << ") at " << time << "s");
    
    std::cout << "ADR: Node " << nodeId << " changed from SF" << (12-oldDr) 
              << " to SF" << (12-newDr) << " at " << time << "s" << std::endl;
}

void OnTxPowerChange(double oldTxPower, double newTxPower) {
    uint32_t nodeId = Simulator::GetContext();
    double time = Simulator::Now().GetSeconds();
    
    NS_LOG_INFO("Node " << nodeId << " TX Power change: " << oldTxPower << " -> " << newTxPower 
                << " dBm at " << time << "s");
                
    std::cout << "ADR: Node " << nodeId << " power changed from " << oldTxPower 
              << " to " << newTxPower << " dBm at " << time << "s" << std::endl;
}

// Add debug function to check ADR configuration
void DebugAdrConfiguration(NodeContainer endDevices) {
    std::cout << "\n=== ADR Configuration Debug ===" << std::endl;
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        if (i >= 5) break; // Show first 5 nodes only
        
        Ptr<LoraNetDevice> device = endDevices.Get(i)->GetDevice(0)->GetObject<LoraNetDevice>();
        Ptr<EndDeviceLorawanMac> mac = device->GetMac()->GetObject<EndDeviceLorawanMac>();
        
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint8_t currentDR = mac->GetDataRate();
        double currentTP = mac->GetTransmissionPowerDbm();
        
        std::cout << "Node " << nodeId << ": DR=" << (int)currentDR 
                  << " (SF" << (12-currentDR) << "), TP=" << currentTP << "dBm" << std::endl;
    }
    std::cout << "===============================\n" << std::endl;
}

// ==============================================================================
// DEVICE MAPPING AND INITIALIZATION
// ==============================================================================

void BuildDeviceMapping(NodeContainer endDevices) {
    // Use standard mapping first
    BuildStandardDeviceMapping(endDevices);
    
    // Initialize tracking maps - add null pointer protection
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        g_adrChangesPerNode[nodeId] = 0;
        
        // Store initial parameters with null pointer checks
        Ptr<LoraNetDevice> loraNetDevice = endDevices.Get(i)->GetDevice(0)->GetObject<LoraNetDevice>();
        if (!loraNetDevice) {
            NS_FATAL_ERROR("Node " << nodeId << " has no LoraNetDevice");
            continue;
        }
        
        Ptr<EndDeviceLorawanMac> mac = loraNetDevice->GetMac()->GetObject<EndDeviceLorawanMac>();
        if (!mac) {
            NS_FATAL_ERROR("Node " << nodeId << " has no EndDeviceLorawanMac");
            continue;
        }
        
        g_initialSFPerNode[nodeId] = mac->GetDataRate();
        g_initialTPPerNode[nodeId] = (uint8_t)mac->GetTransmissionPowerDbm();
        g_finalSFPerNode[nodeId] = mac->GetDataRate();
        g_finalTPPerNode[nodeId] = (uint8_t)mac->GetTransmissionPowerDbm();
    }
    
    std::cout << "✅ Baseline device mapping built for " << endDevices.GetN() << " devices" << std::endl;
    std::cout << "📊 Configuration: SF init=" << (g_initSF ? "ON" : "OFF") 
              << ", TP init=" << (g_initTP ? "ON" : "OFF") 
              << ", ADR=" << (g_enableADR ? "ON" : "OFF") << std::endl;
}

void InitializeDeviceParameters(NodeContainer endDevices) {
    std::cout << "Initializing device parameters..." << std::endl;
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        Ptr<LoraNetDevice> loraNetDevice = endDevices.Get(i)->GetDevice(0)->GetObject<LoraNetDevice>();
        if (!loraNetDevice) {
            NS_FATAL_ERROR("Node " << i << " has no LoraNetDevice");
            continue;
        }
        
        Ptr<EndDeviceLorawanMac> mac = loraNetDevice->GetMac()->GetObject<EndDeviceLorawanMac>();
        if (!mac) {
            NS_FATAL_ERROR("Node " << i << " has no EndDeviceLorawanMac");
            continue;
        }
        
        uint32_t nodeId = endDevices.Get(i)->GetId();
        
        // Initialize SF if requested
        if (g_initSF) {
            uint8_t targetDR = 2;  // DR2 = SF10
            mac->SetDataRate(targetDR);
            NS_LOG_DEBUG("Node " << nodeId << " SF initialized to DR" << (int)targetDR);
        }
        
        // Initialize TP if requested
        if (g_initTP) {
            double targetTP = 14.0;  // 14 dBm default
            mac->SetTransmissionPowerDbm(targetTP);
            NS_LOG_DEBUG("Node " << nodeId << " TX Power initialized to " << targetTP << " dBm");
        }
        
        // REMOVED INVALID CALLS:
        // - mac->SetFType() - doesn't exist
        // - mac->SetMType() - doesn't exist  
        // - mac->SetAdaptiveDataRate() - doesn't exist
        // ADR is managed by NetworkServer, not individual devices
        
        // Update initial values after configuration
        g_initialSFPerNode[nodeId] = mac->GetDataRate();
        g_initialTPPerNode[nodeId] = (uint8_t)mac->GetTransmissionPowerDbm();
    }
    
    std::cout << "Parameters initialized: SF=" << (g_initSF ? "SF10" : "default") 
              << ", TP=" << (g_initTP ? "14dBm" : "default") << std::endl;
              
    // Debug ADR configuration
    if (g_enableADR) {
        std::cout << "ADR will be managed by NetworkServer" << std::endl;
        DebugAdrConfiguration(endDevices);
    }
}

void CaptureEndStates(NodeContainer endDevices) {
    // Capture final SF and TP for each device
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        Ptr<LoraNetDevice> loraNetDevice = endDevices.Get(i)->GetDevice(0)->GetObject<LoraNetDevice>();
        if (!loraNetDevice) {
            NS_LOG_ERROR("Node " << nodeId << " has no LoraNetDevice in CaptureEndStates");
            continue;
        }
        
        Ptr<EndDeviceLorawanMac> mac = loraNetDevice->GetMac()->GetObject<EndDeviceLorawanMac>();
        if (!mac) {
            NS_LOG_ERROR("Node " << nodeId << " has no EndDeviceLorawanMac in CaptureEndStates");
            continue;
        }
        
        g_finalSFPerNode[nodeId] = mac->GetDataRate();
        g_finalTPPerNode[nodeId] = (uint8_t)mac->GetTransmissionPowerDbm();
    }
}

// ==============================================================================
// RESULTS EXPORT
// ==============================================================================

void ExportResults(const std::string& filename, NodeContainer endDevices, int simulationTime) {
    std::ofstream file(filename);
    
    // Build configuration description
    std::string configDesc = "SF init=";
    configDesc += g_initSF ? "ON" : "OFF";
    configDesc += ", TP init=";
    configDesc += g_initTP ? "ON" : "OFF";
    configDesc += ", ADR=";
    configDesc += g_enableADR ? "ON" : "OFF";
    
    WriteStandardHeader(file, "Scenario 1: Baseline Reference Case", 
                       endDevices.GetN(), 1, simulationTime, configDesc);
    
    // Configuration details
    file << "CONFIGURATION\n";
    file << "InitSF," << (g_initSF ? "true" : "false") << "\n";
    file << "InitTP," << (g_initTP ? "true" : "false") << "\n";
    file << "EnableADR," << (g_enableADR ? "true" : "false") << "\n";
    file << "DefaultSF,10\n";
    file << "DefaultTP_dBm,14\n\n";
    
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
    
    // Airtime calculations (using average SF if ADR enabled)
    double avgSF = 10.0; // Default for fixed case
    if (g_enableADR) {
        // Calculate average SF from final states
        double sfSum = 0;
        for (const auto& pair : g_finalSFPerNode) {
            sfSum += (12 - pair.second); // Convert DR to SF
        }
        if (g_finalSFPerNode.size() > 0) {
            avgSF = sfSum / g_finalSFPerNode.size();
        }
    }
    
    double toa_ms = lora::CalculateAirTime(avgSF);
    double sim_s = simulationTime * 60.0;
    double totalAirtime = g_totalSent * toa_ms;
    double offered = lora::OfferedLoadErlangs(totalAirtime, sim_s, 1);
    
    file << "AvgSF," << std::fixed << std::setprecision(2) << avgSF << "\n";
    file << "TheoreticalToA_ms," << std::fixed << std::setprecision(2) << toa_ms << "\n";
    file << "TotalAirTime_ms," << std::fixed << std::setprecision(2) << totalAirtime << "\n";
    file << "ChannelUtilization_Percent," << std::fixed << std::setprecision(4) 
         << lora::ChannelUtilizationPercent(offered) << "\n";
    file << "AvgHearingsPerUplink,1\n\n"; // Single GW baseline
    
    // ADR Statistics
    uint32_t totalAdrChanges = 0;
    for (const auto& pair : g_adrChangesPerNode) {
        totalAdrChanges += pair.second;
    }
    file << "TotalADRChanges," << totalAdrChanges << "\n";
    
    // ADR Debug section
    if (g_enableADR) {
        file << "ADRRequests," << g_totalAdrRequests << "\n";
        file << "ADRResponses," << g_totalAdrResponses << "\n";
        
        // Count nodes with ADR changes
        uint32_t nodesWithChanges = 0;
        for (const auto& pair : g_adrChangesPerNode) {
            if (pair.second > 0) nodesWithChanges++;
        }
        file << "NodesWithADRChanges," << nodesWithChanges << "\n";
    }
    file << "\n";
    
    // Per-node stats
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,Drops,ADR_Changes,InitSF_DR,InitTP_dBm,FinalSF_DR,FinalTP_dBm\n";
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = g_sentPacketsPerNode[nodeId];
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        uint32_t nodeDrops = sent >= received ? sent - received : 0;
        uint32_t adrChanges = g_adrChangesPerNode[nodeId];
        uint8_t initSF = g_initialSFPerNode[nodeId];
        uint8_t initTP = g_initialTPPerNode[nodeId];
        uint8_t finalSF = g_finalSFPerNode[nodeId];
        uint8_t finalTP = g_finalTPPerNode[nodeId];
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << "," 
             << nodeDrops << "," << adrChanges << ","
             << (int)initSF << "," << (int)initTP << ","
             << (int)finalSF << "," << (int)finalTP << "\n";
    }
    
    file.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
    
    // Console summary for ADR
    if (g_enableADR && totalAdrChanges > 0) {
        std::cout << "🔄 ADR Activity Summary:" << std::endl;
        std::cout << "   Total ADR changes: " << totalAdrChanges << std::endl;
        std::cout << "   Nodes affected: ";
        uint32_t nodesWithChanges = 0;
        for (const auto& pair : g_adrChangesPerNode) {
            if (pair.second > 0) nodesWithChanges++;
        }
        std::cout << nodesWithChanges << "/" << endDevices.GetN() << std::endl;
    }
}

// ==============================================================================
// MAIN FUNCTION
// ==============================================================================

int main(int argc, char* argv[]) {
    // Default parameters
    int nDevices = 100;
    int nGateways = 1;
    int simulationTime = 10; // minutes
    int packetInterval = 600; // seconds
    std::string outputPrefix = "scenario01_baseline";
    std::string positionFile = "../scenario_positions.csv";  // Look in parent directory
    bool useFilePositions = true;
    
    // New configurable parameters
    bool initSF = true;      // Initialize spreading factor
    bool initTP = true;      // Initialize transmit power
    bool enableADR = false;  // Enable adaptive data rate
    int targetSF = 10;       // Target SF when initSF=true
    int targetTP = 14;       // Target TP when initTP=true

    CommandLine cmd(__FILE__);
    cmd.AddValue("nDevices", "Number of end devices", nDevices);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("packetInterval", "Packet transmission interval in seconds", packetInterval);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("positionFile", "CSV file with node positions", positionFile);
    cmd.AddValue("useFilePositions", "Use positions from file (vs random)", useFilePositions);
    cmd.AddValue("initSF", "Initialize spreading factor", initSF);
    cmd.AddValue("initTP", "Initialize transmit power", initTP);
    cmd.AddValue("enableADR", "Enable adaptive data rate", enableADR);
    cmd.AddValue("targetSF", "Target SF when initSF=true (7-12)", targetSF);
    cmd.AddValue("targetTP", "Target TP when initTP=true (2-14 dBm)", targetTP);
    cmd.Parse(argc, argv);

    // Store global config
    g_initSF = initSF;
    g_initTP = initTP;
    g_enableADR = enableADR;

    // Validate parameters
    if (targetSF < 7 || targetSF > 12) {
        std::cerr << "❌ Error: targetSF must be between 7 and 12" << std::endl;
        return 1;
    }
    if (targetTP < 2 || targetTP > 14) {
        std::cerr << "❌ Error: targetTP must be between 2 and 14 dBm" << std::endl;
        return 1;
    }

    // Logging
    LogComponentEnable("Scenario01Baseline", LOG_LEVEL_INFO);
    if (enableADR) {
        LogComponentEnable("AdrComponent", LOG_LEVEL_INFO);
        LogComponentEnable("EndDeviceLorawanMac", LOG_LEVEL_INFO);
        LogComponentEnable("NetworkServer", LOG_LEVEL_INFO);
        std::cout << "🔍 ADR debugging enabled" << std::endl;
    }
    LogComponentEnable("EndDeviceLorawanMac", LOG_LEVEL_DEBUG);

    // Create node containers
    NodeContainer endDevices, gateways;
    endDevices.Create(nDevices);
    gateways.Create(nGateways);
    
    // Setup network using standardized functions
    Ptr<LoraChannel> channel = SetupStandardChannel();
    if (useFilePositions) {
        SetupMobilityFromFile(endDevices, gateways, 5000, "scenario_01_baseline", positionFile);
    } else {
        // Use random placement with fixed seed for reproducibility
        RngSeedManager::SetSeed(12345);
        RngSeedManager::SetRun(1);
        SetupStandardMobility(endDevices, gateways, 5000);
    }
    
    // Convert SF to DR for LoRa setup
    uint8_t targetDR = 12 - targetSF; // SF to DR conversion for EU868
    
    // Setup LoRa with configurable parameters
    if (initSF) {
        SetupStandardLoRa(endDevices, gateways, channel, targetDR);
    } else {
        SetupStandardLoRa(endDevices, gateways, channel, -1); // Use default DR
    }
    if (enableADR) {
        for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
            Ptr<LoraNetDevice> device = endDevices.Get(i)->GetDevice(0)->GetObject<LoraNetDevice>();
            Ptr<EndDeviceLorawanMac> mac = device->GetMac()->GetObject<EndDeviceLorawanMac>();
            mac->SetAttribute("ADR", BooleanValue(true));
        }
    }
    ApplyOmnetBootstrapDefaults(endDevices, initSF, initTP);
    // TP initialization needs to be handled in SetupStandardLoRa function
    // or through LoRaPhyHelper configuration before device creation
    if (initTP) {
        std::cout << "⚡ TP initialization to " << targetTP << " dBm enabled" << std::endl;
    }
    
    // Setup network server with ADR configuration
    SetupStandardNetworkServer(gateways, endDevices, enableADR);
    
    // Initialize device parameters after network setup
    InitializeDeviceParameters(endDevices);
    
    // Setup timing and traces
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMapping);
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);
    
    // Connect parameter change traces
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/DataRate",
        MakeCallback(&OnDataRateChange));
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/TxPower",
        MakeCallback(&OnTxPowerChange));
    // Run simulation
    Time totalSimulationTime = Seconds(simulationTime * 60);
    Simulator::Stop(totalSimulationTime);

    std::cout << "\n=== Scenario 1: Baseline Reference Case ===" << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "Configuration:" << std::endl;
    std::cout << "  • SF Initialization: " << (initSF ? ("SF" + std::to_string(targetSF)) : "Default") << std::endl;
    std::cout << "  • TP Initialization: " << (initTP ? (std::to_string(targetTP) + " dBm") : "Default") << std::endl;
    std::cout << "  • ADR: " << (enableADR ? "Enabled" : "Disabled") << std::endl;
    std::cout << "Packet interval: " << packetInterval << "s" << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes" << std::endl;
    std::cout << "Starting simulation..." << std::endl;

    Simulator::Run();

    // Capture final states
    CaptureEndStates(endDevices);

    std::cout << "\n=== Simulation Complete ===" << std::endl;
    std::cout << "Total packets sent: " << g_totalSent << std::endl;
    std::cout << "Total packets received: " << g_totalReceived << std::endl;
    
    if (g_totalSent > 0) {
        double pdr = lora::PdrPercent(g_totalReceived, g_totalSent);
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2) << pdr << "%" << std::endl;
    }
  
    // Show ADR activity if enabled
    if (enableADR) {
        uint32_t totalAdrChanges = 0;
        for (const auto& pair : g_adrChangesPerNode) {
            totalAdrChanges += pair.second;
        }
        std::cout << "Total ADR changes: " << totalAdrChanges << std::endl;
        
        if (totalAdrChanges == 0) {
            std::cout << "WARNING: No ADR changes detected!" << std::endl;
            std::cout << "Check NetworkServerHelper.EnableAdr(true) is called" << std::endl;
            std::cout << "Verify sufficient packets per device (need >20 for ADR)" << std::endl;
        } else {
            std::cout << "ADR working - showing first 5 nodes with changes:" << std::endl;
            int count = 0;
            for (const auto& pair : g_adrChangesPerNode) {
                if (pair.second > 0 && count++ < 5) {
                    std::cout << "  Node " << pair.first << ": " << pair.second << " changes" << std::endl;
                }
            }
        }
    }

    // Validate and export results
    ValidateResults(endDevices);

    std::string outputFile = outputPrefix + "_results.csv";
    ExportResults(outputFile, endDevices, simulationTime);

    Simulator::Destroy();
    return 0;
}