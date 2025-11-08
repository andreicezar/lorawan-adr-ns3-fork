#include "../common/metrics_calculator.h"
#include "ns3/rng-seed-manager.h"
#include "paths.h"
#include <cmath>
#include <fstream>
#include <sstream>
#include <vector>
#include <numeric>
#include "ns3/log.h"

NS_LOG_COMPONENT_DEFINE("MetricsCalculator");

namespace scenario {

double MetricsCalculator::CalculateToA(uint8_t sf, double bw_hz, uint8_t cr, uint32_t payload_bytes) {
    // LoRa Time-on-Air calculation (Semtech AN1200.22)
    double t_sym = std::pow(2.0, sf) / bw_hz;  // Symbol time
    double t_preamble = (8.0 + 4.25) * t_sym;   // Preamble time
    
    // Payload symbols
    int de = (sf >= 11) ? 1 : 0;  // Low data rate optimization
    double payload_symbols = 8.0 + std::max(
        std::ceil((8.0 * payload_bytes - 4.0 * sf + 28.0 + 16.0) / 
                  (4.0 * (sf - 2 * de))) * (cr + 4),
        0.0
    );
    
    double t_payload = payload_symbols * t_sym;
    return (t_preamble + t_payload) * 1000.0;  // Convert to ms
}

bool MetricsCalculator::CalculateRssiSnrStats(
    const std::string& snr_log_file,
    double& rssi_mean,
    double& rssi_std,
    double& snr_mean,
    double& snr_std) {
    
    std::ifstream file(snr_log_file);
    if (!file.is_open()) {
        NS_LOG_WARN("Cannot open SNR log: " << snr_log_file);
        rssi_mean = rssi_std = snr_mean = snr_std = 0.0;
        return false;
    }
    
    std::vector<double> rssi_values, snr_values;
    std::string line;
    std::getline(file, line);  // Skip header
    
    while (std::getline(file, line)) {
        std::istringstream iss(line);
        std::string token;
        std::vector<std::string> tokens;
        
        while (std::getline(iss, token, ',')) {
            tokens.push_back(token);
        }
        
        if (tokens.size() >= 7) {
            try {
                rssi_values.push_back(std::stod(tokens[5]));
                snr_values.push_back(std::stod(tokens[6]));
            } catch (...) {}
        }
    }
    file.close();
    
    if (rssi_values.empty()) {
        rssi_mean = rssi_std = snr_mean = snr_std = 0.0;
        return false;
    }
    
    // Calculate mean
    rssi_mean = std::accumulate(rssi_values.begin(), rssi_values.end(), 0.0) / rssi_values.size();
    snr_mean = std::accumulate(snr_values.begin(), snr_values.end(), 0.0) / snr_values.size();
    
    // Calculate std dev
    double rssi_sq_sum = 0.0, snr_sq_sum = 0.0;
    for (size_t i = 0; i < rssi_values.size(); ++i) {
        rssi_sq_sum += std::pow(rssi_values[i] - rssi_mean, 2);
        snr_sq_sum += std::pow(snr_values[i] - snr_mean, 2);
    }
    
    rssi_std = std::sqrt(rssi_sq_sum / rssi_values.size());
    snr_std = std::sqrt(snr_sq_sum / snr_values.size());
    
    return true;
}

} // namespace scenario