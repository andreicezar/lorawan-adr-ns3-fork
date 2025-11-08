#include "../common/logging.h"
#include "../common/paths.h"
#include "../common/scenario_config.h"
#include "ns3/log.h"
#include <iomanip>

NS_LOG_COMPONENT_DEFINE("CsvLogger");

namespace scenario {

std::ofstream CsvLogger::energy_total_csv;
std::ofstream CsvLogger::energy_remain_csv;
std::ofstream CsvLogger::snr_csv;
bool CsvLogger::snr_csv_init = false;
std::ofstream CsvLogger::packet_details_csv;
bool CsvLogger::packet_details_csv_init = false;
std::ofstream CsvLogger::packet_summary_csv;
bool CsvLogger::packet_summary_csv_init = false;

void CsvLogger::OpenEnergyCsvs() {
    auto& config = ScenarioConfig::Get();
    energy_total_csv.open(OutPath(config.en_trace_file_total));
    energy_total_csv << "t_s,total_J\n";
    
    energy_remain_csv.open(OutPath(config.en_trace_file_rmn));
    energy_remain_csv << "t_s,remain_J\n";
}

void CsvLogger::CloseEnergyCsvs() {
    if (energy_total_csv.is_open()) energy_total_csv.close();
    if (energy_remain_csv.is_open()) energy_remain_csv.close();
}

void CsvLogger::WriteEnergyTotal(double t_s, double j) {
    energy_total_csv << t_s << "," << j << "\n";
}

void CsvLogger::WriteEnergyRemaining(double t_s, double j) {
    energy_remain_csv << t_s << "," << j << "\n";
}

void CsvLogger::EnsureSnrCsvOpen() {
    if (!snr_csv_init) {
        auto& config = ScenarioConfig::Get();
        snr_csv.open(OutPath(config.snr_log_file), std::ios::out);
        snr_csv << "t_s,gw_id,dr,sf,frequency_hz,rssi_dbm,snr_db,req_db,margin_db\n";
        snr_csv_init = true;
    }
}
std::ofstream CsvLogger::m_dutyCycleCsv;  // This is where the CSV file will be written

bool CsvLogger::duty_csv_init_ = false;

static std::string s_dutyCycleFilename = "";  // Store the filename

void CsvLogger::OpenDutyCsv(const std::string& scenario_name, int seed) {
    if (!m_dutyCycleCsv.is_open()) {
        s_dutyCycleFilename = scenario_name + "_seed" + std::to_string(seed) + "_duty_cycle.csv";
        std::string outputPath = OutPath(s_dutyCycleFilename);
        
        NS_LOG_INFO("Opening duty cycle CSV at: " << outputPath);
        
        m_dutyCycleCsv.open(outputPath, std::ios::out);
        
        if (m_dutyCycleCsv.is_open()) {
            m_dutyCycleCsv << "Time [s],ED Node ID,Tx Time [s],Off Time [s],Duty Cycle [%],Duty Cycle Fraction,Notes\n";
            m_dutyCycleCsv.flush();
            NS_LOG_INFO("Duty Cycle CSV opened: " << outputPath);
        } else {
            NS_LOG_ERROR("Failed to open Duty Cycle CSV file: " << outputPath);
        }
    }
}

void CsvLogger::EnsureDutyCsvOpen() {
    if (!m_dutyCycleCsv.is_open() && !s_dutyCycleFilename.empty()) {
        // Reopen if needed
        std::string outputPath = OutPath(s_dutyCycleFilename);
        m_dutyCycleCsv.open(outputPath, std::ios::app);  // Append mode
    }
}

void CsvLogger::WriteDutyCycleRow(double time, int nodeId, double tx_s, double off_s, 
                                  double duty_pct, double dc_fraction, const std::string& notes) {
    NS_LOG_UNCOND("DEBUG: WriteDutyCycleRow called - time=" << time << " nodeId=" << nodeId);  // ← ADD THIS
    
    EnsureDutyCsvOpen();
    
    if (!m_dutyCycleCsv.is_open()) {  // ← ADD THIS CHECK
        NS_LOG_ERROR("CRITICAL: Duty cycle CSV still not open after EnsureDutyCsvOpen()!");
        return;
    }
    
    m_dutyCycleCsv << time << "," << nodeId << "," << tx_s << "," << off_s << "," 
                   << duty_pct << "," << dc_fraction << ",\"" << notes << "\"\n";
    m_dutyCycleCsv.flush();
    
    NS_LOG_UNCOND("DEBUG: Wrote duty cycle row to CSV");  // ← ADD THIS
}


void CsvLogger::CloseDutyCsv() {
    if (m_dutyCycleCsv.is_open()) m_dutyCycleCsv.close();
}

void CsvLogger::WriteSnrRow(double t_s, unsigned gw_id, unsigned dr, unsigned sf,
                            double freq_hz, double rssi_dbm, double snr_db,
                            double req_db, double margin_db) {
    EnsureSnrCsvOpen();
    snr_csv << std::fixed
           << t_s << ","
           << gw_id << ","
           << dr << ","
           << sf << ","
           << freq_hz << ","
           << rssi_dbm << ","
           << snr_db << ","
           << req_db << ","
           << margin_db << "\n";
}

void CsvLogger::CloseSnrCsv() {
    if (snr_csv.is_open()) snr_csv.close();
}

void CsvLogger::EnsurePacketDetailsCsvOpen() {
    if (!packet_details_csv_init) {
        packet_details_csv.open(OutPath("packet_details.csv"), std::ios::out);
        packet_details_csv << "t_s,node_id,event_type,seq_num,sf,dr,"
                          << "frequency_hz,tx_power_dbm,distance_m,"
                          << "path_loss_db,shadowing_db,total_loss_db,"
                          << "rssi_dbm,noise_floor_dbm,interference_dbm,"
                          << "snr_db,outcome\n";
        packet_details_csv_init = true;
    }
}

void CsvLogger::WritePacketDetailsRow(
    double t_s, uint32_t node_id, const char* event_type,
    uint32_t seq_num, uint8_t sf, uint8_t dr,
    double freq_hz, double tx_power_dbm, double distance_m,
    double path_loss_db, double shadowing_db, double total_loss_db,
    double rssi_dbm, double noise_floor_dbm, double interference_dbm,
    double snr_db, const char* outcome) {
    
    EnsurePacketDetailsCsvOpen();
    packet_details_csv << std::fixed << std::setprecision(6)
        << t_s << "," << node_id << "," << event_type << ","
        << seq_num << "," << int(sf) << "," << int(dr) << ","
        << freq_hz << "," << tx_power_dbm << "," << distance_m << ","
        << path_loss_db << "," << shadowing_db << "," << total_loss_db << ","
        << rssi_dbm << "," << noise_floor_dbm << "," << interference_dbm << ","
        << snr_db << "," << outcome << "\n";
}

void CsvLogger::ClosePacketDetailsCsv() {
    if (packet_details_csv.is_open()) packet_details_csv.close();
}

// NEW: Packet-level summary CSV
void CsvLogger::OpenPacketSummaryCsv(const std::string& scenario_name, int seed) {
    if (!packet_summary_csv_init) {
        std::string filename = scenario_name + "_seed" + std::to_string(seed) + "_packets.csv";
        packet_summary_csv.open(OutPath(filename), std::ios::out);
        
        packet_summary_csv << "simulator,scenario,seed,distance_m,sf,adr_enabled,n_nodes,"
                          << "packet_seq,rssi_dbm,snr_db,"
                          << "rssi_mean_dbm,rssi_std_dbm,snr_mean_db,snr_std_db,"
                          << "pdr_percent,der_percent,packets_sent,packets_received,"
                          << "latency_ms,latency_p50_ms,latency_p90_ms,toa_ms,"
                          << "energy_per_tx_mj,energy_total_j,runtime_s,notes\n";
        
        packet_summary_csv_init = true;
        NS_LOG_INFO("Opened packet summary CSV: " << filename);
    }
}

void CsvLogger::WritePacketSummaryRow(
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
    const std::string& notes) {
    
    if (!packet_summary_csv_init) {
        NS_LOG_ERROR("Packet summary CSV not initialized!");
        return;
    }
    
    packet_summary_csv << std::fixed << std::setprecision(3)
        << simulator << ","
        << scenario << ","
        << seed << ","
        << distance_m << ","
        << (int)sf << ","
        << (adr_enabled ? "true" : "false") << ","
        << n_nodes << ","
        << packet_seq << ","
        << rssi_dbm << ","
        << snr_db << ","
        << rssi_mean_dbm << ","
        << rssi_std_dbm << ","
        << snr_mean_db << ","
        << snr_std_db << ","
        << pdr_percent << ","
        << der_percent << ","
        << packets_sent << ","
        << packets_received << ","
        << latency_ms << ","
        << latency_p50_ms << ","
        << latency_p90_ms << ","
        << toa_ms << ","
        << energy_per_tx_mj << ","
        << energy_total_j << ","
        << runtime_s << ","
        << "\"" << notes << "\"\n";
    
    packet_summary_csv.flush();
}

void CsvLogger::ClosePacketSummaryCsv() {
    if (packet_summary_csv.is_open()) {
        packet_summary_csv.close();
        packet_summary_csv_init = false;
    }
}

} // namespace scenario