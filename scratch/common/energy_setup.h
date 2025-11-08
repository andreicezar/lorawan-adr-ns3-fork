#ifndef ENERGY_SETUP_H
#define ENERGY_SETUP_H

#include "ns3/net-device-container.h"
#include "ns3/node-container.h"
#include "ns3/energy-source-container.h"

namespace scenario {

class EnergySetup {
public:
    static ns3::energy::EnergySourceContainer InstallEnergyModels(
        const ns3::NodeContainer& endDevices,
        const ns3::NetDeviceContainer& edDevs
    );
    
private:
    static void DumpAttributes(ns3::Ptr<ns3::Object> obj, const char* label);
};

} // namespace scenario

#endif // ENERGY_SETUP_H