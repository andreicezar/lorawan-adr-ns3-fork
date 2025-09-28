#!/usr/bin/env bash
set -euo pipefail

# ---------------------- Config ----------------------
SRC="/home/andrei/development/ns3-comparison-clean/ns-3-dev"
DST="/home/andrei/development/ns3-adropt-development/ns3-lorawan-adropt-project"
FASTRUN_SRC="/home/andrei/development/fastrun.sh"

# MIRROR=1 -> fully replace each dest subdir before copy
: "${MIRROR:=0}"

# After copy, purge any .gitignore inside DST/scratch (1=yes)
: "${PURGE_SCRATCH_GITIGNORE:=1}"

# ---------------------- Helpers ---------------------
say()       { printf "%s\n" "$*"; }
info()      { printf "info: %s\n" "$*"; }
ok()        { printf "updated: %s\n" "$*"; }
warn()      { printf "warn: %s\n" "$*"; }
error_out() { printf "error: %s\n" "$*"; exit 1; }

header() {
  printf "🔄 Copy started at %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
  printf "SRC: %s\nDST: %s\nMIRROR: %s\n" "$SRC" "$DST" "$MIRROR"
  printf "==================================================\n"
}

# Copy a whole directory: cp -a src/. -> dst/, then drop Git internals
# Usage: copy_dir <src_dir> <dst_dir> <req|opt>
copy_dir() {
  local src="$1" dst="$2" req="${3:-opt}"

  if [[ ! -d "$src" ]]; then
    [[ "$req" == "req" ]] && { printf "error: %s (required) not found\n" "$src"; exit 1; }
    printf "info: %s not found, skipped\n" "$src"
    return 0
  fi

  # In MIRROR mode, start clean
  if [[ "${MIRROR:-0}" == "1" && -d "$dst" ]]; then
    rm -rf "$dst"
  fi
  mkdir -p "$dst"

  # Include dotfiles but skip . and .. ; exclude .git and .gitignore
  local save_dotglob save_nullglob
  save_dotglob=$(shopt -p dotglob || true)
  save_nullglob=$(shopt -p nullglob || true)
  shopt -s dotglob nullglob

  for item in "$src"/* "$src"/.*; do
    local base
    base="$(basename "$item")"
    [[ "$base" == "." || "$base" == ".." ]] && continue
    [[ "$base" == ".git" || "$base" == ".gitignore" ]] && continue
    cp -a "$item" "$dst"/
  done

  eval "$save_dotglob" || true
  eval "$save_nullglob" || true

  # Make sure no stray Git internals remain (paranoia)
  rm -rf "$dst/.git" 2>/dev/null || true
  rm -f  "$dst/.gitignore" 2>/dev/null || true

  printf "updated: %s/  ←  %s/\n" "$(basename "$dst")" "$(basename "$src")"
}


copy_file() {
  local src="$1" dst="$2" desc="$3"
  if [[ -f "$src" ]]; then
    mkdir -p "$(dirname "$dst")"
    cp -p "$src" "$dst"
    ok "$desc"
  else
    info "$desc not found in source, skipped"
  fi
}

maybe_copy_glob() {
  local pattern="$1" dstdir="$2" desc="$3"
  shopt -s nullglob
  local matches=( $pattern )
  if (( ${#matches[@]} == 0 )); then
    info "$desc not found, skipped"
    return 0
  fi
  mkdir -p "$dstdir"
  for f in "${matches[@]}"; do cp -p "$f" "$dstdir/$(basename "$f")"; done
  ok "$desc"
}

audit() {
  printf "\n🔍 Audit:\n"
  shopt -s globstar nullglob

  # Quick presence checks for the two missing dirs you showed
  if [[ -d "$DST/scratch/common" ]]; then
    say "• Present: scratch/common"
  else
    warn "Missing: scratch/common"
  fi
  if [[ -d "$DST/scratch/scenario-00-simple" ]]; then
    say "• Present: scratch/scenario-00-simple"
  else
    warn "Missing: scratch/scenario-00-simple"
  fi

  # Count code files
  local cc_list=( "$DST"/scratch/**/*.cc )
  local h_list=( "$DST"/scratch/**/*.h )
  say "• *.cc in DST/scratch: ${#cc_list[@]}"
  say "• *.h  in DST/scratch: ${#h_list[@]}"

  # If SRC has logs, verify they exist in DST
  local src_logs=( "$SRC"/scratch/**/output/*.csv "$SRC"/scratch/**/output/*.txt )
  local checked=0 missing=0
  for s in "${src_logs[@]}"; do
    [[ -e "$s" ]] || continue
    checked=$((checked+1))
    local d="${s/$SRC/$DST}"
    [[ -e "$d" ]] || { warn "Missing log in DST: ${d#$DST/}"; missing=1; }
  done
  if (( checked > 0 && missing == 0 )); then
    say "• Logs OK: ${checked} files under scratch/**/output/"
  elif (( checked == 0 )); then
    say "• No logs to verify from SRC"
  fi

  printf "\n🎯 Backup location: %s\n" "$DST"
}

