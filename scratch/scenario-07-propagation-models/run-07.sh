#!/bin/bash
# run-07.sh - Scenario 7: Propagation Model Testing
set -euo pipefail

echo "🔬 Scenario 7: Propagation Model Testing"
echo "======================================="
echo "📊 Config: 50 devices, 1 gateway, 120min, radial placement"

cd "$(dirname "$0")/../.."

# --- derive CSV tag from POSITION_FILE exported by run-all.sh ---
POS="${POSITION_FILE:-scenario_positions.csv}"
csv_base="$(basename "$POS")"
if [[ "$csv_base" =~ ^scenario_positions_(.+)\.csv$ ]]; then
  POS_TAG="${BASH_REMATCH[1]}"   # e.g. "1x1km", "3x3km"
else
  POS_TAG="$(echo "$csv_base" | sed -E 's/[^A-Za-z0-9]+/_/g; s/^_+|_+$//g')"
fi

# Function to run a single configuration
run_config() {
    local name="$1"
    local init_sf="$2"
    local init_tp="$3"
    local enable_adr="$4"
    local target_sf="${5:-10}"
    local target_tp="${6:-14}"
    
    # Map scenario name to propagation model and parameters
    local propagation_model="LogDistance"
    local path_loss_exponent="3.76"
    local extra_args=""
    
    case "$name" in
        "logdist-32")
            propagation_model="LogDistance"
            path_loss_exponent="3.2"
            ;;
        "logdist-35")
            propagation_model="LogDistance"
            path_loss_exponent="3.5"
            ;;
        "logdist-376")
            propagation_model="LogDistance"
            path_loss_exponent="3.76"
            ;;
        "logdist-40")
            propagation_model="LogDistance"
            path_loss_exponent="4.0"
            ;;
        "freespace")
            propagation_model="FreeSpace"
            path_loss_exponent=""  # Not used for FreeSpace
            ;;
    esac
    
    # Output folder now follows CSV tag
    local output_folder="output/scenario-07-propagation-models_${POS_TAG}/$name"
    mkdir -p "$output_folder"
    
    echo ""
    echo "🚀 Running: $propagation_model"
    if [ -n "$path_loss_exponent" ]; then
        echo "   Path loss exponent: $path_loss_exponent"
    fi
    echo "📁 Output directory: $output_folder"
    echo "🗺️  Positions CSV: $POS"
    echo "⚙️ Config: SF${target_sf}, ${target_tp}dBm, ${propagation_model} model"
    
    # Build command with conditional path loss exponent
    local cmd="./ns3 run \"scratch/scenario-07-propagation-models/scenario-07-propagation-models \
        --simulationTime=120 \
        --positionFile=${POS} \
        --useFilePositions=true \
        --maxDistance=5000 \
        --propagationModel=$propagation_model \
        --outputPrefix=$output_folder/result"
    
    if [ -n "$path_loss_exponent" ]; then
        cmd="$cmd --pathLossExponent=$path_loss_exponent"
    fi
    
    cmd="$cmd\""
    
    if eval $cmd; then
        echo "✅ $propagation_model"
        if [ -n "$path_loss_exponent" ]; then
            echo "   (n=$path_loss_exponent) completed successfully"
        else
            echo "   completed successfully"
        fi
        return 0
    else
        echo "❌ $propagation_model"
        if [ -n "$path_loss_exponent" ]; then
            echo "   (n=$path_loss_exponent) FAILED!"
        else
            echo "   FAILED!"
        fi
        return 1
    fi
}

# Main function that runs all scenarios
run_all_scenarios() {
    local FAILED_CASES=()

    # Scenario 7: Propagation Model Comparison
    # Format: run_config "name" "initSF" "initTP" "enableADR" [targetSF] [targetTP]
    
    # Test LogDistance model with different path loss exponents
    run_config "logdist-32" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("logdist-32")
    
    run_config "logdist-35" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("logdist-35")
    
    run_config "logdist-376" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("logdist-376")
    
    run_config "logdist-40" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("logdist-40")
    
    # Test FreeSpace (Friis) model
    run_config "freespace" "true" "true" "false" 10 14
    [ $? -eq 0 ] || FAILED_CASES+=("freespace")
    
    # Final summary
    echo ""
    if [ ${#FAILED_CASES[@]} -eq 0 ]; then
        echo "✅ All propagation model scenarios completed successfully!"
        echo "📈 Results available under: output/scenario-07-propagation-models_${POS_TAG}/"
        echo ""
        echo "📊 Propagation models tested:"
        echo "   - LogDistance (n=3.2, 3.5, 3.76, 4.0)"
        echo "   - FreeSpace (Friis equation)"
    else
        echo "❌ Some scenarios failed: ${FAILED_CASES[*]}"
        echo "❌ Check the simulation output above for error details"
        exit 1
    fi
}

# Execute if run directly (preserve original functionality)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_all_scenarios
fi
