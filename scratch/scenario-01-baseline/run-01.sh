#!/bin/bash
# run-01-enhanced.sh - Scenario 1: Enhanced Baseline with Sub-scenarios
set -euo pipefail

echo "🔬 Scenario 1: Baseline Reference Case"
echo "=============================================="
echo "📊 Multiple configurations for comprehensive baseline testing"
echo ""

cd "$(dirname "$0")/../.."

# Positions CSV: from env POSITION_FILE or default
POS="${POSITION_FILE:-scenario_positions.csv}"
csv_base="$(basename "$POS")"
if [[ "$csv_base" =~ ^scenario_positions_(.+)\.csv$ ]]; then
  POS_TAG="${BASH_REMATCH[1]}"        # e.g. "1x1km"
else
  POS_TAG="$(echo "$csv_base" | sed -E 's/[^A-Za-z0-9]+/_/g; s/^_+|_+$//g')"
fi

# Base output now follows the CSV tag exactly
base_output="output/scenario-01-enhanced_${POS_TAG}"
mkdir -p "$base_output"

# Common parameters
DEVICES=100
SIM_TIME=600  # 10 minutes for quick testing, increase for production
PACKET_INTERVAL=600

# Function to run a single configuration
run_config() {
    local config_name="$1"
    local init_sf="$2"
    local init_tp="$3"
    local enable_adr="$4"
    local target_sf="${5:-10}"
    local target_tp="${6:-14}"
    
    echo ""
    echo "🚀 Running: $config_name"
    echo "   SF Init: $init_sf | TP Init: $init_tp | ADR: $enable_adr"
    
    # Create specific output directory
    output_folder="$base_output/$config_name"
    mkdir -p "$output_folder"
    
    echo "📁 Output: $output_folder"
    
    # Run simulation
    if ./ns3 run "scratch/scenario-01-baseline/scenario-01-baseline \
        --nDevices=$DEVICES \
        --simulationTime=$SIM_TIME \
        --packetInterval=$PACKET_INTERVAL \
        --positionFile=$POS \
        --useFilePositions=true \
        --initSF=$init_sf \
        --initTP=$init_tp \
        --enableADR=$enable_adr \
        --targetSF=$target_sf \
        --targetTP=$target_tp \
        --outputPrefix=$output_folder/result"; then
        echo "✅ $config_name completed successfully!"
    else
        echo "❌ $config_name FAILED!"
        return 1
    fi
}

# Function to run all sub-scenarios
run_all_scenarios() {
    echo "🎯 Running all baseline sub-scenarios..."
    
    # Core configurations
    run_config "01_fixed_baseline"     "true"  "true"  "false" 10 14
    run_config "02_sf_only"            "true"  "false" "false" 10 14
    run_config "03_tp_only"            "false" "true"  "false" 10 14
    run_config "04_no_init"            "false" "false" "false" 10 14
    
    # ADR variants
    run_config "05_adr_sf_init"        "true"  "false" "true"  10 14
    run_config "06_adr_tp_init"        "false" "true"  "true"  10 14
    run_config "07_adr_both_init"      "true"  "true"  "true"  10 14
    run_config "08_adr_no_init"        "false" "false" "true"  10 14
    
    echo ""
    echo "🎉 All scenarios completed!"
    echo "📈 Results available in: $base_output/"
}

# Function to run quick test scenarios
run_quick_test() {
    echo "⚡ Running quick test scenarios (most common configurations)..."
    run_config "fixed_baseline"       "true"  "true"  "false" 10 14
    run_config "adaptive_baseline"    "true"  "true"  "true"  10 14
    echo ""; echo "✅ Quick test completed!"
}

# Function to run custom configuration
run_custom() {
    local init_sf="${1:-true}"
    local init_tp="${2:-true}"
    local enable_adr="${3:-false}"
    local target_sf="${4:-10}"
    local target_tp="${5:-14}"
    local config_name="custom_sf${init_sf}_tp${init_tp}_adr${enable_adr}"
    echo "🔧 Running custom configuration..."
    run_config "$config_name" "$init_sf" "$init_tp" "$enable_adr" "$target_sf" "$target_tp"
}

# Main script logic
case "${1:-all}" in
    all)        run_all_scenarios ;;
    quick)      run_quick_test ;;
    fixed)      echo "📌 Running fixed parameters baseline..."; run_config "fixed_baseline" "true" "true" "false" 10 14 ;;
    adaptive)   echo "🔄 Running adaptive baseline...";        run_config "adaptive_baseline" "true" "true" "true" 10 14 ;;
    sf-only)    echo "📡 Running SF initialization only...";   run_config "sf_only_baseline" "true" "false" "false" 10 14 ;;
    tp-only)    echo "⚡ Running TP initialization only...";   run_config "tp_only_baseline" "false" "true" "false" 10 14 ;;
    no-init)    echo "🎲 Running no initialization...";        run_config "no_init_baseline" "false" "false" "false" 10 14 ;;
    custom)     echo "🔧 Running custom configuration...";     run_custom "${2:-true}" "${3:-true}" "${4:-false}" "${5:-10}" "${6:-14}" ;;
    help|-h|--help)
        echo ""; echo "Usage: $0 [all|quick|fixed|adaptive|sf-only|tp-only|no-init|custom]"; exit 0;;
    *)  echo "❌ Unknown option: $1"; exit 1;;
esac
