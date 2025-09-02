#!/usr/bin/env python3
"""
Generate OMNeT++ baseline template files for LoRa scenarios
Creates .ini template files that can be used with gen_omnet_scenarios.py
"""

import argparse, re
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class ScenarioConfig:
    """Configuration parameters for a LoRa scenario"""
    scenario_num: int
    scenario_name: str
    description: str
    sim_time_min: int
    packet_interval_sec: int
    initial_sf: int
    initial_tp: int
    sigma: float
    num_devices: int
    num_gateways: int
    position_file_path: str
    app_typename: str = "SimpleLoRaApp"
    bandwidth_khz: int = 125
    coding_rate: int = 4

def read_position_data(position_file_path: str) -> str:
    """Read and extract position data from an OMNeT++ position file"""
    try:
        position_path = Path(position_file_path)
        
        # Handle WSL paths - convert to regular Windows paths for Python
        if position_file_path.startswith("\\\\wsl.localhost\\"):
            # Convert WSL path to Unix-style path for reading
            wsl_path = position_file_path.replace("\\\\wsl.localhost\\Ubuntu-22.04", "")
            wsl_path = wsl_path.replace("\\", "/")
            position_path = Path(wsl_path)
        
        if not position_path.exists():
            print(f"Warning: Position file not found: {position_file_path}")
            return generate_placeholder_positions()
            
        content = position_path.read_text(encoding="utf-8", errors="ignore")
        
        # Extract position lines (gateway and node positions)
        position_lines = []
        for line in content.split('\n'):
            line = line.strip()
            # Look for actual position configuration lines
            if (line.startswith('**.loRaGW[') or line.startswith('**.loRaNodes[')) and 'initial' in line:
                position_lines.append(line)
        
        if not position_lines:
            print(f"Warning: No position data found in {position_file_path}")
            return generate_placeholder_positions()
            
        # Format the positions nicely
        result = []
        result.append("# GATEWAY POSITIONS")
        result.append("#" + "="*50)
        
        # Add gateway positions
        for line in position_lines:
            if line.startswith('**.loRaGW['):
                result.append(line)
                
        result.append("")
        result.append("# END DEVICE POSITIONS")  
        result.append("#" + "="*50)
        
        # Add node positions in groups of 10 for readability
        node_count = 0
        for line in position_lines:
            if line.startswith('**.loRaNodes['):
                if node_count % 10 == 0 and node_count > 0:
                    result.append(f"# Nodes {node_count} - {node_count+9}")
                result.append(line)
                node_count += 1
                
        result.append("")
        result.append(f"# Position data loaded from: {position_file_path}")
        result.append(f"# Total devices: {node_count}, Gateways: {len([l for l in position_lines if 'loRaGW[' in l])//3}")
        
        return '\n'.join(result)
        
    except Exception as e:
        print(f"Error reading position file {position_file_path}: {e}")
        return generate_placeholder_positions()

def generate_placeholder_positions() -> str:
    """Generate placeholder position data when position file is not available"""
    return """# PLACEHOLDER POSITIONS - POSITION FILE NOT FOUND
#==================================================
# Gateway at origin
**.loRaGW[0].**.initialX = 0.00m
**.loRaGW[0].**.initialY = 0.00m
**.loRaGW[0].**.initialZ = 15.0m

# Sample node positions (replace with actual data)
**.loRaNodes[0].**.initialX = 100.00m
**.loRaNodes[0].**.initialY = 100.00m
**.loRaNodes[0].**.initialZ = 1.5m
# ... Add remaining node positions ..."""

