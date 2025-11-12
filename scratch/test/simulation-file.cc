// Complete simulation with both LogDistance and Okumura-Hata support 
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-helper.h"
#include "ns3/lora-helper.h"
#include "ns3/lora-phy-helper.h"
#include "ns3/lorawan-mac-helper.h"
#include "ns3/periodic-sender-helper.h"
#include "ns3/network-server-helper.h"
#include "ns3/forwarder-helper.h"
#include "ns3/log.h"
#include "ns3/command-line.h"
#include "ns3/point-to-point-helper.h"
#include "ns3/class-a-end-device-lorawan-mac.h"
#include "ns3/end-device-lora-phy.h"
#include "ns3/gateway-lora-phy.h"
#include "ns3/propagation-loss-model.h"
#include "ns3/okumura-hata-propagation-loss-model.h"
#include "ns3/correlated-shadowing-propagation-loss-model.h"
#include "ns3/propagation-environment.h" 
#include "ns3/energy-module.h"
#include "ns3/basic-energy-source-helper.h"
#include "ns3/lora-radio-energy-model-helper.h"
#include "ns3/wifi-utils.h"
#include <fstream>
#include <regex> 
#include <iterator>
#include <cmath>
using namespace ns3;
using namespace lorawan; 
using namespace ns3::energy;
NS_LOG_COMPONENT_DEFINE("SimulationFile"); 

// CONFIGURATION STRUCT

struct SimulationParameters
{
    // Timing
    double totalTimeToBeSimulated = 60*100;
    double timeBetweenPackets = 60*10;
    double timeToFirstPacket = 60*10;
    int packetSize = 20;
    bool verbosity = false; 
    // Mobility
    std::string mobilityModel = "ConstantPositionMobilityModel";
    bool useShadowing = false; 
    // Positions
    double distanceBetweenNodes = 100.0;
    double initialEDPositionX = 100.0;
    double initialEDPositionY = 0.0;
    double initialEDPositionZ = 1.0;
    double initialGWPositionX = 0.0;
    double initialGWPositionY = 0.0;
    double initialGWPositionZ = 24.0; 
    
    // LoRa Parameters
    int initialSF = 7;
    int initialTP = 14; 

    // Energy Model Parameters (defaults match FLORA XML units where noted)
    double supplyVoltage = 3.3; // V (FLORA: supplyVoltage)
    double receiverReceivingSupplyCurrent = 9.7; // mA (FLORA units)
    double receiverBusySupplyCurrent = 9.7; // mA (FLORA units)
    double idleSupplyCurrent = 0.0001; // mA (FLORA units)

    // --- ns-3 friendly / legacy names (units in A where appropriate) ---
    double supply_voltage_v = 3.3;       // V
    double initial_energy_j = 10000.0;   // J
    double update_interval_s = 3600;     // s
    double rx_current_a = 0.0097;        // A
    double sleep_current_a = 0.0000015;  // A
    double idle_current_a = 0.0001;      // A (note: user-configurable)
    double tx_model_eta = 0.10;          // unitless
    double tx_model_standby_a = 0.0001;  // A
    // Per-tx-power mapping (mA in XML -> stored as A)
    std::map<int, double> tx_supply_currents_a; // key: txPower(dBm), value: A

    // Propagation Model Selection
    enum PropagationModelType
    {
        LOG_DISTANCE = 0,
        OKUMURA_HATA = 1
    };
    PropagationModelType propagationModel = LOG_DISTANCE; 
    // LogDistance Parameters
    double pathLossExponent = 3.76;
    double referenceDistance = 1.0;
    double referenceLoss = 7.7; 
    // Okumura-Hata Parameters
    double frequencyHz = 868e6;  // 868 MHz for LoRa
    int environment = 0;         // 0=Urban, 1=SubUrban, 2=OpenAreas
    int citySize = 2;            // 0=Small, 1=Medium, 2=Large 
    // Network
    int nDevices = 1;
    int nGateways = 1; 
    // Cloud/Backhaul
    std::string cloudBackhaulDataRate = "1Gbps";
    std::string cloudBackhaulDelay = "10ms"; 
    // Output
    std::string outputFile = "results.csv";
    // Energy config file path (optional)
    std::string energyConfigPath = "energyConsumptionParameters.xml";
}; 

