/*
 * Copyright (c) 2018 University of Padova
 *
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * Author: Davide Magrin <magrinda@dei.unipd.it>
 * Modified to include per-node packet tracking
 */

/*
 * This program creates a simple network which uses an Adaptive Data Rate (ADR) algorithm to set up
 * the Spreading Factors of the devices in the Network.
 * Enhanced with per-node packet tracking for sent and received packets.
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
#include "ns3/periodic-sender.h"
#include "ns3/point-to-point-module.h"
#include "ns3/random-variable-stream.h"
#include "ns3/rectangle.h"
#include "ns3/string.h"
#include <fstream>
#include <iomanip>

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("ComparisonExample");

// Global variables for packet tracking
std::map<uint32_t, uint32_t> sentPacketsPerNode;
std::map<uint32_t, uint32_t> receivedPacketsPerNode;
std::map<LoraDeviceAddress, uint32_t> deviceAddressToNodeId;

/**
 * Record a change in the data rate setting on an end device.
 *
 * @param oldDr The previous data rate value.
 * @param newDr The updated data rate value.
 */
void
OnDataRateChange(uint8_t oldDr, uint8_t newDr)
{
    NS_LOG_DEBUG("DR" << unsigned(oldDr) << " -> DR" << unsigned(newDr));
}

/**
 * Record a change in the transmission power setting on an end device.
 *
 * @param oldTxPower The previous transmission power value.
 * @param newTxPower The updated transmission power value.
 */
void
OnTxPowerChange(double oldTxPower, double newTxPower)
{
    NS_LOG_DEBUG(oldTxPower << " dBm -> " << newTxPower << " dBm");
}

/**
 * Callback function to track sent packets from end devices
 *
 * @param packet The packet being sent
 */
void
OnPacketSent(Ptr<const Packet> packet)
{
    uint32_t nodeId = Simulator::GetContext();
    sentPacketsPerNode[nodeId]++;
    
    NS_LOG_INFO("Node " << nodeId << " sent packet. Total sent: " << sentPacketsPerNode[nodeId]);
}

/**
 * Callback function to track when a packet is successfully received at gateway
 * This trace is fired when a gateway successfully receives a packet
 */
void
OnGatewayReceive(Ptr<const Packet> packet)
{
    // Extract the LoRaWAN header to identify the source device
    LorawanMacHeader macHeader;
    LoraFrameHeader frameHeader;
    
    Ptr<Packet> packetCopy = packet->Copy();
    packetCopy->RemoveHeader(macHeader);
    
    if (macHeader.GetMType() == LorawanMacHeader::UNCONFIRMED_DATA_UP ||
        macHeader.GetMType() == LorawanMacHeader::CONFIRMED_DATA_UP)
    {
        packetCopy->RemoveHeader(frameHeader);
        LoraDeviceAddress deviceAddress = frameHeader.GetAddress();
        
        // Find the corresponding node ID
        auto it = deviceAddressToNodeId.find(deviceAddress);
        if (it != deviceAddressToNodeId.end())
        {
            uint32_t nodeId = it->second;
            receivedPacketsPerNode[nodeId]++;
            NS_LOG_INFO("Packet from Node " << nodeId << " received at gateway. Total received: " 
                       << receivedPacketsPerNode[nodeId]);
        }
    }
}

/**
 * Build mapping between device addresses and node IDs
 *
 * @param endDevices Container of end devices
 */
void
BuildDeviceAddressMapping(NodeContainer endDevices)
{
    for (uint32_t i = 0; i < endDevices.GetN(); ++i)
    {
        Ptr<Node> node = endDevices.Get(i);
        uint32_t nodeId = node->GetId();
        
        Ptr<NetDevice> netDevice = node->GetDevice(0);
        Ptr<LoraNetDevice> loraNetDevice = DynamicCast<LoraNetDevice>(netDevice);
        
        if (loraNetDevice)
        {
            Ptr<LorawanMac> mac = loraNetDevice->GetMac();
            Ptr<EndDeviceLorawanMac> endDeviceMac = DynamicCast<EndDeviceLorawanMac>(mac);
            
            if (endDeviceMac)
            {
                LoraDeviceAddress deviceAddress = endDeviceMac->GetDeviceAddress();
                deviceAddressToNodeId[deviceAddress] = nodeId;
                NS_LOG_DEBUG("Mapped device address to Node " << nodeId);
            }
        }
    }
}

/**
 * Print per-node packet statistics
 *
 * @param endDevices Container of end devices
 * @param outputPrefix Prefix for output files
 */
