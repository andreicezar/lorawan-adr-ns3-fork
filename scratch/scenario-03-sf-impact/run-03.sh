#!/bin/bash
# run-03.sh - Scenario 3: Spreading Factor Impact
set -euo pipefail

echo "🔬 Scenario 3: Spreading Factor Impact"
echo "======================================"
echo "📊 Config: 50 devices, 1 gateway, SF7 to SF12, 15min"

cd "$(dirname "$0")/../.."

FAILED_SFS=()

for SF in {7..12}; do
    output_folder="output/scenario-03-sf-impact/sf-$SF"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: SF$SF"
    echo "📁 Output directory: $output_folder"
    
    if ./ns3 run "scratch/scenario-03-sf-impact/scenario-03-sf-impact \
        --simulationTime=200 \
        --spreadingFactor=$SF \
        --outputPrefix=$output_folder/result \
        --nDevices=50 \
        --packetInterval=300"; then
        echo "✅ SF$SF completed successfully"
    else
        echo "❌ SF$SF FAILED!"
        FAILED_SFS+=("SF$SF")
    fi
done

# Final summary
echo ""
if [ ${#FAILED_SFS[@]} -eq 0 ]; then
    echo "✅ All SF scenarios completed successfully!"
    echo "📈 Results available in output/scenario-03-sf-impact/ directories"
else
    echo "❌ Some scenarios failed: ${FAILED_SFS[*]}"
    echo "❌ Check the simulation output above for error details"
    exit 1
fi