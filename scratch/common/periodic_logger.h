#ifndef PERIODIC_LOGGER_H
#define PERIODIC_LOGGER_H

#include "ns3/simulator.h"
#include "ns3/energy-source-container.h"
#include "logging.h"

namespace scenario {

class PeriodicLogger {
public:
    static void StartPeriodicLogging(double intervalSeconds,
                                     double simTimeSeconds,
                                     const ns3::energy::EnergySourceContainer& sources) {
        m_interval = intervalSeconds;
        m_simTime = simTimeSeconds;
        m_sources = sources;
        
        // Schedule logging events at each second, up to but not beyond sim time
        for (double t = 0.0; t <= simTimeSeconds; t += intervalSeconds) {
            ns3::Simulator::Schedule(ns3::Seconds(t), &PeriodicLogger::LogState, t);
        }
    }

private:
    static void LogState(double timeSeconds) {
        // Safety check: don't log if simulation is stopping
        if (ns3::Simulator::Now().GetSeconds() > m_simTime) {
            return;
        }
        
        // Log energy for each end device
        for (uint32_t i = 0; i < m_sources.GetN(); ++i) {
            ns3::Ptr<ns3::energy::EnergySource> es = m_sources.Get(i);
            if (es) {
                double remaining = es->GetRemainingEnergy();
                double initial = es->GetInitialEnergy();
                double consumed = initial - remaining;
                
                CsvLogger::WriteEnergyTotal(timeSeconds, consumed);
                CsvLogger::WriteEnergyRemaining(timeSeconds, remaining);
            }
        }
    }
    
    static double m_interval;
    static double m_simTime;
    static ns3::energy::EnergySourceContainer m_sources;
};

// Static member definitions
double PeriodicLogger::m_interval = 1.0;
double PeriodicLogger::m_simTime = 0.0;
ns3::energy::EnergySourceContainer PeriodicLogger::m_sources;

} // namespace scenario

#endif // PERIODIC_LOGGER_H