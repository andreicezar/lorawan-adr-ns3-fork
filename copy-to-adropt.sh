#!/usr/bin/env bash
set -euo pipefail

# Source and destination (WSL paths)
SRC="/home/andrei/development/ns3-comparison-clean/ns-3-dev"
DST="/home/andrei/development/ns3-adropt-development/ns3-lorawan-adropt-project"
SCRIPT_SRC="/home/andrei/development/fastrun.sh"

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
    # Copy only if missing or content differs (don't preserve mtime → Git will notice)
    if [[ ! -e "$out" ]] || ! cmp -s "$f" "$out"; then
      if [[ -x "$f" ]]; then mode=755; else mode=644; fi
      install -D -m "$mode" "$f" "$out"
      echo "updated: ${d##*/}/$rel"
    fi
  done
}

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
  else
    echo "warn: $src not found, skipped $desc"
  fi
}

echo "🔄 Updating LoRaWAN comparison project files..."
echo "=" * 50

echo "Updating lorawan …"
copy_update "$SRC/src/lorawan" "$DST/lorawan"

echo "Updating scratch …"
copy_update "$SRC/scratch" "$DST/scratch"

echo "Updating plots folder …"
if [[ -d "$SRC/plots" ]]; then
  copy_update "$SRC/plots" "$DST/plots"
else
  echo "warn: $SRC/plots not found, skipped plots folder"
fi

echo "Updating position data and scripts …"
copy_single_file "$SRC/scenario_positions.csv" "$DST/scenario_positions.csv" "position data (CSV)"
copy_single_file "$SRC/generate_positions.py" "$DST/generate_positions.py" "position generator script"
copy_single_file "$SRC/scenario_plotter.py" "$DST/scenario_plotter.py" "plotting script"

echo "Updating fastrun.sh …"
copy_single_file "$SCRIPT_SRC" "$DST/fastrun.sh" "fastrun.sh"

echo ""
echo "✅ Copy operation completed!"
echo "📂 Copied directories:"
echo "   • lorawan/ (source code)"
echo "   • scratch/ (scenarios and scripts)"
echo "   • plots/ (network topology visualizations)"
echo "📄 Copied files:"
echo "   • scenario_positions.csv (node positions data)"
echo "   • generate_positions.py (position generation script)"
echo "   • scenario_plotter.py (visualization script)"
echo "   • fastrun.sh (build/run helper)"
echo ""
echo "🎯 Backup location: $DST"
echo "Done."