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
#include "ns3/lora-net-device.h"
#include "ns3/end-device-lorawan-mac.h"
#include "ns3/lora-phy.h"
#include "ns3/simple-end-device-lora-phy.h"
#include "ns3/lorawan-mac-helper.h"
#include <vector>

using namespace ns3;
using namespace lorawan;

NS_LOG_COMPONENT_DEFINE("AdrOptSimulation");

void
OnDataRateChange(uint8_t oldDr, uint8_t newDr)
{
    NS_LOG_DEBUG("DR" << unsigned(oldDr) << " -> DR" << unsigned(newDr));
}

void
OnTxPowerChange(double oldTxPower, double newTxPower)
{
    NS_LOG_DEBUG(oldTxPower << " dBm -> " << newTxPower << " dBm");
}

int main(int argc, char* argv[])
{
    // --- Parameters: ADAPTED FOR YOUR REQUEST ---
    bool verbose = false;
    bool adrEnabled = true;
    bool initializeSF = false;
    int nDevices = 1;                // 1 end device
    int nPeriodsOf20Minutes = 20;    // Default simulation duration
    double mobileNodeProbability = 0.0;
    double sideLengthMeters = 1500.0;  // Max range between nodes ≤ 3km
    int gatewayDistanceMeters = 1000;  // GW grid spacing (fits 8 GWs in ~3km)
    double maxRandomLossDb = 10;
    double minSpeedMetersPerSecond = 2;
    double maxSpeedMetersPerSecond = 16;
    int appPeriod = 1200;
    std::string adrType = "ns3::lorawan::ADRoptComponent"; // ADRopt

    CommandLine cmd(__FILE__);
    cmd.AddValue("verbose", "Whether to print output or not", verbose);
    cmd.AddValue("AdrEnabled", "Whether to enable ADR", adrEnabled);
    cmd.AddValue("nDevices", "Number of devices to simulate", nDevices);
    cmd.AddValue("PeriodsToSimulate", "Number of periods (20m) to simulate", nPeriodsOf20Minutes);
    cmd.AddValue("MobileNodeProbability", "Probability of a node being mobile", mobileNodeProbability);
    cmd.AddValue("sideLength", "Side length of placement area (meters)", sideLengthMeters);
    cmd.AddValue("maxRandomLoss", "Max random loss (dB)", maxRandomLossDb);
    cmd.AddValue("gatewayDistance", "Distance (m) between gateways", gatewayDistanceMeters);
    cmd.AddValue("initializeSF", "Whether to initialize the SFs", initializeSF);
    cmd.AddValue("MinSpeed", "Min speed (m/s) for mobile devices", minSpeedMetersPerSecond);
    cmd.AddValue("MaxSpeed", "Max speed (m/s) for mobile devices", maxSpeedMetersPerSecond);
    cmd.AddValue("appPeriod", "Application packet period (seconds)", appPeriod);

    cmd.Parse(argc, argv);

    int nGateways = 8; // *** FIXED to 8 gateways ***

    // --- Logging ---
    LogComponentEnable("AdrOptSimulation", LOG_LEVEL_ALL);
    LogComponentEnable("ADRoptComponent", LOG_LEVEL_ALL);
    LogComponentEnableAll(LOG_PREFIX_FUNC);
    LogComponentEnableAll(LOG_PREFIX_NODE);
    LogComponentEnableAll(LOG_PREFIX_TIME);

    Config::SetDefault("ns3::EndDeviceLorawanMac::ADR", BooleanValue(true));

    // --- Channel setup (loss, delay, random fading) ---
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

    // --- Mobility ---
    MobilityHelper mobilityEd, mobilityGw;
    mobilityEd.SetPositionAllocator("ns3::RandomRectanglePositionAllocator",
                                    "X", PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                        "Min", DoubleValue(-sideLengthMeters),
                                        "Max", DoubleValue(sideLengthMeters))),
                                    "Y", PointerValue(CreateObjectWithAttributes<UniformRandomVariable>(
                                        "Min", DoubleValue(-sideLengthMeters),
                                        "Max", DoubleValue(sideLengthMeters))));
    // Ptr<HexGridPositionAllocator> hexAllocator =
    //     CreateObject<HexGridPositionAllocator>(gatewayDistanceMeters / 2);
    // mobilityGw.SetPositionAllocator(hexAllocator);
    // mobilityGw.SetMobilityModel("ns3::ConstantPositionMobilityModel");

    // // --- Create gateways and install mobility/devices ---
    // NodeContainer gateways;
    // gateways.Create(nGateways);
    // mobilityGw.Install(gateways);

    NodeContainer gateways;
    gateways.Create(nGateways);

    Ptr<ListPositionAllocator> gwPositionAlloc = CreateObject<ListPositionAllocator>();
    gwPositionAlloc->Add(Vector(0, 0, 0));
    gwPositionAlloc->Add(Vector(3000, 0, 0));
    gwPositionAlloc->Add(Vector(0, 3000, 0));
    gwPositionAlloc->Add(Vector(3000, 3000, 0));
    gwPositionAlloc->Add(Vector(1500, 0, 0));
    gwPositionAlloc->Add(Vector(0, 1500, 0));
    gwPositionAlloc->Add(Vector(3000, 1500, 0));
    gwPositionAlloc->Add(Vector(1500, 3000, 0));
    mobilityGw.SetPositionAllocator(gwPositionAlloc);
    mobilityGw.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobilityGw.Install(gateways);


    LoraPhyHelper phyHelper;
    phyHelper.SetChannel(channel);
    LorawanMacHelper macHelper;
    LoraHelper helper;
    helper.EnablePacketTracking();

    phyHelper.SetDeviceType(LoraPhyHelper::GW);
    macHelper.SetDeviceType(LorawanMacHelper::GW);
    helper.Install(phyHelper, macHelper, gateways);

    // --- Create end devices and install mobility/devices ---
    NodeContainer endDevices;
    endDevices.Create(nDevices);

    // Fixed devices
    mobilityEd.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    int fixedPositionNodes = 1; // Only one device, all fixed
    for (int i = 0; i < fixedPositionNodes; ++i)
        mobilityEd.Install(endDevices.Get(i));

    // --- LoraNetDeviceAddress ---
    uint8_t nwkId = 54;
    uint32_t nwkAddr = 1864;
    Ptr<LoraDeviceAddressGenerator> addrGen =
        CreateObject<LoraDeviceAddressGenerator>(nwkId, nwkAddr);

    phyHelper.SetDeviceType(LoraPhyHelper::ED);
    macHelper.SetDeviceType(LorawanMacHelper::ED_A);
    macHelper.SetAddressGenerator(addrGen);
    macHelper.SetRegion(LorawanMacHelper::EU);
    helper.Install(phyHelper, macHelper, endDevices);

    // --- Optionally set spreading factors up
    if (initializeSF) {
        LorawanMacHelper::SetSpreadingFactorsUp(endDevices, gateways, channel);
    }

    for (auto i = 0u; i < endDevices.GetN(); ++i) {
        Ptr<Node> node = endDevices.Get(i);
        Ptr<NetDevice> dev = node->GetDevice(0);
        Ptr<LoraNetDevice> loraDev = DynamicCast<LoraNetDevice>(dev);
        if (loraDev) {
            // Get the PHY and MAC layer objects
            Ptr<LoraPhy> phy = loraDev->GetPhy();
            Ptr<EndDeviceLorawanMac> mac = DynamicCast<EndDeviceLorawanMac>(loraDev->GetMac());

            if (mac) {
                // Set TxPower on the LorawanMac object
                // As per lorawan-mac.cc, the TxPower levels are defined by a vector of dBm values.
                // TP2 (TxPower index 2) corresponds to the 2nd element in the vector.
                // We set all TxPower levels according to the standard and set the 2nd index to 2 dBm.
                std::vector<double> txPowers;
                txPowers.push_back(14); // TP0
                txPowers.push_back(12); // TP1
                txPowers.push_back(2);  // TP2 dBm
                txPowers.push_back(0);  // TP3
                txPowers.push_back(-2); // TP4
                txPowers.push_back(-4); // TP5
                txPowers.push_back(-6); // TP6
                txPowers.push_back(-8); // TP7
                txPowers.push_back(-10); // TP8
                txPowers.push_back(-12); // TP9
                txPowers.push_back(-14); // TP10
                txPowers.push_back(-16); // TP11
                txPowers.push_back(-18); // TP12
                txPowers.push_back(-20); // TP13
                txPowers.push_back(-22); // TP14
                mac->SetTxDbmForTxPower(txPowers);

                // Set Spreading Factor on the MAC layer
                // Note: The spreading factor is typically managed by the MAC layer or a helper class.
                // The method SetSpreadingFactor does not exist on SimpleEndDeviceLoraPhy.
                // We are setting the data rate, which determines the spreading factor for a given region.
                // This corresponds to SF7 for the EU868 region, for example.
                mac->SetDataRate(5); // This corresponds to SF7 in some regions.
                                    // You should verify the data rate to SF mapping for your specific region.
                                    // For a more robust solution, use LorawanMacHelper::SetSpreadingFactorsUp()
                                    // before installing devices, as shown in the ns-3 examples.
            }
        }
    }

    // --- Application on end devices ---
    int appPeriodSeconds = 1200; // 20 minutes per packet
    PeriodicSenderHelper appHelper;
    appHelper.SetPeriod(Seconds(appPeriodSeconds));
    ApplicationContainer appContainer = appHelper.Install(endDevices);

    // --- PointToPoint links between gateways and server ---
    Ptr<Node> networkServer = CreateObject<Node>();
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("5Mbps"));
    p2p.SetChannelAttribute("Delay", StringValue("2ms"));
    typedef std::list<std::pair<Ptr<PointToPointNetDevice>, Ptr<Node>>> P2PGwRegistration_t;
    P2PGwRegistration_t gwRegistration;
    for (auto gw = gateways.Begin(); gw != gateways.End(); ++gw) {
        auto container = p2p.Install(networkServer, *gw);
        auto serverP2PNetDev = DynamicCast<PointToPointNetDevice>(container.Get(0));
        gwRegistration.push_back({serverP2PNetDev, *gw});
    }

    NetworkServerHelper networkServerHelper;
    networkServerHelper.EnableAdr(adrEnabled);
    networkServerHelper.SetAdr(adrType);
    networkServerHelper.SetGatewaysP2P(gwRegistration);
    networkServerHelper.SetEndDevices(endDevices);
    networkServerHelper.Install(networkServer);

    ForwarderHelper forwarderHelper;
    forwarderHelper.Install(gateways);

    // --- Tracing DR/TP changes (optional) ---
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/TxPower",
        MakeCallback(&OnTxPowerChange));
    Config::ConnectWithoutContext(
        "/NodeList/*/DeviceList/0/$ns3::LoraNetDevice/Mac/$ns3::EndDeviceLorawanMac/DataRate",
        MakeCallback(&OnDataRateChange));

    // --- Periodic state/metrics output ---
    Time stateSamplePeriod = Seconds(appPeriodSeconds);
    helper.EnablePeriodicDeviceStatusPrinting(endDevices, gateways, "nodeData.txt", stateSamplePeriod);
    helper.EnablePeriodicPhyPerformancePrinting(gateways, "phyPerformance.txt", stateSamplePeriod);
    helper.EnablePeriodicGlobalPerformancePrinting("globalPerformance.txt", stateSamplePeriod);

    // --- Run the simulation ---
    Time simulationTime = Seconds(appPeriodSeconds * nPeriodsOf20Minutes);
    Simulator::Stop(simulationTime);
    Simulator::Run();
    Simulator::Destroy();

    LoraPacketTracker& tracker = helper.GetPacketTracker();
    std::cout << tracker.CountMacPacketsGlobally(Seconds(appPeriodSeconds * (nPeriodsOf20Minutes - 2)),
                                                 Seconds(appPeriodSeconds * (nPeriodsOf20Minutes - 1)))
              << std::endl;

    return 0;
}
