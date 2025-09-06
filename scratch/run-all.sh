#!/bin/bash
# Master Runner: runs all ns-3 scenarios using a positions CSV (absolute), stops on first failure.

set -e
set -o pipefail

cd "$(dirname "$0")"  # directory where run-01.sh ... run-08.sh live
echo "🚀 NS-3 scenarios (CSV-driven outputs)"
echo "====================================="

# -------------------- CLI --------------------
CSV_ARG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --positions) CSV_ARG="$2"; shift 2;;
    *)           CSV_ARG="${CSV_ARG:-$1}"; shift;;
  esac
done

if [[ -z "$CSV_ARG" ]]; then
  echo "Usage: $0 --positions <path/to/scenario_positions_<TAG>.csv>"
  echo "   or: $0 <path/to/scenario_positions_<TAG>.csv>"
  exit 2
fi

# Resolve to absolute path (works in Linux/WSL; on macOS use greadlink/realpath)
if command -v realpath >/dev/null 2>&1; then
  ABS_CSV="$(realpath -m "$CSV_ARG")"
elif command -v readlink >/dev/null 2>&1; then
  ABS_CSV="$(readlink -f "$CSV_ARG")"
else
  # Fallback: prepend current dir if path is relative
  case "$CSV_ARG" in
    /*) ABS_CSV="$CSV_ARG" ;;
    *)  ABS_CSV="$(pwd)/$CSV_ARG" ;;
  esac
fi

if [[ ! -f "$ABS_CSV" ]]; then
  echo "❌ CSV not found: $ABS_CSV"
  exit 1
fi

# -------------------- Export for child scripts --------------------
export POSITION_FILE="$ABS_CSV"
echo "📍 Using positions CSV: $POSITION_FILE"
echo ""

# -------------------- helpers --------------------
run_scenario() {
    local name="$1"
    local script="$2"

    echo "▶ $name"
    echo "   script  : $script"
    echo "   csv     : $POSITION_FILE"

    if [[ ! -f "$script" ]]; then
        echo "ℹ️ Skipping missing: $script"
        return
    fi
    [[ -x "$script" ]] || chmod +x "$script"

    bash "$script"
    echo "✅ Done: $name"
    echo ""
}

# -------------------- run --------------------
declare -a scenario_list=(
  "Scenario 1: Baseline|scenario-01-baseline/run-01.sh"
  "Scenario 2: ADR Comparison|scenario-02-adr-comparison/run-02.sh"
  "Scenario 3: SF Impact|scenario-03-sf-impact/run-03.sh"
  "Scenario 4: Confirmed Messages|scenario-04-confirmed-messages/run-04.sh"
  "Scenario 5: Traffic Patterns|scenario-05-traffic-patterns/run-05.sh"
  "Scenario 6: Collision Capture|scenario-06-collision-capture/run-06.sh"
  "Scenario 7: Propagation Models|scenario-07-propagation-models/run-07.sh"
  "Scenario 8: Multi-Gateway|scenario-08-multi-gateway/run-08.sh"
)

for item in "${scenario_list[@]}"; do
  name="${item%%|*}"
  path="${item##*|}"
  run_scenario "$name" "$path"
done

echo "🎉 SUCCESS: All requested scenarios completed."
echo "ℹ️ Outputs are under: <ns-3-dev>/output/<scenario>_<TAG>/..."
