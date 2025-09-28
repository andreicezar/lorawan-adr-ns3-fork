// #include "ns3/core-module.h"
// #include "ns3/network-module.h"
// #include "ns3/mobility-module.h"
// #include "ns3/internet-module.h"

// #include "ns3/lorawan-module.h"
// #include "ns3/gateway-lora-phy.h"
// #include "ns3/gateway-lorawan-mac.h"
// #include "ns3/network-server.h"

// #include "ns3/lora-interference-helper.h"   // collision matrix toggle
// #include "ns3/periodic-sender.h"          // reference for traffic
// #include "ns3/lora-radio-energy-model.h"  // energy model
// #include "ns3/okumura-hata-propagation-loss-model.h"

// #include "ns3/lorawan-mac-header.h"

// #include "ns3/random-variable-stream.h"
// #include "ns3/propagation-loss-model.h"
// #include "ns3/propagation-delay-model.h"
// #include "ns3/point-to-point-module.h"

// // Energy module includes - updated for proper ns-3 energy module
// #include "ns3/energy-module.h"            // Main energy module
// #include "ns3/basic-energy-source-helper.h"  // BasicEnergySourceHelper
// #include "ns3/basic-energy-source.h"         // BasicEnergySource
// #include "ns3/energy-source-container.h"     // EnergySourceContainer
// #include "ns3/lora-radio-energy-model.h"     // lorawan::LoraRadioEnergyModel
// #include "ns3/lora-tx-current-model.h"       // lorawan::LinearLoraTxCurrentMode

// #include <fstream>

// // --- CSV logger (file-scope) ---
// static std::ofstream gCsv;
// static bool gCsvInit = false;

// static const std::string kScenarioDir = []() {
//   namespace fs = std::filesystem;
//   fs::path here = fs::absolute(fs::path(__FILE__)).parent_path();
//   return here.string();
// }();

// // Join helper
// static inline std::string Out(const std::string& name) {
//   return (std::filesystem::path(kScenarioDir) / name).string();
// }

// using namespace ns3;
// using ns3::Ptr;
// using ns3::Packet;
// using namespace ns3::lorawan;
// using namespace ns3::energy;  // Add energy namespace
// NS_LOG_COMPONENT_DEFINE("Scenario00Simple");

// // ============================== GLOBAL PROPAGATION CONSTANTS ==============================
// // Propagation Loss Model Parameters
// static const double GAMMA_PATH_LOSS_EXPONENT = 3.76;     // Path loss exponent (gamma/alpha)
// static const double REFERENCE_DISTANCE_M = 1.0;          // Reference distance [m]
// static const double REFERENCE_LOSS_DB = 7.7;             // Reference loss [dB]

// // Shadowing Parameters (Log-Normal)
// static const double SHADOWING_STD_DEV_DB = 8.0;          // Standard deviation for log-normal shadowing [dB]
// static const bool   ENABLE_SHADOWING = true;             // Enable/disable shadowing

// // Physical Layer Constants
// static const double NOISE_FIGURE_DB = 6.0;               // Receiver noise figure [dB]
// static const double THERMAL_NOISE_DBM_HZ = -174.0;       // Thermal noise floor [dBm/Hz]

// // Alternative propagation models (set one to true)
// static const bool USE_LOG_DISTANCE_MODEL = true;         // Basic log-distance model
// static const bool USE_OKUMURA_HATA_MODEL = false;        // Okumura-Hata model
// static const bool USE_FRIIS_MODEL = false;               // Free space (Friis) model

// // Okumura-Hata specific parameters (if enabled)
// static const double OKUMURA_FREQUENCY_MHZ = 868.0;       // Frequency [MHz]
// static const double OKUMURA_GW_HEIGHT_M = 10.0;          // Gateway antenna height [m]  
// static const double OKUMURA_ED_HEIGHT_M = 1.0;           // End device antenna height [m]
// static const bool   OKUMURA_URBAN_ENVIRONMENT = false;   // Urban (true) vs Rural (false)

// // Additional shadowing correlation parameters
// static const double SHADOWING_CORRELATION_DISTANCE_M = 50.0;  // Decorrelation distance [m]

// // Antenna parameters
// static const double GW_ANTENNA_GAIN_DB = 0.0;            // Gateway antenna gain [dB]
// static const double ED_ANTENNA_GAIN_DB = 0.0;            // End device antenna gain [dB]

// // ============================== ADDITIONAL RF CONSTANTS ==============================

// // SNR Requirements for different Spreading Factors [dB]
// // Index 0=SF12, 1=SF11, ..., 5=SF7
// static const double SNR_REQUIREMENTS_DB[6] = {-20.0, -17.5, -15.0, -12.5, -10.0, -7.5};

// // Alternative SNR thresholds (more conservative)
// static const double SNR_REQUIREMENTS_CONSERVATIVE_DB[6] = {-18.0, -15.5, -13.0, -10.5, -8.0, -5.5};

// // Frequency band parameters (EU868)
// static const double BASE_FREQUENCY_HZ = 868100000.0;     // 868.1 MHz
// static const double CHANNEL_SPACING_HZ = 200000.0;       // 200 kHz spacing
// static const uint8_t NUM_CHANNELS = 3;                   // Number of channels

// // Bandwidth mapping for data rates
// static const double BANDWIDTH_125_KHZ = 125000.0;
// static const double BANDWIDTH_250_KHZ = 250000.0;

// // Power settings
// static const double ED_TX_POWER_DBM = 14.0;              // End device TX power [dBm]
// static const double GW_RX_SENSITIVITY_DBM = -137.0;      // Gateway sensitivity [dBm]

// // Timing parameters
// static const double PREAMBLE_SYMBOLS = 8.0;              // Preamble length
// static const double CRYSTAL_TOLERANCE_PPM = 10.0;        // Crystal tolerance [ppm]

// // Fade margin
// static const double FADE_MARGIN_DB = 10.0;               // Additional fade margin [dB]

