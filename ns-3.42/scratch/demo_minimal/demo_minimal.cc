/*
 * Copyright (c) 2018 University of Padova
 *
 * SPDX-License-Identifier: GPL-2.0-only
 *
 * Author: Davide Magrin <magrinda@dei.unipd.it>
 */

/*
 * This program creates a simple LoRaWAN network with specified end devices
 * and gateways, using the Adaptive Data Rate (ADR) algorithm.
 * It integrates parameters and setup style from the user's previous 'demo_minimal.cc'
 * and 'CLEAN_ADROPT_10N.ini' configuration.
 */

#include "ns3/command-line.h"
#include "ns3/config.h"
#include "ns3/core-module.h"
#include "ns3/forwarder-helper.h"
#include "ns3/gateway-lora-phy.h"
#include "ns3/hex-grid-position-allocator.h" // Might not be used if using ListPositionAllocator
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

// Required for CorrelatedShadowingPropagationLossModel
#include "ns3/correlated-shadowing-propagation-loss-model.h"
#include "ns3/class-a-end-device-lorawan-mac.h" // To set initial SF/TxPower on MAC
#include "ns3/lora-packet-tracker.h" // NEW: Explicitly include LoraPacketTracker header

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("AdaptedAdrExample"); // Custom log component name

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

int
main(int argc, char* argv[])
{
    // --- User-defined parameters (from demo_minimal.cc / CLEAN_ADROPT_10N.ini) ---
    uint32_t nDevices = 10;
    uint32_t nGateways = 8;
    double simulationTimeDouble = 1800.0; // Changed to double to match initial value
    Time simulationTime = Seconds(simulationTimeDouble); // Convert to ns3::Time early

    // Command Line parsing (simplified, retaining only relevant options for adapted network)
    CommandLine cmd(__FILE__);
    cmd.AddValue("nDevices", "Number of devices to simulate", nDevices);
    cmd.AddValue("nGateways", "Number of gateways to simulate", nGateways);
    cmd.AddValue("simulationTime", "Simulation time in seconds", simulationTimeDouble); // Use double for cmd arg
    cmd.Parse(argc, argv);

    // Logging (adapted from demo_minimal.cc for more verbose output)
    LogComponentEnable("AdaptedAdrExample", LOG_LEVEL_INFO); // General script logging
    LogComponentEnable("LoraPacketTracker", LOG_LEVEL_INFO); // Packet tracking info
    LogComponentEnable("NetworkServer", LOG_LEVEL_INFO);     // Network server operations
    LogComponentEnable("NetworkController", LOG_LEVEL_INFO); // Network controller actions
    LogComponentEnable("NetworkScheduler", LOG_LEVEL_INFO);  // Packet scheduling
    LogComponentEnable("NetworkStatus", LOG_LEVEL_INFO);     // Network status updates
    LogComponentEnable("EndDeviceStatus", LOG_LEVEL_INFO);   // Individual end device status
    LogComponentEnable("AdrComponent", LOG_LEVEL_ALL);       // Detailed ADR component logs
    LogComponentEnable("ClassAEndDeviceLorawanMac", LOG_LEVEL_INFO); // MAC layer details for Class A EDs
    LogComponentEnable("GatewayLorawanMac", LOG_LEVEL_INFO); // MAC layer details for GWs
    LogComponentEnable("PeriodicSender", LOG_LEVEL_INFO);    // Application traffic generation

    LogComponentEnableAll(LOG_PREFIX_FUNC); // Show function names in logs
    LogComponentEnableAll(LOG_PREFIX_NODE); // Show node ID in logs
    LogComponentEnableAll(LOG_PREFIX_TIME); // Show simulation time in logs

    // Set the end devices to allow data rate control (i.e. adaptive data rate) from the network
    // server (This is a global default, will be overridden by direct setting later if needed)
    Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(true));

    // ADR Algorithm Configuration Attributes (Re-introducing these as per adr-example.cc)
    // Config::SetDefault("ns3::lorawan::AdrComponent::Margin", DoubleValue(15.0));
    // Config::SetDefault("ns3::lorawan::AdrComponent::AdrInterval", TimeValue(Seconds(300)));
    // Config::SetDefault("ns3::lorawan::AdrComponent::AdrRetransmissions", UintegerValue(3));

    // --- Create a simple wireless channel ---
    Ptr<LogDistancePropagationLossModel> loss = CreateObject<LogDistancePropagationLossModel>();
    loss->SetPathLossExponent(3.76);
    loss->SetReference(1.0, 7.7);

    // Using CorrelatedShadowingPropagationLossModel as per user's demo_minimal.cc
    Ptr<CorrelatedShadowingPropagationLossModel> shadowing = CreateObject<CorrelatedShadowingPropagationLossModel>();
    shadowing->SetAttribute("CorrelationDistance", DoubleValue(110.0));
    loss->SetNext(shadowing); // Chaining shadowing over pathloss

    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay);

    // --- Helpers ---
    LoraPhyHelper phyHelper = LoraPhyHelper();
    phyHelper.SetChannel(channel);

    LorawanMacHelper macHelper = LorawanMacHelper();
    LoraHelper helper = LoraHelper();
    helper.EnablePacketTracking(); // Enable packet tracking for detailed results

    // --- Create Nodes ---
    NodeContainer endDevicesNs3;
    endDevicesNs3.Create(nDevices);
    NodeContainer gatewaysNs3;
    gatewaysNs3.Create(nGateways);
    NodeContainer networkServerNs3;
    networkServerNs3.Create(1);

    // --- Mobility (Fixed positions as per demo_minimal.cc) ---
    MobilityHelper mobility;
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");

    Ptr<ListPositionAllocator> edPosAllocator = CreateObject<ListPositionAllocator>();
    edPosAllocator->Add(Vector(0, 0, 0));        // Node 0
    edPosAllocator->Add(Vector(500, 0, 0));       // Node 1
    edPosAllocator->Add(Vector(1000, 0, 0));      // Node 2
    edPosAllocator->Add(Vector(1500, 0, 0));      // Node 3
    edPosAllocator->Add(Vector(2000, 0, 0));      // Node 4
    edPosAllocator->Add(Vector(866, 500, 0));     // Node 5
    edPosAllocator->Add(Vector(-500, 500, 0));    // Node 6
    edPosAllocator->Add(Vector(0, 1000, 0));      // Node 7
    edPosAllocator->Add(Vector(1200, -800, 0));   // Node 8
    edPosAllocator->Add(Vector(-800, -800, 0));   // Node 9
    mobility.SetPositionAllocator(edPosAllocator);
    mobility.Install(endDevicesNs3);
    NS_LOG_INFO("End Device mobility installed with fixed positions.");

    Ptr<ListPositionAllocator> gwPosAllocator = CreateObject<ListPositionAllocator>();
    gwPosAllocator->Add(Vector(520, 0, 15));        // GW 0 (Height 15m)
    gwPosAllocator->Add(Vector(729, 729, 15));      // GW 1
    gwPosAllocator->Add(Vector(0, 1340, 15));       // GW 2
    gwPosAllocator->Add(Vector(-1019, 1019, 15));   // GW 3
    gwPosAllocator->Add(Vector(1506, 1506, 15));    // GW 4
    gwPosAllocator->Add(Vector(-2000, 2000, 15));   // GW 5
    gwPosAllocator->Add(Vector(2828, 2828, 15));    // GW 6
    gwPosAllocator->Add(Vector(1414, -1414, 15));   // GW 7
    mobility.SetPositionAllocator(gwPosAllocator);
    mobility.Install(gatewaysNs3);
    NS_LOG_INFO("Gateway mobility installed with fixed positions.");

    mobility.Install(networkServerNs3); // Server typically at a fixed position too
    NS_LOG_INFO("Network Server mobility installed.");


    // --- Create LoRaWAN devices for Gateways ---
    phyHelper.SetDeviceType(LoraPhyHelper::GW);
    macHelper.SetDeviceType(LorawanMacHelper::GW);
    NetDeviceContainer gatewayDevices = helper.Install(phyHelper, macHelper, gatewaysNs3);
    NS_LOG_INFO(nGateways << " Gateway devices installed.");

    // --- Create LoRaWAN devices for End Devices ---
    Ptr<LoraDeviceAddressGenerator> addrGen =
        CreateObject<LoraDeviceAddressGenerator>(54, 1864); // NwkId and NwkAddr from adr-example.cc
    phyHelper.SetDeviceType(LoraPhyHelper::ED);
    macHelper.SetDeviceType(LorawanMacHelper::ED_A);
    macHelper.SetAddressGenerator(addrGen);
    macHelper.SetRegion(LorawanMacHelper::EU);
    NetDeviceContainer endDeviceDevices = helper.Install(phyHelper, macHelper, endDevicesNs3);
    NS_LOG_INFO(nDevices << " End Device devices installed.");

    // --- Set initial SF and TxPower for End Devices (as in demo_minimal.cc) ---
    std::vector<uint8_t> initialSFs = {12, 10, 11, 12, 12, 9, 10, 11, 12, 12};
    double initialTxPowerDbm = 14.0; // 14dBm
    for (uint32_t i = 0; i < nDevices; ++i) {
        Ptr<LoraNetDevice> loraNetDevice = DynamicCast<LoraNetDevice>(endDeviceDevices.Get(i));
        Ptr<ClassAEndDeviceLorawanMac> edMac = DynamicCast<ClassAEndDeviceLorawanMac>(loraNetDevice->GetMac());
        if (edMac) {
            edMac->SetDataRate(5 - (initialSFs[i] - 7)); // Convert SF to DR (SF7=DR5, SF12=DR0)
            edMac->SetTransmissionPowerDbm(initialTxPowerDbm);
            edMac->SetAttribute("ADR", BooleanValue(true)); // Ensure ADR is enabled on MAC
        } else {
            NS_LOG_WARN("Could not get ClassAEndDeviceLorawanMac for End Device " << i);
        }
    }
    NS_LOG_INFO("Initial Spreading Factors and Transmission Powers set for End Devices.");


    // --- Install applications in end devices ---
    int appPeriodSeconds = 30; // From user's demo_minimal.cc
    PeriodicSenderHelper appHelper = PeriodicSenderHelper();
    appHelper.SetPeriod(Seconds(appPeriodSeconds));
    appHelper.SetPacketSize(20); // From user's demo_minimal.cc
    ApplicationContainer appContainer = appHelper.Install(endDevicesNs3);
    appContainer.Start(Seconds(5.0)); // Start time from demo_minimal.cc
    appContainer.Stop(simulationTime); // Use ns3::Time directly
    NS_LOG_INFO("Periodic Sender application installed on End Devices.");


    // --- Create Network Server ---
    NetworkServerHelper networkServerHelper;
    networkServerHelper.EnableAdr(true);
    networkServerHelper.SetAdr("ns3::AdrComponent");

    // PointToPoint links between gateways and server (using gatewayDevices and networkServerNs3)
    P2PGwRegistration_t gwRegistration;
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("5Mbps"));
    p2p.SetChannelAttribute("Delay", StringValue("2ms"));

    for (uint32_t i = 0; i < nGateways; ++i)
    {
        Ptr<Node> gatewayNode = gatewaysNs3.Get(i);
        NetDeviceContainer p2pDevices = p2p.Install(networkServerNs3.Get(0), gatewayNode);
        Ptr<PointToPointNetDevice> serverP2PNetDev = DynamicCast<PointToPointNetDevice>(p2pDevices.Get(0));
        gwRegistration.emplace_back(serverP2PNetDev, gatewayNode);
    }
    networkServerHelper.SetGatewaysP2P(gwRegistration);
    // Pass NodeContainer to SetEndDevices
    networkServerHelper.SetEndDevices(endDevicesNs3);
    networkServerHelper.Install(networkServerNs3.Get(0));
    NS_LOG_INFO("Network Server installed.");


    // --- Install the Forwarder application on the gateways ---
    ForwarderHelper forwarderHelper;
    forwarderHelper.Install(gatewaysNs3);
    NS_LOG_INFO("Forwarder application installed on Gateways.");


    // --- Connect traces ---
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/TxPower",
        MakeCallback(&OnTxPowerChange));
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/DataRate",
        MakeCallback(&OnDataRateChange));

    // Activate printing of end device MAC parameters
    Time stateSamplePeriod = Seconds(1200); // 20 minutes
    helper.EnablePeriodicDeviceStatusPrinting(endDevicesNs3,
                                              gatewaysNs3,
                                              "nodeData.txt",
                                              stateSamplePeriod);
    helper.EnablePeriodicPhyPerformancePrinting(gatewaysNs3, "phyPerformance.txt", stateSamplePeriod);
    helper.EnablePeriodicGlobalPerformancePrinting("globalPerformance.txt", stateSamplePeriod);
    NS_LOG_INFO("Periodic status and performance printing enabled.");

    LoraPacketTracker& tracker = helper.GetPacketTracker();

    // --- Start simulation ---
    Simulator::Stop(simulationTime);
    Simulator::Run();
    Simulator::Destroy();
    NS_LOG_INFO("Simulation finished.");

    // --- Print results (using LoraPacketTracker from original adr-example.cc) ---
    std::cout << "\n--- Packet Tracking Summary ---" << std::endl;
    // Count MAC packets globally for the last period (as in adr-example.cc)
    // Adjusting for potentially shorter simulation time than 2 full periods
    Time startTrackTime = Seconds(0);
    // Compare Time with Time
    if (simulationTime > Seconds(1200 * 2)) {
      // Subtract Time from Time
      startTrackTime = simulationTime - Seconds(1200 * 2);
    }
    std::cout << "\n--- Packet Tracking Summary ---" << std::endl;
    std::cout << "Total MAC packets in last part of simulation: "
              << tracker.CountMacPacketsGlobally(startTrackTime, simulationTime) << std::endl;
    // Alte statistici nu sunt disponibile cu implementarea curentă!

    return 0;
}
