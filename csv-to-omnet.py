#!/usr/bin/env python3
"""
CSV to OMNET++ Flora Position Converter
Converts node positions from CSV format to OMNET++ Flora INI format
Supports both header and headerless CSV formats
"""

import pandas as pd
import argparse
import os
from pathlib import Path

def detect_csv_format(df):
    """
    Detect the format of the CSV file and return column mappings
    Handles both header and headerless CSV files
    """
    # Check if CSV has headers by examining first row
    first_row = df.iloc[0]
    has_headers = False
    
    # If first row contains strings that look like coordinates, it's probably headerless
    try:
        # Try to convert x,y,z columns to float - if they fail, probably has headers
        float(first_row.iloc[3])  # x coordinate
        float(first_row.iloc[4])  # y coordinate
        float(first_row.iloc[5])  # z coordinate
        # If we get here, first row has numeric coordinates, so no headers
        has_headers = False
    except (ValueError, IndexError):
        # First row contains non-numeric data, probably headers
        has_headers = True
    
    if not has_headers:
        # Headerless CSV - assume standard format: scenario,type,node_id,x,y,z
        print("🔍 Detected headerless CSV format")
        print("📋 Assuming column order: scenario,type,node_id,x,y,z")
        
        # Assign standard column names
        if len(df.columns) >= 6:
            df.columns = ['scenario', 'type', 'node_id', 'x', 'y', 'z']
        elif len(df.columns) >= 5:
            df.columns = ['scenario', 'type', 'node_id', 'x', 'y']
        else:
            print(f"❌ Error: Expected at least 5 columns, got {len(df.columns)}")
            return {}
        
        mapping = {
            'scenario': 'scenario',
            'type': 'type', 
            'node_id': 'node_id',
            'x': 'x',
            'y': 'y'
        }
        if 'z' in df.columns:
            mapping['z'] = 'z'
            
        return mapping
    
    else:
        # Has headers - use improved detection logic
        print("🔍 Detected CSV with headers")
        print(f"📋 Columns found: {list(df.columns)}")
        
        columns = [col.lower().strip() for col in df.columns]
        
        # Common column name patterns (more specific patterns first)
        x_patterns = ['x', 'pos_x', 'position_x', 'coord_x', 'longitude', 'lon']
        y_patterns = ['y', 'pos_y', 'position_y', 'coord_y', 'latitude', 'lat'] 
        z_patterns = ['z', 'pos_z', 'position_z', 'coord_z', 'height', 'altitude']
        node_patterns = ['id', 'node_id', 'nodeid', 'node', 'device_id', 'deviceid']  # Put 'id' first for exact match
        type_patterns = ['type', 'node_type', 'nodetype', 'device_type', 'devicetype']
        scenario_patterns = ['scenario', 'scenario_id', 'scenarioid', 'scene']
        
        mapping = {}
        
        # Find column mappings with exact matches preferred
        for i, col in enumerate(columns):
            original_col = df.columns[i]
            
            # Try exact matches first, then pattern matches
            if col == 'x':
                mapping['x'] = original_col
            elif col == 'y':
                mapping['y'] = original_col
            elif col == 'z':
                mapping['z'] = original_col
            elif col == 'id':
                mapping['node_id'] = original_col
            elif col == 'type':
                mapping['type'] = original_col
            elif col == 'scenario':
                mapping['scenario'] = original_col
            # Pattern matching fallback
            elif not mapping.get('x') and any(pattern in col for pattern in x_patterns):
                mapping['x'] = original_col
            elif not mapping.get('y') and any(pattern in col for pattern in y_patterns):
                mapping['y'] = original_col
            elif not mapping.get('z') and any(pattern in col for pattern in z_patterns):
                mapping['z'] = original_col
            elif not mapping.get('node_id') and any(pattern in col for pattern in node_patterns):
                mapping['node_id'] = original_col
            elif not mapping.get('type') and any(pattern in col for pattern in type_patterns):
                mapping['type'] = original_col
            elif not mapping.get('scenario') and any(pattern in col for pattern in scenario_patterns):
                mapping['scenario'] = original_col
        
        return mapping

