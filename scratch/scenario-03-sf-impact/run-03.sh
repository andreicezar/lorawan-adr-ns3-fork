#!/bin/bash
# run-03.sh - Scenario 3: Spreading Factor Impact
set -euo pipefail

echo "🔬 Scenario 3: Spreading Factor Impact"
echo "======================================"
echo "📊 Config: 50 devices, 1 gateway, SF7 to SF12, 200min"

cd "$(dirname "$0")/../.."

# Function to run a single configuration
run_config() {
    local name="$1"
    local init_sf="$2"
    local init_tp="$3"
    local enable_adr="$4"
    local target_sf="${5:-10}"
    local target_tp="${6:-14}"
    
    local output_folder="output/scenario-03-sf-impact/${name}"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: ${name} (SF${target_sf})"
    echo "📁 Output directory: $output_folder"
    echo "⚙️  Config: Fixed SF${target_sf}, ${target_tp}dBm, ADR=${enable_adr}"
    
    if ./ns3 run "scratch/scenario-03-sf-impact/scenario-03-sf-impact \
        --simulationTime=200 \
        --positionFile=scenario_positions.csv \
        --useFilePositions=true \
        --spreadingFactor=$target_sf \
        --outputPrefix=$output_folder/result \
        --nDevices=50 \
        --packetInterval=300"; then
        echo "✅ $name (SF${target_sf}) completed successfully"
        return 0
    else
        echo "❌ $name (SF${target_sf}) FAILED!"
        return 1
    fi
}

# Main function that runs all scenarios
run_all_scenarios() {
    local FAILED_CASES=()

    # Scenario 3: Spreading Factor Impact Analysis
    # Format: run_config "name" "initSF" "initTP" "enableADR" [targetSF] [targetTP]
    
    # Test each spreading factor from SF7 to SF12
    run_config "sf7-fixed" "true" "true" "false" 7 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf7-fixed")
    
    run_config "sf8-fixed" "true" "true" "false" 8 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf8-fixed")
    
    run_config "sf9-fixed" "true" "true" "false" 9 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf9-fixed")
    
    run_config "sf10-fixed" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf10-fixed")
    
    run_config "sf11-fixed" "true" "true" "false" 11 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf11-fixed")
    
    run_config "sf12-fixed" "true" "true" "false" 12 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf12-fixed")
    
    # Final summary
    echo ""
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All SF impact scenarios completed successfully!"
        echo "📈 Results available in output/scenario-03-sf-impact/"
    else
        echo "❌ Some scenarios failed: ${FAILED_CASES[*]}"
        echo "❌ Check the simulation output above for error details"
        exit 1
    fi
}

# Execute if run directly (preserve original functionality)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_all_scenarios
fi