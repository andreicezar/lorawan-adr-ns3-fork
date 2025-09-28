#include "../common/logging.h"
#include "../common/paths.h"
#include "../common/scenario_config.h"

namespace scenario {

std::ofstream CsvLogger::energy_total_csv;
std::ofstream CsvLogger::energy_remain_csv;
std::ofstream CsvLogger::snr_csv;
bool CsvLogger::snr_csv_init = false;

void CsvLogger::OpenEnergyCsvs() {
    auto& config = ScenarioConfig::Get();
    energy_total_csv.open(OutPath(config.en_trace_file_total));
    energy_total_csv << "t_s,total_J\n";
    
    energy_remain_csv.open(OutPath(config.en_trace_file_remain));
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
        snr_csv << "t_s,gw_id,dr,sf,frequency_hz,rssi_dbm,snr_db,req_db,margin_db,fade_margin_db\n";
        snr_csv_init = true;
    }
}

void CsvLogger::WriteSnrRow(double t_s, unsigned gw_id, unsigned dr, unsigned sf,
                            double freq_hz, double rssi_dbm, double snr_db,
                            double req_db, double margin_db, double fade_margin_db) {
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
           << margin_db << ","
           << fade_margin_db << "\n";
}

void CsvLogger::CloseSnrCsv() {
    if (snr_csv.is_open()) snr_csv.close();
}

} // namespace scenario