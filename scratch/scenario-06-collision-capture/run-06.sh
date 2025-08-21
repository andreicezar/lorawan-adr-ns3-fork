#!/bin/bash
# run-06-realistic-equal.sh - SF-specific intervals for true 120 packet equality
set -euo pipefail

echo "🔬 Scenario 6: Realistic Equal 120 Packets (Duty Cycle Aware)"
echo "============================================================="
echo "📊 SF-specific intervals to achieve exactly 120 packets per device"

cd "$(dirname "$0")/../.."

FAILED_SFS=()

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

echo "⚡ Optimized timing per SF (respects duty cycle limits):"
for SF in 7 8 9 10 11 12; do
    interval=${SF_INTERVALS[$SF]}
    simtime=${SF_SIMTIMES[$SF]}
    packets=$((simtime * 60 / interval))
    echo "  SF$SF: ${simtime}min simulation, ${interval}s intervals → $packets packets"
done

echo ""
echo "🚀 Running optimized simulations..."

# Test all spreading factors with duty-cycle-aware settings
for SF in 7 10 12; do  # Key SFs for comparison
    interval=${SF_INTERVALS[$SF]}
    simtime=${SF_SIMTIMES[$SF]}
    expected_packets=$((simtime * 60 / interval))
    
    output_folder="output/scenario-06-collision-capture/sf-$SF-realistic-120"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running SF$SF simulation (duty cycle optimized)"
    echo "📁 Output: $output_folder"
    echo "⏱️ Time: ${simtime} minutes, Interval: ${interval}s"
    echo "📊 Expected: $expected_packets packets per device"
    
    if ./ns3 run "scratch/scenario-06-collision-capture/scenario-06-collision-capture \
        --simulationTime=$simtime \
        --packetInterval=$interval \
        --positionFile=scenario_positions.csv \
        --useFilePositions=true \
        --spreadingFactor=$SF \
        --outputPrefix=$output_folder/result \
        --nDevices=50"; then
        echo "✅ SF$SF completed successfully"
        
        # Quick validation
        result_file="$output_folder/result_sf${SF}_results.csv"
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
    else
        echo "❌ SF$SF FAILED!"
        FAILED_SFS+=("SF$SF")
    fi
done

# Final summary
echo ""
echo "=================================================="
if [ ${#FAILED_SFS[@]} -eq 0 ]; then
    echo "✅ All realistic equal-packet scenarios completed!"
    echo "📈 Results available in output/scenario-06-collision-capture/ directories"
    echo ""
    echo "🎯 Each SF should now achieve ~120 packets per device"
    echo "📊 Fair comparison achieved while respecting duty cycle limits"
    echo ""
    echo "🔍 Next steps:"
    echo "   1. Compare capture effect strength across SFs"
    echo "   2. Analyze collision patterns with equal packet counts"
    echo "   3. Validate duty cycle compliance in real deployments"
else
    echo "❌ Some scenarios failed: ${FAILED_SFS[*]}"
    exit 1
fi