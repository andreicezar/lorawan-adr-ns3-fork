#!/bin/bash
#------------------------------------------------------------------------------
# run-02.sh - Scenario 2: ADR Comparison
set -euo pipefail

echo "🔬 Scenario 2: ADR Comparison"
echo "=============================="
echo "📊 Config: 100 devices, 1 gateway, 20min, 30s intervals"

cd "$(dirname "$0")/../.."

FAILED_CASES=()

# Case 1: ADR DISABLED (fixed SF12)
output_folder_fixed="output/scenario-02-adr-comparison/fixed"
mkdir -p "$output_folder_fixed"

echo ""
echo "🚀 Running simulation: ADR DISABLED (Fixed SF12)"
echo "📁 Output directory: $output_folder_fixed"

if ./ns3 run "scratch/scenario-02-adr-comparison/scenario-02-adr-comparison \
    --simulationTime=20 \
    --outputPrefix=$output_folder_fixed/result \
    --adrEnabled=false"; then
    echo "✅ Fixed SF12 case completed successfully"
else
    echo "❌ Fixed SF12 case FAILED!"
    FAILED_CASES+=("Fixed SF12")
fi

# Case 2: ADR ENABLED (dynamic SF/TP)
output_folder_adr="output/scenario-02-adr-comparison/adr"
mkdir -p "$output_folder_adr"

echo ""
echo "🚀 Running simulation: ADR ENABLED"
echo "📁 Output directory: $output_folder_adr"

if ./ns3 run "scratch/scenario-02-adr-comparison/scenario-02-adr-comparison \
    --simulationTime=20 \
    --outputPrefix=$output_folder_adr/result \
    --adrEnabled=true \
    --adrType=ns3::AdrComponent"; then
    echo "✅ ADR enabled case completed successfully"
else
    echo "❌ ADR enabled case FAILED!"
    FAILED_CASES+=("ADR enabled")
fi

# Final summary
echo ""
if [ ${#FAILED_CASES[@]} -eq 0 ]; then
    echo "✅ All ADR scenarios completed successfully!"
    echo "📈 Results available in:"
    echo "   - $output_folder_fixed/ (NO ADR, Fixed SF12)"
    echo "   - $output_folder_adr/ (ADR ENABLED, Adaptive)"
else
    echo "❌ Some scenarios failed: ${FAILED_CASES[*]}"
    echo "❌ Check the simulation output above for error details"
    exit 1
fi