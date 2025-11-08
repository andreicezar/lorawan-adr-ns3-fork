#include "../common/scenario_config.h"
#include "ns3/lorawan-module.h"
#include <limits>
#include <algorithm>
#include "ns3/log.h"

using namespace ns3;
using namespace ns3::lorawan;
NS_LOG_COMPONENT_DEFINE ("ScenarioConfig");

namespace scenario {

    ScenarioConfig& ScenarioConfig::Get() {
    static ScenarioConfig instance;
    return instance;
}

void ScenarioConfig::ParseCommandLine(int argc, char** argv) {
    ns3::CommandLine cmd;
    
    // Example of command line parsing
    cmd.AddValue("gw_ed_distance_m", "Gateway-end-device distance", gw_ed_distance_m);
    
    // Add other variables as needed for command-line overrides
    cmd.Parse(argc, argv);
}

double ScenarioConfig::DrToBwHz(unsigned char dr) const {
    switch (dr) {
        case 0: return 125000.0; // SF12
        case 1: return 250000.0; // SF11
        case 2: return 500000.0; // SF10
        // Add other data rates as necessary
        default: return 125000.0; // Default value
    }
}

double ScenarioConfig::NoiseFloorDbm(double bwHz) const {
    // Calculate noise floor: kTB + noise figure (assuming -174 dBm/Hz + 6 dB noise figure)
    double noise_floor = -174.0 + 10 * std::log10(bwHz) + 6.0;
    return noise_floor;
}

double ScenarioConfig::GetSnrRequirement(unsigned char sf) const {
    if (sf >= 7 && sf <= 12) {
        return snr_requirements_db[12 - sf];  // SNR requirements from SF7 to SF12
    }
    return std::numeric_limits<double>::quiet_NaN();  // Invalid SF
}

const char* ScenarioConfig::SfToString(unsigned char sf) const {
    switch (sf) {
        case 7: return "SF7";
        case 8: return "SF8";
        case 9: return "SF9";
        case 10: return "SF10";
        case 11: return "SF11";
        case 12: return "SF12";
        default: return "Unknown SF";
    }
}

static std::vector<std::tuple<double,double,double>> g_dutyBands;

LoraTxParameters BuildTxParamsFrom(const LoraTag& tag)
{
    LoraTxParameters p;

    // Extract values directly from tag
    const uint8_t  sf    = tag.GetSpreadingFactor();
    const uint8_t  dr    = tag.GetDataRate();

    // From ScenarioConfig helper (bandwidth by data rate)
    const uint32_t bw_hz = ScenarioConfig::Get().DrToBwHz(dr);

    p.sf          = sf;
    p.bandwidthHz = bw_hz;
    p.codingRate  = 1;           // LoRa CR = 4/(4+1) = 4/5
    p.nPreamble   = 8;
    p.headerDisabled = false;
    p.crcEnabled  = true;
    // lowDataRateOptimizationEnabled auto-computed inside GetOnAirTime()

    return p;
}

bool HasDutyCycleForFrequency(double f_hz)
{
    for (const auto& b : g_dutyBands) {
        if (f_hz >= std::get<0>(b) && f_hz <= std::get<1>(b)) return true;
    }
    return false;
}

double GetDutyCycleForFrequency(double f_hz)
{
    for (const auto& b : g_dutyBands) {
        if (f_hz >= std::get<0>(b) && f_hz <= std::get<1>(b)) return std::get<2>(b);
    }
    return std::numeric_limits<double>::quiet_NaN();
}

void RegisterDutyCycleBand(double f_start_hz, double f_end_hz, double dc_fraction)
{
    g_dutyBands.emplace_back(f_start_hz, f_end_hz, dc_fraction);
}

void ScenarioConfig::DumpConfig(const std::string& filepath) const {
    std::ofstream out(filepath);
    if (!out.is_open()) {
        NS_LOG_ERROR("Could not open config dump file: " << filepath);
        return;
    }
    
    out << "========================================\n";
    out << "SCENARIO CONFIGURATION - INITIAL VALUES\n";
    out << "========================================\n\n";
    
    // Simulation Control
    out << "[SIMULATION CONTROL]\n";
    out << "sim_time_s = " << sim_time_s << "\n";
    out << "gw_ed_distance_m = " << gw_ed_distance_m << "\n";
    out << "\n";
    
    // Traffic Generation
    out << "[TRAFFIC GENERATION]\n";
    out << "n_pkts_to_send = " << n_pkts_to_send << " (0 = infinite)\n";
    out << "fixed_period_s = " << fixed_period_s << "\n";
    out << "use_exponential_iat = " << (use_exponential_iat ? "true" : "false") << "\n";
    out << "exp_iat_mean_s = " << exp_iat_mean_s << "\n";
    out << "\n";
    
    // Network Configuration
    out << "[NETWORK CONFIGURATION]\n";
    out << "enable_adr = " << (enable_adr ? "true" : "false") << "\n";
    out << "use_aloha_matrix = " << (use_aloha_matrix ? "true" : "false") 
        << " (false = Goursaud, true = ALOHA)\n";
    out << "cloud_backhaul_datarate = " << cloud_backhaul_datarate << "\n";
    out << "cloud_backhaul_delay = " << cloud_backhaul_delay << "\n";
    out << "\n";
    
    // PHY Layer Configuration
    out << "[PHY LAYER CONFIGURATION]\n";
    out << "ed_tx_power_dbm = " << ed_tx_power_dbm << "\n";
    out << "\n";
    
    // LoRa Radio Parameters
    out << "[LORA RADIO PARAMETERS]\n";
    out << "Spreading Factor (SF) = 7 (DR5)\n";
    out << "Data Rate (DR) = 5\n";
    out << "Bandwidth = 125 kHz (hardcoded for DR0-5)\n";
    out << "Coding Rate = 4/5\n";
    out << "\n";
    
    // Propagation Model Selection
    out << "[PROPAGATION MODEL SELECTION]\n";
    out << "use_log_distance_model = " << (use_log_distance_model ? "true" : "false") << "\n";
    if (use_okumura_hata_model || use_friis_model) {
        out << "use_okumura_hata_model = " << (use_okumura_hata_model ? "true" : "false") 
            << " [NOT IMPLEMENTED]\n";
        out << "use_friis_model = " << (use_friis_model ? "true" : "false") 
            << " [NOT IMPLEMENTED]\n";
    }
    out << "\n";
    
    // Path Loss Parameters
    out << "[PATH LOSS PARAMETERS]\n";
    out << "gamma_path_loss_exponent = " << gamma_path_loss_exponent << "\n";
    out << "reference_distance_m = " << reference_distance_m << "\n";
    out << "reference_loss_db = " << reference_loss_db << "\n";
    out << "\n";
    
    // Shadowing Parameters
    out << "[SHADOWING PARAMETERS]\n";
    out << "enable_shadowing = " << (enable_shadowing ? "true" : "false") << "\n";
    out << "shadowing_std_dev_db = " << shadowing_std_dev_db << "\n";
    if (shadowing_correlation_distance_m != 50.0) {
        out << "shadowing_correlation_distance_m = " << shadowing_correlation_distance_m 
            << " [NOT IMPLEMENTED]\n";
    }
    out << "\n";
    
    // Noise Parameters (hardcoded in code)
    out << "[NOISE PARAMETERS] (hardcoded in NoiseFloorDbm())\n";
    out << "thermal_noise_dbm_hz = -174.0 dBm/Hz\n";
    out << "noise_figure_db = 6.0 dB\n";
    double noise_floor_125k = NoiseFloorDbm(125000.0);
    out << "noise_floor_125kHz = " << noise_floor_125k << " dBm\n";
    out << "\n";
    
    // Okumura-Hata Specific (if flags set)
    if (use_okumura_hata_model) {
        out << "[OKUMURA-HATA PARAMETERS] [NOT IMPLEMENTED]\n";
        out << "okumura_frequency_mhz = " << okumura_frequency_mhz << "\n";
        out << "okumura_gw_height_m = " << okumura_gw_height_m << "\n";
        out << "okumura_ed_height_m = " << okumura_ed_height_m << "\n";
        out << "okumura_urban_environment = " << (okumura_urban_environment ? "true" : "false") << "\n";
        out << "\n";
    }
    
    // SNR Requirements
    out << "[SNR REQUIREMENTS] (for logging/analysis only)\n";
    out << "use_conservative_snr_thresholds = " << (use_conservative_snr_thresholds ? "true" : "false") << "\n";
    if (use_conservative_snr_thresholds) {
        out << "SNR Requirements (Conservative):\n";
        out << "  SF12: " << snr_requirements_conservative_db[0] << " dB\n";
        out << "  SF11: " << snr_requirements_conservative_db[1] << " dB\n";
        out << "  SF10: " << snr_requirements_conservative_db[2] << " dB\n";
        out << "  SF9:  " << snr_requirements_conservative_db[3] << " dB\n";
        out << "  SF8:  " << snr_requirements_conservative_db[4] << " dB\n";
        out << "  SF7:  " << snr_requirements_conservative_db[5] << " dB\n";
    } else {
        out << "SNR Requirements (Standard):\n";
        out << "  SF12: " << snr_requirements_db[0] << " dB\n";
        out << "  SF11: " << snr_requirements_db[1] << " dB\n";
        out << "  SF10: " << snr_requirements_db[2] << " dB\n";
        out << "  SF9:  " << snr_requirements_db[3] << " dB\n";
        out << "  SF8:  " << snr_requirements_db[4] << " dB\n";
        out << "  SF7:  " << snr_requirements_db[5] << " dB\n";
    }
    out << "\n";
    
    // Energy Model Parameters
    out << "[ENERGY MODEL PARAMETERS]\n";
    out << "en_supply_voltage_v = " << en_supply_voltage_v << "\n";
    out << "en_initial_energy_j = " << en_initial_energy_j << "\n";
    out << "en_update_interval_s = " << en_update_interval_s << "\n";
    out << "en_idle_current_a = " << en_idle_current_a << " (" << (en_idle_current_a * 1000) << " mA)\n";
    out << "en_rx_current_a = " << en_rx_current_a << " (" << (en_rx_current_a * 1000) << " mA)\n";
    out << "en_sleep_current_a = " << en_sleep_current_a << " (" << (en_sleep_current_a * 1e6) << " µA)\n";
    out << "en_tx_model_eta = " << en_tx_model_eta << "\n";
    out << "en_tx_model_standby_a = " << en_tx_model_standby_a << "\n";
    out << "\n";
    
    // Output Files
    out << "[OUTPUT FILES]\n";
    out << "en_trace_file_total = " << en_trace_file_total << "\n";
    out << "en_trace_file_rmn = " << en_trace_file_rmn << "\n";
    out << "snr_log_file = " << snr_log_file << "\n";
    out << "global_performance_file = " << global_performance_file << "\n";
    out << "phy_performance_file = " << phy_performance_file << "\n";
    out << "device_status_file = " << device_status_file << "\n";
    out << "\n";
    
    out << "========================================\n";
    out << "END OF CONFIGURATION\n";
    out << "========================================\n";
    
    out.close();
    NS_LOG_INFO("Configuration dumped to: " << filepath);
}

} // namespace scenario