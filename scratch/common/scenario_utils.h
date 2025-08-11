// scratch/common/scenario_utils.h
#ifndef SCENARIO_UTILS_H
#define SCENARIO_UTILS_H

// NS-3 includes
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-helper.h"
#include "ns3/lora-helper.h"
#include "ns3/lorawan-mac-helper.h"
#include "ns3/lora-phy-helper.h"
#include "ns3/lora-device-address-generator.h"
#include "ns3/network-server-helper.h"
#include "ns3/forwarder-helper.h"
#include "ns3/periodic-sender-helper.h"
#include "ns3/point-to-point-module.h"

// Standard includes
#include <fstream>
#include <iomanip>
#include <chrono>
#include <sstream>
#include <iostream>

// Local includes
#include "lora_utils.h"

using namespace ns3;
using namespace lorawan;

// ==============================================================================
// GLOBAL VARIABLES (declare in each scenario .cc file)
// ==============================================================================
extern std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
extern std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
extern std::map<LoraDeviceAddress, uint32_t> g_deviceToNodeMap;
extern uint32_t g_totalSent;
extern uint32_t g_totalReceived;

// ==============================================================================
// UTILITY HELPERS
// ==============================================================================
inline std::string GetCurrentTimestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

inline uint32_t GetRandomSeed() {
    // Return current random seed if available, otherwise 0
    // Implementation depends on how you set seeds in NS-3
    return 0; // Placeholder
}

// ==============================================================================
// STANDARD CSV HEADER WRITER
// ==============================================================================
inline void WriteStandardHeader(std::ofstream& file, const std::string& scenarioName, 
                        int nDevices, int nGateways, int simulationTime,
                        const std::string& specificConfig = "") {
    
    file << "# " << scenarioName << " Results\n";
    file << "# Generated: " << GetCurrentTimestamp() << "\n";
    file << "# Simulation Parameters:\n";
    file << "# - Devices: " << nDevices << " | Gateways: " << nGateways << "\n";
    file << "# - SimTime: " << simulationTime << "min | PayloadBytes: 51\n";
    file << "# - BW: 125kHz | CR: 4/5 | NoiseFigure: 6dB\n";
    file << "# - PathLoss: 7.7+37.6*log10(d) | TxPower: 14dBm\n";
    file << "# - Channels: 1 (single channel simulation)\n";
    if (!specificConfig.empty()) {
        file << "# - Config: " << specificConfig << "\n";
    }
    file << "# Note: Drops include path loss, interference, and collisions\n";
    file << "\n";
}

// ==============================================================================
// RESULTS VALIDATION
// ==============================================================================
inline void ValidateResults(NodeContainer endDevices) {
    bool hasErrors = false;
    
    // Check totals match per-node sums
    uint32_t sumSent = 0, sumReceived = 0;
    for (auto& kv : g_sentPacketsPerNode) sumSent += kv.second;
    for (auto& kv : g_receivedPacketsPerNode) sumReceived += kv.second;
    
    if (sumSent != g_totalSent) {
        std::cerr << "[ERROR] Sum(sent per node) != TotalSent: " << sumSent 
                  << " vs " << g_totalSent << std::endl;
        hasErrors = true;
    }
    if (sumReceived != g_totalReceived) {
        std::cerr << "[ERROR] Sum(received per node) != TotalReceived: " << sumReceived 
                  << " vs " << g_totalReceived << std::endl;
        hasErrors = true;
    }
    
    // Check no node received more than sent
    for (auto& kv : g_sentPacketsPerNode) {
        uint32_t nodeId = kv.first;
        uint32_t sent = kv.second;
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        if (received > sent) {
            std::cerr << "[ERROR] Node " << nodeId << " received " << received 
                      << " > sent " << sent << std::endl;
            hasErrors = true;
        }
    }
    
    if (hasErrors) {
        std::cerr << "[FATAL] Validation failed - results may be incorrect!" << std::endl;
    } else {
        std::cout << "✅ Results validation passed" << std::endl;
    }
}

