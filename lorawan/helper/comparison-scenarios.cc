/**
 * Comparison Scenarios Implementation
 * NS3 vs OMNeT++ Flora LoRaWAN comparison study
 */

#include "comparison-scenarios.h"
#include <iostream>
#include <fstream>
#include <iomanip>
#include <chrono>

namespace ComparisonMetrics {
    // Global measurement variables initialization
    std::map<uint32_t, uint32_t> g_sentPacketsPerNode;
    std::map<uint32_t, uint32_t> g_receivedPacketsPerNode;
    std::map<uint32_t, uint32_t> g_acknowledgedPacketsPerNode;
    
    std::map<uint32_t, std::vector<uint8_t>> g_sfHistoryPerNode;
    std::map<uint32_t, std::vector<double>> g_tpHistoryPerNode;
    std::map<uint32_t, uint32_t> g_adrCommandsPerNode;
    
    uint32_t g_totalPacketsSent = 0;
    uint32_t g_totalPacketsReceived = 0;
    uint32_t g_totalPacketsLost = 0;
    uint32_t g_totalAdrCommands = 0;
    
    std::map<uint32_t, double> g_energyConsumedPerNode;
    double g_totalEnergyConsumed = 0.0;
    
    std::map<uint32_t, double> g_avgDelayPerNode;
    double g_simulationStartTime = 0.0;
    double g_simulationEndTime = 0.0;
    
    uint32_t g_totalCollisions = 0;
    uint32_t g_totalInterference = 0;
    
    std::map<uint32_t, uint32_t> g_packetsPerGateway;
}

// Scenario definitions based on comparison matrix
std::vector<ScenarioConfig> g_comparisonScenarios = {
    // Basic scenarios - Single Gateway
    {1, "NS3_Basic_Single_GW", "ns3", 0, 0, 0, 0, 0, 0, 100, 1, 10, 300, 2000, false, "none"},
    {2, "OMNeT_Basic_Single_GW", "omnet", 0, 0, 0, 0, 0, 0, 100, 1, 10, 300, 2000, false, "none"},
    
    // ADR Enabled scenarios
    {3, "NS3_ADR_Basic", "ns3", 0, 1, 0, 0, 0, 0, 100, 1, 10, 300, 2000, true, "basic"},
    {4, "OMNeT_ADR_Basic", "omnet", 0, 1, 0, 0, 0, 0, 100, 1, 10, 300, 2000, true, "avg"},
    
    // Medium load scenarios
    {5, "NS3_Medium_Load", "ns3", 0, 1, 1, 1, 0, 0, 500, 1, 20, 180, 5000, true, "basic"},
    {6, "OMNeT_Medium_Load", "omnet", 0, 1, 1, 1, 0, 0, 500, 1, 20, 180, 5000, true, "avg"},
    
    // High density scenarios
    {7, "NS3_High_Density", "ns3", 1, 1, 1, 2, 0, 0, 1000, 3, 30, 120, 3000, true, "basic"},
    {8, "OMNeT_High_Density", "omnet", 1, 1, 1, 2, 0, 0, 1000, 3, 30, 120, 3000, true, "avg"},
    
    // Heavy traffic scenarios
    {9, "NS3_Heavy_Traffic", "ns3", 1, 1, 2, 1, 0, 1, 500, 3, 30, 60, 4000, true, "advanced"},
    {10, "OMNeT_Heavy_Traffic", "omnet", 1, 1, 2, 1, 0, 1, 500, 3, 30, 60, 4000, true, "max"},
    
    // Mobility scenarios
    {11, "NS3_Low_Mobility", "ns3", 1, 1, 1, 1, 1, 0, 300, 2, 25, 150, 4000, true, "basic"},
    {12, "OMNeT_Low_Mobility", "omnet", 1, 1, 1, 1, 1, 0, 300, 2, 25, 150, 4000, true, "avg"},
    
    // Confirmed messages scenarios
    {13, "NS3_Confirmed_All", "ns3", 0, 1, 1, 1, 0, 2, 200, 1, 20, 200, 3000, true, "basic"},
    {14, "OMNeT_Confirmed_All", "omnet", 0, 1, 1, 1, 0, 2, 200, 1, 20, 200, 3000, true, "avg"},
    
    // Large scale scenarios
    {15, "NS3_Large_Scale", "ns3", 2, 2, 2, 2, 0, 1, 2000, 7, 60, 90, 8000, true, "advanced"},
    {16, "OMNeT_Large_Scale", "omnet", 2, 2, 2, 2, 0, 1, 2000, 7, 60, 90, 8000, true, "max"},
    
    // Stress test scenarios
    {17, "NS3_Stress_Test", "ns3", 2, 2, 2, 2, 1, 2, 5000, 10, 90, 30, 10000, true, "advanced"},
    {18, "OMNeT_Stress_Test", "omnet", 2, 2, 2, 2, 1, 2, 5000, 10, 90, 30, 10000, true, "max"}
};

void InitializeMeasurementVariables() {
    using namespace ComparisonMetrics;
    
    g_sentPacketsPerNode.clear();
    g_receivedPacketsPerNode.clear();
    g_acknowledgedPacketsPerNode.clear();
    g_sfHistoryPerNode.clear();
    g_tpHistoryPerNode.clear();
    g_adrCommandsPerNode.clear();
    g_energyConsumedPerNode.clear();
    g_avgDelayPerNode.clear();
    g_packetsPerGateway.clear();
    
    g_totalPacketsSent = 0;
    g_totalPacketsReceived = 0;
    g_totalPacketsLost = 0;
    g_totalAdrCommands = 0;
    g_totalEnergyConsumed = 0.0;
    g_totalCollisions = 0;
    g_totalInterference = 0;
    
    g_simulationStartTime = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
}

