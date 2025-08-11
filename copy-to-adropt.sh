#!/usr/bin/env bash
set -euo pipefail

# --- Paths (WSL/Linux style) ---
SRC_BASE="/home/andrei/development/ns3-comparison-clean/ns-3-dev"
DEST_BASE="/home/andrei/development/ns3-adropt-development/ns3-lorawan-adropt-project"
SCRIPT_SRC="/home/andrei/development/fastrun.sh"

# --- rsync options & excludes ---
rsync_opts=(
  -a --delete --human-readable --info=stats1,progress2
  --exclude=".git" --exclude=".git/**"
  --exclude=".svn" --exclude=".hg"
  --exclude=".gitignore" --exclude=".gitattributes" --exclude=".gitmodules"
  --exclude=".DS_Store" --exclude="Thumbs.db"
  --exclude="*.swp" --exclude="*.swo"
)

echo "Syncing scratch → scratch…"
rsync "${rsync_opts[@]}" "$SRC_BASE/scratch/" "$DEST_BASE/scratch/"

echo "Syncing src/lorawan → lorawan…"
rsync "${rsync_opts[@]}" "$SRC_BASE/src/lorawan/" "$DEST_BASE/lorawan/"

echo "Copying fastrun.sh to project root…"
install -D -m 755 "$SCRIPT_SRC" "$DEST_BASE/fastrun.sh"

# Optional: normalize line endings if dos2unix is available
if command -v dos2unix >/dev/null 2>&1; then
  dos2unix -q "$DEST_BASE/fastrun.sh" || true
fi

echo "Done."
