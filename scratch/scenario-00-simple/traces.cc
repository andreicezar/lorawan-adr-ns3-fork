#include "../common/traces.h"
#include "../common/logging.h"
#include "../common/scenario_config.h"
#include "../common/detailed_propagation_model.h"
#include "ns3/simulator.h"
#include "ns3/log.h"
#include "ns3/node-list.h"
#include "ns3/mobility-model.h"
#include "ns3/lorawan-mac-header.h"
#include "ns3/lora-tag.h"
#include "ns3/rng-seed-manager.h"
#include <sstream>
#include <cmath>
#include <algorithm>
#include "ns3/lorawan-module.h"
#include <limits>

NS_LOG_COMPONENT_DEFINE("Traces");

namespace scenario {

// Static member definitions
ns3::Ptr<DetailedPropagationLossModel> TraceCallbacks::s_propagationModel = nullptr;
ns3::NodeContainer TraceCallbacks::s_gateways;
ns3::NodeContainer TraceCallbacks::s_endDevices;
std::map<uint32_t, double> TraceCallbacks::s_txTimes;
std::vector<double> TraceCallbacks::s_latencies;

// Packet counters and statistics (for cumulative tracking)
static int s_pkts_sent = 0;
static int s_pkts_recv = 0;
static double s_rssi_sum = 0.0, s_rssi_sq = 0.0;
static double s_snr_sum = 0.0, s_snr_sq = 0.0;

void TraceCallbacks::SetPropagationModel(
    ns3::Ptr<DetailedPropagationLossModel> model,
    const ns3::NodeContainer& gateways,
    const ns3::NodeContainer& endDevices) {
    s_propagationModel = model;
    s_gateways = gateways;
    s_endDevices = endDevices;
}

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
    if (fHz <= 0.0 || rssi >= 0.0) return;
    
    const uint8_t dr = tag.GetDataRate();
    const uint8_t sf = tag.GetSpreadingFactor();
    const double bw = config.DrToBwHz(dr);
    
    // Use the config method which has hardcoded noise parameters
    double totalNoise = config.NoiseFloorDbm(bw);
    double snr = rssi - totalNoise;
    
    const double req = config.GetSnrRequirement(sf);
    double margin = snr - req;
    
