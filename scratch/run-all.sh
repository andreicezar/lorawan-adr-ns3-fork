#!/bin/bash
# Master Runner: runs all ns-3 scenarios using a positions CSV (absolute), stops on first failure.
# NEW: --all option to run all scenarios for all available position files

set -e
set -o pipefail

# Store original directory and script location
ORIGINAL_DIR="$(pwd)"
SCRIPT_DIR="$(dirname "$0")"
NS3_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"  # Go up from scratch/ to ns-3-dev/

cd "$SCRIPT_DIR"  # Go to scratch directory for scenario scripts

echo "🚀 NS-3 scenarios (CSV-driven outputs)"
echo "====================================="

# -------------------- CLI --------------------
CSV_ARG=""
ALL_MODE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --positions) CSV_ARG="$2"; shift 2;;
    --all)       ALL_MODE=true; shift;;
    --help|-h)   
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --positions <csv>    Run all scenarios with specific CSV file"
        echo "  --all               Run all scenarios for all available position files"
        echo "  --help              Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 --positions scenario_positions_3x3km.csv"
        echo "  $0 --all"
        exit 0;;
    *)           CSV_ARG="${CSV_ARG:-$1}"; shift;;
  esac
done

# -------------------- Functions --------------------
discover_position_files() {
    # Look for position files in NS3_ROOT directory
    files=()
    for f in "$NS3_ROOT"/scenario_positions_*km.csv; do
        if [[ -f "$f" ]]; then
            files+=("$(basename "$f")")  # Store just the filename
        fi
    done
    if [[ ${#files[@]} -gt 0 ]]; then
        printf '%s\n' "${files[@]}" | sort -V  # version sort for proper 1x1km, 2x2km, etc.
    fi
}

resolve_absolute_path() {
    csv_file="$1"
    
    # If relative path, look in NS3_ROOT
    case "$csv_file" in
        /*)  # Absolute path
            echo "$csv_file" ;;
        *)   # Relative path - look in NS3_ROOT
            echo "$NS3_ROOT/$csv_file" ;;
    esac
}

run_scenarios_for_csv() {
    csv_file="$1"
    
    abs_csv="$(resolve_absolute_path "$csv_file")"
    
    if [[ ! -f "$abs_csv" ]]; then
        echo "❌ CSV not found: $abs_csv"
        return 1
    fi

    # Extract area tag from filename for display
    csv_base="$(basename "$csv_file")"
    area_tag="unknown"
    if [[ "$csv_base" =~ ^scenario_positions_(.+)\.csv$ ]]; then
        area_tag="${BASH_REMATCH[1]}"
    fi

    echo ""
    echo "🎯 Running all scenarios for: $csv_file (area: $area_tag)"
    echo "📍 Using positions CSV: $abs_csv"
    echo "=================================================="

    # Export for child scripts
    export POSITION_FILE="$abs_csv"

    # Run all scenarios
    failed_scenarios=()
    
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
        script="${item##*|}"
        
        echo ""
        echo "▶ $name"
        echo "   script  : $script"
        echo "   area    : $area_tag"
        echo "   csv     : $POSITION_FILE"

        if [[ ! -f "$script" ]]; then
            echo "ℹ️ Skipping missing: $script"
            continue
        fi
        [[ -x "$script" ]] || chmod +x "$script"

        if bash "$script"; then
            echo "✅ Done: $name"
        else
            echo "❌ Failed: $name"
            failed_scenarios+=("$name")
            # Stop on first failure
            echo ""
            echo "🛑 STOPPING due to failure in: $name"
            echo "📊 Area $area_tag results:"
            echo "   ✅ Completed: $((${#scenario_list[@]} - ${#failed_scenarios[@]} - 1)) scenarios"
            echo "   ❌ Failed: ${failed_scenarios[*]}"
            return 1
        fi
    done

    echo ""
    echo "🎉 SUCCESS: All scenarios completed for area: $area_tag"
    echo "📂 Outputs are under: <ns-3-dev>/output/*_$area_tag/..."
    return 0
}

# -------------------- Main Logic --------------------

if [[ "$ALL_MODE" == true ]]; then
    # Run all scenarios for all available position files
    
    if [[ -n "$CSV_ARG" ]]; then
        echo "❌ Error: Cannot use both --all and --positions"
        exit 1
    fi
    
    echo "🔍 Discovering available position files in: $NS3_ROOT"
    readarray -t position_files < <(discover_position_files)
    
    if [[ ${#position_files[@]} -eq 0 ]]; then
        echo "❌ No scenario_positions_*km.csv files found in: $NS3_ROOT"
        echo "💡 Expected files like: scenario_positions_1x1km.csv, scenario_positions_2x2km.csv, etc."
        echo "📂 Looking in: $NS3_ROOT"
        exit 1
    fi
    
    echo "📋 Found ${#position_files[@]} position files:"
    for f in "${position_files[@]}"; do
        echo "   - $f"
    done
    
    # Estimate total runtime
    total_runs=$((${#position_files[@]} * 8))  # 8 scenarios per position file
    echo ""
    echo "⏱️  Estimated total simulation runs: $total_runs"
    echo "🕐 This may take several hours to complete..."
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
    
    # Run scenarios for each position file
    failed_areas=()
    completed_areas=()
    
    for csv_file in "${position_files[@]}"; do
        if run_scenarios_for_csv "$csv_file"; then
            area_tag="unknown"
            if [[ "$(basename "$csv_file")" =~ ^scenario_positions_(.+)\.csv$ ]]; then
                area_tag="${BASH_REMATCH[1]}"
            fi
            completed_areas+=("$area_tag")
        else
            area_tag="unknown"
            if [[ "$(basename "$csv_file")" =~ ^scenario_positions_(.+)\.csv$ ]]; then
                area_tag="${BASH_REMATCH[1]}"
            fi
            failed_areas+=("$area_tag")
        fi
    done
    
    # Final summary
    echo ""
    echo "========================================"
    echo "🏁 ALL AREAS PROCESSING COMPLETE"
    echo "========================================"
    echo "✅ Successful areas: ${completed_areas[*]}"
    if [[ ${#failed_areas[@]} -gt 0 ]]; then
        echo "❌ Failed areas: ${failed_areas[*]}"
        exit 1
    else
        echo "🎉 All areas completed successfully!"
    fi
    
else
    # Original single CSV mode
    
    if [[ -z "$CSV_ARG" ]]; then
        echo "Usage: $0 --positions <path/to/scenario_positions_<TAG>.csv>"
        echo "   or: $0 <path/to/scenario_positions_<TAG>.csv>"
        echo "   or: $0 --all"
        echo ""
        echo "Available position files in $NS3_ROOT:"
        discover_position_files | sed 's/^/   - /'
        exit 2
    fi

    run_scenarios_for_csv "$CSV_ARG"
fi

echo "ℹ️ Outputs are under: <ns-3-dev>/output/<scenario>_<TAG>/..."