// // Environmental factors
// static const double FOLIAGE_LOSS_DB = 0.0;               // Loss due to foliage [dB]
// static const double BUILDING_PENETRATION_LOSS_DB = 0.0;  // Building penetration loss [dB]

// // ======= Simulation control (no CLI; all constants) =======
// static const double SIM_TIME_S           = 900.0;
// static const double GW_ED_DISTANCE_M     = 1000.0;

// static const uint32_t N_PKTS_TO_SEND     = 0;        // 0 => infinite, else send N packets
// static const double   FIXED_PERIOD_S     = 180.0;    // used when USE_EXPONENTIAL_IAT == false
// static const bool     USE_EXPONENTIAL_IAT= false;     // true: exponential IAT, false: fixed period
// static const double   EXP_IAT_MEAN_S     = 1000.0;   // mean for exponential inter-arrival (s)

// static const bool     ENABLE_ADR         = false;    // toggle ADR in NetworkServer
// static const bool     USE_ALOHA_MATRIX   = false;    // false: Goursaud, true: ALOHA

// // ======= Cloud/backhaul & PHY threshold constants =======
// static const char* CLOUD_BACKHAUL_DATARATE = "1Gbps";  // from cloudDelays.xml
// static const char* CLOUD_BACKHAUL_DELAY    = "10ms";   // from cloudDelays.xml

// static const double PHY_ENERGY_DETECTION_DBM   = -110.0; // INI parity
// static const double PHY_MAX_TX_DURATION_SEC    = 4.0;    // INI parity

// // Energy source (battery)
// static constexpr double EN_SUPPLY_VOLTAGE_V   = 3.3;       // volts
// static constexpr double EN_INITIAL_ENERGY_J   = 10000.0;   // joules
// static constexpr double EN_UPDATE_INTERVAL_S  = 10.0;       // seconds (increased from 1.0 to reduce output)

// // LoRa radio currents (A) â€" from your XML defaults
// static constexpr double EN_IDLE_CURRENT_A     = 0.0001;    // 0.1 mA
// static constexpr double EN_RX_CURRENT_A       = 0.0097;    // 9.7 mA
// static constexpr double EN_SLEEP_CURRENT_A    = 0.0000015; // 1.5 ÂµA

// // Linear TX current model parameters: I_tx = P_tx/(V*eta) + I_standby
// static constexpr double EN_TX_MODEL_ETA       = 0.10;      // PA efficiency
// static constexpr double EN_TX_MODEL_STANDBY_A = EN_IDLE_CURRENT_A;

// // CSV for traces
// static const char* EN_TRACE_FILE_TOTAL = "ed-energy-total.csv";
// static const char* EN_TRACE_FILE_REMAIN= "ed-remaining-energy.csv";

// static std::ofstream gEnergyTotalCsv, gEnergyRemainCsv;
// static void OnEdEnergyTotal(double oldJ, double newJ) {
//   gEnergyTotalCsv << Simulator::Now().GetSeconds() << "," << newJ << "\n";
// }
// static void OnRemainingEnergy(double oldJ, double newJ) {
//   gEnergyRemainCsv << Simulator::Now().GetSeconds() << "," << newJ << "\n";
// }

// // Helper function to get SNR requirement with selectable threshold set
// static inline double GetSnrRequirement(uint8_t sf, bool conservative = false) {
//   if (sf < 7 || sf > 12) return -7.5; // Default to SF7 requirement
//   int index = 12 - sf; // SF12=0, SF11=1, ..., SF7=5
//   return conservative ? SNR_REQUIREMENTS_CONSERVATIVE_DB[index] : SNR_REQUIREMENTS_DB[index];
// }

// // Small helper to render SF nicely
// static inline const char* SfToString(uint8_t sf) {
//   switch (sf) { case 7: return "SF7"; case 8: return "SF8"; case 9: return "SF9";
//                 case 10: return "SF10"; case 11: return "SF11"; case 12: return "SF12";
//                 default: return "SF?"; }
// }
// // Updated helper functions using global constants
// static inline double DrToBwHz(uint8_t dr){ 
//   return (dr<=5) ? 125000.0 : (dr==6 ? 250000.0 : 125000.0); 
// }

// static inline double NoiseFloorDbm(double bwHz, double nfDb = NOISE_FIGURE_DB){ 
//   return THERMAL_NOISE_DBM_HZ + 10.0*std::log10(bwHz) + nfDb; 
// }

// // Configuration flags
// static const bool USE_CONSERVATIVE_SNR_THRESHOLDS = false;  // Set to true for conservative thresholds

// // Updated LogSnrCsv function with configurable thresholds
// static void LogSnrCsv(const ns3::lorawan::LoraTag& tag) {
//   if (!gCsvInit) {
//     gCsv.open(Out("snr_log.csv"), std::ios::out);
//     gCsv << "t_s,gw_id,dr,sf,frequency_hz,rssi_dbm,snr_db,req_db,margin_db,fade_margin_db\n";
//     gCsvInit = true;
//   }
//   const double rssi = tag.GetReceivePower();
//   const double fHz  = tag.GetFrequency();
//   if (fHz <= 0.0 || rssi >= 0.0) return; // only log real receptions

//   const uint8_t dr = tag.GetDataRate();
//   const uint8_t sf = tag.GetSpreadingFactor();
//   const double bw  = DrToBwHz(dr);
  
//   // Calculate SNR with all loss factors
//   double totalNoise = NoiseFloorDbm(bw, NOISE_FIGURE_DB);
//   double adjustedRssi = rssi - FOLIAGE_LOSS_DB - BUILDING_PENETRATION_LOSS_DB;
//   const double snr = adjustedRssi - totalNoise;

//   // Use configurable SNR requirement
//   const double req = GetSnrRequirement(sf, USE_CONSERVATIVE_SNR_THRESHOLDS);
//   const double margin = snr - req;
//   const double marginWithFade = margin - FADE_MARGIN_DB;

