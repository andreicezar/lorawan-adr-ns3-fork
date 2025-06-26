#include "ns3/core-module.h"
#include "ns3/lorawan-module.h"
#include "ns3/mobility-module.h"
#include "ns3/propagation-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/buildings-module.h"
#include "ns3/log.h"
#include "ns3/buildings-helper.h"
// LoRaWAN helpers
#include "ns3/lora-helper.h"
#include "ns3/lora-phy-helper.h"
#include "ns3/lorawan-mac-helper.h"
#include "ns3/network-server-helper.h"
#include "ns3/periodic-sender-helper.h"
#include "ns3/forwarder-helper.h"

// Propagation model
#include "ns3/oh-buildings-propagation-loss-model.h"

using namespace ns3;
using namespace ns3::lorawan;

NS_LOG_COMPONENT_DEFINE("AdrOptSimulation");

int main(int argc, char *argv[])
{
    double appPeriod = 60;
    int nPeriods = 100;
    int nDevices = 1;
    int nGateways = 1;
    double radius = 5000;
    std::string adrMethod = "ADRopt";

    CommandLine cmd(__FILE__);
    cmd.AddValue("appPeriod", "Application period in seconds", appPeriod);
    cmd.AddValue("nPeriods", "Number of application periods for simulation time", nPeriods);
    cmd.AddValue("nDevices", "Number of end devices", nDevices);
    cmd.AddValue("nGateways", "Number of gateways", nGateways);
    cmd.AddValue("radius", "Radius for gateway placement (meters)", radius);
    cmd.AddValue("adrMethod", "ADR method (e.g., ADRopt, AVERAGE, MAXIMUM)", adrMethod);
    cmd.Parse(argc, argv);

    Time simTimeLimit = Seconds(appPeriod * nPeriods + 10);
    Time stateSamplePeriod = Seconds(appPeriod);
    // --- Node and Mobility Setup ---
    NodeContainer endDevice, gateway, networkServer;
    endDevice.Create(nDevices);
    gateway.Create(nGateways);
    networkServer.Create(1);

    MobilityHelper mobility;
    Ptr<ListPositionAllocator> allocator = CreateObject<ListPositionAllocator>();
    for (int i = 0; i < nDevices; ++i) {
        double angle = 2 * M_PI * i / nDevices;
        double x = radius * cos(angle);
        double y = radius * sin(angle);
        allocator->Add(Vector(x, y, 1.5));
    }
    for (int i = 0; i < nGateways; ++i) {
        double angle = 2 * M_PI * i / nGateways;
        double x = radius / 2 * cos(angle);
        double y = radius / 2 * sin(angle);
        allocator->Add(Vector(x, y, 15));
    }
    allocator->Add(Vector(0, 0, 15)); // network server
    mobility.SetPositionAllocator(allocator);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(endDevice);
    mobility.Install(gateway);
    mobility.Install(networkServer);

    // --- LoRaWAN Setup ---
    Ptr<LogDistancePropagationLossModel> loss = CreateObject<LogDistancePropagationLossModel>();
    loss->SetPathLossExponent(3.76);
    loss->SetReference(1, 7.7);
    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay);


    LoraHelper loraHelper;
    loraHelper.EnablePacketTracking();
    LoraPhyHelper phyHelper;
    phyHelper.SetChannel(channel);

    LorawanMacHelper macHelper;
    macHelper.SetRegion(LorawanMacHelper::EU); // Corect, enum (vezi headerul tău!)

    // End Devices
    phyHelper.SetDeviceType(LoraPhyHelper::ED);
    macHelper.SetDeviceType(LorawanMacHelper::ED_A);
    loraHelper.Install(phyHelper, macHelper, endDevice);

    // Gateways
    phyHelper.SetDeviceType(LoraPhyHelper::GW);
    macHelper.SetDeviceType(LorawanMacHelper::GW);
    loraHelper.Install(phyHelper, macHelper, gateway);

    // P2P Links
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue("100Mbps"));
    p2p.SetChannelAttribute("Delay", StringValue("2ms"));
    for (uint32_t i = 0; i < gateway.GetN(); ++i) {
        p2p.Install(networkServer.Get(0), gateway.Get(i));
    }

    // Network server
    NetworkServerHelper nsHelper;
    nsHelper.EnableAdr(true);
    nsHelper.SetAdr("ns3::lorawan::ADRoptComponent");
    nsHelper.SetEndDevices(endDevice);
    nsHelper.Install(networkServer.Get(0));

    // Forwarder
    ForwarderHelper forwarderHelper;
    forwarderHelper.Install(gateway);

    // App
    PeriodicSenderHelper appHelper;
    appHelper.SetPeriod(Seconds(appPeriod));
    appHelper.SetPacketSize(10);
    ApplicationContainer endDeviceApp = appHelper.Install(endDevice);

    // Trace
    for (uint32_t i = 0; i < endDeviceApp.GetN(); ++i) {
        Ptr<Application> app = endDeviceApp.Get(i);
        uint32_t deviceId = endDevice.Get(i)->GetId();
        app->TraceConnectWithoutContext(
            "Tx",
            Callback<void, Ptr<const Packet>>(
                [deviceId](Ptr<const Packet> packet) {
                    NS_LOG_INFO("PACKET_SENT: EndDevice " << deviceId << " sent packet with UID " << packet->GetUid());
                }
            )
        );
    }
    loraHelper.EnablePeriodicDeviceStatusPrinting(endDevice, gateway, "nodeData.txt", stateSamplePeriod);
    loraHelper.EnablePeriodicPhyPerformancePrinting(gateway, "phyPerformance.txt", stateSamplePeriod);
    loraHelper.EnablePeriodicGlobalPerformancePrinting("globalPerformance.txt", stateSamplePeriod);

    endDeviceApp.Start(Seconds(1));
    endDeviceApp.Stop(simTimeLimit);

    LogComponentEnable("ADRoptComponent", LOG_LEVEL_ALL);
    LogComponentEnable("NetworkServer", LOG_LEVEL_INFO);
    LogComponentEnable("AdrOptSimulation", LOG_LEVEL_INFO);

    Simulator::Stop(simTimeLimit);
    Simulator::Run();
    Simulator::Destroy();

    return 0;
}
