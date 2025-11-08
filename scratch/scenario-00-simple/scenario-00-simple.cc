#include "../common/scenario_config.h"
#include "../common/paths.h"
#include "../common/logging.h"
#include "../common/traces.h"
#include "../common/energy_setup.h"
#include "../common/lora_setup.h"
#include "../common/app_simple_sender.h"
#include "../common/periodic_logger.h"

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/internet-module.h"
#include "ns3/lorawan-module.h"
#include "ns3/log.h"

using namespace ns3;
using namespace ns3::lorawan;
using namespace scenario;

NS_LOG_COMPONENT_DEFINE("Scenario00Simple");

int main(int argc, char* argv[]) {
    // Parse command line and load config
    auto& config = scenario::ScenarioConfig::Get();
    config.ParseCommandLine(argc, argv);
    config.DumpConfig(OutPath("init_config.log"));
    
    // Enable logging
    LogComponentEnable("Scenario00Simple",
        static_cast<LogLevel>(LOG_PREFIX_TIME | LOG_PREFIX_NODE | LOG_LEVEL_INFO));
    
    // Create nodes
    NodeContainer gateways;      gateways.Create(1);
    NodeContainer endDevices;    endDevices.Create(1);
    NodeContainer networkServer; networkServer.Create(1);
    
    // Setup mobility
    MobilityHelper mob;
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(gateways);
    mob.Install(endDevices);
    mob.Install(networkServer);
    
    gateways.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 15.0));
    endDevices.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(config.gw_ed_distance_m, 0.0, 1.5));
    networkServer.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 15.0));
    
    NS_LOG_INFO("GW-ED distance = " << config.gw_ed_distance_m << " m");
    
    // Create LoRa network
    auto loraDevices = LoraSetup::CreateLoraNetwork(gateways, endDevices);
    
    // Store propagation model reference for trace callbacks
    TraceCallbacks::SetPropagationModel(loraDevices.propagationModel, 
                                    gateways, endDevices);
    
    // Open CSV files for energy traces
    CsvLogger::OpenEnergyCsvs();
    
    // Open packet-level summary CSV
    std::string scenario_name = "baseline";
    if (config.gw_ed_distance_m != 500.0) {
        scenario_name = "dist" + std::to_string(static_cast<int>(config.gw_ed_distance_m));
    }
    ns3::RngSeedManager::SetSeed(1);
    ns3::RngSeedManager::SetRun(0);
    int seed = ns3::RngSeedManager::GetRun();
    CsvLogger::OpenPacketSummaryCsv(scenario_name, seed);
    CsvLogger::OpenDutyCsv(scenario_name, seed); 
    
    // Install energy models
    auto energySources = EnergySetup::InstallEnergyModels(endDevices, loraDevices.edDevs);
    
    // Start periodic logging every 1 second
    PeriodicLogger::StartPeriodicLogging(1.0, config.sim_time_s, energySources);

    // Configure and connect traces
    LoraSetup::ConnectTraces(loraDevices.gwDevs, loraDevices.edDevs);
    
    // Setup Network Server
    auto nsApps = LoraSetup::SetupNetworkServer(networkServer, gateways, endDevices, loraDevices.gwDevs);
    
    // Create and configure application
    Ptr<LoraNetDevice> edNd = DynamicCast<LoraNetDevice>(loraDevices.edDevs.Get(0));
    Ptr<SimpleSender> app = CreateObject<SimpleSender>();
    
    app->Configure(edNd,
                  config.n_pkts_to_send,
                  Seconds(10.0),
                  Seconds(config.fixed_period_s),
                  config.use_exponential_iat,
                  config.exp_iat_mean_s);
    
    endDevices.Get(0)->AddApplication(app);
    app->SetStartTime(Seconds(0));
    app->SetStopTime(Seconds(config.sim_time_s));
    
    // Enable periodic performance printing
    loraDevices.loraHelper.EnablePeriodicGlobalPerformancePrinting(
        OutPath(config.global_performance_file), Seconds(1));
    loraDevices.loraHelper.EnablePeriodicPhyPerformancePrinting(
        gateways, OutPath(config.phy_performance_file), Seconds(1));
    loraDevices.loraHelper.EnablePeriodicDeviceStatusPrinting(
        endDevices, gateways, OutPath(config.device_status_file), Seconds(1));
    
    // Disable verbose energy source logging
    LogComponentEnable("BasicEnergySource", LOG_LEVEL_ERROR);
    LogComponentEnable("SimpleDeviceEnergyModel", LOG_LEVEL_ERROR);
    
    // Enable component logging as per original
    LogComponentEnable("EndDeviceLorawanMac", LOG_LEVEL_INFO);
    LogComponentEnable("ClassAEndDeviceLorawanMac", LOG_LEVEL_INFO);
    LogComponentEnable("LoraPhy", LOG_LEVEL_INFO);
    LogComponentEnable("EndDeviceLoraPhy", LOG_LEVEL_INFO);
    LogComponentEnable("GatewayLoraPhy", LOG_LEVEL_INFO);
    LogComponentEnable("LoraChannel", LOG_LEVEL_INFO);
    
    // Run simulation
    Simulator::Stop(Seconds(config.sim_time_s));
    Simulator::Run();
    
    // Print final statistics
    LoraPacketTracker& tracker = loraDevices.loraHelper.GetPacketTracker();
    NS_LOG_INFO("=== Final Statistics ===");
    
    std::string globalStats = tracker.CountMacPacketsGlobally(Seconds(0), Seconds(config.sim_time_s));
    NS_LOG_INFO("Global MAC performance: " << globalStats);
    
    for (auto gw = gateways.Begin(); gw != gateways.End(); ++gw) {
        int gwId = (*gw)->GetId();
        std::string phyStats = tracker.PrintPhyPacketsPerGw(Seconds(0), Seconds(config.sim_time_s), gwId);
        NS_LOG_INFO("Gateway " << gwId << " PHY stats: " << phyStats);
    }
    
    // Cleanup
    CsvLogger::CloseEnergyCsvs();
    CsvLogger::CloseSnrCsv();
    CsvLogger::ClosePacketDetailsCsv();
    CsvLogger::ClosePacketSummaryCsv();
    CsvLogger::CloseDutyCsv();
    Simulator::Destroy();

    return 0;
}