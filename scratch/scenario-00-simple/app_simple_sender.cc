#include "../common/app_simple_sender.h"
#include "ns3/packet.h"
#include "ns3/simulator.h"
#include "ns3/log.h"
#include "ns3/double.h"
#include "ns3/lora-tag.h"
#include "ns3/lorawan-mac-header.h"

NS_LOG_COMPONENT_DEFINE("AppSimpleSender");

namespace scenario {

void SimpleSender::Configure(ns3::Ptr<ns3::NetDevice> nd,
                            uint32_t nPkts,
                            ns3::Time first,
                            ns3::Time period,
                            bool expIat,
                            double iatMeanSeconds) {
    m_dev = nd;
    m_nPkts = nPkts;
    m_first = first;
    m_period = period;
    m_expIat = expIat;
    m_iatMean = iatMeanSeconds;
    
    if (m_expIat) {
        m_iatRv = ns3::CreateObject<ns3::ExponentialRandomVariable>();
        m_iatRv->SetAttribute("Mean", ns3::DoubleValue(m_iatMean));
    }
}

void SimpleSender::StartApplication() {
    m_event = ns3::Simulator::Schedule(m_first, &SimpleSender::DoSend, this);
}

void SimpleSender::StopApplication() {
    if (m_event.IsPending()) {
        ns3::Simulator::Cancel(m_event);
    }
}

void SimpleSender::DoSend() {
    if (m_nPkts > 0 && m_sent >= m_nPkts)
        return;
    
    ns3::Ptr<ns3::Packet> pkt = ns3::Create<ns3::Packet>(23);
    
    // Tag for nicer logs
    ns3::lorawan::LoraTag tag;
    tag.SetSpreadingFactor(7);
    tag.SetDataRate(5);
    pkt->AddPacketTag(tag);
    
    NS_LOG_INFO("APP_TX node=" << GetNode()->GetId()
                               << " seq=" << m_sent
                               << " bytes=" << pkt->GetSize());
    
    m_dev->Send(pkt, ns3::Address(), 0);
    ++m_sent;
    
    // Schedule next only once
    if (m_nPkts == 0 || m_sent < m_nPkts) {
        ns3::Time next;
        if (m_expIat) {
            double d = m_iatRv->GetValue();
            NS_LOG_INFO("Next exponential IAT = " << d << " s");
            next = ns3::Seconds(d);
        } else {
            next = m_period;
        }
        m_event = ns3::Simulator::Schedule(next, &SimpleSender::DoSend, this);
    }
}

} // namespace scenario