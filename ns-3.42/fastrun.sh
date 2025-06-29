#!/bin/bash

# 1. Clean
echo "=== CLEAN BUILD ==="
rm -rf build cmake-cache

# 2. Configure
echo "=== CONFIGURE ==="
./ns3 configure --build-profile=debug --enable-examples --enable-tests

# 3. Build
echo "=== FIRST BUILD ==="
./ns3 build

# 4. Copy custom headers for scratch
echo "=== COPY HEADERS ==="
mkdir -p build/include/ns3/lorawan/model/
cp src/lorawan/model/*.h build/include/ns3/lorawan/model/

# 5. Build again (now scratch can see headers)
echo "=== FINAL BUILD (WITH HEADERS) ==="
./ns3 build

# 6. Run your scenario/script (schimbă cu scriptul tău)
echo "=== RUN SIMULATION SCRIPT ==="
./scratch/adr_opt/run_complete_adr.sh

echo "=== ALL DONE ==="
