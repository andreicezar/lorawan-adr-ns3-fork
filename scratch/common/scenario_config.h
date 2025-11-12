#ifndef SCENARIO_CONFIG_H
#define SCENARIO_CONFIG_H

#pragma once
#include <vector>
#include <tuple>
#include <string>

// --- Forward declarations to avoid heavy includes in the header ---
namespace ns3 {
  namespace lorawan {
    struct LoraTxParameters;   // defined in lora-phy.h
    class  LoraTag;            // defined in lora-tag.h
  }
}

namespace scenario {

// Build LoraTxParameters from a packet's LoraTag + current ScenarioConfig (no constants).
ns3::lorawan::LoraTxParameters BuildTxParamsFrom(const ns3::lorawan::LoraTag& tag);

// Runtime registry of configured duty-cycle bands (filled at setup).
bool   HasDutyCycleForFrequency(double freq_hz);
double GetDutyCycleForFrequency(double freq_hz);
void   RegisterDutyCycleBand(double f_start_hz, double f_end_hz, double dc_fraction);

// Global interference tracker
static std::map<uint32_t, double> g_last_interference_dbm;

class ScenarioConfig {
public:
    // Simulation control
    double sim_time_s = 600.0;
    double gw_ed_distance_m = 500.0;
    
    // Traffic generation
    uint32_t n_pkts_to_send = 0;        // 0 => infinite (controlled by sim_time_s)
    double fixed_period_s = 60.0;
    bool use_exponential_iat = false;
    double exp_iat_mean_s = 1000.0;
    
    // Network configuration
    bool enable_adr = false;
    bool use_aloha_matrix = false;      // false: Goursaud, true: ALOHA
    
    // Cloud/backhaul
    std::string cloud_backhaul_datarate = "1Gbps";
    std::string cloud_backhaul_delay = "10ms";
    
    // Propagation model selection
    bool use_log_distance_model = true;
    bool use_okumura_hata_model = false;  // Not implemented
    bool use_friis_model = false;         // Not implemented
    
    // Propagation Loss Model Parameters (FUNCTIONAL)
    double gamma_path_loss_exponent = 2.32;
    double reference_distance_m = 100.0;    // 100m reference
    double reference_loss_db = 104.21;
    
    // Shadowing Parameters (FUNCTIONAL)
    double shadowing_std_dev_db = 3.57;
    bool enable_shadowing = false;
    double shadowing_correlation_distance_m = 50.0;  // Not implemented
    
    // Okumura-Hata specific (NOT IMPLEMENTED)
    double okumura_frequency_mhz = 868.0;
    double okumura_gw_height_m = 10.0;
    double okumura_ed_height_m = 1.0;
    bool okumura_urban_environment = false;
    
    // SNR Requirements for logging [SF12, SF11, SF10, SF9, SF8, SF7]
    double snr_requirements_db[6] = {-20.0, -17.5, -15.0, -12.5, -10.0, -7.5};
    double snr_requirements_conservative_db[6] = {-18.0, -15.5, -13.0, -10.5, -8.0, -5.5};
    bool use_conservative_snr_thresholds = false;
    
    // Power settings (FUNCTIONAL)
    double ed_tx_power_dbm = 14.0;
    
    // Energy source parameters (FUNCTIONAL)
    double en_supply_voltage_v = 3.3;
    double en_initial_energy_j = 10000.0;
    double en_update_interval_s = 3600;
    
    // LoRa radio currents (A) (FUNCTIONAL)
    double en_idle_current_a = 0.0001;     // 0.1 mA
    double en_rx_current_a = 0.0097;       // 9.7 mA
    double en_sleep_current_a = 0.0000015; // 1.5 µA
    
    // Linear TX current model parameters (FUNCTIONAL)
    double en_tx_model_eta = 0.10;
    double en_tx_model_standby_a = 0.0001; // Same as idle
    
    // Output filenames
    std::string en_trace_file_total = "ed-energy-total.csv";
    std::string en_trace_file_rmn = "ed-remaining-energy.csv";
    std::string snr_log_file = "snr_log.csv";
    std::string global_performance_file = "global-performance.txt";
    std::string phy_performance_file = "phy-performance.txt";
    std::string device_status_file = "device-status.txt";
    
    // Singleton access
    static ScenarioConfig& Get();
    
    // Parse command line (optional overrides)
    void ParseCommandLine(int argc, char* argv[]);
    
    // Helpers
    double GetSnrRequirement(uint8_t sf) const;
    double DrToBwHz(uint8_t dr) const;
    double NoiseFloorDbm(double bwHz) const;
    const char* SfToString(uint8_t sf) const;
    void DumpConfig(const std::string& filepath) const;
    
private:
    ScenarioConfig() = default;
};

} // namespace scenario

#endif // SCENARIO_CONFIG_H