    CsvLogger::WriteSnrRow(
        ns3::Simulator::Now().GetSeconds(),
        ns3::Simulator::GetContext(),
        dr, sf, fHz, rssi, snr, req, margin
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
        if (fHz > 0.0 && rssi < 0.0) {
            const double bwHz = config.DrToBwHz(tag.GetDataRate());
            const double noiseFloor = config.NoiseFloorDbm(bwHz);
            const double snr = rssi - noiseFloor;
            
            const uint8_t sf = tag.GetSpreadingFactor();
            const double req = config.GetSnrRequirement(sf);
            const double margin = snr - req;
            
            os << " RSSI=" << rssi << " dBm"
               << " SNR=" << snr << " dB"
               << " (req=" << req << " dB"
               << ", margin=" << margin << " dB)";
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
    
    s_pkts_sent++;
    RecordTxTime(1, p->GetUid(), ns3::Simulator::Now().GetSeconds());
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
    using namespace ns3;
    using namespace ns3::lorawan;
    
    LoraTag tag;
    if (!p->PeekPacketTag(tag)) return;
    
    auto& config = ScenarioConfig::Get();
    const double rssi = tag.GetReceivePower();
    const double fHz = tag.GetFrequency();
    const uint8_t sf = tag.GetSpreadingFactor();
    const uint8_t dr = tag.GetDataRate();
    
    Ptr<Node> gwNode = s_gateways.Get(0);
    Ptr<Node> edNode = s_endDevices.Get(0);
    
    Ptr<MobilityModel> gwMob = gwNode->GetObject<MobilityModel>();
    Ptr<MobilityModel> edMob = edNode->GetObject<MobilityModel>();
    
    double distance = gwMob->GetDistanceFrom(edMob);
    
    double path_loss_db = 0.0;
    double shadowing_db = 0.0;
    double total_loss_db = 0.0;
    
    if (s_propagationModel) {
        PropagationDetails details = s_propagationModel->GetLastDetails(edMob, gwMob);
        path_loss_db = details.path_loss_db;
        shadowing_db = details.shadowing_db;
        total_loss_db = details.total_loss_db;
    }
    
    const double bwHz = config.DrToBwHz(dr);
    const double noise_floor = config.NoiseFloorDbm(bwHz);
    const double interference = -120.0;
    const double snr = rssi - noise_floor;
    
    CsvLogger::WritePacketDetailsRow(
        Simulator::Now().GetSeconds(),
        edNode->GetId(),
        "RX_SUCCESS",
        0,
        sf, dr, fHz,
        config.ed_tx_power_dbm,
        distance,
        path_loss_db,
        shadowing_db,
        total_loss_db,
        rssi,
        noise_floor,
        interference,
        snr,
        "SUCCESS"
    );
    
    LogSnrCsv(tag);
    PrintLoraParams("GW_PHY_RX_OK", 0, p);
}

void TraceCallbacks::OnGwMacRxOk(ns3::Ptr<const ns3::Packet> p)
{
    using namespace ns3;
    using namespace ns3::lorawan;
    NS_LOG_UNCOND("DEBUG: OnGwMacRxOk called at t=" << Simulator::Now().GetSeconds());  // ← ADD THIS
    
    PrintLoraParams("GW_MAC_RX_OK", 0, p);

    LoraTag tag;
    if (!p->PeekPacketTag(tag)) {
        NS_LOG_UNCOND("DEBUG: No LoraTag found!");
        Ptr<Node> edNode = s_endDevices.Get(0);
        CsvLogger::WriteDutyCycleRow(
            Simulator::Now().GetSeconds(),
            edNode->GetId(),
            std::numeric_limits<double>::quiet_NaN(),
            std::numeric_limits<double>::quiet_NaN(),
            std::numeric_limits<double>::quiet_NaN(),
            std::numeric_limits<double>::quiet_NaN(),
            "missing_tag"
        );
    } else {
        // Build tx params from tag + ScenarioConfig (no constants)
        auto txParams = scenario::BuildTxParamsFrom(tag);

        // True ToA via official API (requires non-const packet)
        Ptr<Packet> pCopy = p->Copy();
        Time toa = LoraPhy::GetOnAirTime(pCopy, txParams);
        double tx_s = toa.GetSeconds();

        // Configured duty (from setup-registered bands)
        double f_hz = tag.GetFrequency();
        double dc_fraction = std::numeric_limits<double>::quiet_NaN();
        std::string notes;

        if (scenario::HasDutyCycleForFrequency(f_hz)) {
            dc_fraction = scenario::GetDutyCycleForFrequency(f_hz);
        } else {
            notes = "dutycycle_unknown_for_freq";
        }

        double off_s = std::numeric_limits<double>::quiet_NaN();
        double duty_pct = std::numeric_limits<double>::quiet_NaN();
        if (dc_fraction > 0.0 && dc_fraction <= 1.0) {
            off_s = tx_s * (1.0 / dc_fraction - 1.0);
            duty_pct = 100.0 * tx_s / (tx_s + off_s);
        }

        Ptr<Node> edNode = s_endDevices.Get(0);
        CsvLogger::WriteDutyCycleRow(
            Simulator::Now().GetSeconds(),
            edNode->GetId(),
            tx_s, off_s, duty_pct,
            std::isnan(dc_fraction) ? dc_fraction : (dc_fraction * 100.0),
            notes
        );
    }

    // SNR/margins CSV (uses same tag)
    LogSnrCsv(tag);

    // Record RX time per-packet
    uint32_t pkt_uid = p->GetUid();
    RecordRxTime(0, pkt_uid, Simulator::Now().GetSeconds());

    // ========================================================================
    // Calculate and log packet-level summary
    // ========================================================================
    auto& cfg = ScenarioConfig::Get();

    const double rssi = tag.GetReceivePower();
    const uint8_t dr = tag.GetDataRate();
    const uint8_t sf = tag.GetSpreadingFactor();
    const double bwHz = cfg.DrToBwHz(dr);
    const double noise = cfg.NoiseFloorDbm(bwHz);
    const double snr = rssi - noise;

    s_pkts_recv++;
    s_rssi_sum += rssi;
    s_rssi_sq += rssi * rssi;
    s_snr_sum += snr;
    s_snr_sq += snr * snr;

    const int n = s_pkts_recv;
    const double rssi_mean = s_rssi_sum / n;
    const double snr_mean = s_snr_sum / n;
    const double rssi_std = std::sqrt(std::max(0.0, s_rssi_sq / n - rssi_mean * rssi_mean));
    const double snr_std = std::sqrt(std::max(0.0, s_snr_sq / n - snr_mean * snr_mean));

    const double pdr = (s_pkts_sent > 0) ? (100.0 * s_pkts_recv / s_pkts_sent) : 0.0;
    const double der = 100.0 - pdr;

    double this_latency_ms = 0.0;
    auto it = s_txTimes.find(pkt_uid);
    if (it != s_txTimes.end()) {
        this_latency_ms = (Simulator::Now().GetSeconds() - it->second) * 1000.0;
    }

    const auto latencies = GetLatencies();
    const double lat_p50 = CalculatePercentile(latencies, 50.0);
    const double lat_p90 = CalculatePercentile(latencies, 90.0);

    const double energy_total_j = 0.0;
    const double energy_per_tx_mj = 0.0;

    const int seed = RngSeedManager::GetRun();
    const std::string scenario =
        (cfg.gw_ed_distance_m == 500.0) ? "baseline"
                                        : ("dist" + std::to_string(static_cast<int>(cfg.gw_ed_distance_m)));

    // ToA for summary (API)
    auto txParams_summary = scenario::BuildTxParamsFrom(tag);
    Ptr<Packet> pCopy2 = p->Copy();
    double toa_ms = LoraPhy::GetOnAirTime(pCopy2, txParams_summary).GetSeconds() * 1000.0;

    CsvLogger::WritePacketSummaryRow(
        "ns3",
        scenario,
        seed,
        static_cast<int>(cfg.gw_ed_distance_m),
        sf,
        cfg.enable_adr,
        1,
        s_pkts_recv,
        rssi,
        snr,
        rssi_mean,
        rssi_std,
        snr_mean,
        snr_std,
        pdr,
        der,
        s_pkts_sent,
        s_pkts_recv,
        this_latency_ms,
        lat_p50,
        lat_p90,
        toa_ms,
        energy_per_tx_mj,
        energy_total_j,
        Simulator::Now().GetSeconds(),
        ""
    );
}


void TraceCallbacks::OnNsRxFromGw(ns3::Ptr<const ns3::Packet> p) {
    PrintLoraParams("NS_RX_FROM_GW", 0, p);
}

void TraceCallbacks::RecordTxTime(uint32_t nodeId, uint32_t seqNum, double txTime) {
    s_txTimes[seqNum] = txTime;
}

void TraceCallbacks::RecordRxTime(uint32_t nodeId, uint32_t seqNum, double rxTime) {
    auto it = s_txTimes.find(seqNum);
    if (it != s_txTimes.end()) {
        double latency_s = rxTime - it->second;
        double latency_ms = latency_s * 1000.0;
        s_latencies.push_back(latency_ms);
    }
}

std::vector<double> TraceCallbacks::GetLatencies() {
    return s_latencies;
}

double TraceCallbacks::CalculatePercentile(const std::vector<double>& data, double percentile) {
    if (data.empty()) return 0.0;
    
    std::vector<double> sorted = data;
    std::sort(sorted.begin(), sorted.end());
    
    size_t index = static_cast<size_t>(percentile / 100.0 * sorted.size());
    if (index >= sorted.size()) index = sorted.size() - 1;
    
    return sorted[index];
}

} // namespace scenario