//   gCsv << std::fixed
//        << ns3::Simulator::Now().GetSeconds() << ","
//        << ns3::Simulator::GetContext()       << ","
//        << unsigned(dr) << ","
//        << unsigned(sf) << ","
//        << fHz          << ","
//        << rssi         << ","
//        << snr          << ","
//        << req          << ","
//        << margin       << ","
//        << marginWithFade << "\n";
// }

// // Updated PrintLoraParams function
// [[maybe_unused]] static void PrintLoraParams(const char* who, unsigned id, ns3::Ptr<const ns3::Packet> p) {
//   using namespace ns3;
//   using namespace ns3::lorawan;
//   LoraTag tag; bool has = p->PeekPacketTag(tag);
//   std::ostringstream os; os.setf(std::ios::fixed); os.precision(6);

//   if (has) {
//     os << Simulator::Now().GetSeconds() << "s " << id << " " << who
//        << " sf=" << SfToString(tag.GetSpreadingFactor())
//        << " dr=" << unsigned(tag.GetDataRate());

//     const double rssi = tag.GetReceivePower();
//     const double fHz  = tag.GetFrequency();
//     if (fHz > 0.0 && rssi < 0.0) { // only at reception
//       const double bwHz = DrToBwHz(tag.GetDataRate());
//       const double noiseFloor = THERMAL_NOISE_DBM_HZ + 10.0*std::log10(bwHz) + NOISE_FIGURE_DB;
      
//       // Apply environmental losses
//       double adjustedRssi = rssi - FOLIAGE_LOSS_DB - BUILDING_PENETRATION_LOSS_DB;
//       const double snr = adjustedRssi - noiseFloor;

//       // Use configurable SNR requirement
//       const uint8_t sf = tag.GetSpreadingFactor();
//       const double req = GetSnrRequirement(sf, USE_CONSERVATIVE_SNR_THRESHOLDS);
//       const double margin = snr - req;
//       const double marginWithFade = margin - FADE_MARGIN_DB;

//       os << " RSSI=" << rssi << " dBm"
//          << " SNR="  << snr  << " dB"
//          << " (req=" << req << " dB, margin=" << margin << " dB"
//          << ", w/fade=" << marginWithFade << " dB)";
//     }

//     os << " f=" << fHz << " Hz";
//     NS_LOG_UNCOND(os.str());
//   }
// }

// [[maybe_unused]] static void OnEdPhyTxBegin(Ptr<const Packet> p, unsigned int channelId)
// {
//   // You can still extract LoRa parameters from the packet
//   PrintLoraParams("ED_PHY_TX_BEGIN", 1, p);
// }

// [[maybe_unused]] static void OnEdMacTx(Ptr<const Packet> p)
// {
//   PrintLoraParams("ED_MAC_TX", 1, p);
// }

// [[maybe_unused]] static void OnGwPhyRxLost(Ptr<const Packet> p, uint32_t reason)
// {
//   NS_LOG_UNCOND(Simulator::Now().GetSeconds() << "s GW_PHY_RX_LOST bytes=" 
//                 << p->GetSize() << " reason=Interference");
// }

// [[maybe_unused]] static void OnGwPhyRxUnderSensitivity(Ptr<const Packet> p, unsigned int reason)
// {
//   NS_LOG_UNCOND(Simulator::Now().GetSeconds() << "s GW_PHY_RX_UNDER_SENSITIVITY bytes=" 
//                 << p->GetSize() << " reason=" << reason);
// }

// [[maybe_unused]] static void
// OnGwPhyRxOk(ns3::Ptr<const ns3::Packet> p, unsigned int /*antennaId*/)
// {
//   PrintLoraParams("GW_PHY_RX_OK", 0, p);
//   ns3::lorawan::LoraTag tag; 
//   if (p->PeekPacketTag(tag)) { LogSnrCsv(tag); }   // <â€" write CSV
// }

// [[maybe_unused]] static void
// OnGwMacRxOk(ns3::Ptr<const ns3::Packet> p)
// {
//   PrintLoraParams("GW_MAC_RX_OK", 0, p);
//   ns3::lorawan::LoraTag tag; 
//   if (p->PeekPacketTag(tag)) { LogSnrCsv(tag); }   // <â€" write CSV
// }


// [[maybe_unused]] static void
// OnNsRxFromGw(ns3::Ptr<const ns3::Packet> p)
// {
//   PrintLoraParams("NS_RX_FROM_GW", 0, p);
// }

// // -------- app that sends N packets; supports exponential or fixed IAT --------
// class SimpleSender : public Application
// {
// public:
//   SimpleSender() = default;

//   void Configure(Ptr<NetDevice> nd,
//                  uint32_t nPkts,
//                  Time first,
//                  Time period,
//                  bool expIat,
//                  double iatMeanSeconds)
//   {
//     m_dev     = nd;
//     m_nPkts   = nPkts;
//     m_first   = first;
//     m_period  = period;
//     m_expIat  = expIat;
//     m_iatMean = iatMeanSeconds;

//     if (m_expIat)
//     {
//       m_iatRv = CreateObject<ExponentialRandomVariable>();
//       m_iatRv->SetAttribute("Mean", DoubleValue(m_iatMean));
//     }
//   }

// private:
//   void StartApplication() override
//   {
//     m_event = Simulator::Schedule(m_first, &SimpleSender::DoSend, this);
//   }

//   void StopApplication() override
//   {
//     if (m_event.IsPending())
//     {
//       Simulator::Cancel(m_event);
//     }
//   }

//   void DoSend()
//   {
//     if (m_nPkts > 0 && m_sent >= m_nPkts)
//       return;

//     Ptr<Packet> pkt = Create<Packet>(23);

//     // Tag for nicer logs
//     lorawan::LoraTag tag;
//     tag.SetSpreadingFactor(7);
//     tag.SetDataRate(5);
//     pkt->AddPacketTag(tag);

//     NS_LOG_INFO("APP_TX node=" << GetNode()->GetId()
//                               << " seq=" << m_sent
//                               << " bytes=" << pkt->GetSize());

