/*
 * Scenario 2: ADR vs Fixed SF Comparison
 * Tests both Fixed SF12 and ADR enabled scenarios
 * Same topology as baseline, measures DER, PDR, and ToA changes
 * 
 * Purpose: Compare performance when ADR is active vs fixed parameters
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

NS_LOG_COMPONENT_DEFINE("Scenario02AdrComparison");

// ==============================================================================
// GLOBAL VARIABLES (Scenario 2 specific)
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<uint32_t, uint32_t> g_adrChangesPerNode;
std::map<uint32_t, std::vector<uint8_t>> g_sfHistoryPerNode;
std::map<uint32_t, std::vector<double>> g_tpHistoryPerNode;
std::map<uint32_t, std::vector<std::pair<double, uint8_t>>> g_sfTimeSeriesPerNode;
std::map<uint32_t, std::vector<std::pair<double, double>>> g_tpTimeSeriesPerNode;
std::map<uint32_t, double> g_totalAirTimePerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;
uint32_t g_totalAdrCommands = 0;

// ==============================================================================
// CALLBACK FUNCTIONS
// ==============================================================================

void OnPacketSent(Ptr<const Packet> packet) {
    uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
    
    // Calculate airtime with current DR/SF
    Ptr<Node> node = NodeList::GetNode(nodeId);
    Ptr<LoraNetDevice> loraNetDevice = DynamicCast<LoraNetDevice>(node->GetDevice(0));
    if (loraNetDevice) {
        Ptr<EndDeviceLorawanMac> mac = DynamicCast<EndDeviceLorawanMac>(loraNetDevice->GetMac());
        if (mac) {
            uint8_t dr = mac->GetDataRate();
            double airTime = lora::CalculateAirTimeFromDr(dr);
            g_totalAirTimePerNode[nodeId] += airTime;
        }
    }
    
    // DEBUG: Show timing progress every 1000 packets
    if (g_totalSent % 1000 == 0) {
        double currentTime = Simulator::Now().GetSeconds();
        std::cout << "DEBUG: Packet " << g_totalSent << " sent at " << currentTime 
                  << "s (" << (currentTime/60.0) << " min)" << std::endl;
    }
    
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
    g_totalAdrCommands++;
    
    uint8_t newSf = lora::SfFromDrEu868(newDr);
    g_sfHistoryPerNode[nodeId].push_back(newSf);
    
    // Track time series for detailed analysis
    double currentTime = Simulator::Now().GetSeconds();
    g_sfTimeSeriesPerNode[nodeId].push_back({currentTime, newSf});
    
    NS_LOG_INFO("Node " << nodeId << " ADR change - DR: " << (int)oldDr 
               << " -> " << (int)newDr << " (SF: " << (int)newSf << ") at " 
               << std::fixed << std::setprecision(1) << currentTime << "s");
}

void OnTxPowerChange(double oldTp, double newTp) {
    uint32_t nodeId = Simulator::GetContext();
    g_tpHistoryPerNode[nodeId].push_back(newTp);
    
    double currentTime = Simulator::Now().GetSeconds();
    g_tpTimeSeriesPerNode[nodeId].push_back({currentTime, newTp});
    
    NS_LOG_INFO("Node " << nodeId << " TP change: " << oldTp << " -> " << newTp 
               << " dBm at " << std::fixed << std::setprecision(1) << currentTime << "s");
}

// ==============================================================================
// SCENARIO 2 SPECIFIC SETUP FUNCTIONS
// ==============================================================================

void SetupAdrConfiguration(bool adrEnabled) {
    if (adrEnabled) {
        // Enable ADR with proper configuration
        Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(true));
        Config::SetDefault("ns3::AdrComponent::MultipleGwCombiningMethod", StringValue("avg"));
        Config::SetDefault("ns3::AdrComponent::MultiplePacketsCombiningMethod", StringValue("avg"));
        Config::SetDefault("ns3::AdrComponent::HistoryRange", IntegerValue(20));
        Config::SetDefault("ns3::AdrComponent::ChangeTransmissionPower", BooleanValue(true));
        
        std::cout << "✅ ADR: ENABLED with AVERAGE combining, HistoryRange=20" << std::endl;
    } else {
        // COMPLETELY DISABLE ADR
        Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(false));
        Config::SetDefault("ns3::AdrComponent::ChangeTransmissionPower", BooleanValue(false));
        
        std::cout << "✅ ADR: COMPLETELY DISABLED (Fixed SF12)" << std::endl;
    }
}

void ConnectAdrTraces() {
    // Connect ADR-specific traces in addition to standard ones
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/DataRate",
        MakeCallback(&OnDataRateChange));

    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/TxPower",
        MakeCallback(&OnTxPowerChange));
}

void BuildDeviceMapping(NodeContainer endDevices)
{
    // First call the standard mapping function
    BuildStandardDeviceMapping(endDevices);
    
    // Then add scenario-specific initializations
    for (uint32_t i = 0; i < endDevices.GetN(); ++i)
    {
        Ptr<Node> node = endDevices.Get(i);
        uint32_t nodeId = node->GetId();
        
        // Initialize ADR-specific counters
        g_adrChangesPerNode[nodeId] = 0;
        g_totalAirTimePerNode[nodeId] = 0.0;
        
        // Initialize with starting SF and TP
        Ptr<LoraNetDevice> loraNetDevice = DynamicCast<LoraNetDevice>(node->GetDevice(0));
        if (loraNetDevice) {
            Ptr<EndDeviceLorawanMac> mac = DynamicCast<EndDeviceLorawanMac>(loraNetDevice->GetMac());
            if (mac) {
                uint8_t initialDr = mac->GetDataRate();
                uint8_t initialSf = lora::SfFromDrEu868(initialDr);
                double initialTp = mac->GetTransmissionPowerDbm();
                
                g_sfHistoryPerNode[nodeId].push_back(initialSf);
                g_tpHistoryPerNode[nodeId].push_back(initialTp);
                
                // Initialize time series
                double currentTime = Simulator::Now().GetSeconds();
                g_sfTimeSeriesPerNode[nodeId].push_back({currentTime, initialSf});
                g_tpTimeSeriesPerNode[nodeId].push_back({currentTime, initialTp});
            }
        }
    }
    
    std::cout << "✅ ADR device mapping built for " << endDevices.GetN() << " devices" << std::endl;
}

// ==============================================================================
// RESULTS EXPORT
// ==============================================================================

void ExportScenario2Results(const std::string& filename, NodeContainer endDevices, 
                           int simulationTime, bool adrEnabled)
{
    std::ofstream file(filename);
    WriteStandardHeader(file, "Scenario 2: ADR vs Fixed SF Comparison",
                       endDevices.GetN(), 1, simulationTime,
                       adrEnabled ? "ADR enabled, adaptive SF/TP" : "ADR disabled, fixed SF12");
    
    // Calculate total airtime reduction with ADR
    double totalAirTime = 0.0;
    for (const auto& pair : g_totalAirTimePerNode) {
        totalAirTime += pair.second;
    }
    
    file << "OVERALL_STATS\n";
    file << "ADR_Enabled," << (adrEnabled ? "TRUE" : "FALSE") << "\n";
    file << "TotalSent," << g_totalSent << "\n";
    file << "TotalReceived," << g_totalReceived << "\n";
    file << "PDR_Percent," << std::fixed << std::setprecision(2) 
         << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";
    file << "TotalADRCommands," << g_totalAdrCommands << "\n";
    file << "TotalAirTime_ms," << std::fixed << std::setprecision(2) << totalAirTime << "\n";
    
    // Calculate airtime efficiency vs fixed SF12
    double sf12AirTime = lora::CalculateAirTime(12);
    double theoreticalSF12Total = g_totalSent * sf12AirTime;
    double airtimeReduction = 0.0;
    if (theoreticalSF12Total > 0) {
        airtimeReduction = ((theoreticalSF12Total - totalAirTime) / theoreticalSF12Total) * 100.0;
    }
    file << "AirtimeReduction_vs_SF12_Percent," << std::fixed << std::setprecision(2) 
         << (adrEnabled ? airtimeReduction : 0.0) << "\n\n";
    
    // Per-node stats with SF adaptation tracking
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,ADR_Changes,InitialSF,FinalSF,InitialTP_dBm,FinalTP_dBm,AirTime_ms,SFTimeSeries\n";
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = g_sentPacketsPerNode[nodeId];
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        uint32_t adrChanges = g_adrChangesPerNode[nodeId];
        double airTime = g_totalAirTimePerNode[nodeId];
        
        uint8_t initialSf = 12, finalSf = 12;
        double initialTp = 14.0, finalTp = 14.0;
        
        if (!g_sfHistoryPerNode[nodeId].empty()) {
            initialSf = g_sfHistoryPerNode[nodeId].front();
            finalSf = g_sfHistoryPerNode[nodeId].back();
        }
        if (!g_tpHistoryPerNode[nodeId].empty()) {
            initialTp = g_tpHistoryPerNode[nodeId].front();
            finalTp = g_tpHistoryPerNode[nodeId].back();
        }
        
        // Create SF time series string (first 5 changes)
        std::string sfSeries = "";
        const auto& series = g_sfTimeSeriesPerNode[nodeId];
        for (size_t j = 0; j < std::min((size_t)5, series.size()); ++j) {
            if (j > 0) sfSeries += ";";
            sfSeries += std::to_string((int)series[j].first) + ":" + std::to_string(series[j].second);
        }
        if (series.size() > 5) sfSeries += ";...";
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << "," 
             << adrChanges << "," << (int)initialSf << "," << (int)finalSf << ","
             << initialTp << "," << finalTp << "," << airTime << "," << sfSeries << "\n";
    }
    
    file.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}

// ==============================================================================
// MAIN FUNCTION
// ==============================================================================

int main(int argc, char* argv[])
{
    // Scenario 2 Parameters - OPTIMIZED for ADR testing (100 packets per device)
    int nDevices = 100;
    int nGateways = 1;
    int simulationTime = 200; // minutes (for exactly 100 packets per device)
    int packetInterval = 120; // seconds - 100 packets per device
    double sideLengthMeters = 5000; // 5km x 5km area
    double maxRandomLossDb = 5.0;
    bool adrEnabled = false; // Default to fixed SF, can be overridden
    std::string adrType = "ns3::AdrComponent";
    std::string outputPrefix = "scenario02_adr_comparison";
    
    CommandLine cmd(__FILE__);
    cmd.AddValue("adrEnabled", "Enable ADR (true) or use Fixed SF12 (false)", adrEnabled);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("packetInterval", "Packet interval in seconds", packetInterval);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("adrType", "ADR algorithm type", adrType);
    cmd.Parse(argc, argv);

    // DEBUG: Print actual parameter values being used
    std::cout << "=== DEBUG: ACTUAL PARAMETERS BEING USED ===" << std::endl;
    std::cout << "simulationTime = " << simulationTime << " minutes" << std::endl;
    std::cout << "packetInterval = " << packetInterval << " seconds" << std::endl;
    std::cout << "Expected packets per device = " << (simulationTime * 60 / packetInterval) << std::endl;
    std::cout << "Expected total packets = " << (nDevices * simulationTime * 60 / packetInterval) << std::endl;
    std::cout << "adrEnabled = " << (adrEnabled ? "TRUE" : "FALSE") << std::endl;
    std::cout << "=============================================" << std::endl;

    // Logging
    LogComponentEnable("Scenario02AdrComparison", LOG_LEVEL_INFO);
    
    // EXPLICIT ADR configuration based on parameter
    SetupAdrConfiguration(adrEnabled);
    
    // Create nodes
    NodeContainer endDevices, gateways;
    endDevices.Create(nDevices);
    gateways.Create(nGateways);
    
    // Setup channel
    Ptr<LoraChannel> channel = SetupStandardChannel(maxRandomLossDb);
    
    // Setup mobility
    SetupStandardMobility(endDevices, gateways, sideLengthMeters);
    
    // Setup LoRa with initial SF12 (DR0) for both cases
    SetupStandardLoRa(endDevices, gateways, channel, 0); // DR0 = SF12
    
    // Setup network server with ADR configuration
    SetupStandardNetworkServer(gateways, endDevices, adrEnabled);
    
    // Connect traces
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);
    ConnectAdrTraces(); // ADR-specific traces
    
    // DEBUG: Use standard timing instead of staggered
    std::cout << "DEBUG: Using SetupStandardTiming for debugging..." << std::endl;
    
    // Manual setup for better control and debugging
    Simulator::Schedule(Seconds(1.0), &BuildDeviceMapping, endDevices);

    PeriodicSenderHelper appHelper;
    appHelper.SetPeriod(Seconds(packetInterval));
    appHelper.SetPacketSize(51);
    
    // DEBUG: Check what period is actually being set
    std::cout << "DEBUG: PeriodicSenderHelper configured with period: " << packetInterval << "s" << std::endl;
    
    ApplicationContainer appContainer = appHelper.Install(endDevices);
    
    // EXPLICIT timing
    double startTime = 1.1;
    double stopTime = simulationTime * 60 - 0.1;
    
    std::cout << "DEBUG: Applications start time: " << startTime << "s" << std::endl;
    std::cout << "DEBUG: Applications stop time: " << stopTime << "s" << std::endl;
    std::cout << "DEBUG: Application duration: " << (stopTime - startTime) << "s = " 
              << ((stopTime - startTime)/60.0) << " minutes" << std::endl;
    std::cout << "DEBUG: Expected packets per device: " << ((stopTime - startTime) / packetInterval) + 1 << std::endl;
    
    // Check if there are duty cycle restrictions
    std::cout << "DEBUG: Checking for duty cycle restrictions..." << std::endl;
    double sf12AirTime = lora::CalculateAirTime(12); // SF12 airtime in ms
    double dutyCycleUsage = (sf12AirTime / 1000.0) / packetInterval * 100.0; // % duty cycle per transmission
    std::cout << "DEBUG: SF12 airtime: " << sf12AirTime << "ms" << std::endl;
    std::cout << "DEBUG: Duty cycle per transmission: " << dutyCycleUsage << "%" << std::endl;
    
    if (dutyCycleUsage > 1.0) {
        std::cout << "WARNING: Duty cycle usage (" << dutyCycleUsage 
                  << "%) exceeds 1% EU868 limit!" << std::endl;
        double minInterval = sf12AirTime / 10.0; // 1% duty cycle
        std::cout << "WARNING: Minimum interval for 1% duty cycle: " << minInterval << "s" << std::endl;
    }
    
    appContainer.Start(Seconds(startTime));
    appContainer.Stop(Seconds(stopTime));
    
    // Run simulation
    Time totalSimulationTime = Seconds(simulationTime * 60);
    Simulator::Stop(totalSimulationTime);

    // DEBUG: Show timing information
    std::cout << "DEBUG: Simulation will stop at " << (simulationTime * 60) << " seconds" << std::endl;
    std::cout << "DEBUG: Applications should stop at " << (simulationTime * 60 - 0.1) << " seconds" << std::endl;

    // Console output
    std::cout << "\n=== Scenario 2: ADR vs Fixed SF Comparison ===" << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "ADR: " << (adrEnabled ? "ENABLED" : "DISABLED (Fixed SF12)") << std::endl;
    if (adrEnabled) {
        std::cout << "ADR Type: " << adrType << " (AVERAGE combining, 20 packet history)" << std::endl;
    } else {
        std::cout << "Configuration: Fixed SF12, 14 dBm, NO ADAPTATION" << std::endl;
    }
    std::cout << "Packet interval: " << packetInterval << "s (staggered start times)" << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes (100 packets per device)" << std::endl;
    std::cout << "Starting simulation..." << std::endl;

    Simulator::Run();

    double actualSimTime = Simulator::Now().GetSeconds();
    std::cout << "\n=== Simulation Complete ===" << std::endl;
    std::cout << "DEBUG: Simulation actually ran for " << actualSimTime << " seconds (" 
              << (actualSimTime/60.0) << " minutes)" << std::endl;
    std::cout << "DEBUG: Expected to run for " << (simulationTime * 60) << " seconds (" 
              << simulationTime << " minutes)" << std::endl;
    std::cout << "Total packets sent: " << g_totalSent << std::endl;
    std::cout << "Total packets received: " << g_totalReceived << std::endl;
    std::cout << "Total ADR commands: " << g_totalAdrCommands << std::endl;
    
    if (g_totalSent > 0) {
        double pdr = lora::PdrPercent(g_totalReceived, g_totalSent);
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2) << pdr << "%" << std::endl;
    }

    // Validate results
    ValidateResults(endDevices);

    // Export results
    std::string modeStr = adrEnabled ? "adr_enabled" : "fixed_sf12";
    std::string outputFile = outputPrefix + "_" + modeStr + "_results.csv";
    ExportScenario2Results(outputFile, endDevices, simulationTime, adrEnabled);

    Simulator::Destroy();
    return 0;
}