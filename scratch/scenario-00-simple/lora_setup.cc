#include "../common/lora_setup.h"
#include "../common/scenario_config.h"
#include "../common/traces.h"
#include "ns3/mobility-helper.h"
#include "ns3/lorawan-module.h"
#include "ns3/gateway-lora-phy.h"
#include "ns3/gateway-lorawan-mac.h"
#include "ns3/network-server.h"
#include "ns3/lora-interference-helper.h"
#include "ns3/okumura-hata-propagation-loss-model.h"
#include "ns3/propagation-loss-model.h"
#include "ns3/propagation-delay-model.h"
#include "ns3/point-to-point-module.h"
#include "ns3/log.h"

NS_LOG_COMPONENT_DEFINE("LoraSetup");

namespace scenario {

bool LoraSetup::HasAttribute(ns3::Ptr<ns3::Object> obj, const std::string& name) {
    if (!obj) return false;
    ns3::TypeId tid = obj->GetInstanceTypeId();
    for (uint32_t k = 0; k < tid.GetAttributeN(); ++k) {
        auto info = tid.GetAttribute(k);
        if (name == info.name) return true;
    }
    return false;
}

void LoraSetup::SetDoubleAttrIfPresent(ns3::Ptr<ns3::Object> obj, 
                                       const std::string& name, double value) {
    if (!obj) return;
    ns3::TypeId tid = obj->GetInstanceTypeId();
    for (uint32_t k = 0; k < tid.GetAttributeN(); ++k) {
        if (name == tid.GetAttribute(k).name) {
            obj->SetAttribute(name, ns3::DoubleValue(value));
            NS_LOG_INFO("Set attribute " << name << " = " << value);
            return;
        }
    }
    NS_LOG_INFO("Attribute " << name << " not found on " << tid.GetName());
}

void LoraSetup::SetTimeAttrIfPresent(ns3::Ptr<ns3::Object> obj, 
                                     const std::string& name, ns3::Time value) {
    if (!obj) return;
    ns3::TypeId tid = obj->GetInstanceTypeId();
    for (uint32_t k = 0; k < tid.GetAttributeN(); ++k) {
        if (name == tid.GetAttribute(k).name) {
            obj->SetAttribute(name, ns3::TimeValue(value));
            NS_LOG_INFO("Set attribute " << name << " = " << value.GetSeconds() << " s");
            return;
        }
    }
    NS_LOG_INFO("Attribute " << name << " not found on " << tid.GetName());
}

void LoraSetup::SetBoolAttrIfPresent(ns3::Ptr<ns3::Object> obj, 
                                     const std::string& name, bool value) {
    if (HasAttribute(obj, name)) {
        obj->SetAttribute(name, ns3::BooleanValue(value));
        NS_LOG_INFO("Set attribute " << name << " = " << (value ? "true" : "false"));
    } else {
        NS_LOG_INFO("Attribute " << name << " not found on " << obj->GetInstanceTypeId().GetName());
    }
}

void LoraSetup::DumpAttributes(ns3::Ptr<ns3::Object> obj, const char* label) {
    if (!obj) return;
    ns3::TypeId tid = obj->GetInstanceTypeId();
    NS_LOG_INFO(std::string("Attributes of ") + label + " (" + tid.GetName() + "):");
    for (uint32_t i = 0; i < tid.GetAttributeN(); ++i) {
        const auto info = tid.GetAttribute(i);
        NS_LOG_INFO("  - " << info.name);
    }
}

ns3::Ptr<ns3::PropagationLossModel> LoraSetup::CreatePropagationModel() {
    using namespace ns3;
    auto& config = ScenarioConfig::Get();
    
    Ptr<PropagationLossModel> loss;
    
    if (config.use_friis_model) {
        NS_LOG_INFO("Using Friis (Free Space) propagation model");
        loss = CreateObject<FriisPropagationLossModel>();
        
    } else if (config.use_okumura_hata_model) {
        NS_LOG_INFO("Using Okumura-Hata propagation model");
        Ptr<OkumuraHataPropagationLossModel> okumuraLoss = CreateObject<OkumuraHataPropagationLossModel>();
        okumuraLoss->SetAttribute("Frequency", DoubleValue(config.okumura_frequency_mhz * 1e6));
        
        if (config.okumura_urban_environment) {
            okumuraLoss->SetAttribute("Environment", EnumValue(ns3::UrbanEnvironment));
        } else {
            okumuraLoss->SetAttribute("Environment", EnumValue(ns3::SubUrbanEnvironment));
        }
        okumuraLoss->SetAttribute("CitySize", EnumValue(ns3::SmallCity));
        loss = okumuraLoss;
        
    } else {
        NS_LOG_INFO("Using Log-Distance propagation model with gamma=" << config.gamma_path_loss_exponent);
        Ptr<LogDistancePropagationLossModel> logLoss = CreateObject<LogDistancePropagationLossModel>();
        logLoss->SetAttribute("Exponent", DoubleValue(config.gamma_path_loss_exponent));
        logLoss->SetAttribute("ReferenceDistance", DoubleValue(config.reference_distance_m));
        logLoss->SetAttribute("ReferenceLoss", DoubleValue(config.reference_loss_db));
        loss = logLoss;
    }
    
    if (config.enable_shadowing) {
        NS_LOG_INFO("Adding log-normal shadowing with std dev=" << config.shadowing_std_dev_db << " dB");
        
        Ptr<RandomPropagationLossModel> shadowingLoss = CreateObject<RandomPropagationLossModel>();
        Ptr<LogNormalRandomVariable> shadowingVar = CreateObject<LogNormalRandomVariable>();
        
        shadowingVar->SetAttribute("Mu", DoubleValue(0.0));
        shadowingVar->SetAttribute("Sigma", DoubleValue(config.shadowing_std_dev_db * 0.115129));
        
        shadowingLoss->SetAttribute("Variable", PointerValue(shadowingVar));
        loss->SetNext(shadowingLoss);
    }
    
    NS_LOG_INFO("Propagation setup complete:");
    NS_LOG_INFO("  - Path loss exponent (gamma): " << config.gamma_path_loss_exponent);
    NS_LOG_INFO("  - Reference distance: " << config.reference_distance_m << " m");
    NS_LOG_INFO("  - Reference loss: " << config.reference_loss_db << " dB");
    NS_LOG_INFO("  - Shadowing enabled: " << (config.enable_shadowing ? "YES" : "NO"));
    if (config.enable_shadowing) {
        NS_LOG_INFO("  - Shadowing std dev: " << config.shadowing_std_dev_db << " dB");
    }
    NS_LOG_INFO("  - Noise figure: " << config.noise_figure_db << " dB");
    
    return loss;
}

LoraSetup::LoraDevices LoraSetup::CreateLoraNetwork(
    const ns3::NodeContainer& gateways,
    const ns3::NodeContainer& endDevices) {
    
    using namespace ns3;
    using namespace ns3::lorawan;
    
    auto& config = ScenarioConfig::Get();
    
    // Map collision matrix
    LoraInterferenceHelper::collisionMatrix = config.use_aloha_matrix ?
        LoraInterferenceHelper::ALOHA : LoraInterferenceHelper::GOURSAUD;
    
    // Create channel
    Ptr<PropagationLossModel> loss = CreatePropagationModel();
    Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
    Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay);
    
