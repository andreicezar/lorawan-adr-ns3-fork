#ifndef DETAILED_PROPAGATION_MODEL_H
#define DETAILED_PROPAGATION_MODEL_H

#include "ns3/propagation-loss-model.h"
#include "ns3/propagation-loss-model.h"
#include <map>

namespace scenario {

struct PropagationDetails {
    double distance_m;
    double path_loss_db;
    double shadowing_db;
    double total_loss_db;
};

class DetailedPropagationLossModel : public ns3::PropagationLossModel {
public:
    static ns3::TypeId GetTypeId();
    DetailedPropagationLossModel();
    
    void SetPathLossModel(ns3::Ptr<ns3::PropagationLossModel> model);
    void SetShadowingModel(ns3::Ptr<ns3::RandomPropagationLossModel> model);
    
    PropagationDetails GetLastDetails(ns3::Ptr<ns3::MobilityModel> a, 
                                     ns3::Ptr<ns3::MobilityModel> b) const;
    
private:
    double DoCalcRxPower(double txPowerDbm,
                        ns3::Ptr<ns3::MobilityModel> a,
                        ns3::Ptr<ns3::MobilityModel> b) const override;
    
    int64_t DoAssignStreams(int64_t stream) override;
    
    ns3::Ptr<ns3::PropagationLossModel> m_pathLossModel;
    ns3::Ptr<ns3::RandomPropagationLossModel> m_shadowingModel;
    
    mutable std::map<std::pair<uint32_t, uint32_t>, PropagationDetails> m_detailsCache;
};

} // namespace scenario

#endif