# ---------------------- Main ------------------------
header

# Mandatory sources
[[ -d "$SRC/src/lorawan" ]] || error_out "$SRC/src/lorawan not found (required)"
[[ -d "$SRC/scratch"    ]] || error_out "$SRC/scratch not found (required)"

say "Updating core directories …"
copy_dir "$SRC/src/lorawan"               "$DST/lorawan"                 req
copy_dir "$SRC/scratch"                   "$DST/scratch"                 req
copy_dir "$SRC/plots"                     "$DST/plots"                   opt
copy_dir "$SRC/generated-omnet-scenarios" "$DST/generated-omnet-scenarios" opt
copy_dir "$SRC/omnet_positions"           "$DST/omnet_positions"         opt

say "Updating Python tools …"
maybe_copy_glob "$SRC/analyze_*.py"              "$DST" "analyze_*.py"
maybe_copy_glob "$SRC/analyze_ns3_scenario_*.py" "$DST" "analyze_ns3_scenario_*.py"
copy_file "$SRC/run_analysis.py" "$DST/run_analysis.py" "run_analysis.py"
maybe_copy_glob "$SRC/gen_*.py"                  "$DST" "gen_*.py"
maybe_copy_glob "$SRC/generate_*.py"             "$DST" "generate_*.py"
copy_file "$SRC/csv-to-omnet.py" "$DST/csv-to-omnet.py" "csv-to-omnet.py"
copy_file "$SRC/ns3_lorawan_parser.py" "$DST/ns3_lorawan_parser.py" "ns3_lorawan_parser.py"

say "Updating position CSVs …"
copy_file "$SRC/scenario_positions.csv"           "$DST/scenario_positions.csv"           "scenario_positions.csv"
copy_file "$SRC/scenario_positions_1x1km.csv"     "$DST/scenario_positions_1x1km.csv"     "scenario_positions_1x1km.csv"
copy_file "$SRC/scenario_positions_2x2km.csv"     "$DST/scenario_positions_2x2km.csv"     "scenario_positions_2x2km.csv"
copy_file "$SRC/scenario_positions_3x3km.csv"     "$DST/scenario_positions_3x3km.csv"     "scenario_positions_3x3km.csv"
copy_file "$SRC/scenario_positions_4x4km.csv"     "$DST/scenario_positions_4x4km.csv"     "scenario_positions_4x4km.csv"
copy_file "$SRC/scenario_positions_5x5km.csv"     "$DST/scenario_positions_5x5km.csv"     "scenario_positions_5x5km.csv"

say "Updating helpers …"
copy_file "$SRC/run_all_analyzers.sh" "$DST/run_all_analyzers.sh" "run_all_analyzers.sh"
copy_file "$FASTRUN_SRC"              "$DST/fastrun.sh"           "fastrun.sh"

# Optional: purge any .gitignore left inside DST/scratch (these hide files in git status)
if [[ "$PURGE_SCRATCH_GITIGNORE" == "1" && -d "$DST/scratch" ]]; then
  shopt -s globstar nullglob
  for f in "$DST"/scratch/**/.gitignore; do
    rm -f "$f"
    printf "removed: %s\n" "${f#$DST/}"
  done
fi

say "✅ Copy operation completed!"
audit