    // Configure PHY helpers
    LoraPhyHelper gwPhy;
    gwPhy.SetChannel(channel);
    gwPhy.SetDeviceType(LoraPhyHelper::GW);
    
    LoraPhyHelper edPhy;
    edPhy.SetChannel(channel);
    edPhy.SetDeviceType(LoraPhyHelper::ED);
    
    // Configure MAC helpers
    LorawanMacHelper gwMac;
    gwMac.SetDeviceType(LorawanMacHelper::GW);
    gwMac.SetRegion(LorawanMacHelper::EU);
    
    LorawanMacHelper edMac;
    edMac.SetDeviceType(LorawanMacHelper::ED_A);
    edMac.SetRegion(LorawanMacHelper::EU);
    
    // Create and set address generator
    Ptr<LoraDeviceAddressGenerator> addrGen = CreateObject<LoraDeviceAddressGenerator>(0, 0);
    edMac.SetAddressGenerator(addrGen);
    
    // Install devices with packet tracking
    LoraHelper lora;
    lora.EnablePacketTracking();
    
    LoraDevices devices;
    devices.gwDevs = lora.Install(gwPhy, gwMac, gateways);
    devices.edDevs = lora.Install(edPhy, edMac, endDevices);
    devices.channel = channel;
    devices.loraHelper = lora;
    
