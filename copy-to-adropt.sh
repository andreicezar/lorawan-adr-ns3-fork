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
    # Copy only if missing or content differs (don’t preserve mtime → Git will notice)
    if [[ ! -e "$out" ]] || ! cmp -s "$f" "$out"; then
      if [[ -x "$f" ]]; then mode=755; else mode=644; fi
      install -D -m "$mode" "$f" "$out"
      echo "updated: ${d##*/}/$rel"
    fi
  done
}

echo "Updating lorawan …"
copy_update "$SRC/src/lorawan" "$DST/lorawan"

echo "Updating scratch …"
copy_update "$SRC/scratch" "$DST/scratch"

echo "Updating fastrun.sh …"
if [[ -f "$SCRIPT_SRC" ]]; then
  install -D -m 755 "$SCRIPT_SRC" "$DST/fastrun.sh"
  echo "updated: fastrun.sh"
else
  echo "warn: $SCRIPT_SRC not found, skipped."
fi

echo "Done."
