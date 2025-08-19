#!/bin/bash
# run-04.sh - Scenario 4: Confirmed vs Unconfirmed Messages
set -euo pipefail

echo "🔬 Scenario 4: Confirmed vs Unconfirmed Messages"
echo "==============================================="
echo "📊 Config: 100 devices, 1 gateway, 20min, 120s intervals"

cd "$(dirname "$0")/../.."

FAILED_CASES=()

# Case 1: UNCONFIRMED MESSAGES
output_folder_unconf="output/scenario-04-confirmed-messages/unconfirmed"
mkdir -p "$output_folder_unconf"

echo ""
echo "🚀 Running simulation: UNCONFIRMED messages"
echo "📁 Output directory: $output_folder_unconf"

if ./ns3 run "scratch/scenario-04-confirmed-messages/scenario-04-confirmed-messages \
    --simulationTime=80 \    
    --positionFile=scenario_positions.csv \
    --useFilePositions=true \
    --confirmedMessages=false \
    --outputPrefix=$output_folder_unconf/result"; then
    echo "✅ Unconfirmed case completed successfully"
else
    echo "❌ Unconfirmed case FAILED!"
    FAILED_CASES+=("Unconfirmed")
fi

# Case 2: CONFIRMED MESSAGES
output_folder_conf="output/scenario-04-confirmed-messages/confirmed"
mkdir -p "$output_folder_conf"

echo ""
echo "🚀 Running simulation: CONFIRMED messages"
echo "📁 Output directory: $output_folder_conf"

if ./ns3 run "scratch/scenario-04-confirmed-messages/scenario-04-confirmed-messages \
    --simulationTime=80 \    
    --positionFile=scenario_positions.csv \
    --useFilePositions=true \
    --confirmedMessages=true \
    --outputPrefix=$output_folder_conf/result"; then
    echo "✅ Confirmed case completed successfully"
else
    echo "❌ Confirmed case FAILED!"
    FAILED_CASES+=("Confirmed")
fi

# Final summary
echo ""
if [ ${#FAILED_CASES[@]} -eq 0 ]; then
    echo "✅ All confirmed vs unconfirmed scenarios completed successfully!"
    echo "📈 Results available in:"
    echo "   - $output_folder_unconf/ (UNCONFIRMED messages)"
    echo "   - $output_folder_conf/ (CONFIRMED messages)"
else
    echo "❌ Some scenarios failed: ${FAILED_CASES[*]}"
    echo "❌ Check the simulation output above for error details"
    exit 1
fi