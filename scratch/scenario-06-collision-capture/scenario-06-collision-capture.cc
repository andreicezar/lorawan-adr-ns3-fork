/*
 * Scenario 6: Collision & Capture Effect Testing
 * Tests collision modeling and LoRa capture effect with controlled setup
 * Strategic device placement to create near-far scenarios
 * 
 * Purpose: Validate collision detection and capture effect implementation
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

NS_LOG_COMPONENT_DEFINE("Scenario06CollisionCapture");

#include "common/position_loader.h"
// ==============================================================================
// GLOBAL VARIABLES
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Scenario-specific variables for capture effect analysis
std::map<uint32_t, uint32_t> g_collisionsPerNode; // Derived: sent - received
std::map<uint32_t, Vector> g_nodePositions;
std::map<uint32_t, double> g_nodeDistances;
std::map<uint32_t, bool> g_isNearNode; // True for near cohort, false for far cohort
uint32_t g_nearCohortSent = 0;
uint32_t g_nearCohortReceived = 0;
uint32_t g_farCohortSent = 0;
uint32_t g_farCohortReceived = 0;

// Store current SF for analysis
uint8_t g_currentSpreadingFactor = 10;

// ==============================================================================
// CALLBACK FUNCTIONS
// ==============================================================================

void OnPacketSent(Ptr<const Packet> packet) {
    uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
    
    // Track cohort statistics
    if (g_isNearNode[nodeId]) {
        g_nearCohortSent++;
    } else {
        g_farCohortSent++;
    }
    
    double currentTime = Simulator::Now().GetSeconds();
    NS_LOG_DEBUG("Node " << nodeId << " (" << (g_isNearNode[nodeId] ? "NEAR" : "FAR") 
               << ") sent packet #" << g_sentPacketsPerNode[nodeId] 
               << " at " << std::fixed << std::setprecision(2) << currentTime << "s");
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
            
            // Track cohort statistics for capture analysis
            if (g_isNearNode[nodeId]) {
                g_nearCohortReceived++;
            } else {
                g_farCohortReceived++;
            }
            
            NS_LOG_DEBUG("Gateway received packet from Node " << nodeId 
                       << " (" << (g_isNearNode[nodeId] ? "NEAR" : "FAR") << ") "
                       << "at distance " << std::fixed << std::setprecision(0) 
                       << g_nodeDistances[nodeId] << "m");
        }
    }
}

// ==============================================================================
// CUSTOM MOBILITY SETUP FOR CAPTURE EFFECT TESTING
// ==============================================================================

void SetupCaptureTestMobility(NodeContainer& endDevices, NodeContainer& gateways,
                            const std::string& positionFile, bool useFile) {
    // Gateway at center
    if (useFile) {
        SetupMobilityFromFile(endDevices, gateways, 1000, "scenario_06_collision", positionFile);
        std::cout << "✅ Using positions from file: " << positionFile << std::endl; 
        return;
    }
    
    // Gateway at center (original behavior)
    Ptr<ListPositionAllocator> positionAllocGw = CreateObject<ListPositionAllocator>();
    positionAllocGw->Add(Vector(0.0, 0.0, 15.0));
    MobilityHelper mobilityGw;
    mobilityGw.SetPositionAllocator(positionAllocGw);
    mobilityGw.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobilityGw.Install(gateways);

    // Strategic near/far placement for capture effect testing
    Ptr<ListPositionAllocator> posAllocEd = CreateObject<ListPositionAllocator>();
    
    Ptr<UniformRandomVariable> ang = CreateObject<UniformRandomVariable>();
    ang->SetAttribute("Min", DoubleValue(0.0));
    ang->SetAttribute("Max", DoubleValue(2 * M_PI));
    
    Ptr<UniformRandomVariable> rNear = CreateObject<UniformRandomVariable>();
    rNear->SetAttribute("Min", DoubleValue(50.0));
    rNear->SetAttribute("Max", DoubleValue(150.0));
    
    Ptr<UniformRandomVariable> rFar = CreateObject<UniformRandomVariable>();
    rFar->SetAttribute("Min", DoubleValue(450.0));
    rFar->SetAttribute("Max", DoubleValue(500.0));
    
    uint32_t half = endDevices.GetN() / 2;
    
    // Near ring (high RSSI)
    for (uint32_t i = 0; i < half; ++i) {
        double angle = ang->GetValue();
        double radius = rNear->GetValue();
        posAllocEd->Add(Vector(radius * std::cos(angle), radius * std::sin(angle), 1.5));
    }
    
    // Far ring (low RSSI)
    for (uint32_t i = half; i < endDevices.GetN(); ++i) {
        double angle = ang->GetValue();
        double radius = rFar->GetValue();
        posAllocEd->Add(Vector(radius * std::cos(angle), radius * std::sin(angle), 1.5));
    }
    
    MobilityHelper mobilityEd;
    mobilityEd.SetPositionAllocator(posAllocEd);
    mobilityEd.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobilityEd.Install(endDevices);
    
    std::cout << "✅ Capture test placement: " << half << " devices in near ring (50-150m), " 
              << (endDevices.GetN() - half) << " in far ring (450-500m)" << std::endl;
}

// ==============================================================================
// DEVICE MAPPING
// ==============================================================================

void BuildDeviceMapping(NodeContainer endDevices) {
    // Use standard mapping first
    BuildStandardDeviceMapping(endDevices);
    
    // Add capture effect specific initialization
    Vector gatewayPos(0.0, 0.0, 15.0);
    double nearThreshold = 300.0; // meters - threshold between near/far cohorts
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        
        // Store node position and calculate distance to gateway
        Ptr<MobilityModel> mobility = endDevices.Get(i)->GetObject<MobilityModel>();
        if (mobility) {
            g_nodePositions[nodeId] = mobility->GetPosition();
            Vector nodePos = g_nodePositions[nodeId];
            double distance = lora::Distance2D(nodePos.x, nodePos.y, gatewayPos.x, gatewayPos.y);
            g_nodeDistances[nodeId] = distance;
            
            // Classify as near or far cohort
            g_isNearNode[nodeId] = (distance <= nearThreshold);
        }
        
        // Initialize scenario-specific counters
        g_collisionsPerNode[nodeId] = 0;
    }
    
    std::cout << "✅ Collision capture device mapping built for " << endDevices.GetN() << " devices" << std::endl;
    std::cout << "Near cohort threshold: <= " << nearThreshold << "m" << std::endl;
    std::cout << "Far cohort threshold: > " << nearThreshold << "m" << std::endl;
}

// ==============================================================================
// RESULTS EXPORT
// ==============================================================================

void ExportResults(const std::string& filename, NodeContainer endDevices, 
                  int simulationTime, int packetInterval, uint8_t spreadingFactor)
{
    std::ofstream file(filename);
    WriteStandardHeader(file, "Scenario 6: Collision & Capture Effect Testing",
                       endDevices.GetN(), 1, simulationTime,
                       "SF" + std::to_string(spreadingFactor) + ", near/far cohorts, capture analysis");
    
    uint32_t totalDrops = g_totalSent - g_totalReceived;
    double nearPdr = g_nearCohortSent > 0 ? lora::PdrPercent(g_nearCohortReceived, g_nearCohortSent) : 0.0;
    double farPdr = g_farCohortSent > 0 ? lora::PdrPercent(g_farCohortReceived, g_farCohortSent) : 0.0;
    double captureEffectStrength = nearPdr - farPdr;
    
    file << "OVERALL_STATS\n";
    file << "SpreadingFactor," << (int)spreadingFactor << "\n";
    file << "TotalSent," << g_totalSent << "\n";
    file << "TotalReceived," << g_totalReceived << "\n";
    file << "PDR_Percent," << std::fixed << std::setprecision(2) 
         << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";
    file << "PacketsDropped_SentMinusReceived," << totalDrops << "\n";
    file << "DropRate_Percent," << std::fixed << std::setprecision(2) 
         << lora::DropRatePercent(totalDrops, g_totalSent) << "\n\n";
    
    // Capture effect analysis
    file << "CAPTURE_EFFECT_ANALYSIS\n";
    file << "NearCohortSent," << g_nearCohortSent << "\n";
    file << "NearCohortReceived," << g_nearCohortReceived << "\n";
    file << "NearCohortPDR_Percent," << std::fixed << std::setprecision(2) << nearPdr << "\n";
    file << "FarCohortSent," << g_farCohortSent << "\n";
    file << "FarCohortReceived," << g_farCohortReceived << "\n";
    file << "FarCohortPDR_Percent," << std::fixed << std::setprecision(2) << farPdr << "\n";
    file << "CaptureEffectStrength_PDR_Delta," << std::fixed << std::setprecision(2) 
         << captureEffectStrength << "\n";
    
    // Interpretation
    std::string captureLevel = "NONE";
    if (captureEffectStrength > 20.0) captureLevel = "STRONG";
    else if (captureEffectStrength > 10.0) captureLevel = "MODERATE";
    else if (captureEffectStrength > 5.0) captureLevel = "WEAK";
    file << "CaptureEffectLevel," << captureLevel << "\n\n";
    
    // Per-node stats with capture analysis
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,Collisions,Distance_m,Cohort,Position_X,Position_Y,EstimatedRSSI_dBm\n";
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = g_sentPacketsPerNode[nodeId];
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        uint32_t collisions = sent - received; // MAC-level collision detection
        g_collisionsPerNode[nodeId] = collisions;
        double distance = g_nodeDistances[nodeId];
        std::string cohort = g_isNearNode[nodeId] ? "NEAR" : "FAR";
        Vector nodePos = g_nodePositions[nodeId];
        
        // Calculate estimated RSSI for analysis
        double estimatedRssi = lora::Rssi_dBm_fromDistance(14.0, distance, 7.7, 3.76);
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << "," 
             << collisions << "," << std::setprecision(0) << distance << "," << cohort << ","
             << nodePos.x << "," << nodePos.y << "," 
             << std::setprecision(1) << estimatedRssi << "\n";
    }
    
    file.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}

// ==============================================================================
// SF-SPECIFIC TIMING FOR EQUAL PACKETS
// ==============================================================================

void GetOptimalIntervalForSF(uint8_t spreadingFactor, int& packetInterval, int& simulationTime) {
    // Calculate intervals that respect duty cycle but achieve ~120 packets
    switch(spreadingFactor) {
        case 7:
            packetInterval = 90;   // SF7: Short ToA, can send frequently
            simulationTime = 180;  // 3 hours: (180*60)/90 = 120 packets
            break;
        case 8:
            packetInterval = 95;
            simulationTime = 190;  // (190*60)/95 = 120 packets
            break;
        case 9:
            packetInterval = 100;
            simulationTime = 200;  // (200*60)/100 = 120 packets
            break;
        case 10:
            packetInterval = 150;  // Original works fine
            simulationTime = 300;  // (300*60)/150 = 120 packets
            break;
        case 11:
            packetInterval = 200;  // Longer interval needed
            simulationTime = 400;  // (400*60)/200 = 120 packets
            break;
        case 12:
            packetInterval = 260;  // Much longer interval for SF12
            simulationTime = 520;  // (520*60)/260 = 120 packets
            break;
        default:
            packetInterval = 150;
            simulationTime = 300;
    }
}

// ==============================================================================
// MAIN FUNCTION
// ==============================================================================

int main(int argc, char* argv[])
{
    // NEW CODE - SF-aware parameters:
    int nDevices = 50;        
    int nGateways = 1;
    int simulationTime = 300; // Will be overridden by SF-specific values
    int packetInterval = 150; // Will be overridden by SF-specific values
    double maxRandomLossDb = 3.0;
    uint8_t spreadingFactor = 10;
    
    std::string outputPrefix = "scenario06_collision_capture";
    std::string positionFile = "scenario_positions.csv";
    bool useFilePositions = true;
    // Get SF-specific timing BEFORE command line parsing
    GetOptimalIntervalForSF(spreadingFactor, packetInterval, simulationTime);

    CommandLine cmd(__FILE__);
    cmd.AddValue("spreadingFactor", "Spreading Factor to test (7-12)", spreadingFactor);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("packetInterval", "Packet interval in seconds", packetInterval);
    cmd.AddValue("nDevices", "Number of devices", nDevices);
    cmd.AddValue("positionFile", "CSV file with node positions", positionFile);
    cmd.AddValue("useFilePositions", "Use positions from file (vs random)", useFilePositions);
    cmd.Parse(argc, argv);

    // Recalculate timing if SF was changed via command line
    GetOptimalIntervalForSF(spreadingFactor, packetInterval, simulationTime);

    // Validate SF range
    if (spreadingFactor < 7 || spreadingFactor > 12) {
        std::cerr << "Error: Spreading Factor must be between 7 and 12" << std::endl;
        return 1;
    }

    // Display optimized settings
    std::cout << "📊 SF" << (int)spreadingFactor << " optimized settings:" << std::endl;
    std::cout << "   Packet interval: " << packetInterval << "s" << std::endl;
    std::cout << "   Simulation time: " << simulationTime << " minutes" << std::endl;
    std::cout << "   Expected packets per device: " << (simulationTime * 60 / packetInterval) << std::endl;

    // Store current SF for analysis
    g_currentSpreadingFactor = spreadingFactor;

    // Logging
    LogComponentEnable("Scenario06CollisionCapture", LOG_LEVEL_INFO);
    
    // Create node containers
    NodeContainer endDevices, gateways;
    endDevices.Create(nDevices);
    gateways.Create(nGateways);
    
    // Setup network using standardized functions
    Ptr<LoraChannel> channel = SetupStandardChannel(maxRandomLossDb);
    
    // Use CUSTOM mobility setup for capture effect testing
    SetupCaptureTestMobility(endDevices, gateways, positionFile, useFilePositions);
    
    // Convert SF to DR and setup LoRa
    uint8_t dataRate = lora::DrFromSfEu868(spreadingFactor);
    SetupStandardLoRa(endDevices, gateways, channel, dataRate);
    SetupStandardNetworkServer(gateways, endDevices, false); // No ADR
    
    // Setup timing and traces
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMapping);
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);

    // Run simulation
    Time totalSimulationTime = Seconds(simulationTime * 60);
    Simulator::Stop(totalSimulationTime);

    std::cout << "\n=== Scenario 6: Collision & Capture Effect (SF-Optimized Equal Packets) ===" << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "Spreading Factor: SF" << (int)spreadingFactor << std::endl;
    std::cout << "Packet interval: " << packetInterval << "s (optimized for SF" << (int)spreadingFactor << ")" << std::endl;
    std::cout << "Expected packets per device: " << (simulationTime * 60 / packetInterval) << std::endl;
    std::cout << "Expected total packets: " << (nDevices * simulationTime * 60 / packetInterval) << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes" << std::endl;
    std::cout << "Strategic placement: Near/far rings for controlled capture effect scenarios" << std::endl;
    std::cout << "Starting simulation..." << std::endl;

    Simulator::Run();

    std::cout << "\n=== Simulation Complete ===" << std::endl;
    std::cout << "Total packets sent: " << g_totalSent << std::endl;
    std::cout << "Total packets received: " << g_totalReceived << std::endl;
    
    // Calculate collision statistics
    uint32_t totalCollisions = g_totalSent - g_totalReceived;
    std::cout << "Total collisions (sent-received): " << totalCollisions << std::endl;
    
    // Calculate capture effect strength
    double nearPdr = g_nearCohortSent > 0 ? lora::PdrPercent(g_nearCohortReceived, g_nearCohortSent) : 0.0;
    double farPdr = g_farCohortSent > 0 ? lora::PdrPercent(g_farCohortReceived, g_farCohortSent) : 0.0;
    double captureStrength = nearPdr - farPdr;
    
    std::cout << "Near cohort PDR: " << std::fixed << std::setprecision(2) << nearPdr << "%" << std::endl;
    std::cout << "Far cohort PDR: " << std::fixed << std::setprecision(2) << farPdr << "%" << std::endl;
    std::cout << "Capture effect strength: " << std::fixed << std::setprecision(2) << captureStrength << "%" << std::endl;
    
    if (captureStrength > 10.0) {
        std::cout << "✅ Strong capture effect detected!" << std::endl;
    } else if (captureStrength > 5.0) {
        std::cout << "📶 Moderate capture effect detected" << std::endl;
    } else if (captureStrength > 0.0) {
        std::cout << "📸 Weak capture effect detected" << std::endl;
    } else {
        std::cout << "⌐ No significant capture effect detected" << std::endl;
    }
    
    if (g_totalSent > 0) {
        double pdr = lora::PdrPercent(g_totalReceived, g_totalSent);
        double collisionRate = lora::DropRatePercent(totalCollisions, g_totalSent);
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2) << pdr << "%" << std::endl;
        std::cout << "Collision rate: " << std::fixed << std::setprecision(2) << collisionRate << "%" << std::endl;
    }

    // Validate and export results
    ValidateResults(endDevices);

    std::string outputFile = outputPrefix + "_sf" + std::to_string(spreadingFactor) + "_results.csv";
    ExportResults(outputFile, endDevices, simulationTime, packetInterval, spreadingFactor);

    Simulator::Destroy();
    return 0;
}