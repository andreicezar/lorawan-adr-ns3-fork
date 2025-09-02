/*
 * Scenario 8: Multi-Gateway Coordination (updated to use common helpers)
 * - Compares 1, 2, 4 gateways
 * - Measures raw hearings, deduplicated receptions, load balance, owner GW
 */

#include "ns3/command-line.h"
#include "ns3/config.h"
#include "ns3/core-module.h"
#include "ns3/forwarder-helper.h"
#include "ns3/gateway-lora-phy.h"
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

// Common helpers (shared across scenarios)
#include "common/lora_utils.h"
#include "common/scenario_utils.h"

#include <fstream>
#include <iomanip>
#include <cmath>
#include <unordered_set>
#include <map>
#include <string>

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("Scenario08MultiGateway");

#include "common/position_loader.h"
// ============================================================================
// GLOBALS
// ============================================================================
static uint32_t g_nGateways = 1;
static int g_packetInterval = 300;

std::map<uint32_t, uint32_t> g_sentPacketsPerNode;          // node -> tx
std::map<uint32_t, uint32_t> g_rawHearingsPerNode;          // node -> raw rx (all GWs)
std::map<uint32_t, uint32_t> g_uniqueRecvPerNode;           // node -> unique rx (dedup)
std::map<uint32_t, std::map<uint32_t, uint32_t>> g_rawPerGwPerNode;    // node -> gwIdx -> raw
std::map<uint32_t, std::map<uint32_t, uint32_t>> g_uniquePerGwPerNode; // node -> gwIdx -> unique
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;  // nodeId -> RX (unique) count

std::map<uint32_t, Vector> g_nodePos;                       // nodeId -> pos
std::map<uint32_t, Vector> g_gwPos;                         // gateway nodeId -> pos
std::map<uint32_t, uint32_t> g_gwNodeIdToIdx;               // gateway nodeId -> 0..N-1
std::map<uint32_t, uint32_t> g_totalRawPerGw;               // gwIdx -> raw hearings

std::unordered_set<uint64_t> g_seenKeys;                    // (DevAddr<<32) | FCnt

uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;
uint32_t g_totalRaw = 0;
uint32_t g_totalUnique = 0;
uint32_t g_totalDuplicate = 0;

// ============================================================================
// CALLBACKS
// ============================================================================
static void OnPacketSent(Ptr<const Packet>)
{
    const uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
}

static void OnGatewayReceiveWithContext(std::string context, Ptr<const Packet> pkt)
{
    if (!pkt || pkt->GetSize() == 0) return;

    LorawanMacHeader mh; LoraFrameHeader fh;
    Ptr<Packet> copy = pkt->Copy();
    if (copy->RemoveHeader(mh) == 0 || !mh.IsUplink()) return;
    if (copy->RemoveHeader(fh) == 0) return;

    const LoraDeviceAddress dev = fh.GetAddress();
    const uint32_t fcnt = fh.GetFCnt();
    const uint64_t key = lora::MakePacketKey(dev.Get(), fcnt);

    const bool firstTime = g_seenKeys.insert(key).second;
    if (firstTime) g_totalUnique++; else g_totalDuplicate++;

    const uint32_t gwNodeId = lora::ExtractGatewayNodeIdFromContext(context);
    auto itIdx = g_gwNodeIdToIdx.find(gwNodeId);
    if (itIdx == g_gwNodeIdToIdx.end()) return;
    const uint32_t gwIdx = itIdx->second;

    auto itNode = g_deviceToNodeMap.find(dev);
    if (itNode == g_deviceToNodeMap.end()) return;
    const uint32_t nodeId = itNode->second;

    g_totalRaw++;
    g_rawHearingsPerNode[nodeId]++;
    g_rawPerGwPerNode[nodeId][gwIdx]++;
    g_totalRawPerGw[gwIdx]++;

    if (firstTime) {
        g_uniqueRecvPerNode[nodeId]++;
        g_uniquePerGwPerNode[nodeId][gwIdx]++;
    }
}

static void BuildMappingScenario8(NodeContainer endDevices)
{
    // Use standard mapper for DevAddr->nodeId and zeroed counters
    BuildStandardDeviceMapping(endDevices);

    // Also store node positions
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        const uint32_t nodeId = endDevices.Get(i)->GetId();
        if (auto m = endDevices.Get(i)->GetObject<MobilityModel>()) {
            g_nodePos[nodeId] = m->GetPosition();
        }
        g_rawHearingsPerNode[nodeId] = 0;
        g_uniqueRecvPerNode[nodeId] = 0;
    }
}