def generate_baseline_template(config: ScenarioConfig, output_dir: Path) -> str:
    """Generate a baseline OMNeT++ .ini template file with actual position data"""
    
    output_file = output_dir / f"omnetpp-scenario-{config.scenario_num:02d}-baseline.ini"
    
    # Read actual position data from file
    print(f"Reading positions from: {config.position_file_path}")
    position_data = read_position_data(config.position_file_path)
    
    template_content = f'''[General]
network = flora.simulations.LoRaNetworkTest
sim-time-limit = {config.sim_time_min}min           # {config.sim_time_min} minutes for {config.scenario_name}
simtime-resolution = -11
repeat = 1

# Output - will be overridden by generator
output-vector-file = ../results/scenario-{config.scenario_num:02d}-baseline-s${{runnumber}}.vec
output-scalar-file = ../results/scenario-{config.scenario_num:02d}-baseline-s${{runnumber}}.sca
**.vector-recording = true

# RNG
rng-class = "cMersenneTwister"

#================================================================================
# NETWORK TOPOLOGY & COUNTS
#================================================================================
**.numberOfNodes = {config.num_devices}
**.numberOfGateways = {config.num_gateways}

# Area (constraint area adjusted to match CSV coordinate ranges)
**.constraintAreaMinX = -3000m
**.constraintAreaMinY = -3000m
**.constraintAreaMinZ = 0m
**.constraintAreaMaxX = 3000m
**.constraintAreaMaxY = 3000m
**.constraintAreaMaxZ = 20m

# Mobility/placement flags
**.loRaNodes[*].**.initFromDisplayString = false
**.loRaGW[*].**.initFromDisplayString = false

#================================================================================
# PHY / CHANNEL CONFIGURATION
#================================================================================
**.radio.radioMediumModule = "LoRaMedium"
**.LoRaMedium.pathLossType = "LoRaLogNormalShadowing"
**.sigma = {config.sigma}                      # {config.description} - sigma {config.sigma}dB
**.minInterferenceTime = 0s
**.alohaChannelModel = false
**.energyDetection = -110dBm
**.maxTransmissionDuration = 4s
LoRaNetworkTest.**.radio.separateTransmissionParts = false
LoRaNetworkTest.**.radio.separateReceptionParts = false

#================================================================================
# GATEWAY CONFIGURATION
#================================================================================
**.LoRaGWNic.radio.iAmGateway = true
**.loRaGW[*].numUdpApps = 1
**.loRaGW[0].packetForwarder.localPort = 2000
**.loRaGW[0].packetForwarder.destPort = 1000
**.loRaGW[0].packetForwarder.destAddresses = "networkServer"
**.loRaGW[0].packetForwarder.indexNumber = 0

#================================================================================
# NETWORK SERVER CONFIGURATION - WILL BE OVERRIDDEN BY GENERATOR
#================================================================================
**.networkServer.numApps = 1
**.networkServer.app[0].typename = "NetworkServerApp"
**.networkServer.app[0].destAddresses = "loRaGW[0]"
**.networkServer.app[0].destPort = 2000
**.networkServer.app[0].localPort = 1000

# ADR Configuration - DEFAULT (will be overridden per sub-scenario)
**.networkServer.**.evaluateADRinServer = false

#================================================================================
# NODE RADIO CONFIGURATION - SCENARIO {config.scenario_num:02d} DEFAULTS
#================================================================================
# Default radio parameters: SF{config.initial_sf}, {config.initial_tp}dBm, {config.bandwidth_khz}kHz, CR4/{config.coding_rate+1}
**.loRaNodes[*].**initialLoRaSF = {config.initial_sf}
**.loRaNodes[*].**initialLoRaBW = {config.bandwidth_khz} kHz
**.loRaNodes[*].**initialLoRaCR = {config.coding_rate}
**.loRaNodes[*].**initialLoRaTP = {config.initial_tp}dBm
**.loRaNodes[*].**.evaluateADRinNode = false

#================================================================================
# APPLICATION CONFIGURATION - SCENARIO {config.scenario_num:02d} SPECIFIC
#================================================================================
**.loRaNodes[*].numApps = 1
**.loRaNodes[*].app[0].typename = "{config.app_typename}"

# Packet configuration for {config.scenario_name} ({config.packet_interval_sec}s intervals)
**.numberOfPacketsToSend = 0                      # infinite packets 
**.timeToFirstPacket = uniform(1s, 10s)           # spread first transmissions
**.timeToNextPacket = {config.packet_interval_sec}s                        # send every {config.packet_interval_sec//60} minutes (matches ns-3)

#================================================================================
# OPTIONAL MODULES (ENERGY & DELAYS)
#================================================================================
**.ipv4Delayer.config = xmldoc("../cloudDelays.xml")
**.loRaNodes[*].LoRaNic.radio.energyConsumer.typename = "LoRaEnergyConsumer"
**.loRaNodes[*].**.energySourceModule = "^.IdealEpEnergyStorage"
**.loRaNodes[*].LoRaNic.radio.energyConsumer.configFile = xmldoc("../energyConsumptionParameters.xml")

#================================================================================
# NODE POSITIONS - LOADED FROM POSITION FILE
#================================================================================
{position_data}

#================================================================================
# SCENARIO {config.scenario_num:02d} CONFIGURATION NOTES
#================================================================================
# {config.description}
#
# This baseline template will be processed by gen_omnet_scenarios.py to create
# multiple sub-scenario configurations with different parameter combinations.
#
# Key scenario {config.scenario_num:02d} parameters:
# - Initial SF: {config.initial_sf} (DR{12-config.initial_sf})
# - Initial TP: {config.initial_tp} dBm  
# - Packet interval: {config.packet_interval_sec}s ({config.packet_interval_sec//60} minutes)
# - Simulation time: {config.sim_time_min} minutes
# - Path loss sigma: {config.sigma} dB
# - Devices: {config.num_devices}, Gateways: {config.num_gateways}
'''

    output_file.write_text(template_content)
    return str(output_file)

