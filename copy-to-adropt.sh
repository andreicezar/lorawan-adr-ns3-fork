#!/usr/bin/env bash
set -euo pipefail

# --- Configuration ---
# Source and destination (WSL paths)
SRC="/home/andrei/development/ns3-comparison-clean/ns-3-dev"
DST="/home/andrei/development/ns3-adropt-development/ns3-lorawan-adropt-project"
SCRIPT_SRC="/home/andrei/development/fastrun.sh"

# --- State Tracking for Dynamic Summary ---
# Arrays to hold the descriptions of successfully processed items
declare -a copied_dirs
declare -a copied_files

# --- Helper function to copy/update a directory ---
copy_update() {
  local s="$1" d="$2"
  mkdir -p "$d"
  find "$s" \
    -type d \( -name .git -o -name .svn -o -name .hg \) -prune -o \
    -type f \
      ! -name '.DS_Store' \
      ! -name 'Thumbs.db' \
      ! -name '.gitignore' \
      ! -name '.gitattributes' \
      ! -name '.gitmodules' \
    -print0 |
  while IFS= read -r -d '' f; do
    rel="${f#$s/}"
    out="$d/$rel"
    mkdir -p "$(dirname "$out")"
    # Copy only if missing or content differs
    if [[ ! -e "$out" ]] || ! cmp -s "$f" "$out"; then
      if [[ -x "$f" ]]; then mode=755; else mode=644; fi
      install -D -m "$mode" "$f" "$out"
      echo "updated: ${d##*/}/$rel"
    fi
  done
}

# --- Helper function to copy a single file ---
copy_single_file() {
  local src="$1" dst="$2" desc="$3"
  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    if [[ ! -e "$dst" ]] || ! cmp -s "$src" "$dst"; then
      if [[ -x "$src" ]]; then mode=755; else mode=644; fi
      install -D -m "$mode" "$src" "$dst"
      echo "updated: $desc"
    else
      echo "unchanged: $desc"
    fi
    return 0 # Success
  else
    echo "warn: $src not found, skipped $desc"
    return 1 # Failure
  fi
}

# --- Main Execution ---
echo "🔄 Updating LoRaWAN comparison project files..."
echo "=================================================="

# --- Directories ---
echo "Updating core directories …"
if [[ -d "$SRC/src/lorawan" ]]; then
  copy_update "$SRC/src/lorawan" "$DST/lorawan"
  copied_dirs+=("lorawan/ (source code)")
fi

if [[ -d "$SRC/scratch" ]]; then
  copy_update "$SRC/scratch" "$DST/scratch"
  copied_dirs+=("scratch/ (scenarios and scripts)")
fi

if [[ -d "$SRC/plots" ]]; then
  copy_update "$SRC/plots" "$DST/plots"
  copied_dirs+=("plots/ (network topology visualizations)")
fi

if [[ -d "$SRC/generated-omnet-scenarios" ]]; then
  copy_update "$SRC/generated-omnet-scenarios" "$DST/generated-omnet-scenarios"
  copied_dirs+=("generated-omnet-scenarios/")
fi

if [[ -d "$SRC/omnet_positions" ]]; then
  copy_update "$SRC/omnet_positions" "$DST/omnet_positions"
  copied_dirs+=("omnet_positions/")
fi

# --- NEW: Find individual baseline files and copy them to a 'baselines' directory ---
echo "Updating OMNeT++ baseline files …"
baselines_found=0
# Use a glob to find all matching baseline files in the source directory
for f in "$SRC"/omnetpp-scenario-*-baseline; do
    # Check if the glob found any actual files
    if [[ -f "$f" ]]; then
        baselines_found=1
        filename=$(basename "$f")
        # Copy the file into the 'baselines' directory at the destination
        copy_single_file "$f" "$DST/baselines/$filename" "$filename"
    fi
done
# If we found and copied any baseline files, add the new directory to the summary
if ((baselines_found)); then
    copied_dirs+=("baselines/ (OMNeT++ baseline files)")
else
    echo "info: No OMNeT++ baseline files found to copy."
fi


# --- Python Scripts ---
echo "Updating Python scripts …"
PY_SCRIPTS=(
    "ns3_lorawan_parser.py" "run_diagnostics.py" "run_analysis.py"
    "analyze_comparison.py" "generate_omnet_baselines.py"
    "generate_positions.py" "scenario_plotter.py" "gen_omnet_scenarios.py"
    "csv-to-omnet.py" 
    "analyze_ns3_scenario_01.py" "analyze_ns3_scenario_02.py" 
    "analyze_ns3_scenario_03.py" "analyze_ns3_scenario_05.py"
    "analyze_ns3_scenario_06.py" "analyze_ns3_scenario_07.py"
    "analyze_ns3_scenario_08.py"
)
py_scripts_found=0
for script in "${PY_SCRIPTS[@]}"; do
    # copy_single_file returns 0 on success
    if copy_single_file "$SRC/$script" "$DST/$script" "$script"; then
        py_scripts_found=1
    fi
done
if ((py_scripts_found)); then
    copied_files+=("Core Python scripts (analysis, plotting, etc.)")
fi

# --- Individual Data and Helper Files ---
echo "Updating individual files …"
if copy_single_file "$SRC/scenario_positions.csv" "$DST/scenario_positions.csv" "position data (CSV)"; then
    copied_files+=("scenario_positions.csv (node positions data)")
fi
if copy_single_file "$SRC/scenario_positions_1x1km.csv" "$DST/scenario_positions_1x1km.csv" "position data (CSV)"; then
    copied_files+=("scenario_positions_1x1km.csv (node positions data)")
fi
if copy_single_file "$SRC/scenario_positions_2x2km.csv" "$DST/scenario_positions_2x2km.csv" "position data (CSV)"; then
    copied_files+=("scenario_positions_2x2km.csv (node positions data)")
fi
if copy_single_file "$SRC/scenario_positions_3x3km.csv" "$DST/scenario_positions_3x3km.csv" "position data (CSV)"; then
    copied_files+=("scenario_positions_3x3km.csv (node positions data)")
fi
if copy_single_file "$SRC/scenario_positions_4x4km.csv" "$DST/scenario_positions_4x4km.csv" "position data (CSV)"; then
    copied_files+=("scenario_positions_4x4km.csv (node positions data)")
fi
if copy_single_file "$SRC/scenario_positions_5x5km.csv" "$DST/scenario_positions_5x5km.csv" "position data (CSV)"; then
    copied_files+=("scenario_positions_5x5km.csv (node positions data)")
fi
if copy_single_file "$SRC/run_all_analyzers.sh" "$DST/run_all_analyzers.sh" "run_all_analyzers.sh"; then
    copied_files+=("run_all_analyzers.sh (run helper)")
fi
if copy_single_file "$SCRIPT_SRC" "$DST/fastrun.sh" "fastrun.sh"; then
    copied_files+=("fastrun.sh (build/run helper)")
fi

# --- Dynamic Final Summary ---
echo ""
echo "✅ Copy operation completed!"

if [ ${#copied_dirs[@]} -gt 0 ]; then
    echo "📂 Copied directories:"
    for item in "${copied_dirs[@]}"; do
        echo "   • $item"
    done
fi

if [ ${#copied_files[@]} -gt 0 ]; then
    echo "📄 Copied files:"
    for item in "${copied_files[@]}"; do
        echo "   • $item"
    done
fi

echo ""
echo "🎯 Backup location: $DST"
echo "Done."