#!/bin/bash
# run-01.sh - Scenario 1: Baseline Reference Case
set -euo pipefail

echo "🔬 Scenario 1: Baseline Reference Case"
echo "======================================"
echo "📊 Config: 100 devices, 1 gateway, SF10 fixed, 600min"
echo "📍 Using positions from: all_positions.csv"

cd "$(dirname "$0")/../.."

# Create output directory
output_folder="output/scenario-01-baseline/baseline"
mkdir -p "$output_folder"

echo ""
echo "🚀 Running simulation: Baseline Reference"
echo "📁 Output directory: $output_folder"

# Run simulation
if ./ns3 run "scratch/scenario-01-baseline/scenario-01-baseline \
    --simulationTime=600 \
    --positionFile=scenario_positions.csv \
    --useFilePositions=true \
    --outputPrefix=$output_folder/result"; then
    echo "✅ Scenario 1 completed successfully!"
    echo "📈 Results available in $output_folder/"
else
    echo "❌ Scenario 1 FAILED!"
    echo "❌ Check the simulation output above for error details"
    exit 1
fi