// ==============================================================================
// STANDARD CHANNEL SETUP
// ==============================================================================
inline Ptr<LoraChannel> SetupStandardChannel(double maxRandomLossDb = 5.0) {
    // Standard log-distance propagation (matches all scenarios)
    Ptr<LogDistancePropagationLossModel> loss = CreateObject<LogDistancePropagationLossModel>();
    loss->SetPathLossExponent(3.76);
    loss->SetReference(1, 7.7);

    Ptr<UniformRandomVariable> randomLoss = CreateObject<UniformRandomVariable>();
    randomLoss->SetAttribute("Min", DoubleValue(0.0));
    randomLoss->SetAttribute("Max", DoubleValue(maxRandomLossDb));

    Ptr<RandomPropagationLossModel> randomLossModel = CreateObject<RandomPropagationLossModel>();
    randomLossModel->SetAttribute("Variable", PointerValue(randomLoss));
    loss->SetNext(randomLossModel);

    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    return CreateObject<LoraChannel>(loss, delay);
}

// ==============================================================================
// STANDARD MOBILITY SETUP
// ==============================================================================
inline void SetupStandardMobility(NodeContainer& endDevices, NodeContainer& gateways,
                          double areaSize = 5000.0) {
    MobilityHelper mobilityEd, mobilityGw;
    
    // End devices: random placement in square area
    mobilityEd.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                                    "X", PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                        "Min", DoubleValue(-areaSize/2),
                                        "Max", DoubleValue(areaSize/2))),
                                    "Y", PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                        "Min", DoubleValue(-areaSize/2),
                                        "Max", DoubleValue(areaSize/2))));
    mobilityEd.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobilityEd.Install(endDevices);

    // Single gateway at center (default case)
    Ptr<ListPositionAllocator> positionAllocGw = CreateObject<ListPositionAllocator>();
    positionAllocGw->Add(Vector(0.0, 0.0, 15.0));
    mobilityGw.SetPositionAllocator(positionAllocGw);
    mobilityGw.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobilityGw.Install(gateways);
}

// ==============================================================================
// STANDARD NETWORK SERVER SETUP
// ==============================================================================
inline void SetupStandardNetworkServer(NodeContainer& gateways, NodeContainer& endDevices, 
                               bool adrEnabled = false) {
    // Create network server
    Ptr<Node> networkServer = CreateObject<Node>();

    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("5Mbps"));
    p2p.SetChannelAttribute("Delay", StringValue("2ms"));

    P2PGwRegistration_t gwRegistration;
    for (auto gw = gateways.Begin(); gw != gateways.End(); ++gw) {
        auto container = p2p.Install(networkServer, *gw);
        auto serverP2PNetDev = DynamicCast<PointToPointNetDevice>(container.Get(0));
        NS_ASSERT_MSG(serverP2PNetDev, "Server P2P device is null");
        gwRegistration.emplace_back(serverP2PNetDev, *gw);
    }

    NetworkServerHelper networkServerHelper;
    networkServerHelper.EnableAdr(adrEnabled);
    networkServerHelper.SetGatewaysP2P(gwRegistration);
    networkServerHelper.SetEndDevices(endDevices);
    networkServerHelper.Install(networkServer);

    ForwarderHelper forwarderHelper;
    forwarderHelper.Install(gateways);
}

// put this helper next to your other timing helpers
inline void SetupTimingStaggered(NodeContainer endDevices, int simulationTime,
                                 int packetInterval, void (*buildMappingFunc)(NodeContainer)) {
    Simulator::Schedule(Seconds(1.0), buildMappingFunc, endDevices);

    PeriodicSenderHelper appHelper;
    appHelper.SetPeriod(Seconds(packetInterval));
    appHelper.SetPacketSize(51);
    auto apps = appHelper.Install(endDevices);

    const uint32_t N = apps.GetN();
    for (uint32_t i = 0; i < N; ++i) {
        // even spread in [0, packetInterval)
        double phase = (static_cast<double>(i) / static_cast<double>(N)) * packetInterval;
        apps.Get(i)->SetStartTime(Seconds(1.0 + phase));
        apps.Get(i)->SetStopTime(Seconds(simulationTime * 60 - 0.1));
    }
    std::cout << "✅ Staggered timing across " << N << " nodes within "
              << packetInterval << "s.\n";
}


