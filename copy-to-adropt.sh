#!/usr/bin/env bash
set -euo pipefail

# -------------------------------------------------------------------
# Config (edit these paths)
# -------------------------------------------------------------------
SRC="/home/andrei/development/ns3-comparison-clean/ns-3-dev"
DST="/home/andrei/development/ns3-adropt-development/ns3-lorawan-adropt-project"
FASTRUN_SRC="/home/andrei/development/fastrun.sh"

# MIRROR=1 will wipe each destination subdir before copying (for dirs only)
: "${MIRROR:=0}"

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
header() {
  printf "🔄 Copy started at %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
  printf "SRC: %s\nDST: %s\nMIRROR: %s\n" "$SRC" "$DST" "$MIRROR"
  printf "==================================================\n"
}

say()      { printf "%s\n" "$*"; }
info()     { printf "info: %s\n" "$*"; }
ok()       { printf "updated: %s\n" "$*"; }
warn()     { printf "warn: %s\n" "$*"; }
error_out(){ printf "error: %s\n" "$*"; exit 1; }

# Copy a whole directory tree with cp -a, skipping any .git directory inside src.
# Usage: copy_dir <src_dir> <dst_dir> <required_flag:req|opt>
copy_dir() {
  local src="$1" dst="$2" req="${3:-opt}"

  if [[ ! -d "$src" ]]; then
    [[ "$req" == "req" ]] && error_out "$src (required) not found"
    info "$src not found, skipped"
    return 0
  fi

  if [[ "$MIRROR" == "1" && -d "$dst" ]]; then
    rm -rf "$dst"
  fi
  mkdir -p "$dst"

  # Copy everything (including dotfiles) except .git
  local old_dotglob old_nullglob
  old_dotglob=$(shopt -p dotglob || true)
  old_nullglob=$(shopt -p nullglob || true)
  shopt -s dotglob nullglob

  for item in "$src"/* "$src"/.*; do
    local base
    base="$(basename "$item")"
    [[ "$base" == "." || "$base" == ".." ]] && continue
    [[ "$base" == ".git" ]] && continue
    cp -a "$item" "$dst"/
  done

  # restore shopt flags
  eval "$old_dotglob" || true
  eval "$old_nullglob" || true

  ok "$(basename "$dst")/  ←  $(basename "$src")/"
}

# Copy single file if present (quiet skip otherwise)
# Usage: copy_file <src_file> <dst_file> <desc>
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

# Copy a group of files matched by a glob into a destination directory.
# Pattern must be provided with full SRC prefix.
# Usage: maybe_copy_glob "<src_glob>" "<dst_dir>" "<desc>"
maybe_copy_glob() {
  local pattern="$1" dstdir="$2" desc="$3"

  local old_nullglob
  old_nullglob=$(shopt -p nullglob || true)
  shopt -s nullglob

  local matches=( $pattern )
  if (( ${#matches[@]} == 0 )); then
    info "$desc not found, skipped"
    eval "$old_nullglob" || true
    return 0
  fi

  mkdir -p "$dstdir"
  for f in "${matches[@]}"; do
    cp -p "$f" "$dstdir/$(basename "$f")"
  done
  ok "$desc"

  eval "$old_nullglob" || true
}

# Final audit using only bash globs (no find/rsync)
# Final audit using only bash globs (no find/rsync)
audit() {
  printf "\n🔍 Audit:\n"

  local old_globstar old_nullglob
  old_globstar=$(shopt -p globstar || true)
  old_nullglob=$(shopt -p nullglob || true)
  shopt -s globstar nullglob

  # Ensure at least one .cc and one .h exist under DST/scratch
  local cc_list=( "$DST"/scratch/**/*.cc )
  local h_list=( "$DST"/scratch/**/*.h )

  if (( ${#cc_list[@]} > 0 )); then
    say "• DST/scratch has C++ sources (*.cc): ${#cc_list[@]}"
  else
    warn "DST/scratch has NO *.cc files"
  fi

  if (( ${#h_list[@]} > 0 )); then
    say "• DST/scratch has headers (*.h): ${#h_list[@]}"
  else
    warn "DST/scratch has NO *.h files"
  fi

  # If SRC has any logs under scratch/**/output/*.{csv,txt}, confirm they exist in DST
  local src_logs=( "$SRC"/scratch/**/output/*.csv "$SRC"/scratch/**/output/*.txt )
  local missing=0 checked=0
  for s in "${src_logs[@]}"; do
    [[ -e "$s" ]] || continue
    checked=$((checked+1))
    local d="${s/$SRC/$DST}"
    if [[ ! -e "$d" ]]; then
      warn "Missing log in DST: ${d#$DST/}"
      missing=1
    fi
  done
  if (( checked > 0 && missing == 0 )); then
    say "• All ${checked} logs under scratch/**/output/ are present in DST."
  elif (( checked == 0 )); then
    say "• No logs found under SRC/scratch/**/output/ to verify."
  fi

  eval "$old_globstar" || true
  eval "$old_nullglob" || true

  printf "\n🎯 Backup location: %s\n" "$DST"
}


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------
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

say "✅ Copy operation completed!"
audit
