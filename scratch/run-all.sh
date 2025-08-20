#!/bin/bash
# Master Runner: Execută fiecare scenariu folosind scripturile lor dedicate
# Stops immediately if any scenario fails

set -e  # Exit immediately if a command exits with a non-zero status
set -o pipefail  # Exit if any command in a pipeline fails

cd "$(dirname "$0")"  # Ne asigurăm că suntem în directorul scratch/
echo $(pwd)
echo "🚀 Rulare scenarii NS-3 LoRaWAN"
echo "==============================="
echo "❗ IMPORTANT: Execution will stop at the first scenario failure"
echo ""

# Function to run a scenario with error checking
run_scenario() {
    local scenario_name="$1"
    local script_path="$2"
    local scenario_index="$3"
    
    echo "▶ $scenario_name"
    echo "📂 Running: $script_path"
    
    # Check if script exists
    if [ ! -f "$script_path" ]; then
        echo "❌ ERROR: Script not found: $script_path"
        echo "💥 STOPPING: Cannot continue without all scenario scripts"
        exit 1
    fi
    
    # Check if script is executable
    if [ ! -x "$script_path" ]; then
        echo "⚠️  WARNING: Making script executable: $script_path"
        chmod +x "$script_path"
    fi
    
    # Run the scenario script
    if bash "$script_path"; then
        echo "✅ SUCCESS: $scenario_name completed successfully"
        scenario_status[$scenario_index]="✅"
        echo ""
    else
        local exit_code=$?
        scenario_status[$scenario_index]="❌"
        echo ""
        echo "❌ FAILURE: $scenario_name failed with exit code $exit_code"
        echo "💥 STOPPING: Cannot continue due to scenario failure"
        echo "🔍 Check the error messages above for details"
        echo "🛠️  Fix the issue and re-run the script"
        echo ""
        echo "📊 Execution Summary (at failure point):"
        for i in "${!scenario_names[@]}"; do
            local status="${scenario_status[$i]:-"⏸️"}"
            echo "   $status ${scenario_names[$i]}"
        done
        exit $exit_code
    fi
}

# Track progress and scenario status
completed_scenarios=0
total_scenarios=8
declare -a scenario_status=()
declare -a scenario_names=(
    "Baseline scenario"
    "ADR comparison" 
    "SF impact analysis"
    "Confirmed messages"
    "Traffic patterns"
    "Collision capture"
    "Propagation models"
    "Multi-gateway testing"
)

echo "📋 Starting execution of $total_scenarios scenarios..."
echo ""

# Scenario 1
run_scenario "Scenariul 1: Baseline" "scenario-01-baseline/run-01.sh" 0
completed_scenarios=$((completed_scenarios + 1))

# Scenario 2  
run_scenario "Scenariul 2: ADR Comparison" "scenario-02-adr-comparison/run-02.sh" 1
completed_scenarios=$((completed_scenarios + 1))

# Scenario 3
run_scenario "Scenariul 3: SF Impact" "scenario-03-sf-impact/run-03.sh" 2
completed_scenarios=$((completed_scenarios + 1))

# Scenario 4
run_scenario "Scenariul 4: Confirmed messages" "scenario-04-confirmed-messages/run-04.sh" 3
completed_scenarios=$((completed_scenarios + 1))

# Scenario 5
run_scenario "Scenariul 5: Traffic Patterns" "scenario-05-traffic-patterns/run-05.sh" 4
completed_scenarios=$((completed_scenarios + 1))

# Scenario 6
run_scenario "Scenariul 6: Collision Capture" "scenario-06-collision-capture/run-06.sh" 5
completed_scenarios=$((completed_scenarios + 1))

# Scenario 7
run_scenario "Scenariul 7: Propagation Models" "scenario-07-propagation-models/run-07.sh" 6
completed_scenarios=$((completed_scenarios + 1))

# Scenario 8
run_scenario "Scenariul 8: Multi Gateway" "scenario-08-multi-gateway/run-08.sh" 7
completed_scenarios=$((completed_scenarios + 1))

# Success summary
echo "🎉 SUCCESS: All $completed_scenarios/$total_scenarios scenarios completed successfully!"
echo ""
echo "📊 Final Summary:"
for i in "${!scenario_names[@]}"; do
    echo "   ✅ ${scenario_names[$i]}"
done
echo ""
echo "🗂️  Check individual scenario directories for results and logs"
echo "📈 Ready for data analysis and visualization!"