//     m_dev->Send(pkt, Address(), 0);
//     ++m_sent;

//     // Schedule next only once
//     if (m_nPkts == 0 || m_sent < m_nPkts)
//     {
//       Time next;
//       if (m_expIat) {
//         double d = m_iatRv->GetValue();
//         NS_LOG_INFO("Next exponential IAT = " << d << " s");
//         next = Seconds(d);
//       } else {
//         next = m_period;
//       }
//       m_event = Simulator::Schedule(next, &SimpleSender::DoSend, this);
//     }
//   }

//   Ptr<NetDevice> m_dev;
//   uint32_t       m_nPkts{0};
//   Time           m_first;
//   Time           m_period;
//   uint32_t       m_sent{0};
//   EventId        m_event;

//   bool m_expIat{false};
//   double m_iatMean{1000.0};
//   Ptr<ExponentialRandomVariable> m_iatRv;
// };


// // Helper: check if an object exposes a specific attribute name
// static bool
// HasAttribute (Ptr<ns3::Object> obj, const std::string& name)
// {
//   if (!obj) return false;
//   ns3::TypeId tid = obj->GetInstanceTypeId ();
//   for (uint32_t k = 0; k < tid.GetAttributeN (); ++k)
//   {
//     auto info = tid.GetAttribute (k);
//     if (name == info.name) return true;
//   }
//   return false;
// }

// static void
// SetDoubleAttrIfPresent (Ptr<ns3::Object> obj, const std::string& name, double value)
// {
//   if (!obj) return;
//   ns3::TypeId tid = obj->GetInstanceTypeId();
//   for (uint32_t k = 0; k < tid.GetAttributeN(); ++k) {
//     if (name == tid.GetAttribute(k).name) {
//       obj->SetAttribute(name, ns3::DoubleValue(value));
//       NS_LOG_INFO("Set attribute " << name << " = " << value);
//       return;
//     }
//   }
//   NS_LOG_INFO("Attribute " << name << " not found on " << tid.GetName());
// }

// static void
// SetTimeAttrIfPresent (Ptr<ns3::Object> obj, const std::string& name, ns3::Time value)
// {
//   if (!obj) return;
//   ns3::TypeId tid = obj->GetInstanceTypeId();
//   for (uint32_t k = 0; k < tid.GetAttributeN(); ++k) {
//     if (name == tid.GetAttribute(k).name) {
//       obj->SetAttribute(name, ns3::TimeValue(value));
//       NS_LOG_INFO("Set attribute " << name << " = " << value.GetSeconds() << " s");
//       return;
//     }
//   }
//   NS_LOG_INFO("Attribute " << name << " not found on " << tid.GetName());
// }


// // Helper: set attribute if present (overload for common types you need)
// static void
// SetBoolAttrIfPresent (Ptr<ns3::Object> obj, const std::string& name, bool value)
// {
//   if (HasAttribute (obj, name))
//   {
//     obj->SetAttribute (name, ns3::BooleanValue (value));
//     NS_LOG_INFO ("Set attribute " << name << " = " << (value ? "true" : "false"));
//   }
//   else
//   {
//     NS_LOG_INFO ("Attribute " << name << " not found on " << obj->GetInstanceTypeId ().GetName ());
//   }
// }
// static void DumpAttributes(Ptr<ns3::Object> obj, const char* label) {
//   if (!obj) return;
//   ns3::TypeId tid = obj->GetInstanceTypeId();
//   NS_LOG_INFO(std::string("Attributes of ") + label + " (" + tid.GetName() + "):");
//   for (uint32_t i = 0; i < tid.GetAttributeN(); ++i) {
//     const auto info = tid.GetAttribute(i);
//     NS_LOG_INFO("  - " << info.name);
//   }
// }

// // ============================== MAIN ==============================
// int
// main(int argc, char* argv[])
// {
//   // knobs (constants, no CLI)
//   double   simTime = SIM_TIME_S;
//   double   period  = FIXED_PERIOD_S;
//   uint32_t nPkts   = N_PKTS_TO_SEND;
//   double   dist    = GW_ED_DISTANCE_M;

//   // Map FLoRa's alohaChannelModel to ns-3â€™s collision matrix
//   ns3::lorawan::LoraInterferenceHelper::collisionMatrix =
//       USE_ALOHA_MATRIX
//         ? ns3::lorawan::LoraInterferenceHelper::ALOHA
//         : ns3::lorawan::LoraInterferenceHelper::GOURSAUD;  // default

//   // human-readable logs (time + node + INFO of our component)
//   LogComponentEnable(
//       "Scenario00Simple",
//       static_cast<LogLevel>(LOG_PREFIX_TIME | LOG_PREFIX_NODE | LOG_LEVEL_INFO));

//   // nodes
//   NodeContainer gateways;      gateways.Create(1);
//   NodeContainer endDevices;    endDevices.Create(1);
//   NodeContainer networkServer; networkServer.Create(1);

//   // positions
//   MobilityHelper mob;
//   mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
//   mob.Install(gateways);
//   mob.Install(endDevices);
//   mob.Install(networkServer);

//   gateways.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 10.0));
//   endDevices.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(dist, 0.0, 1.0));
//   networkServer.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 10.0));
  
//   NS_LOG_INFO("GW-ED distance = " << dist << " m");

// // ------ LoRa channel + PHY/MAC helpers with configurable propagation ------
//   Ptr<PropagationLossModel> loss;
  
//   if (USE_FRIIS_MODEL) {
//     // Free space propagation model
//     NS_LOG_INFO("Using Friis (Free Space) propagation model");
//     loss = CreateObject<FriisPropagationLossModel>();
    
//   } else if (USE_OKUMURA_HATA_MODEL) {
//       // Okumura-Hata model for urban/suburban environments
//       NS_LOG_INFO("Using Okumura-Hata propagation model");
//       Ptr<OkumuraHataPropagationLossModel> okumuraLoss = CreateObject<OkumuraHataPropagationLossModel>();
//       okumuraLoss->SetAttribute("Frequency", DoubleValue(OKUMURA_FREQUENCY_MHZ * 1e6)); // Convert to Hz
      