    NS_LOG_INFO("GW LoRa devs: " << devices.gwDevs.GetN() << " | ED LoRa devs: " << devices.edDevs.GetN());
    
    return devices;
}

void LoraSetup::ConfigureEndDevices(const ns3::NetDeviceContainer& edDevs) {
    using namespace ns3;
    using namespace ns3::lorawan;
    
    auto& config = ScenarioConfig::Get();
    
    for (uint32_t i = 0; i < edDevs.GetN(); ++i) {
        Ptr<LoraNetDevice> edNd = DynamicCast<LoraNetDevice>(edDevs.Get(i));
        if (!edNd) continue;
        
        // PHY configuration
        Ptr<LoraPhy> edPhy = edNd->GetPhy();
        if (edPhy) {
            edPhy->TraceConnectWithoutContext("StartSending", MakeCallback(&TraceCallbacks::OnEdPhyTxBegin));
            
            Ptr<EndDeviceLoraPhy> edPhyObj = edPhy->GetObject<EndDeviceLoraPhy>();
            DumpAttributes(edPhyObj, "EndDevice PHY");
            
            if (edPhyObj) {
                edPhyObj->SetSpreadingFactor(7);
                NS_LOG_INFO("[ED " << i << "] PHY SF set to 7 (may be overridden by MAC DR)");
                
                SetDoubleAttrIfPresent(edPhyObj, "EnergyDetection", config.phy_energy_detection_dbm);
                SetTimeAttrIfPresent(edPhyObj, "MaxTransmissionDuration", Seconds(config.phy_max_tx_duration_sec));
            }
        }
        
        // MAC configuration
        Ptr<LorawanMac> edMacObj = edNd->GetMac();
        if (edMacObj) {
            edMacObj->TraceConnectWithoutContext("SentNewPacket", MakeCallback(&TraceCallbacks::OnEdMacTx));
            
            Ptr<ClassAEndDeviceLorawanMac> classAMac = 
                edMacObj->GetObject<ClassAEndDeviceLorawanMac>();
            if (classAMac) {
                TypeId tid = classAMac->GetInstanceTypeId();
                NS_LOG_INFO("[ED " << i << "] ClassA MAC attributes:");
                for (uint32_t a = 0; a < tid.GetAttributeN(); ++a) {
                    auto info = tid.GetAttribute(a);
                    NS_LOG_INFO("  - " << info.name);
                }
                
                // Force DR5
                classAMac->SetDataRate(5);
                NS_LOG_INFO("[ED " << i << "] MAC DataRate set to DR5 (SF7/125kHz)");
                
                // Disable duty-cycle if available
                SetBoolAttrIfPresent(classAMac, "DutyCycleEnabled", false);
            }
        }
    }
}