void
PrintPerNodeStatistics(NodeContainer endDevices, const std::string& outputPrefix)
{
    std::cout << "\n========== SIMULATION RESULTS SUMMARY ==========" << std::endl;
    std::cout << "===== PER-NODE PACKET STATISTICS =====" << std::endl;
    std::cout << "Node ID\t| Sent\t| Received\t| Success Rate (%)" << std::endl;
    std::cout << "--------|-------|---------------|------------------" << std::endl;
    
    uint32_t totalSent = 0;
    uint32_t totalReceived = 0;
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i)
    {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = sentPacketsPerNode[nodeId];
        uint32_t received = receivedPacketsPerNode[nodeId];
        
        totalSent += sent;
        totalReceived += received;
        
        double successRate = sent > 0 ? (double(received) / double(sent)) * 100.0 : 0.0;
        
        std::cout << nodeId << "\t| " << sent << "\t| " << received 
                  << "\t\t| " << std::fixed << std::setprecision(2) << successRate << std::endl;
    }
    
    std::cout << "--------|-------|---------------|------------------" << std::endl;
    std::cout << "TOTAL\t| " << totalSent << "\t| " << totalReceived;
    
    if (totalSent > 0) {
        double overallSuccessRate = (double(totalReceived) / double(totalSent)) * 100.0;
        std::cout << "\t\t| " << std::fixed << std::setprecision(2) << overallSuccessRate;
    } else {
        std::cout << "\t\t| 0.00";
    }
    std::cout << std::endl;
    std::cout << "=================================================" << std::endl;
}

/**
 * Export per-node statistics to CSV file
 *
 * @param endDevices Container of end devices
 * @param filename Name of the CSV file to create
 */
void
ExportStatisticsToCSV(NodeContainer endDevices, const std::string& filename)
{
    std::ofstream file(filename);
    file << "NodeID,SentPackets,ReceivedPackets,SuccessRate" << std::endl;
    
    for (uint32_t i = 0; i < endDevices.GetN(); ++i)
    {
        uint32_t nodeId = endDevices.Get(i)->GetId();
        uint32_t sent = sentPacketsPerNode[nodeId];
        uint32_t received = receivedPacketsPerNode[nodeId];
        double successRate = sent > 0 ? (double(received) / double(sent)) * 100.0 : 0.0;
        
        file << nodeId << "," << sent << "," << received << "," 
             << std::fixed << std::setprecision(2) << successRate << std::endl;
    }
    
    file.close();
    std::cout << "Statistics exported to " << filename << std::endl;
}

