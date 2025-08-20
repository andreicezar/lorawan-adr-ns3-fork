#!/bin/bash
# run-06-equal-120.sh - Equal 120 packets for ALL SFs (long simulation)
set -euo pipefail

echo "🔬 Scenario 6: Equal 120 Packets for ALL SFs"
echo "============================================="
echo "📊 Config: 50 devices, 300min, 150s intervals"
echo "📊 Target: Exactly 120 packets for ALL SFs (perfectly fair)"

cd "$(dirname "$0")/../.."

FAILED_SFS=()

echo "⚠️ WARNING: This is a 5-hour simulation for perfect equality"
echo "For faster results, use the practical approach instead"
echo ""

# Test key spreading factors with perfectly equal packets
for SF in 7 10 12; do
    output_folder="output/scenario-06-collision-capture/sf-$SF-equal-120"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: SF$SF (equal 120 packets)"
    echo "📁 Output directory: $output_folder"
    echo "📊 Expected: Exactly 120 packets per device (all SFs)"
    echo "⏱️ Simulation time: 5 hours"
    
    if ./ns3 run "scratch/scenario-06-collision-capture/scenario-06-collision-capture \
        --simulationTime=300 \
        --positionFile=scenario_positions.csv \
        --useFilePositions=true \
        --spreadingFactor=$SF \
        --outputPrefix=$output_folder/result \
        --nDevices=50 \
        --packetInterval=150"; then
        echo "✅ SF$SF completed successfully"
    else
        echo "❌ SF$SF FAILED!"
        FAILED_SFS+=("SF$SF")
    fi
done

# Final summary
echo ""
if [ ${#FAILED_SFS[@]} -eq 0 ]; then
    echo "✅ All equal 120-packet scenarios completed!"
    echo "📈 Results available in output/scenario-06-collision-capture/ directories"
    echo ""
    echo "📊 Expected results: 6000 packets (120 per device) for ALL SFs"
    echo "🎯 Perfect fairness for collision and capture comparison"
else
    echo "❌ Some scenarios failed: ${FAILED_SFS[*]}"
    exit 1
fi