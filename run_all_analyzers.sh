#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------------------------------------------
# Run all ns-3 analyzers (01..08) for all areas (1x1km..5x5km).
# Place this next to analyze_ns3_scenario_*.py and run:
#   ./run_all_analyzers.sh
#
# Options:
#   AREAS env var to override areas, e.g.:
#     AREAS="1x1km 3x3km 5x5km" ./run_all_analyzers.sh
#   PYTHON env var to override interpreter (default: python3)
#     PYTHON=/usr/bin/python3.11 ./run_all_analyzers.sh
# -----------------------------------------------------------------------------

PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Default areas if not provided
if [[ -z "${AREAS:-}" ]]; then
  AREAS="1x1km 2x2km 3x3km 4x4km 5x5km"
fi

# Ordered list of analyzers to run (edit if you add more)
ANALYZERS=(
  "analyze_ns3_scenario_01.py"
  "analyze_ns3_scenario_02.py"
  "analyze_ns3_scenario_03.py"
  "analyze_ns3_scenario_05.py"
  "analyze_ns3_scenario_06.py"
  "analyze_ns3_scenario_07.py"
  "analyze_ns3_scenario_08.py"
)

# scenario 04 is optional—add it if you have it
if [[ -f "$SCRIPT_DIR/analyze_ns3_scenario_04.py" ]]; then
  ANALYZERS+=( "analyze_ns3_scenario_04.py" )
fi

# Pretty printing
bold() { printf "\033[1m%s\033[0m\n" "$*"; }
info() { printf "  \033[36m%s\033[0m\n" "$*"; }
warn() { printf "  \033[33m%s\033[0m\n" "$*"; }
err () { printf "  \033[31m%s\033[0m\n" "$*" >&2; }

bold "🚀 Running ns-3 analyzers for all areas"
info "Using Python: $PYTHON"
info "Analyzer dir: $SCRIPT_DIR"
info "Areas       : $AREAS"
echo

overall_fail=0
declare -a failed

for area in $AREAS; do
  bold "📍 Area: $area"
  for script in "${ANALYZERS[@]}"; do
    path="$SCRIPT_DIR/$script"
    if [[ ! -f "$path" ]]; then
      warn "Skip: $script (not found)"
      continue
    fi
    info "▶ $script --area $area"
    set +e
    "$PYTHON" "$path" --area "$area"
    code=$?
    set -e
    if [[ $code -ne 0 ]]; then
      warn "✖ $script (area $area) exited with code $code"
      overall_fail=1
      failed+=("$script --area $area [exit=$code]")
    else
      info "✔ $script (area $area) completed"
    fi
    echo
  done
done

if [[ $overall_fail -ne 0 ]]; then
  bold "⚠️  Some analyzers reported errors:"
  for f in "${failed[@]}"; do
    err " - $f"
  done
  exit 1
fi

bold "🎉 All analyzers ran successfully for all areas."
