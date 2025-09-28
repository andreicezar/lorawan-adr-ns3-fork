#!/bin/bash
# run-04.sh - Scenario 4: Confirmed vs Unconfirmed Messages
set -euo pipefail

echo "🔬 Scenario 4: Confirmed vs Unconfirmed Messages"
echo "==============================================="
echo "📊 Config: 100 devices, 1 gateway, 80min, 120s intervals"

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
    
    # Map scenario name to confirmed messages setting
    local confirmed_messages="false"
    if [[ "$name" == "confirmed" ]]; then
        confirmed_messages="true"
    fi
    
    # Output folder now follows CSV tag
    local output_folder="output/scenario-04-confirmed-messages_${POS_TAG}/${name}"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: ${name} messages"
    echo "📁 Output directory: $output_folder"
    echo "🗺️  Positions CSV: $POS"
    echo "⚙️  Config: SF${target_sf}, ${target_tp}dBm, Confirmed=${confirmed_messages}"
    
    if ./ns3 run "scratch/scenario-04-confirmed-messages/scenario-04-confirmed-messages \
        --simulationTime=80 \
        --packetInterval=600 \
        --positionFile=${POS} \
        --useFilePositions=true \
        --confirmedMessages=$confirmed_messages \
        --outputPrefix=$output_folder/result"; then
        echo "✅ $name messages completed successfully"
        return 0
    else
        echo "❌ $name messages FAILED!"
        return 1
    fi
}

# Main function that runs all scenarios
run_all_scenarios() {
    local FAILED_CASES=()

    # Scenario 4: Confirmed vs Unconfirmed Message Comparison
    # Format: run_config "name" "initSF" "initTP" "enableADR" [targetSF] [targetTP]
    
    # Test unconfirmed vs confirmed messages (SF10, 14dBm, no ADR)
    run_config "unconfirmed" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("unconfirmed")
    
    run_config "confirmed" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("confirmed")
    
    # Final summary
    echo ""
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All confirmed vs unconfirmed scenarios completed successfully!"
        echo "📈 Results available in: output/scenario-04-confirmed-messages_${POS_TAG}/"
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