// ============================================================================
// EXPORT
// ============================================================================
static void ExportScenario8(const std::string& filename,
                            NodeContainer endDevices,
                            NodeContainer gateways,
                            int simulationTimeMin)
{
    std::ofstream f(filename);
    WriteStandardHeader(f, "Scenario 8: Multi-Gateway Coordination",
                        endDevices.GetN(), gateways.GetN(), simulationTimeMin,
                        std::to_string(gateways.GetN()) + " gateways, dedup + load balance");

    const double uniquePdr = lora::PdrPercent(g_totalUnique, g_totalSent);
    const double rawHearingsRate = lora::RatePercent(g_totalRaw, g_totalSent);
    const double dedupRate = lora::DeduplicationRatePercent(
        g_totalDuplicate, g_totalRaw);
    const double avgHearingsPerUplink = (g_totalSent > 0)
        ? static_cast<double>(g_totalRaw) / g_totalSent : 0.0;

    // load variance
    double avgLoad = (gateways.GetN() > 0) ? static_cast<double>(g_totalRaw) / gateways.GetN() : 0.0;
    double loadVar = 0.0;
    for (uint32_t i = 0; i < gateways.GetN(); ++i) {
        double load = g_totalRawPerGw[i];
        loadVar += (load - avgLoad) * (load - avgLoad);
    }
    loadVar = (gateways.GetN() > 0) ? loadVar / gateways.GetN() : 0.0;

    f << "OVERALL_STATS\n";
    f << "NumberOfGateways," << gateways.GetN() << "\n";
    f << "TotalSent," << g_totalSent << "\n";
    f << "TotalRawHearings," << g_totalRaw << "\n";
    f << "UniquePackets," << g_totalUnique << "\n";
    f << "DuplicatePackets," << g_totalDuplicate << "\n";
    f << "UniquePDR_Percent," << std::fixed << std::setprecision(2) << uniquePdr << "\n";
    f << "RawHearingsRate_Percent," << std::fixed << std::setprecision(2) << rawHearingsRate << "\n";
    f << "DeduplicationRate_Percent," << std::fixed << std::setprecision(2) << dedupRate << "\n";
    f << "AvgHearingsPerUplink," << std::fixed << std::setprecision(2) << avgHearingsPerUplink << "\n";
    f << "GatewayLoadVariance," << std::fixed << std::setprecision(2) << loadVar << "\n\n";

    f << "PER_GATEWAY_STATS\n";
    f << "GatewayID,RawHearings,LoadPercentage,Position_X,Position_Y\n";
    for (uint32_t i = 0; i < gateways.GetN(); ++i) {
        const uint32_t gwNodeId = gateways.Get(i)->GetId();
        const uint32_t idx = g_gwNodeIdToIdx[gwNodeId];
        const uint32_t hearings = g_totalRawPerGw[idx];
        const double loadPct = (g_totalRaw > 0) ? (100.0 * hearings / g_totalRaw) : 0.0;
        Vector pos = g_gwPos[gwNodeId];

        f << gwNodeId << "," << hearings << ","
          << std::fixed << std::setprecision(2) << loadPct << ","
          << std::setprecision(0) << pos.x << "," << pos.y << "\n";
    }
    f << "\n";

    f << "PER_NODE_STATS\n";
    f << "NodeID,Sent,RawHearings,UniqueReceived,UniquePDR_Percent,OwnerGatewayIdx,GatewayDistributionUnique\n";
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        const uint32_t nodeId = endDevices.Get(i)->GetId();
        const uint32_t tx = g_sentPacketsPerNode[nodeId];
        const uint32_t raw = g_rawHearingsPerNode[nodeId];
        const uint32_t uniq = g_uniqueRecvPerNode[nodeId];

        // owner by max unique
        uint32_t owner = 0, bestCnt = 0;
        std::string dist;
        for (uint32_t gw = 0; gw < gateways.GetN(); ++gw) {
            if (gw > 0) dist += ";";
            const uint32_t cnt = g_uniquePerGwPerNode[nodeId][gw];
            dist += std::to_string(cnt);
            if (cnt > bestCnt) { bestCnt = cnt; owner = gw; }
        }

        f << nodeId << ","
          << tx << ","
          << raw << ","
          << uniq << ","
          << std::fixed << std::setprecision(2) << lora::PdrPercent(uniq, tx) << ","
          << owner << ","
          << dist << "\n";
    }
    f.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}