int
main(int argc, char* argv[])
{
    bool verbose = false;
    bool adrEnabled = true;
    bool initializeSF = false;
    int nDevices = 400;
    int simulationTime = 20; // in minutes
    double mobileNodeProbability = 0;
    double sideLengthMeters = 10000;
    int gatewayDistanceMeters = 5000;
    double maxRandomLossDb = 10;
    double minSpeedMetersPerSecond = 2;
    double maxSpeedMetersPerSecond = 16;
    int packetInterval = 1200; // seconds between packets
    std::string adrType = "ns3::AdrComponent";
    std::string outputPrefix = "comparison";

    CommandLine cmd(__FILE__);
    cmd.AddValue("verbose", "Whether to print output or not", verbose);
    cmd.AddValue("MultipleGwCombiningMethod", "ns3::AdrComponent::MultipleGwCombiningMethod");
    cmd.AddValue("MultiplePacketsCombiningMethod",
                 "ns3::AdrComponent::MultiplePacketsCombiningMethod");
    cmd.AddValue("HistoryRange", "ns3::AdrComponent::HistoryRange");
    cmd.AddValue("MType", "ns3::EndDeviceLorawanMac::MType");
    cmd.AddValue("EDDRAdaptation", "ns3::EndDeviceLorawanMac::EnableEDDataRateAdaptation");
    cmd.AddValue("ChangeTransmissionPower", "ns3::AdrComponent::ChangeTransmissionPower");
    cmd.AddValue("adrEnabled", "Whether to enable Adaptive Data Rate (ADR)", adrEnabled);
    cmd.AddValue("nDevices", "Number of devices to simulate", nDevices);
    cmd.AddValue("simulationTime", "Simulation time in minutes", simulationTime);
    cmd.AddValue("MobileNodeProbability",
                 "Probability of a node being a mobile node",
                 mobileNodeProbability);
    cmd.AddValue("sideLength",
                 "Length (m) of the side of the rectangle nodes will be placed in",
                 sideLengthMeters);
    cmd.AddValue("maxRandomLoss",
                 "Maximum amount (dB) of the random loss component",
                 maxRandomLossDb);
    cmd.AddValue("gatewayDistance", "Distance (m) between gateways", gatewayDistanceMeters);
    cmd.AddValue("initializeSF", "Whether to initialize the SFs", initializeSF);
    cmd.AddValue("MinSpeed", "Minimum speed (m/s) for mobile devices", minSpeedMetersPerSecond);
    cmd.AddValue("MaxSpeed", "Maximum speed (m/s) for mobile devices", maxSpeedMetersPerSecond);
    cmd.AddValue("packetInterval", "Interval between packets in seconds", packetInterval);
    cmd.AddValue("outputPrefix", "Prefix for output files", outputPrefix);
    cmd.AddValue("MaxTransmissions", "ns3::EndDeviceLorawanMac::MaxTransmissions");
    cmd.Parse(argc, argv);

    // Calculate number of gateways based on area and gateway distance
    int nGateways = 1; // Default to 1 gateway
    if (gatewayDistanceMeters > 0) {
        int gatewayRings = 2 + (std::sqrt(2) * sideLengthMeters) / (gatewayDistanceMeters);
        nGateways = 3 * gatewayRings * gatewayRings - 3 * gatewayRings + 1;
    }

    // Initialize packet counters for all nodes
    for (int i = 0; i < nDevices; ++i)
    {
        sentPacketsPerNode[i] = 0;
        receivedPacketsPerNode[i] = 0;
    }

    // Logging
    //////////

    LogComponentEnable("ComparisonExample", LOG_LEVEL_ALL);
    LogComponentEnable("AdrComponent", LOG_LEVEL_ALL);
    LogComponentEnableAll(LOG_PREFIX_FUNC);
    LogComponentEnableAll(LOG_PREFIX_NODE);
    LogComponentEnableAll(LOG_PREFIX_TIME);

    // Set the end devices to allow data rate control (i.e. adaptive data rate) from the network
    // server
    Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(true));

    // Create a simple wireless channel
    ///////////////////////////////////

    Ptr<LogDistancePropagationLossModel> loss = CreateObject<LogDistancePropagationLossModel>();
    loss->SetPathLossExponent(3.76);
    loss->SetReference(1, 7.7);

    Ptr<UniformRandomVariable> x = CreateObject<UniformRandomVariable>();
    x->SetAttribute("Min", DoubleValue(0.0));
    x->SetAttribute("Max", DoubleValue(maxRandomLossDb));

    Ptr<RandomPropagationLossModel> randomLoss = CreateObject<RandomPropagationLossModel>();
    randomLoss->SetAttribute("Variable", PointerValue(x));

    loss->SetNext(randomLoss);

    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();

    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay);

    // Helpers
    //////////

    // End device mobility
    MobilityHelper mobilityEd;
    MobilityHelper mobilityGw;
    mobilityEd.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                                    "X",
                                    PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                        "Min",
                                        DoubleValue(-sideLengthMeters),
                                        "Max",
                                        DoubleValue(sideLengthMeters))),
                                    "Y",
                                    PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                        "Min",
                                        DoubleValue(-sideLengthMeters),
                                        "Max",
                                        DoubleValue(sideLengthMeters))));

    // Gateway positioning
    if (gatewayDistanceMeters > 0) {
        Ptr<HexGridPositionAllocator> hexAllocator =
            CreateObject<HexGridPositionAllocator>(gatewayDistanceMeters / 2);
        mobilityGw.SetPositionAllocator(hexAllocator);
    } else {
        // Single gateway at center
        Ptr<ListPositionAllocator> positionAllocGw = CreateObject<ListPositionAllocator>();
        positionAllocGw->Add(Vector(0.0, 0.0, 15.0));
        mobilityGw.SetPositionAllocator(positionAllocGw);
    }
    mobilityGw.SetMobilityModel("ns3::ConstantPositionMobilityModel");

    // Create the LoraPhyHelper
    LoraPhyHelper phyHelper = LoraPhyHelper();
    phyHelper.SetChannel(channel);

    // Create the LorawanMacHelper
    LorawanMacHelper macHelper = LorawanMacHelper();

    // Create the LoraHelper
    LoraHelper helper = LoraHelper();
    helper.EnablePacketTracking();

    ////////////////
    // Create gateways //
    ////////////////

    NodeContainer gateways;
    gateways.Create(nGateways);
    mobilityGw.Install(gateways);

    // Create the LoraNetDevices of the gateways
    phyHelper.SetDeviceType(LoraPhyHelper::GW);
    macHelper.SetDeviceType(LorawanMacHelper::GW);
    helper.Install(phyHelper, macHelper, gateways);

    // Create end devices
    /////////////

    NodeContainer endDevices;
    endDevices.Create(nDevices);

    // Install mobility model on all nodes as fixed
    mobilityEd.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobilityEd.Install(endDevices);
    
    // Create a LoraDeviceAddressGenerator
    uint8_t nwkId = 54;
    uint32_t nwkAddr = 1864;
    Ptr<LoraDeviceAddressGenerator> addrGen =
        CreateObject<LoraDeviceAddressGenerator>(nwkId, nwkAddr);

    // Create the LoraNetDevices of the end devices
    phyHelper.SetDeviceType(LoraPhyHelper::ED);
    macHelper.SetDeviceType(LorawanMacHelper::ED_A);
    macHelper.SetAddressGenerator(addrGen);
    macHelper.SetRegion(LorawanMacHelper::EU);
    helper.Install(phyHelper, macHelper, endDevices);

    // Build device address mapping after devices are created
    Simulator::Schedule(Seconds(1.0), &BuildDeviceAddressMapping, endDevices);

    // Install applications in end devices
    PeriodicSenderHelper appHelper = PeriodicSenderHelper();
    appHelper.SetPeriod(Seconds(packetInterval));
    ApplicationContainer appContainer = appHelper.Install(endDevices);

    // Do not set spreading factors up: we will wait for the network server to do this
    if (initializeSF)
    {
        LorawanMacHelper::SetSpreadingFactorsUp(endDevices, gateways, channel);
    }

    ////////////
    // Create network server
    ////////////

    Ptr<Node> networkServer = CreateObject<Node>();

    // PointToPoint links between gateways and server
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("5Mbps"));
    p2p.SetChannelAttribute("Delay", StringValue("2ms"));
    // Store network server app registration details for later
    P2PGwRegistration_t gwRegistration;
    for (auto gw = gateways.Begin(); gw != gateways.End(); ++gw)
    {
        auto container = p2p.Install(networkServer, *gw);
        auto serverP2PNetDev = DynamicCast<PointToPointNetDevice>(container.Get(0));
        gwRegistration.emplace_back(serverP2PNetDev, *gw);
    }

    // Install the NetworkServer application on the network server
    NetworkServerHelper networkServerHelper;
    networkServerHelper.EnableAdr(adrEnabled);
    networkServerHelper.SetAdr(adrType);
    networkServerHelper.SetGatewaysP2P(gwRegistration);
    networkServerHelper.SetEndDevices(endDevices);
    networkServerHelper.Install(networkServer);

    // Install the Forwarder application on the gateways
    ForwarderHelper forwarderHelper;
    forwarderHelper.Install(gateways);

    // Connect our traces for data rate and power changes
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/TxPower",
        MakeCallback(&OnTxPowerChange));
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/DataRate",
        MakeCallback(&OnDataRateChange));

    // Connect traces for packet tracking
    // Track sent packets from end devices at MAC layer
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/SentNewPacket",
        MakeCallback(&OnPacketSent));

    // Track received packets at gateways at MAC layer
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::GatewayLorawanMac/ReceivedPacket",
        MakeCallback(&OnGatewayReceive));

    // Activate printing of end device MAC parameters
    Time stateSamplePeriod = Seconds(packetInterval);
    std::string nodeDataFile = outputPrefix + "_nodeData.txt";
    std::string phyPerfFile = outputPrefix + "_phyPerformance.txt";
    std::string globalPerfFile = outputPrefix + "_globalPerformance.txt";
    
    helper.EnablePeriodicDeviceStatusPrinting(endDevices,
                                              gateways,
                                              nodeDataFile,
                                              stateSamplePeriod);
    helper.EnablePeriodicPhyPerformancePrinting(gateways, phyPerfFile, stateSamplePeriod);
    helper.EnablePeriodicGlobalPerformancePrinting(globalPerfFile, stateSamplePeriod);

    LoraPacketTracker& tracker = helper.GetPacketTracker();

    // Start simulation
    Time totalSimulationTime = Seconds(simulationTime * 60); // Convert minutes to seconds
    Simulator::Stop(totalSimulationTime);
    
    std::cout << "\n🚀 Starting LoRaWAN simulation..." << std::endl;
    std::cout << "Devices: " << nDevices << " | Gateways: " << nGateways << std::endl;
    std::cout << "Area: " << sideLengthMeters*2 << "m x " << sideLengthMeters*2 << "m" << std::endl;
    std::cout << "Simulation time: " << simulationTime << " minutes" << std::endl;
    std::cout << "Packet interval: " << packetInterval << " seconds" << std::endl;
    std::cout << "ADR enabled: " << (adrEnabled ? "Yes" : "No") << std::endl;
    
    Simulator::Run();

    // Print results
    std::cout << "\n✅ Simulation completed successfully!" << std::endl;
    std::cout << "Total simulation time: " << totalSimulationTime.GetSeconds() << " seconds" << std::endl;

    // Print per-node statistics
    PrintPerNodeStatistics(endDevices, outputPrefix);
    
    // Export statistics to CSV
    std::string csvFile = outputPrefix + "_per_node_statistics.csv";
    ExportStatisticsToCSV(endDevices, csvFile);

    // Print global statistics using the original tracker method
    std::cout << "\nGlobal packet statistics:" << std::endl;
    std::cout << "Total packets sent globally: " << tracker.CountMacPacketsGlobally(Seconds(0), totalSimulationTime) << std::endl;

    Simulator::Destroy();

    return 0;
}