def convert_positions_to_omnet(csv_file, output_dir="omnet_positions", 
                              node_height=1.5, gateway_height=15.0,
                              debug=False, target_scenario=None):
    """
    Convert CSV positions to OMNET++ Flora format
    
    Args:
        csv_file: Path to input CSV file
        output_dir: Directory for output files
        node_height: Default height for end devices (meters)
        gateway_height: Default height for gateways (meters)
        debug: Enable debug output
        target_scenario: Process only specific scenario
    """
    
    # Read CSV file - try with headers first
    try:
        # First, try reading with headers to detect format
        df_test = pd.read_csv(csv_file, nrows=5)
        
        # Check if first row looks like data (headerless) or headers
        first_row = df_test.iloc[0]
        try:
            # If we can convert the first few columns to numbers, it's probably headerless
            float(first_row.iloc[0])  # This would be scenario column in headerless format
            has_headers = False
        except (ValueError, TypeError):
            # First column is text, probably headers
            has_headers = True
        
        # Read the full file with or without headers
        if has_headers:
            df = pd.read_csv(csv_file)
            print(f"✅ Loaded CSV file with headers: {csv_file}")
        else:
            df = pd.read_csv(csv_file, header=None)
            print(f"✅ Loaded headerless CSV file: {csv_file}")
        
        print(f"📊 Total rows: {len(df)}")
        print(f"📋 Columns detected: {list(df.columns)}")
        
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return
    
    # Detect CSV format and get column mappings
    mapping = detect_csv_format(df)
    print(f"🔍 Detected column mapping: {mapping}")
    
    # Validate required columns
    required_cols = ['x', 'y', 'scenario']
    missing_cols = [col for col in required_cols if col not in mapping]
    if missing_cols:
        print(f"❌ Missing required columns: {missing_cols}")
        print("Available mappings:", list(mapping.keys()))
        print("Detected columns:", list(df.columns))
        return
    
    # Create output directory
    Path(output_dir).mkdir(exist_ok=True)
    
    # Process by scenario if scenario column exists
    if 'scenario' in mapping:
        scenarios = df[mapping['scenario']].unique()
        print(f"🗂 Found {len(scenarios)} scenarios: {sorted(scenarios)}")
        
        # Show what the output filenames will be
        if not target_scenario:
            print("📄 Output files will be:")
            for s in sorted(scenarios):
                clean_s = str(s)
                if clean_s.lower().startswith('scenario_'):
                    clean_s = clean_s[9:]
                print(f"   • {clean_s}_positions.ini (from scenario '{s}')")
        
        # Filter to target scenario if specified
        if target_scenario:
            # Try exact match first
            matching_scenarios = [s for s in scenarios if str(s) == target_scenario]
            
            # If no exact match, try matching cleaned names or partial matches
            if not matching_scenarios:
                matching_scenarios = [s for s in scenarios if target_scenario in str(s).lower()]
            
            if not matching_scenarios:
                # Try matching with "scenario_" prefix
                target_with_prefix = f"scenario_{target_scenario}"
                matching_scenarios = [s for s in scenarios if str(s).lower() == target_with_prefix.lower()]
            
            if matching_scenarios:
                scenarios = matching_scenarios
                print(f"🎯 Processing scenario(s): {scenarios}")
            else:
                print(f"❌ Target scenario '{target_scenario}' not found in data")
                print(f"Available scenarios: {sorted(scenarios)}")
                return
        
        for scenario in scenarios:
            scenario_df = df[df[mapping['scenario']] == scenario]
            
            if debug:
                print(f"\n🐛 DEBUG - Scenario {scenario}:")
                print(f"   Total rows: {len(scenario_df)}")
                if 'type' in mapping:
                    type_counts = scenario_df[mapping['type']].value_counts()
                    print(f"   Node types: {dict(type_counts)}")
                    
                    # Show sample of each type
                    for node_type in type_counts.index[:3]:  # Limit to first 3 types
                        sample = scenario_df[scenario_df[mapping['type']] == node_type].head(2)
                        print(f"   Sample {node_type} nodes:")
                        for _, row in sample.iterrows():
                            node_id_val = row[mapping['node_id']] if 'node_id' in mapping else 'N/A'
                            type_val = row[mapping['type']] if 'type' in mapping else 'N/A'
                            print(f"     ID: {node_id_val}, Type: {type_val}, Pos: ({row[mapping['x']]:.1f}, {row[mapping['y']]:.1f})")
            
            # Clean scenario name for filename (remove redundant "scenario_" prefix)
            clean_scenario = str(scenario)
            if clean_scenario.lower().startswith('scenario_'):
                clean_scenario = clean_scenario[9:]  # Remove "scenario_" prefix
            
            if debug:
                print(f"📁 Output file: {output_dir}/{clean_scenario}_positions.ini")
            
            output_file = f"{output_dir}/{clean_scenario}_positions.ini"
            _write_omnet_positions(scenario_df, output_file, mapping, 
                                 scenario, node_height, gateway_height, debug)
    else:
        # Single scenario
        output_file = f"{output_dir}/positions.ini"
        _write_omnet_positions(df, output_file, mapping, 
                             "default", node_height, gateway_height, debug)

