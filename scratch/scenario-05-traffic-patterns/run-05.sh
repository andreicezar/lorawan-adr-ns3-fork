#!/bin/bash
# run-05.sh - Scenario 5: Traffic Pattern Variation
set -euo pipefail

echo "🔬 Scenario 5: Traffic Pattern Variation"
echo "======================================="
echo "📊 Config: 100 devices, 1 gateway, 30min, varying intervals"

cd "$(dirname "$0")/../.."

FAILED_INTERVALS=()

for INTERVAL in 600 300 60; do
    output_folder="output/scenario-05-traffic-patterns/interval-${INTERVAL}s"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running simulation: ${INTERVAL}s packet interval"
    echo "📁 Output directory: $output_folder"
    
    if ./ns3 run "scratch/scenario-05-traffic-patterns/scenario-05-traffic-patterns \
        --simulationTime=$((40 * INTERVAL / 60)) \
        --packetInterval=$INTERVAL \
        --outputPrefix=$output_folder/result"; then
        echo "✅ ${INTERVAL}s interval completed successfully"
    else
        echo "❌ ${INTERVAL}s interval FAILED!"
        FAILED_INTERVALS+=("${INTERVAL}s")
    fi
done

# Final summary
echo ""
if [ ${#FAILED_INTERVALS[@]} -eq 0 ]; then
    echo "✅ All traffic pattern scenarios completed successfully!"
    echo "📈 Results available in output/scenario-05-traffic-patterns/ directories"
else
    echo "❌ Some intervals failed: ${FAILED_INTERVALS[*]}"
    echo "❌ Check the simulation output above for error details"
    exit 1
fi