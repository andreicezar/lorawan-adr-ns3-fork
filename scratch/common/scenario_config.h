#ifndef SCENARIO_CONFIG_H
#define SCENARIO_CONFIG_H

#include <string>
#include <cstdint>

namespace scenario {

class ScenarioConfig {
public:
    // Simulation control
    double sim_time_s = 900.0;
    double gw_ed_distance_m = 1000.0;
    
    // Traffic generation
    uint32_t n_pkts_to_send = 0;        // 0 => infinite
    double fixed_period_s = 180.0;
    bool use_exponential_iat = false;
    double exp_iat_mean_s = 1000.0;
    
    // Network configuration
    bool enable_adr = false;
    bool use_aloha_matrix = false;      // false: Goursaud, true: ALOHA
    
    // Cloud/backhaul
    std::string cloud_backhaul_datarate = "1Gbps";
    std::string cloud_backhaul_delay = "10ms";
    
    // PHY thresholds
    double phy_energy_detection_dbm = -110.0;
    double phy_max_tx_duration_sec = 4.0;
    
    // Propagation model selection
    bool use_log_distance_model = true;
    bool use_okumura_hata_model = false;
    bool use_friis_model = false;
    
    // Propagation Loss Model Parameters
    double gamma_path_loss_exponent = 3.76;
    double reference_distance_m = 1.0;
    double reference_loss_db = 7.7;
    
    // Shadowing Parameters
    double shadowing_std_dev_db = 8.0;
    bool enable_shadowing = true;
    
    // Physical Layer Constants
    double noise_figure_db = 6.0;
    double thermal_noise_dbm_hz = -174.0;
    
    // Okumura-Hata specific
    double okumura_frequency_mhz = 868.0;
    double okumura_gw_height_m = 10.0;
    double okumura_ed_height_m = 1.0;
    bool okumura_urban_environment = false;
    
    // Additional parameters
    double shadowing_correlation_distance_m = 50.0;
    double gw_antenna_gain_db = 0.0;
    double ed_antenna_gain_db = 0.0;
    
    // SNR Requirements [SF12, SF11, SF10, SF9, SF8, SF7]
    double snr_requirements_db[6] = {-20.0, -17.5, -15.0, -12.5, -10.0, -7.5};
    double snr_requirements_conservative_db[6] = {-18.0, -15.5, -13.0, -10.5, -8.0, -5.5};
    bool use_conservative_snr_thresholds = false;
    
    // Frequency band parameters
    double base_frequency_hz = 868100000.0;
    double channel_spacing_hz = 200000.0;
    uint8_t num_channels = 3;
    
    // Bandwidth
    double bandwidth_125_khz = 125000.0;
    double bandwidth_250_khz = 250000.0;
    
    // Power settings
    double ed_tx_power_dbm = 14.0;
    double gw_rx_sensitivity_dbm = -137.0;
    
    // Timing parameters
    double preamble_symbols = 8.0;
    double crystal_tolerance_ppm = 10.0;
    
    // Margins
    double fade_margin_db = 10.0;
    double foliage_loss_db = 0.0;
    double building_penetration_loss_db = 0.0;
    
    // Energy source parameters
    double en_supply_voltage_v = 3.3;
    double en_initial_energy_j = 10000.0;
    double en_update_interval_s = 10.0;
    
    // LoRa radio currents (A)
    double en_idle_current_a = 0.0001;     // 0.1 mA
    double en_rx_current_a = 0.0097;       // 9.7 mA
    double en_sleep_current_a = 0.0000015; // 1.5 µA
    
    // Linear TX current model parameters
    double en_tx_model_eta = 0.10;
    double en_tx_model_standby_a = 0.0001; // Same as idle
    
    // Output filenames
    std::string en_trace_file_total = "ed-energy-total.csv";
    std::string en_trace_file_remain = "ed-remaining-energy.csv";
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
    double NoiseFloorDbm(double bwHz, double nfDb) const;
    const char* SfToString(uint8_t sf) const;
    
private:
    ScenarioConfig() = default;
};

} // namespace scenario

#endif // SCENARIO_CONFIG_H