// ==============================================================================
// STANDARD LORA SETUP
// ==============================================================================
inline void SetupStandardLoRa(NodeContainer& endDevices, NodeContainer& gateways, 
                      Ptr<LoraChannel> channel, uint8_t dataRate = 2) {
    // Disable ADR by default (scenarios can override)
    Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(false));
    
    // Create helpers
    LoraPhyHelper phyHelper;
    phyHelper.SetChannel(channel);

    LorawanMacHelper macHelper;
    LoraHelper helper;
    helper.EnablePacketTracking();

    // Create and setup gateways
    phyHelper.SetDeviceType(LoraPhyHelper::GW);
    macHelper.SetDeviceType(LorawanMacHelper::GW);
    helper.Install(phyHelper, macHelper, gateways);

    // Create and setup end devices
    uint8_t nwkId = 54;
    uint32_t nwkAddr = 1864;
    Ptr<LoraDeviceAddressGenerator> addrGen = CreateObject<LoraDeviceAddressGenerator>(nwkId, nwkAddr);

    phyHelper.SetDeviceType(LoraPhyHelper::ED);
    macHelper.SetDeviceType(LorawanMacHelper::ED_A);
    macHelper.SetAddressGenerator(addrGen);
    macHelper.SetRegion(LorawanMacHelper::EU);
    helper.Install(phyHelper, macHelper, endDevices);

    // Set standard parameters for all devices
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        Ptr<Node> node = endDevices.Get(i);
        Ptr<LoraNetDevice> loraNetDevice = DynamicCast<LoraNetDevice>(node->GetDevice(0));
        Ptr<EndDeviceLorawanMac> mac = DynamicCast<EndDeviceLorawanMac>(loraNetDevice->GetMac());
        mac->SetDataRate(dataRate);              // DR2 = SF10 by default
        mac->SetTransmissionPowerDbm(14);        // Standard 14 dBm
    }
}

// ==============================================================================
// STANDARD DEVICE MAPPING
// ==============================================================================
inline void BuildStandardDeviceMapping(NodeContainer endDevices) {
    for (uint32_t i = 0; i < endDevices.GetN(); ++i) {
        Ptr<Node> node = endDevices.Get(i);
        uint32_t nodeId = node->GetId();
        
        Ptr<NetDevice> netDevice = node->GetDevice(0);
        Ptr<LoraNetDevice> loraNetDevice = DynamicCast<LoraNetDevice>(netDevice);
        
        if (loraNetDevice) {
            Ptr<LorawanMac> mac = loraNetDevice->GetMac();
            Ptr<EndDeviceLorawanMac> endDeviceMac = DynamicCast<EndDeviceLorawanMac>(mac);
            
            if (endDeviceMac) {
                LoraDeviceAddress deviceAddress = endDeviceMac->GetDeviceAddress();
                g_deviceToNodeMap[deviceAddress] = nodeId;
                
                // Initialize ALL common counters
                g_sentPacketsPerNode[nodeId] = 0;
                g_receivedPacketsPerNode[nodeId] = 0;
                // Scenarios can add: g_totalAirTimePerNode, g_rssiPerNode, etc.
            }
        }
    }
    
    std::cout << "Device mapping built for " << endDevices.GetN() << " devices" << std::endl;
}

// ==============================================================================
// STANDARD TIMING SETUP
// ==============================================================================
inline void SetupStandardTiming(NodeContainer endDevices, int simulationTime, 
                        int packetInterval, void (*buildMappingFunc)(NodeContainer)) {
    // CRITICAL: Use exact same timing across ALL scenarios
    Simulator::Schedule(Seconds(1.0), buildMappingFunc, endDevices);

    PeriodicSenderHelper appHelper;
    appHelper.SetPeriod(Seconds(packetInterval));
    appHelper.SetPacketSize(51); // Standard LoRaWAN payload
    ApplicationContainer appContainer = appHelper.Install(endDevices);
    
    // Consistent timing: Start at 1.1s, stop 0.1s before end
    appContainer.Start(Seconds(1.1));
    appContainer.Stop(Seconds(simulationTime * 60 - 0.1));
    
    std::cout << "✅ Standard timing configured: mapping@1.0s, start@1.1s, stop@" 
              << (simulationTime * 60 - 0.1) << "s" << std::endl;
}

// ==============================================================================
// STANDARD TRACE CONNECTIONS
// ==============================================================================
inline void ConnectStandardTraces(void (*onPacketSent)(Ptr<const Packet>),
                                 void (*onGatewayReceive)(Ptr<const Packet>)) {
    // End-device: SentNewPacket
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/SentNewPacket",
        MakeCallback(onPacketSent));

    // Gateway: ReceivedPacket  
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::GatewayLorawanMac/ReceivedPacket",
        MakeCallback(onGatewayReceive));
}

#endif // SCENARIO_UTILS_H