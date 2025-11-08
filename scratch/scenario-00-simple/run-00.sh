#!/usr/bin/env bash
set -euo pipefail

# Find ns-3 root (two levels up)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$ROOT/../.." && pwd)"
cd "$ROOT"

BIN="scratch/scenario-00-simple/scenario-00-simple"

# Output location (where files are actually created)
ACTUAL_OUTPUT="$ROOT/scratch/scenario-00-simple/output"
BASE_OUTPUT="$ROOT/scratch/scenario-00-simple/output"

# Include distances that may fail with SF7
for dist in 100 250 500 1000 2000 3000 4000 5000 6000 6200 6400 6600 6800 7000 8000 9000 10000; do
    # Create separate folder for this distance
    OUTPUT_DIR="${BASE_OUTPUT}/${dist}m"
    mkdir -p "$OUTPUT_DIR"
    
    echo "========================================="
    echo "Running distance = ${dist}m"
    echo "Output: ${OUTPUT_DIR}"
    echo "========================================="
    
    # Run simulation (|| true prevents exit on crash)
    ./ns3 run "$BIN --gw_ed_distance_m=${dist}" 2>&1 | tee "${OUTPUT_DIR}/run.log" || true
    
    # Move output files from root output to this distance's folder
    [ -f "${ACTUAL_OUTPUT}/init_config.log" ] && \
        mv "${ACTUAL_OUTPUT}/init_config.log" "${OUTPUT_DIR}/"
        
    [ -f "${ACTUAL_OUTPUT}/snr_log.csv" ] && \
        mv "${ACTUAL_OUTPUT}/snr_log.csv" "${OUTPUT_DIR}/"
    
    [ -f "${ACTUAL_OUTPUT}/packet_details.csv" ] && \
        mv "${ACTUAL_OUTPUT}/packet_details.csv" "${OUTPUT_DIR}/"
    
    [ -f "${ACTUAL_OUTPUT}/ed-energy-total.csv" ] && \
        mv "${ACTUAL_OUTPUT}/ed-energy-total.csv" "${OUTPUT_DIR}/"
    
    [ -f "${ACTUAL_OUTPUT}/ed-remaining-energy.csv" ] && \
        mv "${ACTUAL_OUTPUT}/ed-remaining-energy.csv" "${OUTPUT_DIR}/"
    
    [ -f "${ACTUAL_OUTPUT}/global-performance.txt" ] && \
        mv "${ACTUAL_OUTPUT}/global-performance.txt" "${OUTPUT_DIR}/"
    
    [ -f "${ACTUAL_OUTPUT}/phy-performance.txt" ] && \
        mv "${ACTUAL_OUTPUT}/phy-performance.txt" "${OUTPUT_DIR}/"
    
    [ -f "${ACTUAL_OUTPUT}/device-status.txt" ] && \
        mv "${ACTUAL_OUTPUT}/device-status.txt" "${OUTPUT_DIR}/"
    
    echo "✓ Completed: ${dist}m"
    echo ""
done

echo "========================================="
echo "All distances complete!"
echo "Results in: ${BASE_OUTPUT}/"
ls -ld ${BASE_OUTPUT}/*/ 2>/dev/null | grep -v "^d.*output/$"
echo "========================================="