def create_predefined_scenarios():
    """Define the predefined scenario configurations"""
    return {
        1: ScenarioConfig(
            scenario_num=1,
            scenario_name="baseline",
            description="Baseline Reference Case with configurable SF/TP initialization and ADR",
            sim_time_min=600,
            packet_interval_sec=600,
            initial_sf=10,
            initial_tp=14,
            sigma=3.57,
            num_devices=100,
            num_gateways=1,
            position_file_path="omnet_positions/01_baseline_positions.ini"
        ),
        2: ScenarioConfig(
            scenario_num=2,
            scenario_name="adr-comparison", 
            description="ADR Effectiveness Comparison: Fixed SF12 vs ADR-enabled adaptation",
            sim_time_min=500,
            packet_interval_sec=300,
            initial_sf=12,
            initial_tp=14,
            sigma=5.0,
            num_devices=100,
            num_gateways=1,
            position_file_path="omnet_positions/02_adr_positions.ini"
        ),
        3: ScenarioConfig(
            scenario_num=3,
            scenario_name="sf-impact",
            description="Spreading Factor Impact Analysis on network performance",
            sim_time_min=300,
            packet_interval_sec=600,
            initial_sf=10,
            initial_tp=14,
            sigma=4.0,
            num_devices=100,
            num_gateways=1,
            position_file_path="omnet_positions/03_sf_impact_positions.ini"
        ),
        4: ScenarioConfig(
            scenario_num=4,
            scenario_name="confirmed",
            description="Confirmed vs Unconfirmed packet transmission comparison", 
            sim_time_min=400,
            packet_interval_sec=600,
            initial_sf=10,
            initial_tp=14,
            sigma=3.5,
            num_devices=100,
            num_gateways=1,
            position_file_path="omnet_positions/04_confirmed_positions.ini"
        ),
        5: ScenarioConfig(
            scenario_num=5,
            scenario_name="traffic",
            description="Traffic Load Analysis with varying packet intervals and load patterns",
            sim_time_min=300,
            packet_interval_sec=300,
            initial_sf=10,
            initial_tp=14,
            sigma=4.0,
            num_devices=100,
            num_gateways=1,
            position_file_path="omnet_positions/05_traffic_positions.ini"
        ),
        6: ScenarioConfig(
            scenario_num=6,
            scenario_name="collision",
            description="Collision Analysis with high interference and packet collision scenarios",
            sim_time_min=250,
            packet_interval_sec=180,
            initial_sf=7,
            initial_tp=14,
            sigma=6.0,
            num_devices=150,
            num_gateways=1,
            position_file_path="omnet_positions/06_collision_positions.ini"
        ),
        7: ScenarioConfig(
            scenario_num=7,
            scenario_name="propagation",
            description="Propagation Model Comparison across different path loss models",
            sim_time_min=400,
            packet_interval_sec=600,
            initial_sf=10,
            initial_tp=14,
            sigma=4.5,
            num_devices=100,
            num_gateways=1,
            position_file_path="omnet_positions/07_propagation_positions.ini"
        ),
        8: ScenarioConfig(
            scenario_num=8,
            scenario_name="multigw-1gw",
            description="Multi-Gateway Performance with 1 gateway configuration (baseline)", 
            sim_time_min=400,
            packet_interval_sec=600,
            initial_sf=10,
            initial_tp=14,
            sigma=3.5,
            num_devices=100,
            num_gateways=1,
            position_file_path="omnet_positions/08_multigw_1gw_positions.ini"
        ),
        9: ScenarioConfig(
            scenario_num=9,
            scenario_name="multigw-2gw",
            description="Multi-Gateway Performance with 2 gateway configuration", 
            sim_time_min=400,
            packet_interval_sec=600,
            initial_sf=10,
            initial_tp=14,
            sigma=3.5,
            num_devices=100,
            num_gateways=2,
            position_file_path="omnet_positions/08_multigw_2gw_positions.ini"
        ),
        10: ScenarioConfig(
            scenario_num=10,
            scenario_name="multigw-4gw",
            description="Multi-Gateway Performance with 4 gateway configuration", 
            sim_time_min=400,
            packet_interval_sec=600,
            initial_sf=10,
            initial_tp=14,
            sigma=3.5,
            num_devices=100,
            num_gateways=4,
            position_file_path="omnet_positions/08_multigw_4gw_positions.ini"
        )
    }

