#!/bin/bash
# ==============================================================================
# run-08.sh - Scenario 8: Multi-Gateway Coordination
# Runs the ns-3 simulation with different gateway counts and saves results.
# Follows the same structure and final summary pattern as run-06.sh.
# ==============================================================================

set -euo pipefail

echo "🔬 Scenario 8: Multi-Gateway Coordination"
echo "========================================="
echo "📊 Config base: 200 devices, DR2(SF10), interval 300s, sim 20 min"

# Move to repo root (same style as run-06.sh)
cd "$(dirname "$0")/../.."

# Optional build step (keep same check/flow as your other scripts)
if [ -d "cmake-cache" ]; then
  /usr/bin/cmake --build "$(pwd)/cmake-cache" -j"$(nproc)"
else
  echo "ℹ️  Skipping build: cmake-cache not found (make sure you've configured CMake)."
fi

# ------------------------------------------------------------------------------
# Scenario variables (tweak as needed)
# ------------------------------------------------------------------------------
SCENARIO_PATH="scratch/scenario-08-multi-gateway/scenario-08-multi-gateway"
OUTPUT_BASE="output/scenario-08-multi-gateway"

SIMULATION_TIME=200        # minutes
N_DEVICES=200
INTERVAL=300              # seconds (fixed in scenario; here just informative)
GATEWAY_SPACING=2000      # meters between gateways (for 2/4 GW layouts)

GATEWAY_COUNTS=(1 2 4)

# ------------------------------------------------------------------------------
# Run matrix
# ------------------------------------------------------------------------------
mkdir -p "${OUTPUT_BASE}"
FAILED_RUNS=()

for NGW in "${GATEWAY_COUNTS[@]}"; do
  CASE_DIR="${OUTPUT_BASE}/${NGW}gw"
  mkdir -p "${CASE_DIR}"

  echo ""
  echo "🚀 Running: ${NGW} gateway(s)"
  echo "📁 Output directory: ${CASE_DIR}"

  if ./ns3 run "${SCENARIO_PATH} \
      --nGateways=${NGW} \
      --simulationTime=${SIMULATION_TIME} \
      --nDevices=${N_DEVICES} \
      --gatewaySpacing=${GATEWAY_SPACING} \
      --outputPrefix=${CASE_DIR}/result"; then
    echo "✅ ${NGW} GW run completed successfully"
  else
    echo "❌ ${NGW} GW run FAILED!"
    FAILED_RUNS+=("${NGW}gw")
  fi
done

# ------------------------------------------------------------------------------
# Final summary (same pattern/feel as run-06.sh)
# ------------------------------------------------------------------------------
echo ""
if [ ${#FAILED_RUNS[@]} -eq 0 ]; then
  echo "✅ All Scenario 8 runs completed successfully!"
  echo "📈 Results available under: ${OUTPUT_BASE}/"
else
  echo "❌ Some Scenario 8 runs failed: ${FAILED_RUNS[*]}"
  echo "🔎 Check the logs above for details."
  exit 1
fi
