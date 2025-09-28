#!/bin/bash
# run-08.sh - Scenario 8: Multi-Gateway Coordination
set -euo pipefail

echo "🔬 Scenario 8: Multi-Gateway Coordination"
echo "========================================="
echo "📊 Baseline: 200 devices, DR2(SF10), interval 300s, sim 200min"

cd "$(dirname "$0")/../.."

SCENARIO_PATH="scratch/scenario-08-multi-gateway/scenario-08-multi-gateway"

# --- derive CSV tag from POSITION_FILE exported by run-all.sh ---
POS="${POSITION_FILE:-scenario_positions.csv}"
csv_base="$(basename "$POS")"
if [[ "$csv_base" =~ ^scenario_positions_(.+)\.csv$ ]]; then
  POS_TAG="${BASH_REMATCH[1]}"   # e.g. "1x1km", "3x3km", ...
else
  POS_TAG="$(echo "$csv_base" | sed -E 's/[^A-Za-z0-9]+/_/g; s/^_+|_+$//g')"
fi

# outputs now keyed by CSV tag
OUTPUT_BASE="output/scenario-08-multi-gateway_${POS_TAG}"

SIM_MIN=200
NDEV=200
GW_SPACING=2000

# run_config <name> <init_sf:true|false> <init_tp:true|false> <enable_adr:true|false> [targetSF targetTP]
run_config() {
  local name="$1"
  local init_sf="$2"
  local init_tp="$3"
  local enable_adr="$4"
  local target_sf="${5:-10}"
  local target_tp="${6:-14}"

  local NGW=1
  if [[ "$name" =~ ^([0-9]+)gw$ ]]; then
    NGW="${BASH_REMATCH[1]}"
  fi

  local out_dir="${OUTPUT_BASE}/${name}"
  mkdir -p "$out_dir"

  echo ""
  echo "🚀 Running: ${name}"
  echo "   nGW=${NGW}, initSF=${init_sf}(${target_sf}), initTP=${init_tp}(${target_tp} dBm), ADR=${enable_adr}"
  echo "📁 Output: ${out_dir}"
  echo "🗺️  Positions CSV: ${POS}"

  local cmd="./ns3 run \"${SCENARIO_PATH} \
    --nGateways=${NGW} \
    --nDevices=${NDEV} \
    --gatewaySpacing=${GW_SPACING} \
    --simulationTime=${SIM_MIN} \
    --useFilePositions=true \
    --positionFile=${POS} \
    --outputPrefix=${out_dir}/result"

  # Pass the new flags only when requested
  if [[ "$init_sf" == "true" ]]; then
    cmd="${cmd} --initSf=${target_sf}"
  fi
  if [[ "$init_tp" == "true" ]]; then
    cmd="${cmd} --initTp=${target_tp}"
  fi
  if [[ "$enable_adr" == "true" ]]; then
    cmd="${cmd} --enableADR=true"
  fi

  cmd="${cmd}\""

  if eval $cmd; then
    echo "✅ ${name} completed successfully"
    return 0
  else
    echo "❌ ${name} FAILED"
    return 1
  fi
}

run_all_scenarios() {
  local FAILED_CASES=()

  run_config "1gw" "true" "true" "false" 10 14     || FAILED_CASES+=("1gw")
  run_config "2gw" "true" "true" "false" 10 14     || FAILED_CASES+=("2gw")
  run_config "4gw" "true" "true" "false" 10 14     || FAILED_CASES+=("4gw")

  echo ""
  if [ ${#FAILED_CASES[@]} -eq 0 ]; then
    echo "✅ All Scenario 8 runs completed successfully!"
    echo "📈 Results available under: ${OUTPUT_BASE}/"
  else
    echo "❌ Some Scenario 8 runs failed: ${FAILED_CASES[*]}"
    echo "🔎 Check the logs above for details."
    exit 1
  fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  run_all_scenarios
fi
