// common/position_loader.h
// Helper functions to load positions from CSV file for consistent topology

#ifndef POSITION_LOADER_H
#define POSITION_LOADER_H

#include "ns3/core-module.h"
#include "ns3/mobility-helper.h"
#include "ns3/node-container.h"
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <map>
#include <filesystem>   // ✅ added

namespace ns3 {

namespace fs = std::filesystem; // ✅ added

struct Position {
    double x;
    double y; 
    double z;
};

class PositionLoader {
public:
    /**
     * Load positions from CSV file for a specific scenario
     * @param filename Path to CSV file (relative or absolute)
     * @param scenarioName Name of scenario to load (e.g., "scenario_01_baseline")
     * @return true if successful
     */
    static bool LoadFromCSV(const std::string& filename, const std::string& scenarioName) {
        // Reset
        m_devicePositions.clear();
        m_gatewayPositions.clear();

        // --- Build candidate paths (safe joins)
        namespace fs = std::filesystem;
        fs::path requested(filename);
        std::vector<fs::path> candidates;

        if (requested.is_absolute()) {
            candidates.push_back(requested);
        } else {
            const fs::path cwd = fs::current_path();
            candidates.push_back(cwd / requested);
            if (!scenarioName.empty()) {
                candidates.push_back(cwd / scenarioName / requested);
                candidates.push_back(cwd / "output" / scenarioName / requested);
            }
            candidates.push_back(cwd / "positions" / requested); // common folder name

    #ifdef PROJECT_SOURCE_PATH
            {
                const fs::path projectRoot(PROJECT_SOURCE_PATH);
                candidates.push_back(projectRoot / requested);
                if (!scenarioName.empty()) {
                    candidates.push_back(projectRoot / scenarioName / requested);
                    candidates.push_back(projectRoot / "output" / scenarioName / requested);
                }
                candidates.push_back(projectRoot / "positions" / requested);
            }
    #endif
            if (const char* env = std::getenv("NS3_PROJECT_ROOT")) {
                const fs::path envRoot(env);
                candidates.push_back(envRoot / requested);
                if (!scenarioName.empty()) {
                    candidates.push_back(envRoot / scenarioName / requested);
                    candidates.push_back(envRoot / "output" / scenarioName / requested);
                }
                candidates.push_back(envRoot / "positions" / requested);
            }
        }

        NS_LOG_INFO("PositionLoader: cwd = " << fs::current_path().string());
        fs::path chosen;
        std::error_code ec;
        for (const auto& p : candidates) {
            NS_LOG_INFO("PositionLoader: trying " << p.string());
            if (fs::exists(p, ec) && fs::is_regular_file(p, ec)) { chosen = p; break; }
        }

        if (chosen.empty()) {
            NS_LOG_ERROR("PositionLoader: could not locate position file. Tried:");
            for (const auto& p : candidates) { NS_LOG_ERROR("  " << p.string()); }
            return false;
        }

        NS_LOG_INFO("Loading positions from " << chosen.string() << " for " << scenarioName);
        std::ifstream file(chosen);
        if (!file.is_open()) {
            NS_LOG_ERROR("Found file but could not open: " << chosen.string());
            return false;
        }

        // --- Helpers
        auto trim = [](std::string& s) {
            auto notsp = [](int ch){ return !std::isspace(ch); };
            s.erase(s.begin(), std::find_if(s.begin(), s.end(), notsp));
            s.erase(std::find_if(s.rbegin(), s.rend(), notsp).base(), s.end());
        };
        auto lower = [](std::string s) {
            std::transform(s.begin(), s.end(), s.begin(),
                        [](unsigned char c){ return std::tolower(c); });
            return s;
        };

        // --- Parse CSV (columns: scenario,type,id,x,y,z). Skips header/comments.
        std::string line;
        bool first = true;
        while (std::getline(file, line)) {
            if (line.empty()) continue;
            if (line[0] == '#') continue;

            // Handle header on first line
            if (first) {
                std::string probe = lower(line);
                if (probe.find("scenario") != std::string::npos &&
                    probe.find("type")     != std::string::npos) {
                    first = false;
                    continue; // skip header
                }
                first = false;
            }

            std::istringstream iss(line);
            std::string scenario, type, idStr, xStr, yStr, zStr;
            if (!std::getline(iss, scenario, ',')) continue;
            if (!std::getline(iss, type,     ',')) continue;
            if (!std::getline(iss, idStr,    ',')) continue;
            if (!std::getline(iss, xStr,     ',')) continue;
            if (!std::getline(iss, yStr,     ',')) continue;
            if (!std::getline(iss, zStr,     ',')) continue;

            trim(scenario); trim(type); trim(idStr); trim(xStr); trim(yStr); trim(zStr);
            if (scenario != scenarioName) continue;

            // Accept common synonyms for type
            std::string t = lower(type);
            bool isGw = (t == "gateway" || t == "gw" || t == "g" || t == "base" || t == "bs");
            bool isEd = (t == "enddevice" || t == "end_device" || t == "end-device" ||
                        t == "endnode"   || t == "device"     || t == "node"      ||
                        t == "ed"        || t == "end");

            try {
                Position pos { std::stod(xStr), std::stod(yStr), std::stod(zStr) };
                if (isGw) {
                    m_gatewayPositions.push_back(pos);
                } else if (isEd) {
                    m_devicePositions.push_back(pos);
                } else {
                    NS_LOG_WARN("Unknown CSV type: '" << type << "' — line ignored: " << line);
                }
            } catch (const std::exception& e) {
                NS_LOG_WARN("Bad numeric fields in line: " << line << " (" << e.what() << ")");
                continue;
            }
        }
        file.close();

        NS_LOG_INFO("Loaded " << m_devicePositions.size()
                    << " device positions and " << m_gatewayPositions.size()
                    << " gateway positions for " << scenarioName);

        // If no devices were loaded for the scenario, signal failure so caller can fallback.
        if (m_devicePositions.empty()) {
            NS_LOG_ERROR("No end-device positions found for " << scenarioName
                        << " in " << chosen.string());
            return false;
        }
        return true;
    }

