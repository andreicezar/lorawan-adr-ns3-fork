
/**
 * Comparison Scenarios Header File
 * Defines global measurement variables and scenario configurations
 * for NS3 vs OMNeT++ Flora LoRaWAN comparison study
 */

#ifndef COMPARISON_SCENARIOS_H
#define COMPARISON_SCENARIOS_H

#include <map>
#include <vector>
#include <string>

// Global measurement variables for accurate data collection
namespace ComparisonMetrics {
    // Packet tracking variables
    extern std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
    extern std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
    extern std::map<uint32_t, uint32_t> g_acknowledgedPacketsPerNode;
    
    // ADR tracking variables
    extern std::map<uint32_t, std::vector<uint8_t>> g_sfHistoryPerNode;
    extern std::map<uint32_t, std::vector<double>> g_tpHistoryPerNode;
    extern std::map<uint32_t, uint32_t> g_adrCommandsPerNode;
    
    // Network performance variables
    extern uint32_t g_totalPacketsSent;
    extern uint32_t g_totalPacketsReceived;
    extern uint32_t g_totalPacketsLost;
    extern uint32_t g_totalAdrCommands;
    
    // Energy consumption tracking
    extern std::map<uint32_t, double> g_energyConsumedPerNode;
    extern double g_totalEnergyConsumed;
    
    // Timing measurements
    extern std::map<uint32_t, double> g_avgDelayPerNode;
    extern double g_simulationStartTime;
    extern double g_simulationEndTime;
    
    // Collision and interference tracking
    extern uint32_t g_totalCollisions;
    extern uint32_t g_totalInterference;
    
    // Gateway load balancing
    extern std::map<uint32_t, uint32_t> g_packetsPerGateway;
}

// Scenario configuration matrix
// Matrix values: 0 = disabled/low, 1 = enabled/medium, 2 = high/optimized
struct ScenarioConfig {
    uint32_t scenarioId;
    std::string scenarioName;
    std::string simulator; // "ns3" or "omnet"
    
    // Network topology (0=single GW, 1=multiple GW, 2=optimized placement)
    uint8_t gatewayTopology;
    
    // ADR configuration (0=disabled, 1=basic, 2=advanced)
    uint8_t adrLevel;
    
    // Traffic load (0=light, 1=medium, 2=heavy)
    uint8_t trafficLoad;
    
    // Node density (0=sparse, 1=medium, 2=dense)
    uint8_t nodeDensity;
    
    // Mobility (0=static, 1=low mobility, 2=high mobility)
    uint8_t mobility;
    
    // Confirmed messages (0=none, 1=some, 2=all)
    uint8_t confirmedMessages;
    
    // Parameters
    uint32_t numNodes;
    uint32_t numGateways;
    uint32_t simulationTime; // minutes
    uint32_t packetInterval; // seconds
    double areaSize; // meters
    bool adrEnabled;
    std::string adrMethod;
};

// Predefined scenarios for comparison
extern std::vector<ScenarioConfig> g_comparisonScenarios;

// Function declarations
void InitializeMeasurementVariables();
void ResetMeasurementVariables();
void RecordPacketSent(uint32_t nodeId);
void RecordPacketReceived(uint32_t nodeId, uint32_t gatewayId);
void RecordPacketAcknowledged(uint32_t nodeId);
void RecordAdrCommand(uint32_t nodeId, uint8_t newSf, double newTp);
void RecordEnergyConsumption(uint32_t nodeId, double energy);
void RecordCollision();
void RecordInterference();
void ExportResults(const ScenarioConfig& config, const std::string& outputFile);
ScenarioConfig GetScenarioConfig(uint32_t scenarioId);

#endif // COMPARISON_SCENARIOS_H