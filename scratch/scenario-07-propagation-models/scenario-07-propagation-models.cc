/*
 * Scenario 7: Propagation Model Testing (updated to use common helpers)
 * Compares propagation models and measures RSSI/SNR vs. distance & practical range
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

// Local helpers
#include "common/lora_utils.h"       // PHY/RF math (RSSI/SNR/ToA etc.)
#include "common/scenario_utils.h"   // Standardized setup + CSV/validation

#include <fstream>
#include <iomanip>
#include <cmath>
#include <map>

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("Scenario07PropagationModels");

// ============================================================================
// GLOBALS (standardized across scenarios)
// ============================================================================
std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
uint32_t g_totalSent = 0;
uint32_t g_totalReceived = 0;

// Scenario 7 specific
std::map<uint32_t, double> g_avgRssiPerNode;
std::map<uint32_t, double> g_avgSnrPerNode;
std::map<uint32_t, uint32_t> g_rssiSampleCount;
std::map<uint32_t, Vector> g_nodePositions;
std::map<uint32_t, double> g_nodeDistances;

std::string g_propagationModel = "LogDistance";
static constexpr double kBwHz = 125000.0;
static constexpr double kNoiseFigureDb = 6.0;
static constexpr double kTxPowerDbm = 14.0;
static constexpr double kFreqHz = 868e6; // for Friis

// ============================================================================
// CALLBACKS
// ============================================================================
void OnPacketSent(Ptr<const Packet>)
{
    const uint32_t nodeId = Simulator::GetContext();
    g_sentPacketsPerNode[nodeId]++;
    g_totalSent++;
}

void OnGatewayReceive(Ptr<const Packet> packet)
{
    if (!packet || packet->GetSize() == 0) return;

    LorawanMacHeader mh;
    Ptr<Packet> copy = packet->Copy();
    if (copy->RemoveHeader(mh) == 0 || !mh.IsUplink()) return;

    LoraFrameHeader fh;
    if (copy->RemoveHeader(fh) == 0) return;

    auto it = g_deviceToNodeMap.find(fh.GetAddress());
    if (it == g_deviceToNodeMap.end()) return;

    const uint32_t nodeId = it->second;
    g_receivedPacketsPerNode[nodeId]++;
    g_totalReceived++;

    // Estimate RSSI/SNR based on chosen model & stored distance
    const double d = g_nodeDistances[nodeId];
    double rssiDbm = 0.0;

    if (g_propagationModel == "LogDistance") {
        // ref=7.7 dB @1m, exponent=3.76 (same as standard channel)  — tune via cmd flag if needed
        rssiDbm = lora::Rssi_dBm_fromDistance(kTxPowerDbm, d, 7.7, 3.76);
    } else if (g_propagationModel == "FreeSpace") {
        rssiDbm = lora::Rssi_dBm_FreeSpace(kTxPowerDbm, kFreqHz, d);
    } else {
        // Fallback to log-distance if something odd slips through
        rssiDbm = lora::Rssi_dBm_fromDistance(kTxPowerDbm, d, 7.7, 3.76);
    }

    const double noiseDbm = lora::NoiseFloor_dBm(kBwHz, kNoiseFigureDb);
    const double snrDb = lora::Snr_dB(rssiDbm, noiseDbm);

    // Running averages
    const uint32_t n = g_rssiSampleCount[nodeId];
    if (n == 0) {
        g_avgRssiPerNode[nodeId] = rssiDbm;
        g_avgSnrPerNode[nodeId]  = snrDb;
    } else {
        g_avgRssiPerNode[nodeId] = (g_avgRssiPerNode[nodeId] * n + rssiDbm) / (n + 1);
        g_avgSnrPerNode[nodeId]  = (g_avgSnrPerNode[nodeId]  * n + snrDb ) / (n + 1);
    }
    g_rssiSampleCount[nodeId] = n + 1;
}

// ============================================================================
// DEVICE MAPPING (build standard mapping + record positions/distances)
// ============================================================================
void BuildDeviceMappingForScenario7(NodeContainer endDevices)
{
    // Standard mapping initializes per-node counters and deviceAddress->node map
    BuildStandardDeviceMapping(endDevices);  // common helper :contentReference[oaicite:3]{index=3}

    const Vector gwPos(0.0, 0.0, 15.0);
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        const uint32_t nodeId = endDevices.Get(i)->GetId();
        Ptr<MobilityModel> mob = endDevices.Get(i)->GetObject<MobilityModel>();
        if (!mob) continue;
        const Vector pos = mob->GetPosition();
        g_nodePositions[nodeId] = pos;
        g_nodeDistances[nodeId] = lora::Distance2D(pos.x, pos.y, gwPos.x, gwPos.y);
        // Keep RSSI stats initialized
        g_avgRssiPerNode[nodeId] = 0.0;
        g_avgSnrPerNode[nodeId]  = 0.0;
        g_rssiSampleCount[nodeId] = 0;
    }
}

// ============================================================================
// RESULTS EXPORT (standard header + per-node RF stats)
// ============================================================================
void ExportResults(const std::string& filename,
                   NodeContainer endDevices,
                   int simulationTimeMin,
                   const std::string& propagationModel)
{
    std::ofstream f(filename);
    WriteStandardHeader(f, "Scenario 7: Propagation Model Testing",
                        endDevices.GetN(), 1, simulationTimeMin,
                        "Model: " + propagationModel + ", RSSI/SNR vs distance"); // common header :contentReference[oaicite:4]{index=4}

    // Range stats
    double maxOkDist = 0.0;
    double minFailDist = 1e9;
    double rssiSum = 0.0;
    uint32_t rssiOkCount = 0;

    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        const uint32_t nid = endDevices.Get(i)->GetId();
        const double d = g_nodeDistances[nid];
        const uint32_t rx = g_receivedPacketsPerNode[nid];

        if (rx > 0) {
            maxOkDist = std::max(maxOkDist, d);
            if (g_rssiSampleCount[nid] > 0) {
                rssiSum += g_avgRssiPerNode[nid];
                rssiOkCount++;
            }
        } else {
            minFailDist = std::min(minFailDist, d);
        }
    }

    f << "OVERALL_STATS\n";
    f << "PropagationModel," << propagationModel << "\n";
    f << "TotalSent," << g_totalSent << "\n";
    f << "TotalReceived," << g_totalReceived << "\n";
    f << "PDR_Percent," << std::fixed << std::setprecision(2)
      << lora::PdrPercent(g_totalReceived, g_totalSent) << "\n";           // lora_utils :contentReference[oaicite:5]{index=5}
    f << "MaxSuccessfulDistance_m," << std::fixed << std::setprecision(0) << maxOkDist << "\n";
    f << "MinFailureDistance_m,"     << std::fixed << std::setprecision(0) << minFailDist << "\n";
    f << "OverallAvgRSSI_dBm,"       << std::fixed << std::setprecision(2)
      << (rssiOkCount ? (rssiSum / rssiOkCount) : 0.0) << "\n\n";

    f << "PER_NODE_STATS\n";
    f << "NodeID,Sent,Received,PDR_Percent,Distance_m,AvgRSSI_dBm,AvgSNR_dB,Position_X,Position_Y,RSSISamples\n";
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        const uint32_t nid = endDevices.Get(i)->GetId();
        const uint32_t tx = g_sentPacketsPerNode[nid];
        const uint32_t rx = g_receivedPacketsPerNode[nid];
        const double pdr = lora::PdrPercent(rx, tx);                         // lora_utils :contentReference[oaicite:6]{index=6}
        const double d   = g_nodeDistances[nid];
        const Vector pos = g_nodePositions[nid];
        const double avgRssi = g_avgRssiPerNode[nid];
        const double avgSnr  = g_avgSnrPerNode[nid];
        const uint32_t samples = g_rssiSampleCount[nid];

        f << nid << "," << tx << "," << rx << ","
          << std::fixed << std::setprecision(2) << pdr << ","
          << std::setprecision(0) << d << ","
          << std::setprecision(2) << avgRssi << "," << avgSnr << ","
          << std::setprecision(0) << pos.x << "," << pos.y << ","
          << samples << "\n";
    }
    f.close();
    std::cout << "✅ Results exported to " << filename << std::endl;
}

// ============================================================================
// MAIN
// ============================================================================
int main(int argc, char* argv[])
{
    // Parameters (kept from original scenario)
    int nDevices = 50;
    int nGateways = 1;
    int simulationTime = 15;     // minutes
    int packetInterval = 180;    // seconds
    double maxDistance = 5000;   // meters
    std::string propagationModel = "LogDistance";  // LogDistance | FreeSpace
    double pathLossExponent = 3.76;
    std::string outputPrefix = "scenario07_propagation";

    CommandLine cmd(__FILE__);
    cmd.AddValue("propagationModel", "Propagation model (LogDistance, FreeSpace)", propagationModel);
    cmd.AddValue("pathLossExponent", "Path loss exponent for LogDistance model", pathLossExponent);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("outputPrefix", "Output file prefix", outputPrefix);
    cmd.AddValue("maxDistance", "Maximum test distance in meters", maxDistance);
    cmd.Parse(argc, argv);

    g_propagationModel = propagationModel;

    LogComponentEnable("Scenario07PropagationModels", LOG_LEVEL_INFO);
    Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(false)); // consistent testing

    // --- Channel with selectable loss model ---
    Ptr<PropagationLossModel> lossModel;
    if (propagationModel == "LogDistance") {
        Ptr<LogDistancePropagationLossModel> logModel = CreateObject<LogDistancePropagationLossModel>();
        logModel->SetPathLossExponent(pathLossExponent);
        logModel->SetReference(1, 7.7);
        lossModel = logModel;
        std::cout << "Using LogDistance, n=" << pathLossExponent << " (ref=7.7dB@1m)\n";
    } else if (propagationModel == "FreeSpace") {
        Ptr<FriisPropagationLossModel> friis = CreateObject<FriisPropagationLossModel>();
        friis->SetFrequency(kFreqHz);
        lossModel = friis;
        std::cout << "Using Friis Free-Space @ 868 MHz\n";
    } else {
        std::cerr << "Unsupported propagation model: " << propagationModel << "\n";
        return 1;
    }
    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(lossModel, delay);

    // --- Nodes & mobility (radial placement for distance sweep) ---
    NodeContainer gateways, endDevices;
    gateways.Create(nGateways);
    endDevices.Create(nDevices);

    MobilityHelper mobEd, mobGw;
    mobEd.SetPositionAllocator("ns3::RandomDiscPositionAllocator",
                               "X", DoubleValue(0.0),
                               "Y", DoubleValue(0.0),
                               "Rho", PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                   "Min", DoubleValue(100.0),
                                   "Max", DoubleValue(maxDistance))));
    mobEd.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobEd.Install(endDevices);

    Ptr<ListPositionAllocator> gwPosAlloc = CreateObject<ListPositionAllocator>();
    gwPosAlloc->Add(Vector(0.0, 0.0, 15.0));
    mobGw.SetPositionAllocator(gwPosAlloc);
    mobGw.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobGw.Install(gateways);

    // --- LoRa stack & server via common helpers ---
    const uint8_t dataRate = 2; // DR2 = SF10 (EU868)
    SetupStandardLoRa(endDevices, gateways, channel, dataRate);              // :contentReference[oaicite:7]{index=7}
    SetupStandardNetworkServer(gateways, endDevices, false);                 // :contentReference[oaicite:8]{index=8}

    // --- Timing & traces (standardized) ---
    SetupStandardTiming(endDevices, simulationTime, packetInterval, &BuildDeviceMappingForScenario7); // :contentReference[oaicite:9]{index=9}
    ConnectStandardTraces(&OnPacketSent, &OnGatewayReceive);                 // :contentReference[oaicite:10]{index=10}

    // --- Run ---
    std::cout << "=== Scenario 7: Propagation Model Testing ===\n";
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << "\n";
    std::cout << "Model: " << propagationModel << (propagationModel=="LogDistance" ? (", n=" + std::to_string(pathLossExponent)) : "") << "\n";
    std::cout << "Max distance: " << maxDistance << " m | Packet interval: " << packetInterval << " s\n";
    std::cout << "Expected packets/device: " << (simulationTime * 60 / packetInterval) << "\n";
    std::cout << "Starting simulation...\n";

    Simulator::Stop(Seconds(simulationTime * 60));
    Simulator::Run();

    std::cout << "\n=== Simulation Complete ===\n";
    std::cout << "Total sent: " << g_totalSent << " | Total received: " << g_totalReceived << "\n";
    if (g_totalSent > 0) {
        std::cout << "Overall PDR: " << std::fixed << std::setprecision(2)
                  << lora::PdrPercent(g_totalReceived, g_totalSent) << "%\n"; // lora_utils :contentReference[oaicite:11]{index=11}
    }

    // Validate & export
    ValidateResults(endDevices);                                            // :contentReference[oaicite:12]{index=12}
    const std::string outFile = outputPrefix + "_" + propagationModel + "_results.csv";
    ExportResults(outFile, endDevices, simulationTime, propagationModel);

    Simulator::Destroy();
    return 0;
}
