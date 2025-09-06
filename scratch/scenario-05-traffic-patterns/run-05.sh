#!/bin/bash
# run-05.sh - Scenario 5: Traffic Pattern Variation
set -euo pipefail

echo "🔬 Scenario 5: Traffic Pattern Variation"
echo "======================================="
echo "📊 Config: 100 devices, 1 gateway, varying intervals and sim times"

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
    
    # Map scenario name to packet interval and simulation time
    local packet_interval=300
    local sim_time=200
    
    case "$name" in
        "low-traffic")
            packet_interval=600
            sim_time=400  # 40 * 600 / 60 = 400 minutes
            ;;
        "medium-traffic")
            packet_interval=300
            sim_time=200  # 40 * 300 / 60 = 200 minutes
            ;;
        "high-traffic")
            packet_interval=60
            sim_time=40   # 40 * 60 / 60 = 40 minutes
            ;;
    esac
    
    # Output folder now follows CSV tag
    local output_folder="output/scenario-05-traffic-patterns_${POS_TAG}/interval-${packet_interval}s"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: ${name} (${packet_interval}s intervals)"
    echo "📁 Output directory: $output_folder"
    echo "🗺️  Positions CSV: $POS"
    echo "⚙️  Config: SF${target_sf}, ${target_tp}dBm, ${packet_interval}s intervals, ${sim_time}min"
    
    if ./ns3 run "scratch/scenario-05-traffic-patterns/scenario-05-traffic-patterns \
        --simulationTime=$sim_time \
        --positionFile=${POS} \
        --useFilePositions=true \
        --packetInterval=$packet_interval \
        --outputPrefix=$output_folder/result"; then
        echo "✅ $name (${packet_interval}s interval) completed successfully"
        return 0
    else
        echo "❌ $name (${packet_interval}s interval) FAILED!"
        return 1
    fi
}

# Main function that runs all scenarios
run_all_scenarios() {
    local FAILED_CASES=()

    # Scenario 5: Traffic Pattern Variation Analysis
    # Format: run_config "name" "initSF" "initTP" "enableADR" [targetSF] [targetTP]
    
    # Test different traffic loads with same radio settings (SF10, 14dBm, no ADR)
    run_config "low-traffic" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("low-traffic")
    
    run_config "medium-traffic" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("medium-traffic")
    
    run_config "high-traffic" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("high-traffic")
    
    # Final summary
    echo ""
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All traffic pattern scenarios completed successfully!"
        echo "📈 Results available in:"
        echo "   - output/scenario-05-traffic-patterns_${POS_TAG}/interval-600s/ (LOW traffic: 10min intervals)"
        echo "   - output/scenario-05-traffic-patterns_${POS_TAG}/interval-300s/ (MEDIUM traffic: 5min intervals)"
        echo "   - output/scenario-05-traffic-patterns_${POS_TAG}/interval-60s/ (HIGH traffic: 1min intervals)"
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
