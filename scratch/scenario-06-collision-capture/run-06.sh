#!/bin/bash
# run-06.sh - Scenario 6: Realistic Equal 120 Packets (Duty Cycle Aware)
set -euo pipefail

echo "🔬 Scenario 6: Realistic Equal 120 Packets (Duty Cycle Aware)"
echo "============================================================="
echo "📊 SF-specific intervals to achieve exactly 120 packets per device"

cd "$(dirname "$0")/../.."

# --- derive CSV tag from POSITION_FILE exported by run-all.sh ---
POS="${POSITION_FILE:-scenario_positions.csv}"
csv_base="$(basename "$POS")"
if [[ "$csv_base" =~ ^scenario_positions_(.+)\.csv$ ]]; then
  POS_TAG="${BASH_REMATCH[1]}"   # e.g. "1x1km", "3x3km"
else
  POS_TAG="$(echo "$csv_base" | sed -E 's/[^A-Za-z0-9]+/_/g; s/^_+|_+$//g')"
fi

# SF-specific configurations for exactly 120 packets (duty cycle aware)
declare -A SF_INTERVALS=(
    [7]=90     # SF7:  3.0 hours, (180*60)/90  = 120 packets
    [8]=95     # SF8:  3.2 hours, (190*60)/95  = 120 packets
    [9]=100    # SF9:  3.3 hours, (200*60)/100 = 120 packets
    [10]=150   # SF10: 5.0 hours, (300*60)/150 = 120 packets
    [11]=200   # SF11: 6.7 hours, (400*60)/200 = 120 packets
    [12]=260   # SF12: 8.7 hours, (520*60)/260 = 120 packets
)

declare -A SF_SIMTIMES=(
    [7]=180    # 3.0 hours
    [8]=190    # 3.2 hours
    [9]=200    # 3.3 hours
    [10]=300   # 5.0 hours
    [11]=400   # 6.7 hours
    [12]=520   # 8.7 hours
)

# Function to run a single configuration
run_config() {
    local name="$1"
    local init_sf="$2"
    local init_tp="$3"
    local enable_adr="$4"
    local target_sf="${5:-10}"
    local target_tp="${6:-14}"

    # Get SF-specific timing parameters
    local interval=${SF_INTERVALS[$target_sf]}
    local simtime=${SF_SIMTIMES[$target_sf]}
    local expected_packets=$((simtime * 60 / interval))

    # Output folder now follows CSV tag
    local output_folder="output/scenario-06-collision-capture_${POS_TAG}/sf-${target_sf}-realistic-120"
    mkdir -p "$output_folder"

    echo ""
    echo "🚀 Running SF${target_sf} simulation (duty cycle optimized)"
    echo "📁 Output: $output_folder"
    echo "🗺️  Positions CSV: $POS"
    echo "⏱️ Time: ${simtime} minutes, Interval: ${interval}s"
    echo "📊 Expected: $expected_packets packets per device"

    if ./ns3 run "scratch/scenario-06-collision-capture/scenario-06-collision-capture \
        --simulationTime=$simtime \
        --packetInterval=$interval \
        --positionFile=$POS \
        --useFilePositions=true \
        --spreadingFactor=$target_sf \
        --outputPrefix=$output_folder/result \
        --nDevices=50"; then

        echo "✅ SF${target_sf} completed successfully"

        # Quick validation (adjust if your program names differently)
        result_file="$output_folder/result_sf${target_sf}_results.csv"
        if [ -f "$result_file" ]; then
            total_sent=$(grep "TotalSent," "$result_file" | cut -d',' -f2)
            avg_per_device=$((total_sent / 50))
            echo "📈 Result: $total_sent total packets ($avg_per_device per device)"
            if [ $avg_per_device -ge 115 ] && [ $avg_per_device -le 125 ]; then
                echo "✅ Target achieved: ~120 packets per device"
            else
                echo "⚠️ Target missed: Expected ~120, got $avg_per_device"
            fi
        fi
        return 0
    else
        echo "❌ SF${target_sf} FAILED!"
        return 1
    fi
}

# Main function that runs all scenarios
run_all_scenarios() {
    local FAILED_CASES=()

    echo "⚡ Optimized timing per SF (respects duty cycle limits):"
    for SF in 7 10 12; do
        interval=${SF_INTERVALS[$SF]}
        simtime=${SF_SIMTIMES[$SF]}
        packets=$((simtime * 60 / interval))
        echo "  SF$SF: ${simtime}min simulation, ${interval}s intervals → $packets packets"
    done

    echo ""
    echo "🚀 Running optimized simulations..."

    # Scenario 6: Collision Capture with Duty Cycle Awareness
    run_config "sf7-collision"  "true" "true" "false"  7  14 || FAILED_CASES+=("sf7-collision")
    run_config "sf10-collision" "true" "true" "false" 10  14 || FAILED_CASES+=("sf10-collision")
    run_config "sf12-collision" "true" "true" "false" 12  14 || FAILED_CASES+=("sf12-collision")

    echo ""
    echo "=================================================="
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All realistic equal-packet scenarios completed!"
        echo "📈 Results available in output/scenario-06-collision-capture_${POS_TAG}/"
        echo ""
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
