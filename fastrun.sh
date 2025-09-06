#!/bin/bash

# Navigate to the NS-3 development directory
cd ~/development/ns3-comparison-clean/ns-3-dev

# 1. Clean
echo "=== CLEAN BUILD ==="
rm -rf build cmake-cache

# 2. Configure
echo "=== CONFIGURE ==="
./ns3 configure --build-profile=debug --enable-examples --enable-tests

# 3. Build
echo "=== FIRST BUILD ==="
./ns3 build

# 4. Run all scenarios
echo "=== RUN SIMULATION SCRIPT ==="
# bash scratch/scenario-01-baseline/run-01.sh all
# bash scratch/scenario-02-adr-comparison/run-02.sh 
# bash scratch/scenario-03-sf-impact/run-03.sh
# bash scratch/scenario-04-confirmed-messages/run-04.sh
# bash scratch/scenario-05-traffic-patterns/run-05.sh
bash scratch/scenario-06-collision-capture/run-06.sh
bash scratch/scenario-07-propagation-models/run-07.sh
# bash scratch/scenario-08-multi-gateway/run-08.sh
# bash scratch/run-all.sh

echo "=== ALL DONE ==="
