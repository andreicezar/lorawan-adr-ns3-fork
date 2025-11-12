#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

# =============================================================================
# Complete Parametric Study Script - COMPREHENSIVE METRICS VERSION
# Now with MAC + PHY layer metrics from all LoraPacketTracker APIs
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# =============================================================================
# CONFIGURATION
# =============================================================================
DISTANCES=(100 250 500 750 1000 1250 1500 2000 2500 3000 4000 5000 6000 7000 8000 9000 10000)
# DISTANCES=(100)
SPREADING_FACTORS=(7 8 9 10 11 12)
# SPREADING_FACTORS=(7)
TX_POWERS=(14)

# 0=LogDistance, 1=OkumuraHata
PROPAGATION_MODELS=(0 1)

RESULTS_DIR="results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RUN_DIR="${RESULTS_DIR}/run_${TIMESTAMP}"

# Map numeric model id -> human-readable name for filenames
model_name() {
  case "$1" in
    0) echo "LogDistance" ;;
    1) echo "OkumuraHata" ;;
    # Add more mappings here if you introduce new models:
    # 2) echo "Friis" ;;
    # 3) echo "TwoRayGround" ;;
    # 4) echo "COST231" ;;
    *) echo "Model$1" ;;
  esac
}

# =============================================================================
# HEADER
# =============================================================================
echo -e "${BLUE}Parametric Study Starting${NC}"
echo "Results directory: ${RUN_DIR}"

# =============================================================================
# SETUP
# =============================================================================
mkdir -p "${RUN_DIR}"

TOTAL=$((${#DISTANCES[@]} * ${#SPREADING_FACTORS[@]} * ${#TX_POWERS[@]} * ${#PROPAGATION_MODELS[@]}))
COUNTER=0
SUCCESS=0
FAILED=0

LOG_FILE="${RUN_DIR}/simulation.log"
touch "${LOG_FILE}"

START_TIME=$(date +%s)

echo -e "${BLUE}Starting ${TOTAL} simulations...${NC}"

# =============================================================================
# RUN SIMULATIONS
# =============================================================================

for MODEL in "${PROPAGATION_MODELS[@]}"; do
  MODEL_NAME="$(model_name "$MODEL")"
  for TP in "${TX_POWERS[@]}"; do
    for SF in "${SPREADING_FACTORS[@]}"; do
      for DIST in "${DISTANCES[@]}"; do
        COUNTER=$((COUNTER + 1))

        # Progress
        PERCENT=$((COUNTER * 100 / TOTAL))
        echo -ne "${BLUE}[${COUNTER}/${TOTAL}]${NC} ${PERCENT}% - "
        echo -ne "Model=${MODEL_NAME} (id=${MODEL}) SF=${SF} TP=${TP} Dist=${DIST}m... "

        # Output file name now includes the model name
        OUTPUT_FILE="${RUN_DIR}/sim_model_${MODEL_NAME}_sf${SF}_tp${TP}_dist${DIST}.csv"

        # Run simulation
        if ./ns3 run "scratch/test/simulation-file \
            --distanceBetweenNodes=${DIST} \
            --initialSF=${SF} \
            --initialTP=${TP} \
            --propagationModel=${MODEL} \
            --outputFile=${OUTPUT_FILE}" >> "${LOG_FILE}" 2>&1; then

          echo -e "${GREEN}✓${NC}"
          SUCCESS=$((SUCCESS + 1))

        else
          echo -e "${RED}✗${NC}"
          FAILED=$((FAILED + 1))
        fi
      done
    done
  done
done

# =============================================================================
# SUMMARY
# =============================================================================

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo -e "${BLUE}Complete! ${SUCCESS}/${TOTAL} successful${NC}"
echo -e "${BLUE}Failed: ${FAILED}${NC}"
echo -e "${BLUE}Elapsed time: ${ELAPSED} seconds${NC}"
