#include "../common/lora_setup.h"
#include "../common/scenario_config.h"
#include "../common/traces.h"
#include "../common/detailed_propagation_model.h" 
#include "ns3/mobility-helper.h"
#include "ns3/constant-position-mobility-model.h"  // ← ADD THIS LINE
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
#include <cmath>  // ← ADD THIS LINE for std::log10

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
    
    // Create Log-Distance path loss model
    NS_LOG_INFO("Using Log-Distance propagation model with gamma=" << config.gamma_path_loss_exponent);
    Ptr<LogDistancePropagationLossModel> logLoss = CreateObject<LogDistancePropagationLossModel>();
    logLoss->SetAttribute("Exponent", DoubleValue(config.gamma_path_loss_exponent));
    logLoss->SetAttribute("ReferenceDistance", DoubleValue(config.reference_distance_m));
    logLoss->SetAttribute("ReferenceLoss", DoubleValue(config.reference_loss_db));
    
    // Verify configuration
    DoubleValue actualExponent, actualRefDist, actualRefLoss;
    logLoss->GetAttribute("Exponent", actualExponent);
    logLoss->GetAttribute("ReferenceDistance", actualRefDist);
    logLoss->GetAttribute("ReferenceLoss", actualRefLoss);
    
    NS_LOG_UNCOND("=== PROPAGATION MODEL ===");
    NS_LOG_UNCOND("Exponent: " << actualExponent.Get());
    NS_LOG_UNCOND("RefDistance: " << actualRefDist.Get() << " m");
    NS_LOG_UNCOND("RefLoss: " << actualRefLoss.Get() << " dB");
    NS_LOG_UNCOND("Shadowing: DISABLED (matching FLoRa sigma=0)");
    NS_LOG_UNCOND("========================");
    
    // Wrap in detailed model for logging
    Ptr<scenario::DetailedPropagationLossModel> detailedLoss = 
        CreateObject<scenario::DetailedPropagationLossModel>();
    detailedLoss->SetPathLossModel(logLoss);
    
    return detailedLoss;
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
    Ptr<scenario::DetailedPropagationLossModel> detailedLoss = 
        DynamicCast<scenario::DetailedPropagationLossModel>(loss);  
    
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
    
    // Register duty cycle bands
    scenario::RegisterDutyCycleBand(868.0e6, 868.6e6, 0.01);
    scenario::RegisterDutyCycleBand(868.7e6, 869.2e6, 0.01);

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
    devices.propagationModel = detailedLoss;
    
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
                
                // Force DR5 (SF7)
                classAMac->SetDataRate(5);
                NS_LOG_INFO("[ED " << i << "] MAC DataRate set to DR5 (SF7/125kHz)");
                
                // Set TX power on MAC
                classAMac->SetTransmissionPowerDbm(config.ed_tx_power_dbm);
                NS_LOG_INFO("[ED " << i << "] MAC TX Power set to " << config.ed_tx_power_dbm << " dBm");
            }
        }
    }
}

void LoraSetup::ConfigureGateways(const ns3::NetDeviceContainer& gwDevs) {
    using namespace ns3;
    using namespace ns3::lorawan;

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