def _write_omnet_positions(df, output_file, mapping, scenario_name, 
                          node_height, gateway_height, debug=False):
    """
    Write positions for a single scenario to OMNET++ Flora format
    """
    
    with open(output_file, 'w') as f:
        f.write("#" + "="*80 + "\n")
        f.write(f"# OMNET++ Flora Node Positions - Scenario {scenario_name}\n")
        f.write(f"# Generated from CSV data\n")
        f.write(f"# Total nodes: {len(df)}\n")
        f.write("#" + "="*80 + "\n\n")
        
        # Separate nodes by type if type column exists
        if 'type' in mapping:
            # First pass: collect all gateways and end devices separately
            gateways = []
            end_devices = []
            
            for idx, row in df.iterrows():
                node_type = str(row[mapping['type']]).lower().strip()
                if 'gateway' in node_type or 'gw' in node_type:
                    gateways.append(row)
                else:
                    end_devices.append(row)
            
            # Sort by ID if available to maintain consistent ordering
            if 'node_id' in mapping:
                try:
                    gateways = sorted(gateways, key=lambda x: int(x[mapping['node_id']]))
                    end_devices = sorted(end_devices, key=lambda x: int(x[mapping['node_id']]))
                except (ValueError, TypeError):
                    # If sorting fails, keep original order
                    pass
            
            if debug:
                print(f"🐛 DEBUG - After sorting:")
                gw_ids = [row[mapping['node_id']] if 'node_id' in mapping else 'N/A' for row in gateways]
                ed_ids = [row[mapping['node_id']] if 'node_id' in mapping else 'N/A' for row in end_devices[:5]]
                print(f"   Gateways: {gw_ids}")
                print(f"   First 5 end devices: {ed_ids}")
            
            print(f"📡 Scenario {scenario_name} - {len(end_devices)} end devices, {len(gateways)} gateways")
            
            # Write gateways first (sorted by ID)
            if gateways:
                f.write(f"# GATEWAY POSITIONS ({len(gateways)} gateways)\n")
                f.write("#" + "="*50 + "\n")
                
                for gw_idx, row in enumerate(gateways):
                    x = float(row[mapping['x']])
                    y = float(row[mapping['y']])
                    z = float(row[mapping['z']]) if 'z' in mapping else gateway_height
                    
                    # Add original ID as comment for debugging
                    if 'node_id' in mapping:
                        f.write(f"# Original ID: {row[mapping['node_id']]}\n")
                    
                    f.write(f"**.loRaGW[{gw_idx}].**.initialX = {x:.2f}m\n")
                    f.write(f"**.loRaGW[{gw_idx}].**.initialY = {y:.2f}m\n")
                    f.write(f"**.loRaGW[{gw_idx}].**.initialZ = {z:.1f}m\n\n")
            
            # Write end devices (sorted by ID)
            if end_devices:
                f.write(f"# END DEVICE POSITIONS ({len(end_devices)} nodes)\n")
                f.write("#" + "="*50 + "\n")
                
                for ed_idx, row in enumerate(end_devices):
                    x = float(row[mapping['x']])
                    y = float(row[mapping['y']])
                    z = float(row[mapping['z']]) if 'z' in mapping else node_height
                    
                    # Add original ID as comment every 10 nodes to reduce clutter
                    if 'node_id' in mapping and ed_idx % 10 == 0:
                        f.write(f"# Original IDs starting from {row[mapping['node_id']]}...\n")
                    
                    f.write(f"**.loRaNodes[{ed_idx}].**.initialX = {x:.2f}m\n")
                    f.write(f"**.loRaNodes[{ed_idx}].**.initialY = {y:.2f}m\n")
                    f.write(f"**.loRaNodes[{ed_idx}].**.initialZ = {z:.1f}m\n")
                
                f.write("\n")
            
            # Summary with actual counts from CSV data
            f.write(f"# NETWORK SUMMARY\n")
            f.write("#" + "="*50 + "\n")
            f.write(f"# Actual node counts from CSV data:\n")
            f.write(f"# - End devices: {len(end_devices)}\n")
            f.write(f"# - Gateways: {len(gateways)}\n")
            f.write(f"# - Total nodes: {len(end_devices) + len(gateways)}\n")
            f.write(f"#\n")
            f.write(f"# OMNET++ Configuration Parameters:\n")
            f.write(f"**.numberOfNodes = {len(end_devices)}\n")
            f.write(f"**.numberOfGateways = {len(gateways)}\n")
            
            # Add gateway-specific configuration based on actual count
            if len(gateways) > 1:
                f.write(f"#\n")
                f.write(f"# Multi-gateway scenario configuration:\n")
                f.write(f"# Set up {len(gateways)} gateways in your network configuration\n")
                for i in range(len(gateways)):
                    f.write(f"# Gateway {i}: loRaGW[{i}]\n")
            
            f.write(f"\n")
            
        else:
            # No type column - sort by node_id if available, otherwise use order
            df_sorted = df.copy()
            if 'node_id' in mapping:
                try:
                    df_sorted = df_sorted.sort_values(by=mapping['node_id'])
                except:
                    pass  # Keep original order if sorting fails
            
            # Assume last node is gateway, rest are end devices
            total_nodes = len(df_sorted)
            end_devices_count = total_nodes - 1
            
            print(f"📡 Scenario {scenario_name} - {end_devices_count} end devices, 1 gateway (assumed)")
            
            # Write end devices first
            f.write(f"# END DEVICE POSITIONS ({end_devices_count} nodes)\n")
            f.write("#" + "="*50 + "\n")
            
            for idx, (_, row) in enumerate(df_sorted.iterrows()):
                if idx < end_devices_count:
                    x = float(row[mapping['x']])
                    y = float(row[mapping['y']])
                    z = float(row[mapping['z']]) if 'z' in mapping else node_height
                    
                    f.write(f"**.loRaNodes[{idx}].**.initialX = {x:.2f}m\n")
                    f.write(f"**.loRaNodes[{idx}].**.initialY = {y:.2f}m\n")
                    f.write(f"**.loRaNodes[{idx}].**.initialZ = {z:.1f}m\n")
            
            f.write("\n")
            
            # Write gateway (last node)
            f.write(f"# GATEWAY POSITION (1 gateway)\n")
            f.write("#" + "="*50 + "\n")
            
            last_row = df_sorted.iloc[-1]
            x = float(last_row[mapping['x']])
            y = float(last_row[mapping['y']])
            z = gateway_height  # Always use gateway height for gateway
            
            f.write(f"**.loRaGW[0].**.initialX = {x:.2f}m\n")
            f.write(f"**.loRaGW[0].**.initialY = {y:.2f}m\n")
            f.write(f"**.loRaGW[0].**.initialZ = {z:.1f}m\n\n")
            
            # Summary
            f.write(f"# NETWORK SUMMARY\n")
            f.write("#" + "="*50 + "\n")
            f.write(f"**.numberOfNodes = {end_devices_count}\n")
            f.write(f"**.numberOfGateways = 1\n")
    
    print(f"✅ Generated: {output_file}")

