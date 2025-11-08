#ifndef APP_SIMPLE_SENDER_H
#define APP_SIMPLE_SENDER_H

#include "ns3/application.h"
#include "ns3/net-device.h"
#include "ns3/event-id.h"
#include "ns3/random-variable-stream.h"

namespace scenario {

class SimpleSender : public ns3::Application {
public:
    SimpleSender() = default;
    
    void Configure(ns3::Ptr<ns3::NetDevice> nd,
                  uint32_t nPkts,
                  ns3::Time first,
                  ns3::Time period,
                  bool expIat,
                  double iatMeanSeconds);
    
private:
    void StartApplication() override;
    void StopApplication() override;
    void DoSend();
    
    ns3::Ptr<ns3::NetDevice> m_dev;
    uint32_t m_nPkts{0};
    ns3::Time m_first;
    ns3::Time m_period;
    uint32_t m_sent{0};
    ns3::EventId m_event;
    
    bool m_expIat{false};
    double m_iatMean{1000.0};
    ns3::Ptr<ns3::ExponentialRandomVariable> m_iatRv; // @todo In flora we have rng-class = "cMersenneTwister". Update it here
};

} // namespace scenario

#endif // APP_SIMPLE_SENDER_H