    /**
     * Apply loaded positions to nodes
     * @param endDevices Container of end device nodes
     * @param gateways Container of gateway nodes
     */
    static void ApplyPositions(NodeContainer& endDevices, NodeContainer& gateways) {
        MobilityHelper mobility;

        // Apply gateway positions
        if (!m_gatewayPositions.empty()) {
            Ptr<ListPositionAllocator> gwPositionAlloc = CreateObject<ListPositionAllocator>();
            for (const auto& pos : m_gatewayPositions) {
                gwPositionAlloc->Add(Vector(pos.x, pos.y, pos.z));
            }
            mobility.SetPositionAllocator(gwPositionAlloc);
            mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
            mobility.Install(gateways);

            NS_LOG_INFO("Applied positions to " << gateways.GetN() << " gateways");
        }

        // Apply end device positions
        if (!m_devicePositions.empty()) {
            Ptr<ListPositionAllocator> edPositionAlloc = CreateObject<ListPositionAllocator>();
            for (uint32_t i = 0; i < std::min((uint32_t)m_devicePositions.size(), endDevices.GetN()); i++) {
                edPositionAlloc->Add(Vector(m_devicePositions[i].x,
                                           m_devicePositions[i].y,
                                           m_devicePositions[i].z));
            }
            mobility.SetPositionAllocator(edPositionAlloc);
            mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
            mobility.Install(endDevices);

            NS_LOG_INFO("Applied positions to " << endDevices.GetN() << " end devices");
        }
    }

    static bool LoadAndApplyPositions(const std::string& filename,
                                      const std::string& scenarioName,
                                      NodeContainer& endDevices,
                                      NodeContainer& gateways,
                                      bool fallbackToRandom = true) {

        // Try to load from file
        if (LoadFromCSV(filename, scenarioName)) {
            ApplyPositions(endDevices, gateways);
            std::cout << "✅ Loaded positions from " << filename << " for " << scenarioName << std::endl;
            return true;
        }

        // Fallback to random if enabled and file not found
        if (fallbackToRandom) {
            std::cout << "⚠️ Position file not found, using random positions with fixed seed" << std::endl;
            RngSeedManager::SetSeed(12345);  // Use same seed as Python script
            RngSeedManager::SetRun(1);
            return false;
        }

        NS_FATAL_ERROR("Could not load positions from " << filename << " for " << scenarioName);
        return false;
    }

    static const std::vector<Position>& GetDevicePositions() {
        return m_devicePositions;
    }

    static const std::vector<Position>& GetGatewayPositions() {
        return m_gatewayPositions;
    }

private:
    static std::vector<Position> m_devicePositions;
    static std::vector<Position> m_gatewayPositions;
};

// Static member definitions
std::vector<Position> PositionLoader::m_devicePositions;
std::vector<Position> PositionLoader::m_gatewayPositions;

/**
 * Replacement for SetupStandardMobility that uses CSV positions
 * @param endDevices End device container
 * @param gateways Gateway container  
 * @param sideLengthMeters Area size (not used when loading from file)
 * @param scenarioName Name of scenario for CSV lookup
 * @param positionFile Path to CSV file (default: "scenario_positions.csv")
 */
void SetupMobilityFromFile(NodeContainer& endDevices,
                           NodeContainer& gateways,
                           double sideLengthMeters,
                           const std::string& scenarioName,
                           const std::string& positionFile = "scenario_positions.csv") {

    // Try to load from CSV
    bool loadedFromFile = PositionLoader::LoadAndApplyPositions(
        positionFile, scenarioName, endDevices, gateways, true);

    // If loading failed, fall back to the original SetupStandardMobility
    if (!loadedFromFile) {
        // This calls the original random placement function
        SetupStandardMobility(endDevices, gateways, sideLengthMeters);
    }
}

} // namespace ns3

#endif // POSITION_LOADER_H