// ==============================================================================
// FIXED SETUP HELPERS
// ==============================================================================
static void BuildGatewayMapping(NodeContainer& gateways)
{
    // Build nodeId->idx map and position map from already-positioned gateways
    for (uint32_t i = 0; i < gateways.GetN(); ++i) {
        const uint32_t gwNodeId = gateways.Get(i)->GetId();
        g_gwNodeIdToIdx[gwNodeId] = i;

        Ptr<MobilityModel> m = gateways.Get(i)->GetObject<MobilityModel>();
        if (m) {
            g_gwPos[gwNodeId] = m->GetPosition();
            std::cout << "Gateway " << gwNodeId << " (idx=" << i 
                      << ") at position: " << m->GetPosition() << std::endl;
        }

        g_totalRawPerGw[i] = 0;
    }
    std::cout << "✅ Gateway mapping built for " << gateways.GetN() << " gateways" << std::endl;
}


static void PlaceGateways(NodeContainer& gateways, uint32_t n, double spacing)
{
    MobilityHelper mob;
    Ptr<ListPositionAllocator> alloc = CreateObject<ListPositionAllocator>();

    if (n == 1) {
        alloc->Add(Vector(0,0,15));
    } else if (n == 2) {
        alloc->Add(Vector(-spacing/2, 0, 15));
        alloc->Add(Vector( spacing/2, 0, 15));
    } else if (n == 4) {
        alloc->Add(Vector(-spacing/2, -spacing/2, 15));
        alloc->Add(Vector( spacing/2, -spacing/2, 15));
        alloc->Add(Vector(-spacing/2,  spacing/2, 15));
        alloc->Add(Vector( spacing/2,  spacing/2, 15));
    }

    mob.SetPositionAllocator(alloc);
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(gateways);

    // CRITICAL FIX: Build the mapping after positioning
    BuildGatewayMapping(gateways);
}

