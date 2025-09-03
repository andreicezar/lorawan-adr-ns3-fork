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
#include "ns3/lora-net-device.h"
#include "ns3/lora-phy.h"
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

#include "common/position_loader.h"
// ==============================================================================
// GLOBAL VARIABLES
// ==============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Collision and interference tracking
uint32_t g_totalCollisions = 0;
uint32_t g_totalInterference = 0;
std::map<uint32_t, uint32_t> g_collisionsPerNode;
std::map<uint32_t, uint32_t> g_interferencePerNode;
std::map<uint8_t, uint32_t> g_interferencePerSF; // Track which SFs cause interference
// Scenario-level counters
static uint64_t g_rxOk = 0;
static uint64_t g_lostInterf = 0;
static uint64_t g_lostUnderSens = 0;

// Optional: per-node (or per-GW) tallies
static std::map<uint32_t,uint64_t> g_rxOkPerGw;
static std::map<uint32_t,uint64_t> g_interfPerGw;
static std::map<uint32_t,uint64_t> g_underPerGw;

// Scenario-specific variables
std::map<uint32_t, double> g_totalAirTimePerNode;
std::map<uint32_t, double> g_rssiPerNode;
std::map<uint32_t, double> g_snrPerNode;
double g_totalAirTime = 0.0;

// Store current SF for airtime calculations
uint8_t g_currentSpreadingFactor = 10;
// -- detailed GW-aware callbacks --
// Per-gateway handlers — signature must match after binding: (gwId, Packet)
// Correct per-GW handlers: (packet, freqHz, gwId)
static void RxOkPerGw(uint32_t gwId, Ptr<const Packet> p, uint32_t freqHz)
{
  (void)freqHz; // silence -Werror=unused-parameter
  g_rxOk++;
  g_rxOkPerGw[gwId]++;
}

static void RxInterfPerGw(uint32_t gwId, Ptr<const Packet> p, uint32_t freqHz)
{
  (void)freqHz;
  g_lostInterf++;
  g_interfPerGw[gwId]++;

  // attribute loss to the sending node
  LorawanMacHeader mh;
  LoraFrameHeader fh;
  Ptr<Packet> c = p->Copy();
  c->RemoveHeader(mh);
  if (mh.GetMType() == LorawanMacHeader::UNCONFIRMED_DATA_UP ||
      mh.GetMType() == LorawanMacHeader::CONFIRMED_DATA_UP)
  {
    c->RemoveHeader(fh);
    auto it = g_deviceToNodeMap.find(fh.GetAddress());
    if (it != g_deviceToNodeMap.end())
    {
      const uint32_t nodeId = it->second;
      g_collisionsPerNode[nodeId]++;       // collisions == interference-driven losses
      g_interferencePerNode[nodeId]++;     // keep both columns if you want both
    }
  }
}

static void RxUnderPerGw(uint32_t gwId, Ptr<const Packet> p, uint32_t freqHz)
{
  (void)freqHz;
  g_lostUnderSens++;
  g_underPerGw[gwId]++;
}

static void ConnectGatewayPhyTraces(const NodeContainer& gateways) {
  for (auto it = gateways.Begin(); it != gateways.End(); ++it) {
    Ptr<Node> gw = *it;
    const uint32_t gwId = gw->GetId();

    for (uint32_t i = 0; i < gw->GetNDevices(); ++i) {
      auto dev = DynamicCast<lorawan::LoraNetDevice>(gw->GetDevice(i));
      if (!dev) continue;
      auto phy = dev->GetPhy();
      if (!phy) continue;

    phy->TraceConnectWithoutContext("ReceivedPacket",
        MakeBoundCallback(&RxOkPerGw, gwId));
    phy->TraceConnectWithoutContext("LostPacketBecauseInterference",
        MakeBoundCallback(&RxInterfPerGw, gwId));
    phy->TraceConnectWithoutContext("LostPacketBecauseUnderSensitivity",
        MakeBoundCallback(&RxUnderPerGw, gwId));


    }
  }
}

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

void OnPacketDestroyed(Ptr<const Packet> packet, uint32_t nodeId, uint8_t interferingSF) {
    if (interferingSF > 0) {
        // Packet was destroyed by interference
        g_totalInterference++;
        g_interferencePerNode[nodeId]++;
        g_interferencePerSF[interferingSF]++;
        
        NS_LOG_DEBUG("Node " << nodeId << " packet destroyed by SF" << (int)interferingSF << " interference");
    } else {
        // Packet was lost due to collision (generic)
        g_totalCollisions++;
        g_collisionsPerNode[nodeId]++;
        
        NS_LOG_DEBUG("Node " << nodeId << " packet lost due to collision");
    }
}

void TrackInterferenceEvents() {
    // This requires access to the LoraInterferenceHelper
    // We'll need to modify the existing callback structure
    
    // Alternative: Track via packet loss analysis
    // Compare sent vs received to infer collisions
}

