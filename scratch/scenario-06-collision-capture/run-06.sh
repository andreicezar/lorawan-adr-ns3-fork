#!/bin/bash
# run-06.sh - Scenario 6: Collision & Capture Effect
set -euo pipefail

echo "🔬 Scenario 6: Collision & Capture Effect"
echo "========================================"
echo "📊 Config: 20 devices, 1 gateway, 170min, 60s intervals"

cd "$(dirname "$0")/../.."

FAILED_SFS=()

# Test key spreading factors for collision analysis
for SF in 7 10 12; do
    output_folder="output/scenario-06-collision-capture/sf-$SF"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: SF$SF collision testing"
    echo "📁 Output directory: $output_folder"
    
    if ./ns3 run "scratch/scenario-06-collision-capture/scenario-06-collision-capture \
        --simulationTime=170 \    
        --positionFile=scenario_positions.csv \
        --useFilePositions=true \
        --spreadingFactor=$SF \
        --outputPrefix=$output_folder/result \
        --packetInterval=60"; then
        echo "✅ SF$SF completed successfully"
    else
        echo "❌ SF$SF FAILED!"
        FAILED_SFS+=("SF$SF")
    fi
done

# Final summary
echo ""
if [ ${#FAILED_SFS[@]} -eq 0 ]; then
    echo "✅ All collision & capture scenarios completed successfully!"
    echo "📈 Results available in output/scenario-06-collision-capture/ directories"
else
    echo "❌ Some scenarios failed: ${FAILED_SFS[*]}"
    echo "❌ Check the simulation output above for error details"
    exit 1
fi