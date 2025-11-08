// scratch/common/lora_utils.h
#pragma once
#include <algorithm>
#include <cstdint>
#include <cmath>
#include <string>

namespace lora {

// ==============================
// Region helpers (EU868 defaults)
// ==============================
inline uint8_t DrFromSfEu868(uint8_t sf) { sf = std::clamp<uint8_t>(sf, 7, 12); return 12 - sf; }
inline uint8_t SfFromDrEu868(uint8_t dr) { dr = std::clamp<uint8_t>(dr, 0,  5);  return 12 - dr; }

// Low Data Rate Optimization (DE) for 125 kHz: enabled at SF11–12
inline int LdrOptimization(uint8_t sf) { return (sf >= 11) ? 1 : 0; }

// ==============================
// Core LoRa PHY math (Semtech)
// ==============================

inline double SymbolTime_ms(uint8_t sf, double bw_hz) {
    // T_sym = 2^SF / BW   (seconds)  => *1000 for ms
    return (static_cast<double>(1u << sf) / bw_hz) * 1000.0;
}

/**
 * Time-on-air (ms) per Semtech formula.
 * cr in {1,2,3,4} corresponds to coding rate 4/(4+cr) i.e. 1 => 4/5.
 * Defaults: BW=125kHz, CR=4/5, Explicit header, CRC on, Preamble=8+4.25.
 */
inline double ToA_ms(uint8_t sf,
                     double bw_hz = 125000.0,
                     uint8_t cr = 1,
                     uint16_t payload_bytes = 51,
                     bool explicit_header = true,
                     bool crc_on = true,
                     double preamble_sym = 8.0,
                     double extra_preamble = 4.25)
{
    sf = std::clamp<uint8_t>(sf, 7, 12);
    const double tsym = SymbolTime_ms(sf, bw_hz);
    const double tpreamble = (preamble_sym + extra_preamble) * tsym;

    const int DE  = LdrOptimization(sf);         // (for 125 kHz)
    const int IH  = explicit_header ? 0 : 1;
    const int CRC = crc_on ? 1 : 0;

    const double num = std::max(0.0,
        std::ceil((8.0 * payload_bytes - 4.0 * sf + 28.0 + 16.0 * CRC - 20.0 * IH) /
                  (4.0 * (sf - 2.0 * DE))) * (cr + 4));

    const double payload_symbols = 8.0 + num;
    return tpreamble + payload_symbols * tsym;   // ms
}

// Friendly wrappers (keep your old call names)
inline double CalculateAirTime(uint8_t sf,
                               double bw_hz = 125000.0,
                               uint8_t cr = 1,
                               uint16_t payload_bytes = 51,
                               bool explicit_header = true,
                               bool crc_on = true,
                               double preamble_sym = 8.0,
                               double extra_preamble = 4.25)
{
    return ToA_ms(sf, bw_hz, cr, payload_bytes, explicit_header, crc_on,
                  preamble_sym, extra_preamble);
}

inline double CalculateAirTimeFromDr(uint8_t dr,
                                     double bw_hz = 125000.0,
                                     uint8_t cr = 1,
                                     uint16_t payload_bytes = 51,
                                     bool explicit_header = true,
                                     bool crc_on = true,
                                     double preamble_sym = 8.0,
                                     double extra_preamble = 4.25)
{
    return ToA_ms(SfFromDrEu868(dr), bw_hz, cr, payload_bytes, explicit_header, crc_on,
                  preamble_sym, extra_preamble);
}

// ==================================
// Propagation / RF helpers (Log/Friis)
// ==================================

// Log-distance path loss (dB). refLoss_dB is PL at 1 m. Clamp d >= 1 m.
inline double PathLossLogDistance_dB(double d_m,
                                     double refLoss_dB = 7.7,
                                     double n = 3.76)
{
    if (d_m < 1.0) d_m = 1.0;
    return refLoss_dB + 10.0 * n * std::log10(d_m);
}

inline double Rssi_dBm_fromDistance(double txPower_dBm, double d_m,
                                    double refLoss_dB = 7.7, double n = 3.76)
{
    return txPower_dBm - PathLossLogDistance_dB(d_m, refLoss_dB, n);
}

// Free-space path loss (dB). Uses exact physics: 20 log10(4π d f / c).
inline double FreeSpacePathLoss_dB(double freq_hz, double d_m) {
    constexpr double c = 299'792'458.0; // m/s
    if (d_m <= 0.0) d_m = 1.0;
    const double arg = 4.0 * M_PI * d_m * freq_hz / c;
    return 20.0 * std::log10(arg);
}

inline double Rssi_dBm_FreeSpace(double txPower_dBm, double freq_hz, double d_m) {
    return txPower_dBm - FreeSpacePathLoss_dB(freq_hz, d_m);
}

// Noise floor (dBm) in given BW with a receiver noise figure (dB)
inline double NoiseFloor_dBm(double bw_hz = 125000.0, double noiseFigure_dB = 6.0) {
    // -174 dBm/Hz + 10 log10(BW) + NF
    return -174.0 + 10.0 * std::log10(bw_hz) + noiseFigure_dB;
}

inline double Snr_dB(double rssi_dBm, double noiseFloor_dBm) {
    return rssi_dBm - noiseFloor_dBm;
}

// ==================================
// Traffic/load helpers (Erlangs etc.)
// ==================================
inline double OfferedLoadErlangs(double total_airtime_ms,
                                 double sim_seconds,
                                 int channels = 1)
{
    if (sim_seconds <= 0.0 || channels <= 0) return 0.0;
    // G per channel = (busy time) / (available time)
    return (total_airtime_ms / 1000.0) / (sim_seconds * channels);
}

// Keep unclamped so you can see overload; clamp in UI if desired.
inline double ChannelUtilizationPercent(double offered_load_erlangs) {
    return offered_load_erlangs * 100.0;
}

// ==================================
// Packet identity & context helpers
// ==================================
inline std::uint64_t MakePacketKey(std::uint32_t devaddr, std::uint32_t fcnt) {
    return (static_cast<std::uint64_t>(devaddr) << 32) | static_cast<std::uint64_t>(fcnt);
}

/**
 * Extracts the numeric NodeId from an ns-3 Config context path like:
 *   "/NodeList/12/DeviceList/0/$ns3::LorawanNetDevice/..."
 * Returns 0 if not found or parse fails (treat 0 as "unknown" if that's safer for you).
 */
inline std::uint32_t ExtractGatewayNodeIdFromContext(const std::string& ctx) {
    const std::string needle = "/NodeList/";
    std::size_t p = ctx.find(needle);
    if (p == std::string::npos) return 0;
    p += needle.size();
    std::size_t q = p;
    while (q < ctx.size() && std::isdigit(static_cast<unsigned char>(ctx[q]))) ++q;
    if (q == p) return 0;
    try {
        return static_cast<std::uint32_t>(std::stoul(ctx.substr(p, q - p)));
    } catch (...) { return 0; }
}

// ==============================
// Geometry helpers
// ==============================
inline double Distance2D(double x1, double y1, double x2, double y2) {
    const double dx = x1 - x2, dy = y1 - y2;
    return std::hypot(dx, dy);
}

inline double Distance3D(double x1, double y1, double z1,
                         double x2, double y2, double z2) {
    const double dx = x1 - x2, dy = y1 - y2, dz = z1 - z2;
    return std::sqrt(dx*dx + dy*dy + dz*dz);
}

// ==============================
// Generic metric helpers
// ==============================
inline double RatePercent(std::uint64_t num, std::uint64_t den) {
    return den ? (100.0 * static_cast<double>(num) / static_cast<double>(den)) : 0.0;
}

inline double PdrPercent(std::uint64_t received, std::uint64_t sent) {
    return RatePercent(received, sent);
}

inline double DeduplicationRatePercent(std::uint64_t duplicates, std::uint64_t total_hearings) {
    return total_hearings ? (100.0 * static_cast<double>(duplicates) / static_cast<double>(total_hearings)) : 0.0;
}

inline double DropRatePercent(std::uint64_t lost, std::uint64_t sent) {
    return RatePercent(lost, sent);
}

} // namespace lora