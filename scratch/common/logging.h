#ifndef LOGGING_H
#define LOGGING_H

#include <string>
#include <fstream>

namespace scenario {

class CsvLogger {
public:
    // ---- Duty-cycle CSV ----
    static void OpenDutyCsv(const std::string& scenario_name, int seed);
    static void EnsureDutyCsvOpen();
    static void WriteDutyCycleRow(double sim_time_s, int node_id,
                              double tx_s, double off_s, double duty_pct,
                              double duty_cfg_pct, const std::string& notes);

    static void CloseDutyCsv();
    // Energy CSV operations
    static void OpenEnergyCsvs();
    static void CloseEnergyCsvs();
    static void WriteEnergyTotal(double t_s, double j);
    static void WriteEnergyRemaining(double t_s, double j);
    
    // SNR CSV operations
    static void EnsureSnrCsvOpen();
    static void WriteSnrRow(double t_s, unsigned gw_id, unsigned dr, unsigned sf,
                           double freq_hz, double rssi_dbm, double snr_db,
                           double req_db, double margin_db);
    static void CloseSnrCsv();
    
    // Packet details CSV operations
    static void EnsurePacketDetailsCsvOpen();
    static void WritePacketDetailsRow(
        double t_s,
        uint32_t node_id,
        const char* event_type,
        uint32_t seq_num,
        uint8_t sf,
        uint8_t dr,
        double freq_hz,
        double tx_power_dbm,
        double distance_m,
        double path_loss_db,
        double shadowing_db,
        double total_loss_db,
        double rssi_dbm,
        double noise_floor_dbm,
        double interference_dbm,
        double snr_db,
        const char* outcome
    );
    static void ClosePacketDetailsCsv();
    
    // NEW: Packet-level summary CSV (one row per received packet)
    static void OpenPacketSummaryCsv(const std::string& scenario_name, int seed);
    static void WritePacketSummaryRow(
        const std::string& simulator,
        const std::string& scenario,
        int seed,
        int distance_m,
        int sf,
        bool adr_enabled,
        int n_nodes,
        int packet_seq,
        double rssi_dbm,
        double snr_db,
        double rssi_mean_dbm,
        double rssi_std_dbm,
        double snr_mean_db,
        double snr_std_db,
        double pdr_percent,
        double der_percent,
        int packets_sent,
        int packets_received,
        double latency_ms,
        double latency_p50_ms,
        double latency_p90_ms,
        double toa_ms,
        double energy_per_tx_mj,
        double energy_total_j,
        double runtime_s,
        const std::string& notes
    );
    static void ClosePacketSummaryCsv();
    
private:
    static std::ofstream m_dutyCycleCsv; 
    static bool duty_csv_init_;
    static std::ofstream energy_total_csv;
    static std::ofstream energy_remain_csv;
    static std::ofstream snr_csv;
    static bool snr_csv_init;
    static std::ofstream packet_details_csv;
    static bool packet_details_csv_init;
    static std::ofstream packet_summary_csv;
    static bool packet_summary_csv_init;
};

} // namespace scenario

#endif // LOGGING_H