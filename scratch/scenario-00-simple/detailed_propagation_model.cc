#include "../common/detailed_propagation_model.h"
#include "ns3/mobility-model.h"
#include "ns3/log.h"
#include "ns3/node.h"
#include <cmath>

NS_LOG_COMPONENT_DEFINE("DetailedPropagationLossModel");

namespace scenario {

NS_OBJECT_ENSURE_REGISTERED(DetailedPropagationLossModel);

ns3::TypeId DetailedPropagationLossModel::GetTypeId() {
    static ns3::TypeId tid = ns3::TypeId("scenario::DetailedPropagationLossModel")
        .SetParent<ns3::PropagationLossModel>()
        .SetGroupName("Propagation")
        .AddConstructor<DetailedPropagationLossModel>();
    return tid;
}

DetailedPropagationLossModel::DetailedPropagationLossModel() {}

void DetailedPropagationLossModel::SetPathLossModel(
    ns3::Ptr<ns3::PropagationLossModel> model) {
    m_pathLossModel = model;
}

void DetailedPropagationLossModel::SetShadowingModel(
    ns3::Ptr<ns3::RandomPropagationLossModel> model) {
    m_shadowingModel = model;
}

double DetailedPropagationLossModel::DoCalcRxPower(
    double txPowerDbm,
    ns3::Ptr<ns3::MobilityModel> a,
    ns3::Ptr<ns3::MobilityModel> b) const {
    
    PropagationDetails details;
    
    // Calculate distance
    details.distance_m = a->GetDistanceFrom(b);
    
    // Step 1: Path loss
    double rxAfterPathLoss = txPowerDbm;
    if (m_pathLossModel) {
        rxAfterPathLoss = m_pathLossModel->CalcRxPower(txPowerDbm, a, b);
    }
    details.path_loss_db = txPowerDbm - rxAfterPathLoss;
    
    // Step 2: Shadowing (log-normal)
    double rxAfterShadowing = rxAfterPathLoss;
    details.shadowing_db = 0.0;
    if (m_shadowingModel) {
        rxAfterShadowing = m_shadowingModel->CalcRxPower(rxAfterPathLoss, a, b);
        details.shadowing_db = rxAfterPathLoss - rxAfterShadowing;
    }
    
    double rxFinal = rxAfterShadowing;
    
    details.total_loss_db = txPowerDbm - rxFinal;
    
    // Cache details
    uint32_t idA = a->GetObject<ns3::Node>()->GetId();
    uint32_t idB = b->GetObject<ns3::Node>()->GetId();
    m_detailsCache[std::make_pair(idA, idB)] = details;
    
    return rxFinal;
}

PropagationDetails DetailedPropagationLossModel::GetLastDetails(
    ns3::Ptr<ns3::MobilityModel> a,
    ns3::Ptr<ns3::MobilityModel> b) const {
    
    uint32_t idA = a->GetObject<ns3::Node>()->GetId();
    uint32_t idB = b->GetObject<ns3::Node>()->GetId();
    auto it = m_detailsCache.find(std::make_pair(idA, idB));
    
    if (it != m_detailsCache.end()) {
        return it->second;
    }
    
    // Return empty if not found
    return PropagationDetails{0, 0, 0, 0};
}

int64_t DetailedPropagationLossModel::DoAssignStreams(int64_t stream) {
    int64_t assigned = 0;
    if (m_pathLossModel) {
        assigned += m_pathLossModel->AssignStreams(stream);
    }
    if (m_shadowingModel) {
        assigned += m_shadowingModel->AssignStreams(stream + assigned);
    }
    return assigned;
}

} // namespace scenario