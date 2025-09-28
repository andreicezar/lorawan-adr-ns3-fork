#include "../common/scenario_config.h"
#include "ns3/command-line.h"
#include <cmath>
NS_LOG_COMPONENT_DEFINE("ScenarioConfig");
namespace scenario {

ScenarioConfig& ScenarioConfig::Get() {
    static ScenarioConfig instance;
    return instance;
}

void ScenarioConfig::ParseCommandLine(int argc, char* argv[]) {
    ns3::CommandLine cmd;
    cmd.AddValue("useExpIat", "Use exponential inter-arrival time", use_exponential_iat);
    cmd.AddValue("useOkumura", "Use Okumura-Hata propagation model", use_okumura_hata_model);
    cmd.AddValue("enableAdr", "Enable ADR in NetworkServer", enable_adr);
    cmd.Parse(argc, argv);
    
    // Adjust propagation model flags if Okumura is selected
    if (use_okumura_hata_model) {
        use_log_distance_model = false;
        use_friis_model = false;
    }
}

double ScenarioConfig::GetSnrRequirement(uint8_t sf) const {
    if (sf < 7 || sf > 12) return -7.5; // Default to SF7 requirement
    int index = 12 - sf; // SF12=0, SF11=1, ..., SF7=5
    return use_conservative_snr_thresholds ? 
           snr_requirements_conservative_db[index] : 
           snr_requirements_db[index];
}

double ScenarioConfig::DrToBwHz(uint8_t dr) const {
    return (dr <= 5) ? bandwidth_125_khz : 
           (dr == 6 ? bandwidth_250_khz : bandwidth_125_khz);
}

double ScenarioConfig::NoiseFloorDbm(double bwHz) const {
    return NoiseFloorDbm(bwHz, noise_figure_db);
}

double ScenarioConfig::NoiseFloorDbm(double bwHz, double nfDb) const {
    return thermal_noise_dbm_hz + 10.0 * std::log10(bwHz) + nfDb;
}

const char* ScenarioConfig::SfToString(uint8_t sf) const {
    switch (sf) {
        case 7: return "SF7";
        case 8: return "SF8";
        case 9: return "SF9";
        case 10: return "SF10";
        case 11: return "SF11";
        case 12: return "SF12";
        default: return "SF?";
    }
}

} // namespace scenario