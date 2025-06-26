#!/bin/bash

# Define common parameters that remain constant across all scenarios
APP_PERIOD=60 # seconds, as per your example
RADIUS=5000

# Define arrays for parameters to vary
# Ensure your adr-opt-simulation.cc properly handles "ADRopt", "AVERAGE", and "MAXIMUM"
ADR_METHODS=("ADRopt") # "AVERAGE" "MAXIMUM")
N_PERIODS=(300) # Example periods to simulate

# --- Customizable parameters for GWs and EDs ---
# Modify these values to change the number of devices and gateways
N_DEVICES=1  # Set your desired number of End Devices here
N_GATEWAYS=9 # Set your desired number of Gateways here
# --- End of Customizable parameters ---

# Loop through each combination of parameters
for METHOD in "${ADR_METHODS[@]}"; do
    for PERIODS in "${N_PERIODS[@]}"; do
        # Base name for output files
        BASE_OUTPUT_NAME="results_${METHOD}_${PERIODS}periods_ED${N_DEVICES}_GW${N_GATEWAYS}"
        
        # File for NS_LOG output (console output redirected)
        LOG_FILE="${BASE_OUTPUT_NAME}_log.txt" 
        
        # File for simulation data (if the C++ app uses --outputFile for data)
        # Currently, adr-opt-simulation.cc does not write to this, but it's good practice to keep the argument.

        echo "-----------------------------------------------------"
        echo "Running simulation for Scenario:"
        echo "  ADR Method: ${METHOD}"
        echo "  Number of Periods: ${PERIODS}"
        echo "  Number of End Devices: ${N_DEVICES}"
        echo "  Number of Gateways: ${N_GATEWAYS}"
        echo "  Log File: ${LOG_FILE}"
        echo "-----------------------------------------------------"

        # Execute the ns3 simulation with the chosen parameters
        # Redirect standard output (containing NS_LOG messages) to LOG_FILE
        # 2>&1 redirects standard error to the same log file
        ./ns3 run "adr_opt/adr-opt-simulation --adrMethod=${METHOD} --appPeriod=${APP_PERIOD} --nPeriods=${PERIODS} --nDevices=${N_DEVICES} --nGateways=${N_GATEWAYS} --radius=${RADIUS} " > "${LOG_FILE}" 2>&1

        echo "Simulation for ${METHOD} with ${PERIODS} periods completed. Logs saved to ${LOG_FILE}"
        echo ""
    done
done

echo "All simulations finished."