//       // Use the correct enum values from the header file
//       if (OKUMURA_URBAN_ENVIRONMENT) {
//         okumuraLoss->SetAttribute("Environment", EnumValue(ns3::UrbanEnvironment));
//       } else {
//         okumuraLoss->SetAttribute("Environment", EnumValue(ns3::SubUrbanEnvironment)); 
//       }
//       okumuraLoss->SetAttribute("CitySize", EnumValue(ns3::SmallCity));
//       loss = okumuraLoss;
    
//   } else {
//     // Default: Log-distance path loss model
//     NS_LOG_INFO("Using Log-Distance propagation model with gamma=" << GAMMA_PATH_LOSS_EXPONENT);
//     Ptr<LogDistancePropagationLossModel> logLoss = CreateObject<LogDistancePropagationLossModel>();
//     logLoss->SetAttribute("Exponent", DoubleValue(GAMMA_PATH_LOSS_EXPONENT));
//     logLoss->SetAttribute("ReferenceDistance", DoubleValue(REFERENCE_DISTANCE_M));
//     logLoss->SetAttribute("ReferenceLoss", DoubleValue(REFERENCE_LOSS_DB));
//     loss = logLoss;
//   }

//   // Add shadowing (log-normal random variable) if enabled
//   if (ENABLE_SHADOWING) {
//     NS_LOG_INFO("Adding log-normal shadowing with std dev=" << SHADOWING_STD_DEV_DB << " dB");
    
//     Ptr<RandomPropagationLossModel> shadowingLoss = CreateObject<RandomPropagationLossModel>();
//     Ptr<LogNormalRandomVariable> shadowingVar = CreateObject<LogNormalRandomVariable>();
    
//     // Simplified: LogNormal with mean=1 (0 dB), std dev converted to natural log scale
//     shadowingVar->SetAttribute("Mu", DoubleValue(0.0));  
//     shadowingVar->SetAttribute("Sigma", DoubleValue(SHADOWING_STD_DEV_DB * 0.115129)); // Convert dB to ln scale
    
//     shadowingLoss->SetAttribute("Variable", PointerValue(shadowingVar));
    
//     // Chain the models: path loss + shadowing
//     loss->SetNext(shadowingLoss);
//   }

//   // Propagation delay model
//   Ptr<PropagationDelayModel> delay = CreateObject<ConstantSpeedPropagationDelayModel>();
  
//   // Create the channel
//   Ptr<LoraChannel> channel = CreateObject<LoraChannel>(loss, delay);

//   NS_LOG_INFO("Propagation setup complete:");
//   NS_LOG_INFO("  - Path loss exponent (gamma): " << GAMMA_PATH_LOSS_EXPONENT);
//   NS_LOG_INFO("  - Reference distance: " << REFERENCE_DISTANCE_M << " m");  
//   NS_LOG_INFO("  - Reference loss: " << REFERENCE_LOSS_DB << " dB");
//   NS_LOG_INFO("  - Shadowing enabled: " << (ENABLE_SHADOWING ? "YES" : "NO"));
//   if (ENABLE_SHADOWING) {
//     NS_LOG_INFO("  - Shadowing std dev: " << SHADOWING_STD_DEV_DB << " dB");
//   }
//   NS_LOG_INFO("  - Noise figure: " << NOISE_FIGURE_DB << " dB");

//   // Configure PHY helpers
//   LoraPhyHelper gwPhy; 
//   gwPhy.SetChannel(channel);
//   gwPhy.SetDeviceType(LoraPhyHelper::GW);  // Set device type for gateway PHY
  
//   LoraPhyHelper edPhy; 
//   edPhy.SetChannel(channel);
//   edPhy.SetDeviceType(LoraPhyHelper::ED);  // Set device type for end device PHY

//   // Configure MAC helpers  
//   LorawanMacHelper gwMac;
//   gwMac.SetDeviceType(LorawanMacHelper::GW);  // Set device type for gateway MAC
//   gwMac.SetRegion(LorawanMacHelper::EU);      // Set region
  
//   LorawanMacHelper edMac;
//   edMac.SetDeviceType(LorawanMacHelper::ED_A);  // Set device type for end device MAC
//   edMac.SetRegion(LorawanMacHelper::EU);         // Set region
  
//   // Create and set address generator for end devices
//   Ptr<LoraDeviceAddressGenerator> addrGen = CreateObject<LoraDeviceAddressGenerator>(0, 0);
//   edMac.SetAddressGenerator(addrGen);

//   // install LoRaWAN netdevices with packet tracking
//   LoraHelper lora;
//   lora.EnablePacketTracking();  // Enable packet tracking

//   NetDeviceContainer gwDevs = lora.Install(gwPhy, gwMac, gateways);
//   NetDeviceContainer edDevs = lora.Install(edPhy, edMac, endDevices);

//   NS_LOG_INFO("GW LoRa devs: " << gwDevs.GetN() << " | ED LoRa devs: " << edDevs.GetN());
  
//   // 1) Install one BasicEnergySource per ED node - with proper namespace
//   BasicEnergySourceHelper sourceHelper;
//   sourceHelper.Set("BasicEnergySupplyVoltageV",   DoubleValue(EN_SUPPLY_VOLTAGE_V));
//   sourceHelper.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(EN_INITIAL_ENERGY_J));
//   sourceHelper.Set("PeriodicEnergyUpdateInterval", TimeValue(Seconds(EN_UPDATE_INTERVAL_S)));
//   EnergySourceContainer sources = sourceHelper.Install(endDevices);

//   // 2) Open CSVs
//   gEnergyTotalCsv.open(Out(EN_TRACE_FILE_TOTAL)); gEnergyTotalCsv << "t_s,total_J\n";
//   gEnergyRemainCsv.open(Out(EN_TRACE_FILE_REMAIN)); gEnergyRemainCsv << "t_s,remain_J\n";