// Modified packet sent callback to include collision tracking
void OnPacketSentWithCollisionTracking(Ptr<const Packet> packet) {
    uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
    
    // Calculate airtime
    double airTime = lora::CalculateAirTime(g_currentSpreadingFactor);
    g_totalAirTimePerNode[nodeId] += airTime;
    g_totalAirTime += airTime;
    
    // Initialize collision counters for new nodes
    if (g_collisionsPerNode.find(nodeId) == g_collisionsPerNode.end()) {
        g_collisionsPerNode[nodeId] = 0;
        g_interferencePerNode[nodeId] = 0;
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

    // --- OVERALL ---
    const double theoreticalAirTimeMs = lora::CalculateAirTime(spreadingFactor); // ms/packet
    const uint32_t packetsDropped = (g_totalSent >= g_totalReceived) ? (g_totalSent - g_totalReceived) : 0u;

    file << "OVERALL_STATS\n";
    file << "SpreadingFactor," << static_cast<int>(spreadingFactor) << "\n";
    file << "TotalSent," << g_totalSent << "\n";
    file << "TotalReceived," << g_totalReceived << "\n";
    file << "PDR_Percent," << std::fixed << std::setprecision(2)
         << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";
    file << "PacketsDropped_SentMinusReceived," << packetsDropped << "\n";
    file << "DropRate_Percent," << std::fixed << std::setprecision(2)
         << lora::DropRatePercent(packetsDropped, g_totalSent) << "\n";

    // Collisions & under-sensitivity from PHY trace counters
    const double denom = (g_totalSent > 0) ? double(g_totalSent) : 1.0;
    file << "TotalCollisions," << g_lostInterf << "\n";          // interference-driven loss
    file << "TotalUnderSensitivity," << g_lostUnderSens << "\n";
    file << "CollisionRate_Percent," << std::fixed << std::setprecision(2)
        << (100.0 * double(g_lostInterf) / denom) << "\n";
    file << "UnderSensitivityRate_Percent," << std::fixed << std::setprecision(2)
        << (100.0 * double(g_lostUnderSens) / denom) << "\n";

    // Interference breakdown by *destroyer* SF (if collected)
    for (const auto& kv : g_interferencePerSF) {
        file << "InterferenceBySF" << static_cast<int>(kv.first) << "," << kv.second << "\n";
    }

    // Airtime & utilization
    file << "TotalAirTime_ms," << std::fixed << std::setprecision(2) << g_totalAirTime << "\n";
    file << "TheoreticalAirTimePerPacket_ms," << std::fixed << std::setprecision(2)
         << theoreticalAirTimeMs << "\n";

    const double simSeconds = static_cast<double>(simulationTime) * 60.0;
    const double offered = lora::OfferedLoadErlangs(g_totalAirTime / 1000.0, simSeconds, /*channels=*/1);
    file << "ChannelUtilization_Percent," << std::fixed << std::setprecision(4)
         << lora::ChannelUtilizationPercent(offered) << "\n";

    // Airtime scale vs SF7
    const double sf7AirTimeMs = lora::CalculateAirTime(7);
    const double airtimeScale = (sf7AirTimeMs > 0.0) ? (theoreticalAirTimeMs / sf7AirTimeMs) : 0.0;
    file << "AirtimeScale_vs_SF7," << std::fixed << std::setprecision(2) << airtimeScale << "\n\n";

    // --- PER NODE ---
    file << "PER_NODE_STATS\n";
    file << "NodeID,Sent,Received,PDR_Percent,AirTime_ms,Collisions,Interference,AvgRSSI_dBm,AvgSNR_dB,Distance_m\n";

    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        const uint32_t nodeId = endDevices.Get(i)->GetId();
        const uint32_t sent = g_sentPacketsPerNode[nodeId];
        const uint32_t received = g_receivedPacketsPerNode[nodeId];
        const double airTime = g_totalAirTimePerNode[nodeId];
        const uint32_t collisions = g_collisionsPerNode[nodeId];
        const uint32_t interference = g_interferencePerNode[nodeId];
        const double avgRssi = g_rssiPerNode[nodeId];
        const double avgSnr = g_snrPerNode[nodeId];

        // Distance from origin (0,0) in XY plane
        Ptr<Node> node = NodeList::GetNode(nodeId);
        Vector pos = node->GetObject<MobilityModel>()->GetPosition();
        const double distance = lora::Distance2D(pos.x, pos.y, 0.0, 0.0);

        file << nodeId << "," << sent << "," << received << ","
             << std::fixed << std::setprecision(2) << lora::PdrPercent(received, sent) << ","
             << airTime << "," << collisions << "," << interference << ","
             << avgRssi << "," << avgSnr << ","
             << std::setprecision(0) << distance << "\n";
    }

    // --- GATEWAY PHY-LEVEL LOSS ACCOUNTING (from trace sources) ---
    file << "INTERFERENCE_STATS\n";
    file << "RxOk_Total," << g_rxOk << "\n";
    file << "Lost_Interference_Total," << g_lostInterf << "\n";
    file << "Lost_UnderSensitivity_Total," << g_lostUnderSens << "\n";
    file << "PacketsLost_SentMinusReceived," << packetsDropped << "\n\n";

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
    std::string positionFile = "scenario_positions.csv";
    bool useFilePositions = true;

    CommandLine cmd(__FILE__);
    cmd.AddValue("spreadingFactor", "Spreading Factor to test (7-12)", spreadingFactor);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("nDevices", "Number of devices", nDevices);
    cmd.AddValue("packetInterval", "Packet interval in seconds", packetInterval);
    cmd.AddValue("positionFile", "CSV file with node positions", positionFile);
    cmd.AddValue("useFilePositions", "Use positions from file (vs random)", useFilePositions);
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
    if (useFilePositions) {
        SetupMobilityFromFile(endDevices, gateways, sideLengthMeters,
                            "scenario_03_sf_impact", positionFile);
    } else {
        RngSeedManager::SetSeed(12347);
        RngSeedManager::SetRun(1);
        SetupStandardMobility(endDevices, gateways, sideLengthMeters);
    }
    
    // Convert SF to DR for EU868
    uint8_t dataRate = lora::DrFromSfEu868(spreadingFactor);
    SetupStandardLoRa(endDevices, gateways, channel, dataRate);

    SetupStandardNetworkServer(gateways, endDevices, false); // No ADR
    
    // Setup timing and traces
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMapping);
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);
    ConnectGatewayPhyTraces(gateways);
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