#!/bin/bash
# run-01-enhanced.sh - Scenario 1: Enhanced Baseline with Sub-scenarios
set -euo pipefail

echo "🔬 Scenario 1: Baseline Reference Case"
echo "=============================================="
echo "📊 Multiple configurations for comprehensive baseline testing"
echo ""

cd "$(dirname "$0")/../.."

# Create base output directory
base_output="output/scenario-01-enhanced"
mkdir -p "$base_output"

# Common parameters
DEVICES=100
SIM_TIME=600  # 10 minutes for quick testing, increase for production
PACKET_INTERVAL=600
POSITION_FILE="scenario_positions.csv"

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
        --positionFile=$POSITION_FILE \
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
    run_config "02_sf_only"           "true"  "false" "false" 10 14
    run_config "03_tp_only"           "false" "true"  "false" 10 14
    run_config "04_no_init"           "false" "false" "false" 10 14
    
    # ADR variants
    run_config "05_adr_sf_init"       "true"  "false" "true"  10 14
    run_config "06_adr_tp_init"       "false" "true"  "true"  10 14
    run_config "07_adr_both_init"     "true"  "true"  "true"  10 14
    run_config "08_adr_no_init"       "false" "false" "true"  10 14
    
    echo ""
    echo "🎉 All scenarios completed!"
    echo "📈 Results available in: $base_output/"
}

# Function to run quick test scenarios
run_quick_test() {
    echo "⚡ Running quick test scenarios (most common configurations)..."
    
    run_config "fixed_baseline"       "true"  "true"  "false" 10 14
    run_config "adaptive_baseline"    "true"  "true"  "true"  10 14
    
    echo ""
    echo "✅ Quick test completed!"
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
    "all")
        run_all_scenarios
        ;;
    "quick")
        run_quick_test
        ;;
    "fixed")
        echo "📌 Running fixed parameters baseline..."
        run_config "fixed_baseline" "true" "true" "false" 10 14
        ;;
    "adaptive")
        echo "🔄 Running adaptive baseline..."
        run_config "adaptive_baseline" "true" "true" "true" 10 14
        ;;
    "sf-only")
        echo "📡 Running SF initialization only..."
        run_config "sf_only_baseline" "true" "false" "false" 10 14
        ;;
    "tp-only")
        echo "⚡ Running TP initialization only..."
        run_config "tp_only_baseline" "false" "true" "false" 10 14
        ;;
    "no-init")
        echo "🎲 Running no initialization (default values)..."
        run_config "no_init_baseline" "false" "false" "false" 10 14
        ;;
    "custom")
        echo "🔧 Running custom configuration..."
        echo "Usage: $0 custom [initSF] [initTP] [enableADR] [targetSF] [targetTP]"
        echo "Example: $0 custom true false true 12 10"
        run_custom "${2:-true}" "${3:-true}" "${4:-false}" "${5:-10}" "${6:-14}"
        ;;
    "help"|"-h"|"--help")
        echo ""
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  all        Run all 8 sub-scenarios (default)"
        echo "  quick      Run only fixed and adaptive baselines"
        echo "  fixed      Run fixed parameters baseline (SF10, 14dBm, no ADR)"
        echo "  adaptive   Run adaptive baseline (SF10 init, 14dBm init, ADR enabled)"
        echo "  sf-only    Initialize SF only, default TP, no ADR"
        echo "  tp-only    Initialize TP only, default SF, no ADR"
        echo "  no-init    No parameter initialization, no ADR"
        echo "  custom     Custom configuration - see usage above"
        echo "  help       Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Run all scenarios"
        echo "  $0 quick                             # Quick comparison"
        echo "  $0 fixed                             # Traditional fixed baseline"
        echo "  $0 custom true false true 12 10     # SF12 init, no TP init, ADR on"
        echo ""
        ;;
    *)
        echo "❌ Unknown option: $1"
        echo "Use '$0 help' for available options"
        exit 1
        ;;
esac

echo ""
echo "📊 Summary of configurations tested:"
echo "   • initSF: Controls whether to set initial spreading factor"
echo "   • initTP: Controls whether to set initial transmit power"  
echo "   • enableADR: Controls whether ADR algorithm is active"
echo ""
echo "💡 Use these results to understand how different initialization"
echo "   strategies affect network performance in your baseline scenario."