#!/usr/bin/env bash
set -euo pipefail

# Go to ns-3 root (two levels up from this script’s folder)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BIN="scratch/scenario-00-simple/scenario-00-simple"

set -x
./ns3 run "$BIN"