// ============================================================================
// MAIN
// ============================================================================
int main(int argc, char* argv[])
{
    // Defaults consistent with the previous Scenario 8 draft
    int nDevices = 200;
    uint32_t nGateways = 1;       // 1, 2, 4
    int simulationTime = 20;      // minutes
    g_packetInterval = 300;       // seconds
    double gatewaySpacing = 2000; // meters between GWs
    double areaSize = 3000;       // m (square side)
    std::string outputPrefix = "scenario08_multi_gateway";
    std::string positionFile = "scenario_positions.csv";
    bool useFilePositions = true;
    int initSf = -1;        // when 7..12 → force SF, else ignore
    int initTp = -1000;     // when 2..14 → force TP dBm, else ignore
    bool enableADR = false; // off by default

    CommandLine cmd(__FILE__);
    cmd.AddValue("nGateways", "Number of gateways (1, 2, 4)", nGateways);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("gatewaySpacing", "Distance between gateways (m)", gatewaySpacing);
    cmd.AddValue("nDevices", "Number of devices", nDevices);
    cmd.AddValue("positionFile", "CSV file with node positions", positionFile);
    cmd.AddValue("useFilePositions", "Use positions from file (vs random)", useFilePositions);
    cmd.AddValue("initSf", "Initial spreading factor (7..12, EU868). Omit to keep default.", initSf);
    cmd.AddValue("initTp", "Initial TX power in dBm (2..14). Omit to keep default.", initTp);
    cmd.AddValue("enableADR", "Enable ADR on end devices and server", enableADR);
    cmd.Parse(argc, argv);

    if (nGateways != 1 && nGateways != 2 && nGateways != 4) {
        std::cerr << "Error: nGateways must be 1, 2, or 4\n";
        return 1;
    }
    g_nGateways = nGateways;

    LogComponentEnable("Scenario08MultiGateway", LOG_LEVEL_INFO);
    Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(enableADR)); 

    // --- Channel (LogDistance + small random loss), same as original draft ---
    Ptr<LogDistancePropagationLossModel> log = CreateObject<LogDistancePropagationLossModel>();
    log->SetPathLossExponent(3.76);
    log->SetReference(1, 7.7);

    Ptr<UniformRandomVariable> rv = CreateObject<UniformRandomVariable>();
    rv->SetAttribute("Min", DoubleValue(0.0));
    rv->SetAttribute("Max", DoubleValue(5.0));
    Ptr<RandomPropagationLossModel> rnd = CreateObject<RandomPropagationLossModel>();
    rnd->SetAttribute("Variable", PointerValue(rv));
    log->SetNext(rnd);

    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(log, delay);

    // --- Nodes & mobility ---
    NodeContainer gateways, endDevices;
    gateways.Create(nGateways);
    endDevices.Create(nDevices);

    std::string scenarioName = std::string("scenario_08_multigw_") + std::to_string(nGateways) + "gw";
    if (useFilePositions) {
        // Load positions from file
        SetupMobilityFromFile(endDevices, gateways, areaSize, scenarioName, positionFile);
        // CRITICAL FIX: Build gateway mapping even when using file positions
        BuildGatewayMapping(gateways);
    } else {
        // End devices uniformly in a square area (original behavior)
        MobilityHelper mobEd;
        mobEd.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                                   "X", PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                         "Min", DoubleValue(-areaSize/2), "Max", DoubleValue(areaSize/2))),
                                   "Y", PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                         "Min", DoubleValue(-areaSize/2), "Max", DoubleValue(areaSize/2))));
        mobEd.SetMobilityModel("ns3::ConstantPositionMobilityModel");
        mobEd.Install(endDevices);
        
        // Place gateways (this now calls BuildGatewayMapping internally)
        PlaceGateways(gateways, nGateways, gatewaySpacing);
    }

    // Add verification after mobility setup
    std::cout << "🔍 Verifying gateway setup:" << std::endl;
    for (uint32_t i = 0; i < gateways.GetN(); ++i) {
        const uint32_t gwNodeId = gateways.Get(i)->GetId();
        Ptr<MobilityModel> m = gateways.Get(i)->GetObject<MobilityModel>();
        if (m) {
            Vector pos = m->GetPosition();
            std::cout << "  Gateway " << gwNodeId << " at (" << pos.x << ", " << pos.y << ", " << pos.z << ")" << std::endl;
        }
    }

    // --- LoRa stack & server via common helpers ---
    // Map SF→DR if requested, otherwise pass -1 (same contract as Scenario 1).
    int dr = -1;
    if (initSf >= 7 && initSf <= 12) {
        dr = 12 - initSf; // EU868: DR = 12 - SF (same mapping S1 uses)
    }
    SetupStandardLoRa(endDevices, gateways, channel, dr);
    SetupStandardNetworkServer(gateways, endDevices, /*enableAdr=*/enableADR);

    // Apply per-device TX power at the MAC level if requested (like Scenario 1)
    if (initTp >= 2 && initTp <= 14) {
        for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
            Ptr<LoraNetDevice> nd = endDevices.Get(i)->GetDevice(0)->GetObject<LoraNetDevice>();
            if (!nd) continue;
            Ptr<EndDeviceLorawanMac> mac = nd->GetMac()->GetObject<EndDeviceLorawanMac>();
            if (!mac) continue;
            mac->SetTransmissionPowerDbm(static_cast<double>(initTp));
        }
        std::cout << "⚡ Applied per-device TX power: " << initTp << " dBm" << std::endl;
    }
    // --- Timing & mapping ---
    SetupStandardTiming(endDevices, simulationTime, g_packetInterval, &BuildMappingScenario8);

    // --- Traces ---
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/SentNewPacket",
        MakeCallback(&OnPacketSent));

    // Context-aware GW reception to identify gateway
    Config::Connect(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::GatewayLorawanMac/ReceivedPacket",
        MakeCallback(&OnGatewayReceiveWithContext));

    std::cout << "=== Scenario 8: Multi-Gateway Coordination ===\n";
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << "\n";
    std::cout << "Spacing: " << gatewaySpacing << " m | Area: " << areaSize << " m\n";
    std::cout << "Interval: " << g_packetInterval << " s | Sim: " << simulationTime << " min\n";
    std::cout << "Starting simulation...\n";

    Simulator::Stop(Seconds(simulationTime * 60));
    Simulator::Run();

    std::cout << "\n=== Simulation Complete ===\n";
    std::cout << "Total sent: " << g_totalSent
              << " | Raw hearings: " << g_totalRaw
              << " | Unique (dedup): " << g_totalUnique
              << " | Duplicates: " << g_totalDuplicate << "\n";
    if (g_totalSent > 0) {
        std::cout << "Unique PDR: " << std::fixed << std::setprecision(2)
                  << lora::PdrPercent(g_totalUnique, g_totalSent) << "%\n";
    }

    // Export
    const std::string out = outputPrefix + "_" + std::to_string(nGateways) + "gw_results.csv";
    ExportScenario8(out, endDevices, gateways, simulationTime);

    Simulator::Destroy();
    return 0;
}