void LoraSetup::ConfigureGateways(const ns3::NetDeviceContainer& gwDevs) {
    using namespace ns3;
    using namespace ns3::lorawan;
    
    auto& config = ScenarioConfig::Get();
    
    for (uint32_t g = 0; g < gwDevs.GetN(); ++g) {
        auto gwNd = DynamicCast<LoraNetDevice>(gwDevs.Get(g));
        if (!gwNd) continue;
        
        auto gwPhy = gwNd->GetPhy();
        if (gwPhy) {
            gwPhy->TraceConnectWithoutContext("EndReceive", MakeCallback(&TraceCallbacks::OnGwPhyRxOk));
            
            Ptr<GatewayLoraPhy> gphy = gwNd->GetPhy()->GetObject<GatewayLoraPhy>();
            DumpAttributes(gphy, "Gateway PHY");
            
            if (gphy) {
                gphy->TraceConnectWithoutContext("LostPacketBecauseNoMoreReceivers",
                                                MakeCallback(&TraceCallbacks::OnGwPhyRxUnderSensitivity));
                gphy->TraceConnectWithoutContext("NoReceptionBecauseTransmitting",
                                                MakeCallback(&TraceCallbacks::OnGwPhyRxLost));
                
                TypeId tid = gphy->GetTypeId();
                NS_LOG_INFO("Available Gateway PHY traces:");
                for (uint32_t i = 0; i < tid.GetTraceSourceN(); ++i) {
                    struct TypeId::TraceSourceInformation info = tid.GetTraceSource(i);
                    NS_LOG_INFO("  " << info.name << ": " << info.help);
                }
                
                SetDoubleAttrIfPresent(gphy, "EnergyDetection", config.phy_energy_detection_dbm);
                SetTimeAttrIfPresent(gphy, "MaxTransmissionDuration", Seconds(config.phy_max_tx_duration_sec));
            }
        }
        
        auto gwMac = gwNd->GetMac();
        if (gwMac) {
            gwMac->TraceConnectWithoutContext("ReceivedPacket", MakeCallback(&TraceCallbacks::OnGwMacRxOk));
        }
    }
}

void LoraSetup::ConnectTraces(const ns3::NetDeviceContainer& gwDevs,
                              const ns3::NetDeviceContainer& edDevs) {
    ConfigureGateways(gwDevs);
    ConfigureEndDevices(edDevs);
}

ns3::ApplicationContainer LoraSetup::SetupNetworkServer(
    const ns3::NodeContainer& networkServer,
    const ns3::NodeContainer& gateways,
    const ns3::NodeContainer& endDevices,
    const ns3::NetDeviceContainer& gwDevs) {
    
    using namespace ns3;
    using namespace ns3::lorawan;
    
    auto& config = ScenarioConfig::Get();
    
    // Setup backhaul
    P2PGwRegistration_t p2pReg;
    PointToPointHelper p2p;
    p2p.SetDeviceAttribute("DataRate", StringValue(config.cloud_backhaul_datarate));
    p2p.SetChannelAttribute("Delay", StringValue(config.cloud_backhaul_delay));
    
    NetDeviceContainer d = p2p.Install(networkServer.Get(0), gateways.Get(0));
    Ptr<PointToPointNetDevice> nsBackhaul = DynamicCast<PointToPointNetDevice>(d.Get(0));
    if (nsBackhaul) {
        p2pReg.emplace_back(nsBackhaul, gateways.Get(0));
    }
    
    // Install Network Server
    NetworkServerHelper nsHelper;
    nsHelper.SetEndDevices(endDevices);
    nsHelper.SetGatewaysP2P(p2pReg);
    nsHelper.EnableAdr(config.enable_adr);
    
    ApplicationContainer nsApps = nsHelper.Install(networkServer.Get(0));
    
    // Connect NS traces
    if (nsApps.GetN() > 0) {
        Ptr<NetworkServer> ns = nsApps.Get(0)->GetObject<NetworkServer>();
        if (ns) {
            ns->TraceConnectWithoutContext("ReceivedFromGateway",
                                          MakeCallback(&TraceCallbacks::OnNsRxFromGw));
        }
    }
    
    return nsApps;
}

} // namespace scenario