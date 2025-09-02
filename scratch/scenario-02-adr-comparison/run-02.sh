#!/bin/bash
# run-02.sh - Scenario 2: ADR Comparison
set -euo pipefail

echo "🔬 Scenario 2: ADR Comparison"
echo "=============================="
echo "📊 Config: 100 devices, 1 gateway, 500min, 300s intervals"

cd "$(dirname "$0")/../.."

# Simulation parameters
SIM_TIME=500
PKT_INTERVAL=300

# Function to run a single configuration
run_config() {
    local name="$1"
    local init_sf="$2"
    local init_tp="$3"
    local enable_adr="$4"
    local target_sf="${5:-12}"  # Default SF12 if not provided
    local target_tp="${6:-14}"  # Default 14dBm if not provided
    
    local output_folder="output/scenario-02-adr-comparison/${name}"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: ${name}"
    echo "📁 Output directory: $output_folder"
    echo "⚙️  Config: initSF=$init_sf, initTP=$init_tp, ADR=$enable_adr"
    if [ "$enable_adr" = "true" ]; then
        echo "🎯 Target: SF$target_sf, ${target_tp}dBm"
    else
        echo "🔒 Fixed: SF$target_sf, ${target_tp}dBm (no adaptation)"
    fi
    
    if ./ns3 run "scratch/scenario-02-adr-comparison/scenario-02-adr-comparison \
        --simulationTime=${SIM_TIME} \
        --positionFile=scenario_positions.csv \
        --useFilePositions=true \
        --packetInterval=${PKT_INTERVAL} \
        --outputPrefix=$output_folder/result \
        --adrEnabled=$enable_adr"; then
        echo "✅ $name completed successfully"
        return 0
    else
        echo "❌ $name FAILED!"
        return 1
    fi
}

# Main function that runs all scenarios
run_all_scenarios() {
    local FAILED_CASES=()

    # Scenario 2: Core ADR comparison (SF12, 14dBm initial for both)
    # Format: run_config "name" "initSF" "initTP" "enableADR" [targetSF] [targetTP]
    
    # Case 1: ADR DISABLED - fixed SF12, 14dBm (no adaptation)
    run_config "fixed-sf12" "true" "true" "false" 12 14
    [ $? -eq 0 ] || FAILED_CASES+=("fixed-sf12")
    
    # Case 2: ADR ENABLED - starts SF12, 14dBm but adapts during simulation
    run_config "adr-enabled" "true" "true" "true" 12 14
    [ $? -eq 0 ] || FAILED_CASES+=("adr-enabled")
    
    # Final summary
    echo ""
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All ADR comparison scenarios completed successfully!"
        echo "📈 Results available in output/scenario-02-adr-comparison/"
    else
        echo "❌ Some scenarios failed: ${FAILED_CASES[*]}"
        echo "❌ Check the simulation output above for error details"
        exit 1
    fi
}

# Execute if run directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_all_scenarios
fi