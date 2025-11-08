#include "../common/energy_setup.h"
#include "../common/scenario_config.h"
#include "../common/traces.h"
#include "ns3/energy-module.h"
#include "ns3/basic-energy-source-helper.h"
#include "ns3/lora-radio-energy-model.h"
#include "ns3/lora-tx-current-model.h"
#include "ns3/lorawan-module.h"
#include "ns3/log.h"

NS_LOG_COMPONENT_DEFINE("EnergySetup");

namespace scenario {

void EnergySetup::DumpAttributes(ns3::Ptr<ns3::Object> obj, const char* label) {
    if (!obj) return;
    ns3::TypeId tid = obj->GetInstanceTypeId();
    NS_LOG_INFO(std::string("Attributes of ") + label + " (" + tid.GetName() + "):");
    for (uint32_t i = 0; i < tid.GetAttributeN(); ++i) {
        const auto info = tid.GetAttribute(i);
        NS_LOG_INFO("  - " << info.name);
    }
}

ns3::energy::EnergySourceContainer EnergySetup::InstallEnergyModels(
    const ns3::NodeContainer& endDevices,
    const ns3::NetDeviceContainer& edDevs) {
    
    using namespace ns3;
    using namespace ns3::energy;
    using namespace ns3::lorawan;
    
    auto& config = ScenarioConfig::Get();
    
    // 1) Install one BasicEnergySource per ED node
    BasicEnergySourceHelper sourceHelper;
    sourceHelper.Set("BasicEnergySupplyVoltageV", DoubleValue(config.en_supply_voltage_v));
    sourceHelper.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(config.en_initial_energy_j));
    sourceHelper.Set("PeriodicEnergyUpdateInterval", TimeValue(Seconds(config.en_update_interval_s)));
    EnergySourceContainer sources = sourceHelper.Install(endDevices);
    
    // 2) For each ED: create LoraRadioEnergyModel, attach to source, hook PHY listener & traces
    for (uint32_t i = 0; i < edDevs.GetN(); ++i) {
        Ptr<LoraNetDevice> edNd = DynamicCast<LoraNetDevice>(edDevs.Get(i));
        if (!edNd) continue;
        
        Ptr<EnergySource> es = sources.Get(i);
        
        // (a) Create radio device energy model and set per-state currents
        Ptr<lorawan::LoraRadioEnergyModel> lrm = CreateObject<lorawan::LoraRadioEnergyModel>();
        lrm->SetEnergySource(es);
        lrm->SetAttribute("StandbyCurrentA", DoubleValue(config.en_idle_current_a));
        lrm->SetAttribute("RxCurrentA", DoubleValue(config.en_rx_current_a));
        lrm->SetAttribute("SleepCurrentA", DoubleValue(config.en_sleep_current_a));
        
        // (b) Linear TX current model
        Ptr<lorawan::LinearLoraTxCurrentModel> txModel = CreateObject<lorawan::LinearLoraTxCurrentModel>();
        txModel->SetAttribute("Eta", DoubleValue(config.en_tx_model_eta));
        txModel->SetAttribute("Voltage", DoubleValue(config.en_supply_voltage_v));
        txModel->SetAttribute("StandbyCurrent", DoubleValue(config.en_tx_model_standby_a));
        lrm->SetTxCurrentModel(txModel);
        
        // (c) Register device energy model with the source
        es->AppendDeviceEnergyModel(lrm);
        
        // (d) Hook PHY listener so TX/RX/SLEEP drive current updates
        Ptr<EndDeviceLoraPhy> edPhyObj = edNd->GetPhy()->GetObject<EndDeviceLoraPhy>();
        if (edPhyObj) {
            edPhyObj->RegisterListener(lrm->GetPhyListener());
        }
        
        // (e) Traces
        // lrm->TraceConnectWithoutContext("TotalEnergyConsumption", 
        //                                MakeCallback(&TraceCallbacks::OnEdEnergyTotal));
        // Ptr<BasicEnergySource> bes = DynamicCast<BasicEnergySource>(es);
        // if (bes) {
        //     bes->TraceConnectWithoutContext("RemainingEnergy", 
        //                                    MakeCallback(&TraceCallbacks::OnRemainingEnergy));
        // }
    }
    
    return sources;
}

} // namespace scenario