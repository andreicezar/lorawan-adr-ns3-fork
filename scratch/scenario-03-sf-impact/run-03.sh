#!/bin/bash
# run-03.sh - Scenario 3: Spreading Factor Impact
set -euo pipefail

echo "🔬 Scenario 3: Spreading Factor Impact"
echo "======================================"
echo "📊 Config: 50 devices, 1 gateway, SF7 to SF12, 200min"

cd "$(dirname "$0")/../.."

# --- derive CSV tag from POSITION_FILE exported by run-all.sh ---
POS="${POSITION_FILE:-scenario_positions.csv}"
csv_base="$(basename "$POS")"
if [[ "$csv_base" =~ ^scenario_positions_(.+)\.csv$ ]]; then
  POS_TAG="${BASH_REMATCH[1]}"   # e.g. "1x1km", "3x3km"
else
  POS_TAG="$(echo "$csv_base" | sed -E 's/[^A-Za-z0-9]+/_/g; s/^_+|_+$//g')"
fi

# Function to run a single configuration
run_config() {
    local name="$1"
    local init_sf="$2"
    local init_tp="$3"
    local enable_adr="$4"
    local target_sf="${5:-10}"
    local target_tp="${6:-14}"
    
    # Output folder now follows CSV tag
    local output_folder="output/scenario-03-sf-impact_${POS_TAG}/${name}"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: ${name} (SF${target_sf})"
    echo "📁 Output directory: $output_folder"
    echo "🗺️  Positions CSV: $POS"
    echo "⚙️  Config: Fixed SF${target_sf}, ${target_tp}dBm, ADR=${enable_adr}"
    
    if ./ns3 run "scratch/scenario-03-sf-impact/scenario-03-sf-impact \
        --simulationTime=200 \
        --positionFile=${POS} \
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
    run_config "sf7-fixed"  "true" "true" "false" 7  14; [ $? -eq 0 ] || FAILED_CASES+=("sf7-fixed")
    run_config "sf8-fixed"  "true" "true" "false" 8  14; [ $? -eq 0 ] || FAILED_CASES+=("sf8-fixed")
    run_config "sf9-fixed"  "true" "true" "false" 9  14; [ $? -eq 0 ] || FAILED_CASES+=("sf9-fixed")
    run_config "sf10-fixed" "true" "true" "false" 10 14; [ $? -eq 0 ] || FAILED_CASES+=("sf10-fixed")
    run_config "sf11-fixed" "true" "true" "false" 11 14; [ $? -eq 0 ] || FAILED_CASES+=("sf11-fixed")
    run_config "sf12-fixed" "true" "true" "false" 12 14; [ $? -eq 0 ] || FAILED_CASES+=("sf12-fixed")
    
    # Final summary
    echo ""
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All SF impact scenarios completed successfully!"
        echo "📈 Results available in output/scenario-03-sf-impact_${POS_TAG}/"
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