void ResetMeasurementVariables() {
    InitializeMeasurementVariables();
}

void RecordPacketSent(uint32_t nodeId) {
    using namespace ComparisonMetrics;
    g_sentPacketsPerNode[nodeId]++;
    g_totalPacketsSent++;
}

void RecordPacketReceived(uint32_t nodeId, uint32_t gatewayId) {
    using namespace ComparisonMetrics;
    g_receivedPacketsPerNode[nodeId]++;
    g_packetsPerGateway[gatewayId]++;
    g_totalPacketsReceived++;
}

void RecordPacketAcknowledged(uint32_t nodeId) {
    using namespace ComparisonMetrics;
    g_acknowledgedPacketsPerNode[nodeId]++;
}

void RecordAdrCommand(uint32_t nodeId, uint8_t newSf, double newTp) {
    using namespace ComparisonMetrics;
    g_sfHistoryPerNode[nodeId].push_back(newSf);
    g_tpHistoryPerNode[nodeId].push_back(newTp);
    g_adrCommandsPerNode[nodeId]++;
    g_totalAdrCommands++;
}

void RecordEnergyConsumption(uint32_t nodeId, double energy) {
    using namespace ComparisonMetrics;
    g_energyConsumedPerNode[nodeId] += energy;
    g_totalEnergyConsumed += energy;
}

void RecordCollision() {
    using namespace ComparisonMetrics;
    g_totalCollisions++;
}

void RecordInterference() {
    using namespace ComparisonMetrics;
    g_totalInterference++;
}

void ExportResults(const ScenarioConfig& config, const std::string& outputFile) {
    using namespace ComparisonMetrics;
    
    g_simulationEndTime = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    
    std::ofstream file(outputFile);
    if (!file.is_open()) {
        std::cerr << "Error: Cannot open output file " << outputFile << std::endl;
        return;
    }
    
    // Header
    file << "# Comparison Results for Scenario: " << config.scenarioName << std::endl;
    file << "# Simulator: " << config.simulator << std::endl;
    file << "# Nodes: " << config.numNodes << ", Gateways: " << config.numGateways << std::endl;
    file << "# ADR: " << (config.adrEnabled ? "Enabled" : "Disabled") << std::endl;
    file << "# Simulation Time: " << config.simulationTime << " minutes" << std::endl;
    file << std::endl;
    
    // Overall statistics
    file << "# OVERALL STATISTICS" << std::endl;
    file << "TotalPacketsSent," << g_totalPacketsSent << std::endl;
    file << "TotalPacketsReceived," << g_totalPacketsReceived << std::endl;
    file << "TotalPacketsLost," << (g_totalPacketsSent - g_totalPacketsReceived) << std::endl;
    file << "OverallPDR," << std::fixed << std::setprecision(4) 
         << (g_totalPacketsSent > 0 ? (double)g_totalPacketsReceived / g_totalPacketsSent : 0.0) << std::endl;
    file << "TotalAdrCommands," << g_totalAdrCommands << std::endl;
    file << "TotalCollisions," << g_totalCollisions << std::endl;
    file << "TotalInterference," << g_totalInterference << std::endl;
    file << "TotalEnergyConsumed," << g_totalEnergyConsumed << std::endl;
    file << "SimulationDuration," << (g_simulationEndTime - g_simulationStartTime) / 1000.0 << std::endl;
    file << std::endl;
    
    // Per-node statistics
    file << "# PER-NODE STATISTICS" << std::endl;
    file << "NodeID,SentPackets,ReceivedPackets,AcknowledgedPackets,PDR,AdrCommands,EnergyConsumed,FinalSF,FinalTP" << std::endl;
    
    for (const auto& pair : g_sentPacketsPerNode) {
        uint32_t nodeId = pair.first;
        uint32_t sent = pair.second;
        uint32_t received = g_receivedPacketsPerNode[nodeId];
        uint32_t acknowledged = g_acknowledgedPacketsPerNode[nodeId];
        double pdr = sent > 0 ? (double)received / sent : 0.0;
        uint32_t adrCmds = g_adrCommandsPerNode[nodeId];
        double energy = g_energyConsumedPerNode[nodeId];
        
        uint8_t finalSf = 12; // default
        double finalTp = 14.0; // default
        if (!g_sfHistoryPerNode[nodeId].empty()) {
            finalSf = g_sfHistoryPerNode[nodeId].back();
        }
        if (!g_tpHistoryPerNode[nodeId].empty()) {
            finalTp = g_tpHistoryPerNode[nodeId].back();
        }
        
        file << nodeId << "," << sent << "," << received << "," << acknowledged << ","
             << std::fixed << std::setprecision(4) << pdr << "," << adrCmds << ","
             << energy << "," << (int)finalSf << "," << finalTp << std::endl;
    }
    
    file << std::endl;
    
    // Gateway load balancing
    file << "# GATEWAY LOAD BALANCING" << std::endl;
    file << "GatewayID,ReceivedPackets" << std::endl;
    for (const auto& pair : g_packetsPerGateway) {
        file << pair.first << "," << pair.second << std::endl;
    }
    
    file.close();
    std::cout << "Results exported to " << outputFile << std::endl;
}

ScenarioConfig GetScenarioConfig(uint32_t scenarioId) {
    for (const auto& config : g_comparisonScenarios) {
        if (config.scenarioId == scenarioId) {
            return config;
        }
    }
    // Return default config if not found
    return g_comparisonScenarios[0];
}