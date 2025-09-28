#ifndef LOGGING_H
#define LOGGING_H

#include <string>
#include <fstream>

namespace scenario {

class CsvLogger {
public:
    // Energy CSV operations
    static void OpenEnergyCsvs();
    static void CloseEnergyCsvs();
    static void WriteEnergyTotal(double t_s, double j);
    static void WriteEnergyRemaining(double t_s, double j);
    
    // SNR CSV operations
    static void EnsureSnrCsvOpen();
    static void WriteSnrRow(double t_s, unsigned gw_id, unsigned dr, unsigned sf,
                           double freq_hz, double rssi_dbm, double snr_db,
                           double req_db, double margin_db, double fade_margin_db);
    static void CloseSnrCsv();
    
private:
    static std::ofstream energy_total_csv;
    static std::ofstream energy_remain_csv;
    static std::ofstream snr_csv;
    static bool snr_csv_init;
};

} // namespace scenario

#endif // LOGGING_H