//   // 3) For each ED: create LoraRadioEnergyModel, attach to source, hook PHY listener & traces
//   for (uint32_t i = 0; i < edDevs.GetN(); ++i) {
//     Ptr<LoraNetDevice> edNd = DynamicCast<LoraNetDevice>(edDevs.Get(i));
//     if (!edNd) continue;

//     Ptr<EnergySource> es = sources.Get(i);

//     // (a) Create radio device energy model and set per-state currents
//     Ptr<lorawan::LoraRadioEnergyModel> lrm = CreateObject<lorawan::LoraRadioEnergyModel>();
//     lrm->SetEnergySource(es);                                                               // bind to source
//     lrm->SetAttribute("StandbyCurrentA", DoubleValue(EN_IDLE_CURRENT_A));
//     lrm->SetAttribute("RxCurrentA",      DoubleValue(EN_RX_CURRENT_A));
//     lrm->SetAttribute("SleepCurrentA",   DoubleValue(EN_SLEEP_CURRENT_A));

//     // (b) Linear TX current model
//     Ptr<lorawan::LinearLoraTxCurrentModel> txModel = CreateObject<lorawan::LinearLoraTxCurrentModel>();
//     txModel->SetAttribute("Eta",            DoubleValue(EN_TX_MODEL_ETA));
//     txModel->SetAttribute("Voltage",        DoubleValue(EN_SUPPLY_VOLTAGE_V));
//     txModel->SetAttribute("StandbyCurrent", DoubleValue(EN_TX_MODEL_STANDBY_A));
//     lrm->SetTxCurrentModel(txModel);

//     // (c) Register device energy model with the source so it's accounted in drains
//     es->AppendDeviceEnergyModel(lrm);                                                       // source owns models

//     // (d) Hook PHY listener so TX/RX/SLEEP drive current updates
//     Ptr<EndDeviceLoraPhy> edPhyObj = edNd->GetPhy()->GetObject<EndDeviceLoraPhy>();
//     if (edPhyObj) {
//       edPhyObj->RegisterListener(lrm->GetPhyListener());
//     }

//     // (e) Traces - with proper namespace
//     lrm->TraceConnectWithoutContext("TotalEnergyConsumption", MakeCallback(&OnEdEnergyTotal)); // device energy trace
//     Ptr<ns3::energy::BasicEnergySource> bes = DynamicCast<ns3::energy::BasicEnergySource>(es);
//     if (bes) {
//       bes->TraceConnectWithoutContext("RemainingEnergy", MakeCallback(&OnRemainingEnergy));    // source energy trace
//     }
//   }

//   for (uint32_t g = 0; g < gwDevs.GetN(); ++g) {
//     auto gwNd  = DynamicCast<lorawan::LoraNetDevice>(gwDevs.Get(g));
//     if (!gwNd) continue;

//     auto gwPhy = gwNd->GetPhy();
//     if (gwPhy) {
//       gwPhy->TraceConnectWithoutContext("EndReceive", MakeCallback(&OnGwPhyRxOk));
//       // After getting the gateway PHY (around line 256 in your code)
//       Ptr<GatewayLoraPhy> gphy = gwNd->GetPhy()->GetObject<GatewayLoraPhy>();
//       DumpAttributes(gphy,   "Gateway PHY");     // after you get Ptr<GatewayLoraPhy> gphy

//       if (gphy) {
//         gphy->TraceConnectWithoutContext("LostPacketBecauseNoMoreReceivers",
//                                  MakeCallback(&OnGwPhyRxUnderSensitivity)); // or a custom sink
//         gphy->TraceConnectWithoutContext("NoReceptionBecauseTransmitting",
//                                         MakeCallback(&OnGwPhyRxLost));             // adjust sink signature if needed
//         // Check if the PHY has SNR information available
//         // This depends on your specific LoRaWAN fork implementation
        
//         // Try connecting to any SNR-related traces if they exist
//         TypeId tid = gphy->GetTypeId();
//         NS_LOG_INFO("Available Gateway PHY traces:");
//         for (uint32_t i = 0; i < tid.GetTraceSourceN(); ++i) {
//           struct TypeId::TraceSourceInformation info = tid.GetTraceSource(i);
//           NS_LOG_INFO("  " << info.name << ": " << info.help);
//         }
//         SetDoubleAttrIfPresent(gphy, "EnergyDetection", PHY_ENERGY_DETECTION_DBM);              // dBm
//         SetTimeAttrIfPresent  (gphy, "MaxTransmissionDuration", Seconds(PHY_MAX_TX_DURATION_SEC));
//       }
//     }
//     auto gwMac = gwNd->GetMac();
//     if (gwMac) {
//       gwMac->TraceConnectWithoutContext("ReceivedPacket", MakeCallback(&OnGwMacRxOk));
//     }
//   }

//   // ----- End-device traces + config (place this before creating SimpleSender/app) -----
//   for (uint32_t i = 0; i < edDevs.GetN(); ++i)
//   {
//     Ptr<lorawan::LoraNetDevice> edNd = DynamicCast<lorawan::LoraNetDevice>(edDevs.Get(i));
//     if (!edNd) continue;

//     // PHY traces + optional SF at PHY (MAC DR still wins)
//     Ptr<lorawan::LoraPhy> edPhy = edNd->GetPhy();
//     if (edPhy)
//     {
//       edPhy->TraceConnectWithoutContext("StartSending", ns3::MakeCallback(&OnEdPhyTxBegin));

//       Ptr<lorawan::EndDeviceLoraPhy> edPhyObj = edPhy->GetObject<lorawan::EndDeviceLoraPhy>();
//       DumpAttributes(edPhyObj,"EndDevice PHY");  // after you get Ptr<EndDeviceLoraPhy> edPhyObj
//       if (edPhyObj)
//       {
//         edPhyObj->SetSpreadingFactor(7);
//         NS_LOG_INFO("[ED " << i << "] PHY SF set to 7 (may be overridden by MAC DR)");

