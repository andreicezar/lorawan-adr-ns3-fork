#!/usr/bin/env bash
set -euo pipefail

# ===================== Config (edit if needed) =====================
# Windows UNC-style WSL paths (as you requested):
SRC_WIN='\\wsl.localhost\Ubuntu-22.04\home\andrei\development\ns3-comparison-clean\ns-3-dev'
DST_WIN='\\wsl.localhost\Ubuntu-22.04\home\andrei\repos\adropt-ns3'

# Mirror scratch/: delete destination scratch before copying (0/1)
: "${MIRROR_SCRATCH:=1}"

# ===================== Helpers =====================
say()  { printf "%s\n" "$*"; }
ok()   { printf "updated: %s\n" "$*"; }
warn() { printf "warn: %s\n" "$*"; }
die()  { printf "error: %s\n" "$*"; exit 1; }

to_unix_path() {
  # Convert UNC (\\wsl.localhost\Distro\path) to a Linux path inside this distro.
  # wslpath handles UNC ↔ POSIX; fallback to a best-effort sed if wslpath is absent.
  local p="$1"
  if command -v wslpath >/dev/null 2>&1; then
    # Escape backslashes for wslpath
    # shellcheck disable=SC1003
    p="${p//\\/\\\\}"
    wslpath -u "$p"
  else
    # Fallback heuristic (works for \\wsl.localhost\Ubuntu-22.04\home\user\...):
    # Strip leading \\wsl.localhost\Ubuntu-22.04 and keep /home/...
    echo "$p" | sed -E 's#^\\\\wsl\.localhost\\Ubuntu-22\.04##; s#\\#/#g'
  fi
}

copy_scratch() {
  local src="$1" dst="$2"
  local src_s="$src/scratch"
  local dst_s="$dst/scratch"

  [[ -d "$src_s" ]] || die "Source scratch/ not found: $src_s"

  if [[ "${MIRROR_SCRATCH}" == "1" && -d "$dst_s" ]]; then
    rm -rf "$dst_s"
  fi
  mkdir -p "$dst_s"

  # Copy everything from scratch/, excluding git internals
  # Use rsync if available for clean filters; otherwise fallback to cp.
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete \
      --exclude='.git/' --exclude='.gitignore' \
      "$src_s/" "$dst_s/"
  else
    # Fallback cp: copy entries except .git/.gitignore
    shopt -s dotglob nullglob
    for item in "$src_s"/* "$src_s"/.*; do
      base="$(basename "$item")"
      [[ "$base" == "." || "$base" == ".." || "$base" == ".git" || "$base" == ".gitignore" ]] && continue
      cp -a "$item" "$dst_s/"
    done
    shopt -u dotglob nullglob
  fi
  ok "scratch/ ← copied (excluding Git files)"
}

copy_all_python() {
  local src="$1" dst="$2"
  # Recursively copy *.py while preserving directory structure, excluding .git folders.
  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --prune-empty-dirs \
      --exclude='.git/' \
      --include='*/' --include='*.py' --exclude='*' \
      "$src/" "$dst/"
    ok "all *.py files ← copied recursively"
  else
    # Portable fallback using find + tar to preserve structure
    (
      cd "$src"
      # Build a tar stream of .py files (excluding .git) and extract at $dst
      # The '|| true' makes it tolerant if no .py files exist.
      find . -type d -name .git -prune -o -type f -name '*.py' -print0 | \
      tar --null -T - -cf - 2>/dev/null || true
    ) | ( mkdir -p "$dst" && cd "$dst" && tar -xf - )
    ok "all *.py files ← copied recursively (fallback)"
  fi
}

audit() {
  printf "\n🔍 Audit:\n"
  [[ -d "$DST_UNIX/scratch" ]] && say "• Present: $(realpath "$DST_UNIX/scratch")" || warn "Missing: scratch in destination"
  local pycount
  pycount=$(find "$DST_UNIX" -type f -name '*.py' | wc -l | tr -d ' ')
  say "• Python files in destination: $pycount"
  printf "\nDone.\n"
}

# ===================== Main =====================
SRC_UNIX="$(to_unix_path "$SRC_WIN")"
DST_UNIX="$(to_unix_path "$DST_WIN")"

[[ -d "$SRC_UNIX" ]] || die "Source dir not found: $SRC_UNIX"
mkdir -p "$DST_UNIX"

printf "🔄 Copy started: %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
printf "SRC: %s\nDST: %s\n" "$SRC_UNIX" "$DST_UNIX"
printf "==================================================\n"

copy_scratch "$SRC_UNIX" "$DST_UNIX"
copy_all_python "$SRC_UNIX" "$DST_UNIX"

audit