// Load energy parameters from a FLORA XML file (simple, robust parser)
static void
LoadEnergyConfigFromXml(const std::string& path, SimulationParameters& params)
{
    std::ifstream in(path);
    if (!in)
    {
        NS_LOG_INFO("Energy config not found: " << path);
        return;
    }

    std::string content((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    std::smatch m;

    // supplyVoltage
    std::regex rSupply(R"(<supplyVoltage\s+value\s*=\s*\"([0-9+\-\.eE]+)\"))");
    if (std::regex_search(content, m, rSupply))
    {
        params.supplyVoltage = std::stod(m[1].str());
        params.supply_voltage_v = params.supplyVoltage;
    }

    // receiverReceivingSupplyCurrent (mA)
    std::regex rRx(R"(<receiverReceivingSupplyCurrent\s+value\s*=\s*\"([0-9+\-\.eE]+)\"))");
    if (std::regex_search(content, m, rRx))
    {
        double v = std::stod(m[1].str());
        params.receiverReceivingSupplyCurrent = v; // mA as in FLORA
        params.rx_current_a = v / 1000.0;         // convert to A
    }

    // receiverBusySupplyCurrent (mA)
    std::regex rBusy(R"(<receiverBusySupplyCurrent\s+value\s*=\s*\"([0-9+\-\.eE]+)\"))");
    if (std::regex_search(content, m, rBusy))
    {
        params.receiverBusySupplyCurrent = std::stod(m[1].str());
    }

    // idleSupplyCurrent (mA)
    std::regex rIdle(R"(<idleSupplyCurrent\s+value\s*=\s*\"([0-9+\-\.eE]+)\"))");
    if (std::regex_search(content, m, rIdle))
    {
        double v = std::stod(m[1].str());
        params.idleSupplyCurrent = v;         // mA
        params.idle_current_a = v / 1000.0;   // A
        params.tx_model_standby_a = params.idle_current_a;
        params.sleep_current_a = params.idle_current_a;
    }

    // txSupplyCurrent entries (txPower -> supplyCurrent) (mA -> A)
    std::regex rTx(R"(<txSupplyCurrent\s+txPower\s*=\s*\"([0-9]+)\"\s+supplyCurrent\s*=\s*\"([0-9+\-\.eE]+)\"))");
    auto begin = std::sregex_iterator(content.begin(), content.end(), rTx);
    auto end = std::sregex_iterator();
    std::vector<std::pair<int, double>> vec;
    for (auto it = begin; it != end; ++it)
    {
        int tp = std::stoi((*it)[1].str());
        double sc_mA = std::stod((*it)[2].str());
        double sc_A = sc_mA / 1000.0;
        params.tx_supply_currents_a[tp] = sc_A;
        vec.emplace_back(tp, sc_A);
    }

    // If we have at least two points, fit a linear-PA model (eta + standby) so the LinearLoraTxCurrentModel
    // reproduces the FLORA measurements (best-effort). Fall back to default otherwise.
    if (vec.size() >= 2)
    {
        auto minmax = std::minmax_element(vec.begin(), vec.end(), [](auto &a, auto &b) { return a.first < b.first; });
        auto p1 = *minmax.first;
        auto p2 = *minmax.second;
        double W1 = DbmToW((double)p1.first);
        double W2 = DbmToW((double)p2.first);
        double I1 = p1.second;
        double I2 = p2.second;
        double denom = (I2 - I1);
        if (denom != 0.0)
        {
            double eta = (W2 - W1) / (params.supply_voltage_v * denom);
            if (eta <= 0.0 || std::isnan(eta) || std::isinf(eta))
            {
                eta = params.tx_model_eta;
            }
            double standby = I1 - W1 / (params.supply_voltage_v * eta);
            params.tx_model_eta = eta;
            params.tx_model_standby_a = standby;
        }
    }
    else if (vec.size() == 1)
    {
        auto p = vec.front();
        double W = DbmToW((double)p.first);
        double I = p.second;
        double eta = params.tx_model_eta;
        double standby = I - W / (params.supply_voltage_v * eta);
        params.tx_model_eta = eta;
        params.tx_model_standby_a = standby;
    }
}

// CSV OUTPUT FUNCTION

void WriteResultsToCSV(const std::string& filename,
                       const SimulationParameters& params,
                       uint32_t sent,
                       uint32_t received,
                       double plr,
                       double der)
{
    std::ofstream outfile;
    bool fileExists = std::ifstream(filename).good();
    
    outfile.open(filename, std::ios::app);
    
    if (!outfile.is_open())
    {
        NS_LOG_ERROR("Could not open output file: " << filename);
        return;
    }
    
    if (!fileExists)
    {
        outfile << "distance,sf,tp,sent,received,plr,der" << std::endl;
    }
    
    outfile << params.distanceBetweenNodes << ","
            << params.initialSF << ","
            << params.initialTP << ","
            << sent << ","
            << received << ","
            << plr << ","
            << der << std::endl;
    
    outfile.close();
    
    NS_LOG_INFO("Results written to: " << filename);
} 

// PARSE PACKET TRACKER OUTPUT
void ParsePacketTrackerOutput(const std::string& output, uint32_t& sent, uint32_t& received)
{
    sent = 0;
    received = 0;

    try {
        // Adjusted regex to match two floating-point numbers
        std::regex packetCountsRegex(R"(\s*([0-9]+\.[0-9]+)\s+([0-9]+\.[0-9]+)\s*)");

        std::smatch match;
        if (std::regex_search(output, match, packetCountsRegex)) {
            // Convert the floating-point values to integers (by truncating them)
            sent = static_cast<uint32_t>(std::stof(match[1].str()));
            received = static_cast<uint32_t>(std::stof(match[2].str()));
        }

        // Fallback if regex does not match (shouldn't happen now)
        if (sent == 0 && received == 0) {
            std::regex numRegex("([0-9]+)");
            auto begin = std::sregex_iterator(output.begin(), output.end(), numRegex);
            auto end = std::sregex_iterator();
            std::vector<uint32_t> nums;
            for (auto it = begin; it != end; ++it) {
                nums.push_back(static_cast<uint32_t>(std::stoul((*it)[1].str())));
            }
            if (nums.size() >= 2) {
                sent = nums[0];
                received = nums[1];
            } else if (nums.size() == 1) {
                // If only one number is present, treat it as both sent and received
                sent = nums[0];
                received = nums[0];
            }
        }
    } catch (const std::exception& e) {
        NS_LOG_ERROR("Failed to parse packet tracker output: " << e.what());
    } catch (...) {
        NS_LOG_ERROR("Failed to parse packet tracker output");
    }
}


void OnPacketReceived(Ptr<const Packet> packet) {
    NS_LOG_UNCOND("✓ GATEWAY MAC RECEIVED PACKET - ID: " << packet->GetUid());
} 

// MAIN

int main(int argc, char* argv[])
{
    // =========================================================================
    // 1. INITIALIZE CONFIGURATION
    // =========================================================================
    SimulationParameters params;
    
    // Use int for command line parsing (enums don't work)
    int propagationModelInt = static_cast<int>(params.propagationModel);
    
    CommandLine cmd(__FILE__);
    cmd.AddValue("distanceBetweenNodes", "Distance between ED and GW (m)", params.distanceBetweenNodes);
    cmd.AddValue("initialSF", "Spreading Factor (7-12)", params.initialSF);
    cmd.AddValue("initialTP", "Transmission Power (dBm)", params.initialTP);
    cmd.AddValue("propagationModel", "Model (0=LogDistance, 1=OkumuraHata)", propagationModelInt);
    cmd.AddValue("verbosity", "Enable verbose logging", params.verbosity);
    cmd.AddValue("simTime", "Simulation time (s)", params.totalTimeToBeSimulated);
    cmd.AddValue("outputFile", "Output CSV filename", params.outputFile);
    cmd.AddValue("pathLossExponent", "Path loss exponent (LogDistance)", params.pathLossExponent);
    cmd.AddValue("frequencyHz", "Frequency in Hz (OkumuraHata)", params.frequencyHz);
    cmd.AddValue("environment", "Environment (0=Urban,1=SubUrban,2=OpenAreas)", params.environment);
    cmd.AddValue("citySize", "City size (0=Small,1=Medium,2=Large)", params.citySize);
    cmd.AddValue("energyConfigXml", "Path to FLORA energyConsumptionParameters.xml", params.energyConfigPath);
    cmd.Parse(argc, argv); 
    // Convert int back to enum
    params.propagationModel = static_cast<SimulationParameters::PropagationModelType>(propagationModelInt); 
    // Update end device X position based on distance
    params.initialEDPositionX = params.distanceBetweenNodes; 
    // Load energy config from XML if provided
    if (!params.energyConfigPath.empty())
    {
        LoadEnergyConfigFromXml(params.energyConfigPath, params);
    }
    // Enable logging if verbose
    if (params.verbosity)
    {
        LogComponentEnable("SimulationFile", LOG_LEVEL_ALL);
    } 
    // Set random seed
    RngSeedManager::SetSeed(1);
    RngSeedManager::SetRun(1); 
    // Configuration logging only in verbose mode
    if (params.verbosity) {
        NS_LOG_INFO("Distance: " << params.distanceBetweenNodes << "m");
        NS_LOG_INFO("SF: " << params.initialSF);
        NS_LOG_INFO("TP: " << params.initialTP << " dBm");
        NS_LOG_INFO("Model: " << (params.propagationModel == SimulationParameters::LOG_DISTANCE ? "LogDistance" : "OkumuraHata"));
    } 
    // =========================================================================
    // 2. CREATE THE CHANNEL
    // ========================================================================= 
    Ptr<PropagationLossModel> loss;
    
    if (params.propagationModel == SimulationParameters::LOG_DISTANCE)
    {
        // LogDistance model
        Ptr<LogDistancePropagationLossModel> logLoss = 
            CreateObject<LogDistancePropagationLossModel>();
        logLoss->SetPathLossExponent(params.pathLossExponent);
        logLoss->SetReference(params.referenceDistance, params.referenceLoss);
        loss = logLoss;
    }
    else
    {
        // Okumura-Hata model
        Ptr<OkumuraHataPropagationLossModel> okumuraLoss = 
            CreateObject<OkumuraHataPropagationLossModel>();
        
        // Set frequency
        okumuraLoss->SetAttribute("Frequency", DoubleValue(params.frequencyHz));
        
        // Set environment (using proper enum values from propagation-environment.h)
        if (params.environment == 0)
        {
            okumuraLoss->SetAttribute("Environment", EnumValue(UrbanEnvironment));
        }
        else if (params.environment == 1)
        {
            okumuraLoss->SetAttribute("Environment", EnumValue(SubUrbanEnvironment));
        }
        else
        {
            okumuraLoss->SetAttribute("Environment", EnumValue(OpenAreasEnvironment));
        }
        
        // Set city size (using proper enum values)
        if (params.citySize == 0)
        {
            okumuraLoss->SetAttribute("CitySize", EnumValue(SmallCity));
        }
        else if (params.citySize == 1)
        {
            okumuraLoss->SetAttribute("CitySize", EnumValue(MediumCity));
        }
        else
        {
            okumuraLoss->SetAttribute("CitySize", EnumValue(LargeCity));
        }
        
        loss = okumuraLoss;
    } 
    // Add shadowing if enabled
    if (params.useShadowing)
    {
        Ptr<CorrelatedShadowingPropagationLossModel> shadowing =
            CreateObject<CorrelatedShadowingPropagationLossModel>();
        loss->SetNext(shadowing);
    } 
    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay); 
    // =========================================================================
    // 3. CREATE HELPERS
    // ========================================================================= 
    LoraPhyHelper phyHelper = LoraPhyHelper();
    phyHelper.SetChannel(channel); 
    LorawanMacHelper macHelper = LorawanMacHelper();
    LoraHelper helper = LoraHelper();
    helper.EnablePacketTracking(); 
    NetworkServerHelper nsHelper = NetworkServerHelper();
    ForwarderHelper forHelper = ForwarderHelper(); 
    BasicEnergySourceHelper basicSourceHelper;
    LoraRadioEnergyModelHelper radioEnergyHelper;
    
    // =========================================================================
    // 4. CREATE END DEVICES
    // ========================================================================= 
    NodeContainer endDevices;
    endDevices.Create(params.nDevices); 
    MobilityHelper mobility;
    mobility.SetMobilityModel("ns3::" + params.mobilityModel); 
    Ptr<ListPositionAllocator> edAllocator = CreateObject<ListPositionAllocator>();
    edAllocator->Add(Vector(params.initialEDPositionX, 
                           params.initialEDPositionY, 
                           params.initialEDPositionZ));
    mobility.SetPositionAllocator(edAllocator);
    mobility.Install(endDevices); 
    phyHelper.SetDeviceType(LoraPhyHelper::ED);
    macHelper.SetDeviceType(LorawanMacHelper::ED_A); 
    uint8_t nwkId = 54;
    uint32_t nwkAddr = 1864;
    Ptr<LoraDeviceAddressGenerator> addrGen =
        CreateObject<LoraDeviceAddressGenerator>(nwkId, nwkAddr);
    macHelper.SetAddressGenerator(addrGen); 
    NetDeviceContainer endDevicesNetDevices = helper.Install(phyHelper, macHelper, endDevices); 
    // Configure SF and TP via EndDeviceLorawanMac
    for (uint32_t i = 0; i < endDevices.GetN(); ++i)
    {
        Ptr<Node> node = endDevices.Get(i);
        Ptr<LoraNetDevice> loraNetDevice = node->GetDevice(0)->GetObject<LoraNetDevice>();
        Ptr<EndDeviceLorawanMac> mac = loraNetDevice->GetMac()->GetObject<EndDeviceLorawanMac>();
        
        // Set Spreading Factor (Data Rate = 12 - SF)
        mac->SetDataRate(12 - params.initialSF);
        
        // Set Transmission Power using the correct method name
        mac->SetTransmissionPowerDbm(params.initialTP);
    } 
    // =========================================================================
    // 5. CREATE GATEWAY
    // ========================================================================= 
    NodeContainer gateways;
    gateways.Create(params.nGateways); 
    Ptr<ListPositionAllocator> gwAllocator = CreateObject<ListPositionAllocator>();
    gwAllocator->Add(Vector(params.initialGWPositionX, 
                           params.initialGWPositionY, 
                           params.initialGWPositionZ));
    mobility.SetPositionAllocator(gwAllocator);
    mobility.Install(gateways); 
    phyHelper.SetDeviceType(LoraPhyHelper::GW);
    macHelper.SetDeviceType(LorawanMacHelper::GW); 

    NetDeviceContainer gatewaysNetDevices = helper.Install(phyHelper, macHelper, gateways); 
    // ADD THIS: Verify gateway MAC is correctly set up
    for (uint32_t i = 0; i < gateways.GetN(); ++i)
    {
        Ptr<Node> gwNode = gateways.Get(i);
        Ptr<LoraNetDevice> loraNetDevice = gwNode->GetDevice(0)->GetObject<LoraNetDevice>();
        Ptr<GatewayLorawanMac> gwMac = loraNetDevice->GetMac()->GetObject<GatewayLorawanMac>();
        
        NS_ASSERT_MSG(gwMac != nullptr, "Gateway MAC is null!");
        
        gwMac->TraceConnectWithoutContext("ReceivedPacket", MakeCallback(&OnPacketReceived));
    }
    // =========================================================================
    // 6. INSTALL APPLICATIONS
    // ========================================================================= 
    PeriodicSenderHelper appHelper = PeriodicSenderHelper();
    appHelper.SetPeriod(Seconds(params.timeBetweenPackets));
    appHelper.SetPacketSize(params.packetSize); 
    ApplicationContainer appContainer = appHelper.Install(endDevices); 
    Time simulationTime = Seconds(params.totalTimeToBeSimulated);
    appContainer.Start(Seconds(params.timeToFirstPacket));
    appContainer.Stop(simulationTime); 

    // =========================================================================
    // 7. INSTALL ENERGY MODELS
    // =========================================================================
    // Configure energy source
    basicSourceHelper.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(params.initial_energy_j));
    basicSourceHelper.Set("BasicEnergySupplyVoltageV", DoubleValue(params.supply_voltage_v));

    // Configure radio energy model
    radioEnergyHelper.Set("StandbyCurrentA", DoubleValue(params.idle_current_a));
    radioEnergyHelper.Set("RxCurrentA", DoubleValue(params.rx_current_a));
    radioEnergyHelper.Set("SleepCurrentA", DoubleValue(params.sleep_current_a));

    // Set TX current model - Linear model
    radioEnergyHelper.SetTxCurrentModel("ns3::LinearLoraTxCurrentModel",
                                        "Eta", DoubleValue(params.tx_model_eta),
                                        "Voltage", DoubleValue(params.supply_voltage_v),
                                        "StandbyCurrent", DoubleValue(params.tx_model_standby_a));

    // Install energy source on end devices
    energy::EnergySourceContainer sources = basicSourceHelper.Install(endDevices);

    // Install device energy model
    DeviceEnergyModelContainer deviceModels = 
        radioEnergyHelper.Install(endDevicesNetDevices, sources);

    // =========================================================================
    // 8. CREATE NETWORK SERVER
    // ========================================================================= 
    Ptr<Node> networkServer = CreateObject<Node>(); 
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue(params.cloudBackhaulDataRate));
    p2p.SetChannelAttribute("Delay", StringValue(params.cloudBackhaulDelay)); 
    P2PGwRegistration_t gwRegistration;
    for (auto gw = gateways.Begin(); gw != gateways.End(); ++gw)
    {
        auto container = p2p.Install(networkServer, *gw);
        auto serverP2PNetDev = DynamicCast<PointToPointNetDevice>(container.Get(0));
        gwRegistration.emplace_back(serverP2PNetDev, *gw);
    } 
    nsHelper.SetGatewaysP2P(gwRegistration);
    nsHelper.SetEndDevices(endDevices);
    nsHelper.Install(networkServer); 
    forHelper.Install(gateways); 
    // After gateway installation
    for (uint32_t i = 0; i < gateways.GetN(); ++i)
    {
        Ptr<Node> gwNode = gateways.Get(i);
        Ptr<LoraNetDevice> loraNetDevice = gwNode->GetDevice(0)->GetObject<LoraNetDevice>();
        Ptr<GatewayLoraPhy> gwPhy = loraNetDevice->GetPhy()->GetObject<GatewayLoraPhy>();
        Ptr<GatewayLorawanMac> gwMac = loraNetDevice->GetMac()->GetObject<GatewayLorawanMac>();
        
        NS_ASSERT_MSG(gwPhy != nullptr, "Gateway PHY is null!");
        NS_ASSERT_MSG(gwMac != nullptr, "Gateway MAC is null!");
        NS_ASSERT_MSG(gwPhy->GetDevice() == loraNetDevice, "PHY not linked to device!");
        NS_ASSERT_MSG(gwMac->GetPhy() == gwPhy, "MAC not linked to PHY!");
    } 
    
    macHelper.SetRegion(LorawanMacHelper::EU); 
    // =========================================================================
    // 9. RUN SIMULATION
    // =========================================================================
    Simulator::Stop(simulationTime + Minutes(10)); 
    Simulator::Run(); 
    // =========================================================================
    // 10. SAVE AND PRINT RESULTS
    // =========================================================================
    LoraPacketTracker& tracker = helper.GetPacketTracker(); 
    // Get packet counts - parse string output
    std::string packetCountsStr = tracker.CountMacPacketsGlobally(Seconds(0), simulationTime);
    
    uint32_t sent = 0;
    uint32_t received = 0;
    ParsePacketTrackerOutput(packetCountsStr, sent, received);
    
    double plr = (sent > 0) ? (1.0 - (double)received / sent) * 100.0 : 0.0;
    double der = (sent > 0) ? (double)received / sent : 0.0; 
    WriteResultsToCSV(params.outputFile, params, sent, received, plr, der); 
    
    Simulator::Destroy(); 
    return 0;
}