//         SetDoubleAttrIfPresent(edPhyObj, "EnergyDetection", PHY_ENERGY_DETECTION_DBM);          // dBm
//         SetTimeAttrIfPresent  (edPhyObj, "MaxTransmissionDuration", Seconds(PHY_MAX_TX_DURATION_SEC));
//       }
//     }

//     // MAC traces + force DR5 and relax duty-cycle if available
//     Ptr<lorawan::LorawanMac> edMacObj = edNd->GetMac();
//     if (edMacObj)
//     {
//       edMacObj->TraceConnectWithoutContext("SentNewPacket", ns3::MakeCallback(&OnEdMacTx));

//       Ptr<lorawan::ClassAEndDeviceLorawanMac> classAMac =
//           edMacObj->GetObject<lorawan::ClassAEndDeviceLorawanMac>();
//       if (classAMac)
//       {
//         ns3::TypeId tid = classAMac->GetInstanceTypeId();
//         NS_LOG_INFO("[ED " << i << "] ClassA MAC attributes:");
//         for (uint32_t a = 0; a < tid.GetAttributeN(); ++a)
//         {
//           auto info = tid.GetAttribute(a);
//           NS_LOG_INFO("  - " << info.name);
//         }

//         // Force DR5 (EU868: SF7/125 kHz)
//         classAMac->SetDataRate(5);
//         NS_LOG_INFO("[ED " << i << "] MAC DataRate set to DR5 (SF7/125kHz)");

//         // Disable duty-cycle if your build exposes this attribute
//         SetBoolAttrIfPresent(classAMac, "DutyCycleEnabled", false);
//         // If your fork has AggregatedDutyCycle as DoubleValue, you can also set it to 1.0 here.
//       }
//     }
//   }

//   // ------ Backhaul GW <-> NS over PointToPoint; register with NetworkServerHelper ------
//   P2PGwRegistration_t p2pReg;

//   PointToPointHelper p2p;
//   p2p.SetDeviceAttribute("DataRate", StringValue(CLOUD_BACKHAUL_DATARATE));
//   p2p.SetChannelAttribute("Delay",    StringValue(CLOUD_BACKHAUL_DELAY));

//   {
//     NetDeviceContainer d = p2p.Install(networkServer.Get(0), gateways.Get(0));

//     // Register the NS-side backhaul device with the NS helper
//     Ptr<PointToPointNetDevice> nsBackhaul = DynamicCast<PointToPointNetDevice>(d.Get(0));
//     if (nsBackhaul)
//     {
//       p2pReg.emplace_back(nsBackhaul, gateways.Get(0));
//     }
//   }

//   NetworkServerHelper nsHelper;
//   nsHelper.SetEndDevices(endDevices);   // expects NodeContainer
//   nsHelper.SetGatewaysP2P(p2pReg);      // registration list (NS p2p dev, GW node)
//   nsHelper.EnableAdr(ENABLE_ADR);

//   ApplicationContainer nsApps = nsHelper.Install(networkServer.Get(0));

//   // After you install the Network Server (nsApps)
//   if (nsApps.GetN() > 0)
//   {
//     Ptr<lorawan::NetworkServer> ns =
//         nsApps.Get(0)->GetObject<lorawan::NetworkServer>();
//     if (ns)
//     {
//       // Your fork exposes either "ReceivedFromGateway" or "ReceivedPacket".
//       ns->TraceConnectWithoutContext("ReceivedFromGateway",
//                   ns3::MakeCallback(&OnNsRxFromGw));
//     }

//   }

//   Ptr<LoraNetDevice> edNd = DynamicCast<LoraNetDevice>(edDevs.Get(0));
//   Ptr<SimpleSender>  app  = CreateObject<SimpleSender>();

//   // first send at t=11s, exponential or fixed IAT controlled by constants above
//   app->Configure(edNd,
//                 nPkts,
//                 Seconds(11.0),
//                 Seconds(period),
//                 USE_EXPONENTIAL_IAT,
//                 EXP_IAT_MEAN_S);

//   endDevices.Get(0)->AddApplication(app);
//   app->SetStartTime(Seconds(0));
//   app->SetStopTime(Seconds(simTime));


//   // Enable periodic performance printing
//   lora.EnablePeriodicGlobalPerformancePrinting(Out("global-performance.txt"), Seconds(30));
//   lora.EnablePeriodicPhyPerformancePrinting(gateways, Out("phy-performance.txt"), Seconds(30));
//   lora.EnablePeriodicDeviceStatusPrinting(endDevices, gateways, Out("device-status.txt"), Seconds(30));

//   // Disable verbose energy source logging to reduce terminal output
//   LogComponentEnable("BasicEnergySource", LOG_LEVEL_ERROR);  // Only show errors
//   LogComponentEnable("SimpleDeviceEnergyModel", LOG_LEVEL_ERROR);
  
//   LogComponentEnable("EndDeviceLorawanMac", LOG_LEVEL_INFO);
//   LogComponentEnable("ClassAEndDeviceLorawanMac", LOG_LEVEL_INFO);
//   LogComponentEnable("LoraPhy", LOG_LEVEL_INFO);
//   LogComponentEnable("EndDeviceLoraPhy", LOG_LEVEL_INFO);
//   LogComponentEnable("GatewayLoraPhy", LOG_LEVEL_INFO);
//   LogComponentEnable("LoraChannel", LOG_LEVEL_INFO);

//   Simulator::Stop(Seconds(simTime));
//   Simulator::Run();
  
//   // Print final statistics
//   LoraPacketTracker& tracker = lora.GetPacketTracker();
//   NS_LOG_INFO("=== Final Statistics ===");
  
//   std::string globalStats = tracker.CountMacPacketsGlobally(Seconds(0), Seconds(simTime));
//   NS_LOG_INFO("Global MAC performance (sent received): " << globalStats);
  
