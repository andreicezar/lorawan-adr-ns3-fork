# Using FLORA Energy Config in ns-3 LoRaWAN Simulation

## Overview

The `simulation-file.cc` simulation now supports loading energy parameters from the FLORA `energyConsumptionParameters.xml` configuration file. This allows you to:

1. **Use exact FLORA energy model values** in ns-3 simulations
2. **Automatically convert** FLORA units (mA) to ns-3 units (A)
3. **Fit a linear TX power amplifier model** based on the FLORA per-TX-power supply currents

## Quick Start

Run the simulation with the FLORA XML config:

```bash
cd /home/andrei/development/ns3-comparison-clean/ns-3-dev
./ns3 run "scratch/test/simulation-file \
  --energyConfigXml=../../omnet/flora/simulations/energyConsumptionParameters.xml \
  --distanceBetweenNodes=500 \
  --initialSF=12 \
  --initialTP=14"
```

Or with all energy parameters explicitly:

```bash
./ns3 run "scratch/test/simulation-file \
  --energyConfigXml=../../omnet/flora/simulations/energyConsumptionParameters.xml \
  --distanceBetweenNodes=1000 \
  --initialSF=7 \
  --initialTP=2"
```

## What the XML Parser Loads

The `LoadEnergyConfigFromXml()` function reads the FLORA XML and populates:

### Supply Voltage
- **FLORA XML:** `<supplyVoltage value="3.3"/>`
- **ns-3:** `params.supply_voltage_v = 3.3` (V)

### RX Current (Receiver)
- **FLORA XML:** `<receiverReceivingSupplyCurrent value="9.7"/>`
- **ns-3:** `params.rx_current_a = 0.0097` (A)  [auto-converted from mA]

### Idle Current (Standby)
- **FLORA XML:** `<idleSupplyCurrent value="0.0001"/>`
- **ns-3:** `params.idle_current_a = 0.0001` (A)  
- **Used for:** Standby, Sleep, TX model standby current

### TX Supply Currents (Power-dependent)
The XML contains per-TX-power supply currents (in mA):

```xml
<txSupplyCurrents>
  <txSupplyCurrent txPower="2" supplyCurrent="24"/>
  <txSupplyCurrent txPower="3" supplyCurrent="24"/>
  ...
  <txSupplyCurrent txPower="14" supplyCurrent="44"/>
</txSupplyCurrents>
```

**Result in ns-3:**
- Stored in `params.tx_supply_currents_a` map: `txPower (dBm) → current (A)`
- Example: TX at 14 dBm → 44 mA → 0.044 A

## Linear TX Current Model Fitting

The function **automatically fits** a linear power amplifier model using the FLORA measurements. This allows the `LinearLoraTxCurrentModel` to reproduce FLORA values.

### Formula
```
TxCurrent(txPowerDbm) = eta × W(txPowerDbm) / V + standby
```

Where:
- `W(txPowerDbm)` = dBm to Watts
- `V` = supply voltage (3.3 V)
- `eta` = efficiency (fitted from data)
- `standby` = standby current (fitted from data)

### Fitting Algorithm
1. **If ≥2 data points:** Use min and max TX power to fit `eta` and `standby`
2. **If 1 data point:** Compute `standby` using default `eta`
3. **If 0 data points:** Use default values

### Example Fit
From FLORA XML (2 dBm: 24 mA, 14 dBm: 44 mA):
- W(2 dBm) ≈ 0.00159 W
- W(14 dBm) ≈ 0.0251 W
- ΔI = 44 - 24 = 20 mA
- ΔW = 0.0251 - 0.00159 = 0.0235 W
- eta ≈ (0.0235) / (3.3 × 0.020) ≈ 0.356
- standby ≈ 24 mA - 0.00159 / (3.3 × 0.356) ≈ 20.4 mA

## SimulationParameters Fields

Added for energy model configuration:

```cpp
// FLORA-sourced (stored in original units where noted)
double supplyVoltage;                      // V
double receiverReceivingSupplyCurrent;     // mA
double receiverBusySupplyCurrent;          // mA
double idleSupplyCurrent;                  // mA

// ns-3 friendly (always in SI units)
double supply_voltage_v;                   // V
double initial_energy_j;                   // J
double update_interval_s;                  // s
double rx_current_a;                       // A
double sleep_current_a;                    // A
double idle_current_a;                     // A
double tx_model_eta;                       // unitless
double tx_model_standby_a;                 // A
std::map<int, double> tx_supply_currents_a; // dBm → A

// Config file path
std::string energyConfigPath;               // path to XML
```

## Energy Model Integration

The energy model setup now uses these parameters:

```cpp
// Basic energy source
sourceHelper.Set("BasicEnergySupplyVoltageV", DoubleValue(params.supply_voltage_v));
sourceHelper.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(params.initial_energy_j));

// LoRa radio energy model
lrm->SetAttribute("StandbyCurrentA", DoubleValue(params.idle_current_a));
lrm->SetAttribute("RxCurrentA", DoubleValue(params.rx_current_a));
lrm->SetAttribute("SleepCurrentA", DoubleValue(params.sleep_current_a));

// TX current model (fitted from XML)
txModel->SetAttribute("Eta", DoubleValue(params.tx_model_eta));
txModel->SetAttribute("Voltage", DoubleValue(params.supply_voltage_v));
txModel->SetAttribute("StandbyCurrent", DoubleValue(params.tx_model_standby_a));
```

## Example Usage Scenarios

### 1. Default ns-3 parameters (no XML)
```bash
./ns3 run "scratch/test/simulation-file \
  --distanceBetweenNodes=500"
```
Uses built-in defaults (3.3 V, 0.0001 A idle, etc.)

### 2. FLORA parameters with custom simulation settings
```bash
./ns3 run "scratch/test/simulation-file \
  --energyConfigXml=../../omnet/flora/simulations/energyConsumptionParameters.xml \
  --distanceBetweenNodes=500 \
  --initialSF=10 \
  --initialTP=10 \
  --simTime=1200"
```

### 3. Run with logging to see fitted model parameters
```bash
./ns3 run "scratch/test/simulation-file \
  --energyConfigXml=../../omnet/flora/simulations/energyConsumptionParameters.xml \
  --verbosity=true"
```

## File Paths

- **FLORA XML:** `../../omnet/flora/simulations/energyConsumptionParameters.xml` (relative to `scratch/test/`)
- **ns-3 Simulation:** `scratch/test/simulation-file.cc`

## Debug / Validation

Add verbosity to see what was loaded:

```bash
./ns3 run "scratch/test/simulation-file \
  --energyConfigXml=../../omnet/flora/simulations/energyConsumptionParameters.xml \
  --verbosity=true"
```

The fitted model parameters (eta, standby current) can help you verify that the linear PA model matches the FLORA data.

## Notes

- If the XML file is not found or `energyConfigPath` is empty, the simulation uses default values.
- Unit conversion is automatic: FLORA mA → ns-3 A (divide by 1000).
- The linear fit may not perfectly match all TX power levels, especially if the actual PA is non-linear.
- For best results, ensure the XML file has at least 2 TX power entries.