def create_sample_csv():
    """
    Create a sample CSV file for testing (headerless format)
    """
    import numpy as np
    
    # Sample data for multiple scenarios - headerless format
    data = []
    
    # Scenario 1: Baseline (100 devices + 1 gateway)
    np.random.seed(12345)
    for i in range(100):
        data.append([
            'scenario_01_baseline',
            'enddevice',
            i,
            np.random.uniform(0, 5000),
            np.random.uniform(0, 5000),
            1.5
        ])
    # Gateway at center
    data.append([
        'scenario_01_baseline',
        'gateway',
        100,
        2500,
        2500,
        15.0
    ])
    
    # Scenario 6: Collision test (50 devices + 1 gateway with near/far placement)
    for i in range(25):  # Near devices
        angle = np.random.uniform(0, 2*np.pi)
        radius = np.random.uniform(50, 150)
        data.append([
            'scenario_06_collision',
            'enddevice_near',
            i,
            2500 + radius * np.cos(angle),
            2500 + radius * np.sin(angle),
            1.5
        ])
    
    for i in range(25, 50):  # Far devices
        angle = np.random.uniform(0, 2*np.pi)
        radius = np.random.uniform(450, 500)
        data.append([
            'scenario_06_collision',
            'enddevice_far',
            i,
            2500 + radius * np.cos(angle),
            2500 + radius * np.sin(angle),
            1.5
        ])
    
    # Gateway at center for scenario 6
    data.append([
        'scenario_06_collision',
        'gateway',
        50,
        2500,
        2500,
        15.0
    ])
    
    # Scenario 8: Multi-gateway like your example
    np.random.seed(42)
    for i in range(50):
        data.append([
            'scenario_08_multigw_4gw',
            'enddevice',
            i,
            np.random.uniform(-1500, 1500),
            np.random.uniform(-1500, 1500),
            1.5
        ])
    
    # Four gateways in corners like your example
    data.append(['scenario_08_multigw_4gw', 'gateway', 0, -1000.0, -1000.0, 15.0])
    data.append(['scenario_08_multigw_4gw', 'gateway', 1, 1000.0, -1000.0, 15.0])
    data.append(['scenario_08_multigw_4gw', 'gateway', 2, -1000.0, 1000.0, 15.0])
    data.append(['scenario_08_multigw_4gw', 'gateway', 3, 1000.0, 1000.0, 15.0])
    
    df = pd.DataFrame(data)
    df.to_csv('sample_positions.csv', index=False, header=False)
    print("✅ Created sample_positions.csv (headerless format) with multiple scenarios")
    print("📋 Format: scenario,type,node_id,x,y,z")
    return df