//   for (auto gw = gateways.Begin(); gw != gateways.End(); ++gw)
//   {
//     int gwId = (*gw)->GetId();
//     std::string phyStats = tracker.PrintPhyPacketsPerGw(Seconds(0), Seconds(simTime), gwId);
//     NS_LOG_INFO("Gateway " << gwId << " PHY stats: " << phyStats);
//   }
  
//   Simulator::Destroy();
//   if (gCsvInit) { gCsv.close(); }
//   if (gEnergyTotalCsv.is_open()) gEnergyTotalCsv.close();
//   if (gEnergyRemainCsv.is_open()) gEnergyRemainCsv.close();

//   return 0;
// }

#include "../common/scenario_config.h"
#include "../common/paths.h"
#include "../common/logging.h"
#include "../common/traces.h"
#include "../common/energy_setup.h"
#include "../common/lora_setup.h"
#include "../common/app_simple_sender.h"

#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/mobility-module.h"
#include "ns3/internet-module.h"
#include "ns3/lorawan-module.h"
#include "ns3/log.h"

using namespace ns3;
using namespace ns3::lorawan;
using namespace scenario;

NS_LOG_COMPONENT_DEFINE("Scenario00Simple");

int main(int argc, char* argv[]) {
    // Parse command line and load config
    auto& config = scenario::ScenarioConfig::Get();
    config.ParseCommandLine(argc, argv);
    
    // Enable logging
    LogComponentEnable("Scenario00Simple",
        static_cast<LogLevel>(LOG_PREFIX_TIME | LOG_PREFIX_NODE | LOG_LEVEL_INFO));
    
    // Create nodes
    NodeContainer gateways;      gateways.Create(1);
    NodeContainer endDevices;    endDevices.Create(1);
    NodeContainer networkServer; networkServer.Create(1);
    
    // Setup mobility
    MobilityHelper mob;
    mob.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mob.Install(gateways);
    mob.Install(endDevices);
    mob.Install(networkServer);
    
    gateways.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 10.0));
    endDevices.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(config.gw_ed_distance_m, 0.0, 1.0));
    networkServer.Get(0)->GetObject<MobilityModel>()->SetPosition(Vector(0.0, 0.0, 10.0));
    
    NS_LOG_INFO("GW-ED distance = " << config.gw_ed_distance_m << " m");
    
    // Create LoRa network
    auto loraDevices = LoraSetup::CreateLoraNetwork(gateways, endDevices);
    
    // Open CSV files for energy traces
    CsvLogger::OpenEnergyCsvs();
    
    // Install energy models
    auto energySources = EnergySetup::InstallEnergyModels(endDevices, loraDevices.edDevs);
    
    // Configure and connect traces
    LoraSetup::ConnectTraces(loraDevices.gwDevs, loraDevices.edDevs);
    
    // Setup Network Server
    auto nsApps = LoraSetup::SetupNetworkServer(networkServer, gateways, endDevices, loraDevices.gwDevs);
    
    // Create and configure application
    Ptr<LoraNetDevice> edNd = DynamicCast<LoraNetDevice>(loraDevices.edDevs.Get(0));
    Ptr<SimpleSender> app = CreateObject<SimpleSender>();
    
    app->Configure(edNd,
                  config.n_pkts_to_send,
                  Seconds(11.0),
                  Seconds(config.fixed_period_s),
                  config.use_exponential_iat,
                  config.exp_iat_mean_s);
    
    endDevices.Get(0)->AddApplication(app);
    app->SetStartTime(Seconds(0));
    app->SetStopTime(Seconds(config.sim_time_s));
    
    // Enable periodic performance printing
    loraDevices.loraHelper.EnablePeriodicGlobalPerformancePrinting(
        OutPath(config.global_performance_file), Seconds(30));
    loraDevices.loraHelper.EnablePeriodicPhyPerformancePrinting(
        gateways, OutPath(config.phy_performance_file), Seconds(30));
    loraDevices.loraHelper.EnablePeriodicDeviceStatusPrinting(
        endDevices, gateways, OutPath(config.device_status_file), Seconds(30));
    
    // Disable verbose energy source logging
    LogComponentEnable("BasicEnergySource", LOG_LEVEL_ERROR);
    LogComponentEnable("SimpleDeviceEnergyModel", LOG_LEVEL_ERROR);
    
    // Enable component logging as per original
    LogComponentEnable("EndDeviceLorawanMac", LOG_LEVEL_INFO);
    LogComponentEnable("ClassAEndDeviceLorawanMac", LOG_LEVEL_INFO);
    LogComponentEnable("LoraPhy", LOG_LEVEL_INFO);
    LogComponentEnable("EndDeviceLoraPhy", LOG_LEVEL_INFO);
    LogComponentEnable("GatewayLoraPhy", LOG_LEVEL_INFO);
    LogComponentEnable("LoraChannel", LOG_LEVEL_INFO);
    
    // Run simulation
    Simulator::Stop(Seconds(config.sim_time_s));
    Simulator::Run();
    
    // Print final statistics
    LoraPacketTracker& tracker = loraDevices.loraHelper.GetPacketTracker();
    NS_LOG_INFO("=== Final Statistics ===");
    
    std::string globalStats = tracker.CountMacPacketsGlobally(Seconds(0), Seconds(config.sim_time_s));
    NS_LOG_INFO("Global MAC performance (sent received): " << globalStats);
    
    for (auto gw = gateways.Begin(); gw != gateways.End(); ++gw) {
        int gwId = (*gw)->GetId();
        std::string phyStats = tracker.PrintPhyPacketsPerGw(Seconds(0), Seconds(config.sim_time_s), gwId);
        NS_LOG_INFO("Gateway " << gwId << " PHY stats: " << phyStats);
    }
    
    // Cleanup
    Simulator::Destroy();
    CsvLogger::CloseEnergyCsvs();
    CsvLogger::CloseSnrCsv();
    
    return 0;
}