def main():
    parser = argparse.ArgumentParser(
        description="Generate OMNeT++ baseline template files for LoRa scenarios",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate all predefined scenarios
  python generate_omnet_baselines.py --all
  
  # Generate specific scenarios
  python generate_omnet_baselines.py --scenarios 1 2
  
  # Generate custom scenario
  python generate_omnet_baselines.py --custom \\
    --scenario-num 6 \\
    --scenario-name "custom-test" \\
    --description "Custom test scenario" \\
    --sim-time 300 \\
    --packet-interval 120 \\
    --initial-sf 8 \\
    --position-file "custom_positions.ini"
        """
    )
    
    parser.add_argument("--all", action="store_true",
                        help="Generate all predefined scenarios")
    parser.add_argument("--scenarios", type=int, nargs="+",
                        help="Generate specific scenario numbers (1-5)")
    parser.add_argument("--outdir", type=Path, default=Path("."),
                        help="Output directory for generated files")
    
    # Custom scenario options
    parser.add_argument("--custom", action="store_true",
                        help="Generate custom scenario with specified parameters")
    parser.add_argument("--scenario-num", type=int,
                        help="Scenario number for custom scenario")
    parser.add_argument("--scenario-name", type=str,
                        help="Scenario name for custom scenario")
    parser.add_argument("--description", type=str,
                        help="Scenario description")
    parser.add_argument("--sim-time", type=int, default=300,
                        help="Simulation time in minutes")
    parser.add_argument("--packet-interval", type=int, default=600,
                        help="Packet interval in seconds")
    parser.add_argument("--initial-sf", type=int, default=10,
                        help="Initial spreading factor (7-12)")
    parser.add_argument("--initial-tp", type=int, default=14,
                        help="Initial transmission power in dBm")
    parser.add_argument("--sigma", type=float, default=3.57,
                        help="Path loss sigma in dB")
    parser.add_argument("--num-devices", type=int, default=100,
                        help="Number of end devices")
    parser.add_argument("--num-gateways", type=int, default=1,
                        help="Number of gateways")
    parser.add_argument("--position-file", type=str,
                        help="Path to position file (required for custom)")
    
    args = parser.parse_args()
    
    # Create output directory
    args.outdir.mkdir(parents=True, exist_ok=True)
    
    predefined_scenarios = create_predefined_scenarios()
    generated_files = []
    
    if args.custom:
        # Validate custom scenario parameters
        if not args.scenario_num:
            parser.error("--scenario-num is required for custom scenarios")
        if not args.scenario_name:
            parser.error("--scenario-name is required for custom scenarios") 
        if not args.position_file:
            parser.error("--position-file is required for custom scenarios")
        if not args.description:
            parser.error("--description is required for custom scenarios")
            
        # Create custom scenario config
        custom_config = ScenarioConfig(
            scenario_num=args.scenario_num,
            scenario_name=args.scenario_name,
            description=args.description,
            sim_time_min=args.sim_time,
            packet_interval_sec=args.packet_interval,
            initial_sf=args.initial_sf,
            initial_tp=args.initial_tp,
            sigma=args.sigma,
            num_devices=args.num_devices,
            num_gateways=args.num_gateways,
            position_file_path=args.position_file
        )
        
        output_file = generate_baseline_template(custom_config, args.outdir)
        generated_files.append(output_file)
        print(f"Generated custom scenario: {output_file}")
        
    elif args.all:
        # Generate all predefined scenarios
        for scenario_num, config in predefined_scenarios.items():
            output_file = generate_baseline_template(config, args.outdir)
            generated_files.append(output_file)
            print(f"Generated scenario {scenario_num}: {output_file}")
            
    elif args.scenarios:
        # Generate specific scenarios
        for scenario_num in args.scenarios:
            if scenario_num not in predefined_scenarios:
                print(f"Warning: Scenario {scenario_num} not found in predefined scenarios")
                continue
            config = predefined_scenarios[scenario_num]
            output_file = generate_baseline_template(config, args.outdir)
            generated_files.append(output_file)
            print(f"Generated scenario {scenario_num}: {output_file}")
    else:
        parser.error("Must specify --all, --scenarios, or --custom")
    
    print(f"\nGenerated {len(generated_files)} baseline template files in: {args.outdir.resolve()}")
    print("These templates can now be used with gen_omnet_scenarios.py to create sub-scenarios.")

if __name__ == "__main__":
    main()