#!/bin/bash
# run-06.sh - Scenario 6: Realistic Equal 120 Packets (Duty Cycle Aware)
set -euo pipefail

echo "🔬 Scenario 6: Realistic Equal 120 Packets (Duty Cycle Aware)"
echo "============================================================="
echo "📊 SF-specific intervals to achieve exactly 120 packets per device"

cd "$(dirname "$0")/../.."

# SF-specific configurations for exactly 120 packets (duty cycle aware)
declare -A SF_INTERVALS=(
    [7]=90    # SF7: 3 hours, 90s intervals = (180*60)/90 = 120 packets
    [8]=95    # SF8: 3.2 hours, 95s intervals = (190*60)/95 = 120 packets  
    [9]=100   # SF9: 3.3 hours, 100s intervals = (200*60)/100 = 120 packets
    [10]=150  # SF10: 5 hours, 150s intervals = (300*60)/150 = 120 packets
    [11]=200  # SF11: 6.7 hours, 200s intervals = (400*60)/200 = 120 packets
    [12]=260  # SF12: 8.7 hours, 260s intervals = (520*60)/260 = 120 packets
)

declare -A SF_SIMTIMES=(
    [7]=180   # 3 hours
    [8]=190   # 3.2 hours
    [9]=200   # 3.3 hours
    [10]=300  # 5 hours
    [11]=400  # 6.7 hours
    [12]=520  # 8.7 hours
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
    
    local output_folder="output/scenario-06-collision-capture/sf-${target_sf}-realistic-120"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running SF${target_sf} simulation (duty cycle optimized)"
    echo "📁 Output: $output_folder"
    echo "⏱️ Time: ${simtime} minutes, Interval: ${interval}s"
    echo "📊 Expected: $expected_packets packets per device"
    
    if ./ns3 run "scratch/scenario-06-collision-capture/scenario-06-collision-capture \
        --simulationTime=$simtime \
        --packetInterval=$interval \
        --positionFile=scenario_positions.csv \
        --useFilePositions=true \
        --spreadingFactor=$target_sf \
        --outputPrefix=$output_folder/result \
        --nDevices=50"; then
        
        echo "✅ SF${target_sf} completed successfully"
        
        # Quick validation
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
    # Format: run_config "name" "initSF" "initTP" "enableADR" [targetSF] [targetTP]
    
    # Test key spreading factors with duty-cycle-aware settings
    run_config "sf7-collision" "true" "true" "false" 7 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf7-collision")
    
    run_config "sf10-collision" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf10-collision")
    
    run_config "sf12-collision" "true" "true" "false" 12 14
    [ $? -eq 0 ] || FAILED_CASES+=("sf12-collision")
    
    # Final summary
    echo ""
    echo "=================================================="
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All realistic equal-packet scenarios completed!"
        echo "📈 Results available in output/scenario-06-collision-capture/ directories"
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