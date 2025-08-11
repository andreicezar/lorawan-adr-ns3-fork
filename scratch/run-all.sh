#!/bin/bash
# Master Runner: Execută fiecare scenariu folosind scripturile lor dedicate

set -e
cd "$(dirname "$0")"  # Ne asigurăm că suntem în directorul scratch/
echo $(pwd)
echo "🚀 Rulare scenarii NS-3 LoRaWAN"
echo "==============================="
echo ""

# Scenario 1
echo "▶ Scenariul 1: Baseline"
bash scenario-01-baseline/run-01.sh
echo ""

# Scenario 2
echo "▶ Scenariul 2: ADR Comparison"
bash scenario-02-adr-comparison/run-02.sh
echo ""

# Scenario 3
echo "▶ Scenariul 3: SF Impact"
bash scenario-03-sf-impact/run-03.sh
echo ""

# Scenario 4
echo "▶ Scenariul 4: Confirmed messages"
bash scenario-04-confirmed-messages/run-04.sh
echo ""

# Scenario 5
echo "▶ Scenariul 5: Traffic Patterns"
bash scenario-05-traffic-patterns/run-05.sh
echo ""

# Scenario 6
echo "▶ Scenariul 6: Collision Capture"
bash scenario-06-collision-capture/run-06.sh
echo ""

# Scenario 7
echo "▶ Scenariul 7: Propagation Models"
bash scenario-07-propagation-models/run-07.sh
echo "" 

# Scenario 8
echo "▶ Scenariul 8: Adaptive Data Rate"        
bash scenario-08-multi-gateway/run-08.sh
echo ""

echo "✅ Toate scenariile au fost rulate cu succes!"
