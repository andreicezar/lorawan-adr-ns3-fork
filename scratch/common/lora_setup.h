#ifndef LORA_SETUP_H
#define LORA_SETUP_H

#include "ns3/node-container.h"
#include "ns3/net-device-container.h"
#include "ns3/lora-channel.h"
#include "ns3/lora-helper.h"
#include "ns3/network-server-helper.h"
#include <vector>

namespace scenario {

class LoraSetup {
public:
    struct LoraDevices {
        ns3::NetDeviceContainer gwDevs;
        ns3::NetDeviceContainer edDevs;
        ns3::Ptr<ns3::lorawan::LoraChannel> channel;
        ns3::lorawan::LoraHelper loraHelper;
    };
    
    static LoraDevices CreateLoraNetwork(
        const ns3::NodeContainer& gateways,
        const ns3::NodeContainer& endDevices
    );
    
    static ns3::ApplicationContainer SetupNetworkServer(
        const ns3::NodeContainer& networkServer,
        const ns3::NodeContainer& gateways,
        const ns3::NodeContainer& endDevices,
        const ns3::NetDeviceContainer& gwDevs
    );
    
    static void ConfigureEndDevices(const ns3::NetDeviceContainer& edDevs);
    static void ConfigureGateways(const ns3::NetDeviceContainer& gwDevs);
    static void ConnectTraces(const ns3::NetDeviceContainer& gwDevs, 
                             const ns3::NetDeviceContainer& edDevs);
    
private:
    static ns3::Ptr<ns3::PropagationLossModel> CreatePropagationModel();
    static bool HasAttribute(ns3::Ptr<ns3::Object> obj, const std::string& name);
    static void SetDoubleAttrIfPresent(ns3::Ptr<ns3::Object> obj, 
                                       const std::string& name, double value);
    static void SetTimeAttrIfPresent(ns3::Ptr<ns3::Object> obj, 
                                     const std::string& name, ns3::Time value);
    static void SetBoolAttrIfPresent(ns3::Ptr<ns3::Object> obj, 
                                     const std::string& name, bool value);
    static void DumpAttributes(ns3::Ptr<ns3::Object> obj, const char* label);
};

} // namespace scenario

#endif // LORA_SETUP_H