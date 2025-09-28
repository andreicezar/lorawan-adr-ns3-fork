#include "common/traces.h"
#include "common/logging.h"
#include "common/scenario_config.h"
#include "ns3/simulator.h"
#include "ns3/log.h"
#include "ns3/lorawan-mac-header.h"
#include "ns3/lora-tag.h"
#include <sstream>
#include <cmath>

NS_LOG_COMPONENT_DEFINE("Traces");

namespace scenario {

void TraceCallbacks::OnEdEnergyTotal(double oldJ, double newJ) {
    CsvLogger::WriteEnergyTotal(ns3::Simulator::Now().GetSeconds(), newJ);
}

void TraceCallbacks::OnRemainingEnergy(double oldJ, double newJ) {
    CsvLogger::WriteEnergyRemaining(ns3::Simulator::Now().GetSeconds(), newJ);
}

void TraceCallbacks::LogSnrCsv(const ns3::lorawan::LoraTag& tag) {
    auto& config = ScenarioConfig::Get();
    const double rssi = tag.GetReceivePower();
    const double fHz = tag.GetFrequency();
    if (fHz <= 0.0 || rssi >= 0.0) return; // only log real receptions
    
    const uint8_t dr = tag.GetDataRate();
    const uint8_t sf = tag.GetSpreadingFactor();
    const double bw = config.DrToBwHz(dr);
    
    // Calculate SNR with all loss factors
    double totalNoise = config.NoiseFloorDbm(bw, config.noise_figure_db);
    double adjustedRssi = rssi - config.foliage_loss_db - config.building_penetration_loss_db;
    const double snr = adjustedRssi - totalNoise;
    
    // Use configurable SNR requirement
    const double req = config.GetSnrRequirement(sf);
    const double margin = snr - req;
    const double marginWithFade = margin - config.fade_margin_db;
    
    CsvLogger::WriteSnrRow(
        ns3::Simulator::Now().GetSeconds(),
        ns3::Simulator::GetContext(),
        dr, sf, fHz, rssi, snr, req, margin, marginWithFade
    );
}

void TraceCallbacks::PrintLoraParams(const char* who, unsigned id, ns3::Ptr<const ns3::Packet> p) {
    using namespace ns3;
    using namespace ns3::lorawan;
    
    auto& config = ScenarioConfig::Get();
    LoraTag tag;
    bool has = p->PeekPacketTag(tag);
    std::ostringstream os;
    os.setf(std::ios::fixed);
    os.precision(6);
    
    if (has) {
        os << Simulator::Now().GetSeconds() << "s " << id << " " << who
           << " sf=" << config.SfToString(tag.GetSpreadingFactor())
           << " dr=" << unsigned(tag.GetDataRate());
        
        const double rssi = tag.GetReceivePower();
        const double fHz = tag.GetFrequency();
        if (fHz > 0.0 && rssi < 0.0) { // only at reception
            const double bwHz = config.DrToBwHz(tag.GetDataRate());
            const double noiseFloor = config.thermal_noise_dbm_hz + 
                                     10.0*std::log10(bwHz) + config.noise_figure_db;
            
            // Apply environmental losses
            double adjustedRssi = rssi - config.foliage_loss_db - config.building_penetration_loss_db;
            const double snr = adjustedRssi - noiseFloor;
            
            // Use configurable SNR requirement
            const uint8_t sf = tag.GetSpreadingFactor();
            const double req = config.GetSnrRequirement(sf);
            const double margin = snr - req;
            const double marginWithFade = margin - config.fade_margin_db;
            
            os << " RSSI=" << rssi << " dBm"
               << " SNR=" << snr << " dB"
               << " (req=" << req << " dB, margin=" << margin << " dB"
               << ", w/fade=" << marginWithFade << " dB)";
        }
        
        os << " f=" << fHz << " Hz";
        NS_LOG_UNCOND(os.str());
    }
}

void TraceCallbacks::OnEdPhyTxBegin(ns3::Ptr<const ns3::Packet> p, unsigned int channelId) {
    PrintLoraParams("ED_PHY_TX_BEGIN", 1, p);
}

void TraceCallbacks::OnEdMacTx(ns3::Ptr<const ns3::Packet> p) {
    PrintLoraParams("ED_MAC_TX", 1, p);
}

void TraceCallbacks::OnGwPhyRxLost(ns3::Ptr<const ns3::Packet> p, uint32_t reason) {
    NS_LOG_UNCOND(ns3::Simulator::Now().GetSeconds() << "s GW_PHY_RX_LOST bytes=" 
                  << p->GetSize() << " reason=Interference");
}

void TraceCallbacks::OnGwPhyRxUnderSensitivity(ns3::Ptr<const ns3::Packet> p, unsigned int reason) {
    NS_LOG_UNCOND(ns3::Simulator::Now().GetSeconds() << "s GW_PHY_RX_UNDER_SENSITIVITY bytes=" 
                  << p->GetSize() << " reason=" << reason);
}

void TraceCallbacks::OnGwPhyRxOk(ns3::Ptr<const ns3::Packet> p, unsigned int antennaId) {
    PrintLoraParams("GW_PHY_RX_OK", 0, p);
    ns3::lorawan::LoraTag tag;
    if (p->PeekPacketTag(tag)) {
        LogSnrCsv(tag);
    }
}

void TraceCallbacks::OnGwMacRxOk(ns3::Ptr<const ns3::Packet> p) {
    PrintLoraParams("GW_MAC_RX_OK", 0, p);
    ns3::lorawan::LoraTag tag;
    if (p->PeekPacketTag(tag)) {
        LogSnrCsv(tag);
    }
}

void TraceCallbacks::OnNsRxFromGw(ns3::Ptr<const ns3::Packet> p) {
    PrintLoraParams("NS_RX_FROM_GW", 0, p);
}

} // namespace scenario