#!/bin/bash
# run-07.sh - Scenario 7: Propagation Model Testing
set -euo pipefail

echo "🔬 Scenario 7: Propagation Model Testing"
echo "======================================="
echo "📊 Config: 50 devices, 1 gateway, 15min, radial placement"

# same repo-root cd style as run-06.sh
cd "$(dirname "$0")/../.."

FAILED_RUNS=()

# --- LogDistance model with several exponents (mirrors SF sweep idea) ---
for EXP in 3.2 3.5 3.76 4.0; do
    output_folder="output/scenario-07-propagation-models/logdistance-n${EXP}"
    mkdir -p "$output_folder"

    echo ""
    echo "🚀 Running: LogDistance (n=${EXP})"
    echo "📁 Output directory: $output_folder"

    if ./ns3 run "scratch/scenario-07-propagation-models/scenario-07-propagation-models \
        --simulationTime=120 \
        --maxDistance=5000 \
        --propagationModel=LogDistance \
        --pathLossExponent=${EXP} \
        --outputPrefix=$output_folder/result"; then
        echo "✅ LogDistance n=${EXP} completed successfully"
    else
        echo "❌ LogDistance n=${EXP} FAILED!"
        FAILED_RUNS+=("LogDistance n=${EXP}")
    fi
done

# --- FreeSpace (Friis) model ---
output_folder="output/scenario-07-propagation-models/freespace"
mkdir -p "$output_folder"

echo ""
echo "🚀 Running: FreeSpace (Friis)"
echo "📁 Output directory: $output_folder"

if ./ns3 run "scratch/scenario-07-propagation-models/scenario-07-propagation-models \
    --simulationTime=120 \
    --maxDistance=5000 \
    --propagationModel=FreeSpace \
    --outputPrefix=$output_folder/result"; then
    echo "✅ FreeSpace completed successfully"
else
    echo "❌ FreeSpace FAILED!"
    FAILED_RUNS+=("FreeSpace")
fi

# --- Final summary (same pattern as run-06.sh) ---
echo ""
if [ ${#FAILED_RUNS[@]} -eq 0 ]; then
    echo "✅ All propagation model scenarios completed successfully!"
    echo "📈 Results available under: output/scenario-07-propagation-models/"
else
    echo "❌ Some scenarios failed: ${FAILED_RUNS[*]}"
    echo "❌ Check the simulation output above for error details"
    exit 1
fi