def main():
    parser = argparse.ArgumentParser(description='Convert CSV positions to OMNET++ Flora format')
    parser.add_argument('csv_file', nargs='?', help='Input CSV file path')
    parser.add_argument('--output-dir', '-o', default='omnet_positions', 
                       help='Output directory (default: omnet_positions)')
    parser.add_argument('--node-height', type=float, default=1.5,
                       help='Default end device height in meters (default: 1.5)')
    parser.add_argument('--gateway-height', type=float, default=15.0,
                       help='Default gateway height in meters (default: 15.0)')
    parser.add_argument('--create-sample', action='store_true',
                       help='Create a sample CSV file for testing')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug output')
    parser.add_argument('--scenario', type=str, 
                       help='Process only specific scenario (e.g., "08_multigw_4gw" or "scenario_08_multigw_4gw")')
    
    args = parser.parse_args()
    
    if args.create_sample:
        create_sample_csv()
        return
    
    if not args.csv_file:
        print("❌ Please provide a CSV file path or use --create-sample")
        parser.print_help()
        return
    
    if not os.path.exists(args.csv_file):
        print(f"❌ CSV file not found: {args.csv_file}")
        return
    
    # Add debug parameter
    convert_positions_to_omnet(
        args.csv_file, 
        args.output_dir,
        args.node_height, 
        args.gateway_height,
        debug=args.debug,
        target_scenario=args.scenario
    )
    
    print(f"\n🎯 Conversion complete!")
    print(f"📁 Output files saved in: {args.output_dir}/")
    print(f"📄 Include the generated .ini files in your OMNET++ configuration")
    print(f"\nExample usage in your scenario INI:")
    if args.scenario:
        # Clean the scenario name for example
        clean_scenario = args.scenario
        if clean_scenario.lower().startswith('scenario_'):
            clean_scenario = clean_scenario[9:]
        print(f"include {args.output_dir}/{clean_scenario}_positions.ini")
    else:
        print(f"# Include individual scenario files:")
        print(f"include {args.output_dir}/01_baseline_positions.ini")
        print(f"include {args.output_dir}/08_multigw_4gw_positions.ini  # 4-gateway scenario")
        print(f"# or process specific scenarios with --scenario parameter")
    print(f"\n📋 Generated files use proper Flora indexing:")
    print(f"   • End devices: **.loRaNodes[0], **.loRaNodes[1], ...")
    print(f"   • Gateways: **.loRaGW[0], **.loRaGW[1], ...")
    print(f"   • Node counts automatically detected from CSV data")
    print(f"   • Multi-gateway scenarios fully supported")
    if args.debug:
        print(f"\n🐛 Debug mode was enabled - check output for detailed information")

if __name__ == "__main__":
    main()