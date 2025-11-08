#ifndef METRICS_CALCULATOR_H
#define METRICS_CALCULATOR_H

#include <string>
#include <vector>

namespace scenario {

class MetricsCalculator {
public:
    // Calculate Time-on-Air in milliseconds
    static double CalculateToA(uint8_t sf, double bw_hz, uint8_t cr, uint32_t payload_bytes);
    
    // Calculate RSSI/SNR statistics from snr_log.csv
    static bool CalculateRssiSnrStats(
        const std::string& snr_log_file,
        double& rssi_mean,
        double& rssi_std,
        double& snr_mean,
        double& snr_std
    );
};

} // namespace scenario

#endif // METRICS_CALCULATOR_H