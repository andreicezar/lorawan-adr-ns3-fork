#!/usr/bin/env python3
"""
Generate consistent device and gateway positions for all ns-3 LoRaWAN scenarios.
Scenarios with the same number of devices and topology type use identical positions
to ensure fair comparison of protocol features.
"""

import numpy as np
import pandas as pd
import os
from typing import List, Tuple, Dict
import argparse

# Default seed for reproducibility (same as you'd use in ns-3)
DEFAULT_SEED = 12345

def set_seed(seed: int):
    """Set random seed for reproducibility"""
    np.random.seed(seed)

def generate_uniform_square_positions(n_devices: int, area_size: float, 
                                     min_distance: float = 10.0) -> np.ndarray:
    """
    Generate uniformly distributed positions in a square area.
    
    Args:
        n_devices: Number of devices
        area_size: Side length of square area in meters
        min_distance: Minimum distance from center (to avoid gateway overlap)
    
    Returns:
        Array of shape (n_devices, 3) with x, y, z coordinates
    """
    print(f"  🎯 Generating {n_devices} uniform positions in {area_size}m area...")
    positions = np.zeros((n_devices, 3))
    half_size = area_size / 2
    
    for i in range(n_devices):
        while True:
            x = np.random.uniform(-half_size, half_size)
            y = np.random.uniform(-half_size, half_size)
            # Ensure minimum distance from center (where gateway typically is)
            if np.sqrt(x**2 + y**2) >= min_distance:
                break
        positions[i] = [x, y, 1.5]  # 1.5m height for end devices
    
    # Validation
    assert positions.shape[0] == n_devices, f"Expected {n_devices} devices, got {positions.shape[0]}"
    print(f"  ✅ Generated exactly {positions.shape[0]} device positions")
    return positions

def generate_radial_positions(n_devices: int, min_radius: float, 
                             max_radius: float) -> np.ndarray:
    """
    Generate positions in a radial pattern (for propagation testing).
    
    Args:
        n_devices: Number of devices
        min_radius: Minimum distance from center
        max_radius: Maximum distance from center
    
    Returns:
        Array of shape (n_devices, 3) with x, y, z coordinates
    """
    print(f"  🎯 Generating {n_devices} radial positions ({min_radius}-{max_radius}m)...")
    positions = np.zeros((n_devices, 3))
    
    for i in range(n_devices):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(min_radius, max_radius)
        positions[i] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            1.5
        ]
    
    # Validation
    assert positions.shape[0] == n_devices, f"Expected {n_devices} devices, got {positions.shape[0]}"
    print(f"  ✅ Generated exactly {positions.shape[0]} device positions")
    return positions

def generate_near_far_rings(n_devices: int, near_min: float, near_max: float,
                           far_min: float, far_max: float) -> np.ndarray:
    """
    Generate positions in near and far rings (for capture effect testing).
    
    Args:
        n_devices: Number of devices
        near_min/max: Near ring radius range
        far_min/max: Far ring radius range
    
    Returns:
        Array of shape (n_devices, 3) with x, y, z coordinates
    """
    print(f"  🎯 Generating {n_devices} near/far ring positions...")
    positions = np.zeros((n_devices, 3))
    half = n_devices // 2
    
    # Near ring
    for i in range(half):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(near_min, near_max)
        positions[i] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            1.5
        ]
    
    # Far ring
    for i in range(half, n_devices):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(far_min, far_max)
        positions[i] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            1.5
        ]
    
    # Validation
    assert positions.shape[0] == n_devices, f"Expected {n_devices} devices, got {positions.shape[0]}"
    print(f"  ✅ Generated exactly {positions.shape[0]} device positions ({half} near, {n_devices-half} far)")
    return positions

def get_gateway_positions(n_gateways: int, spacing: float = 2000) -> np.ndarray:
    """
    Get gateway positions based on number of gateways.
    
    Args:
        n_gateways: Number of gateways (1, 2, or 4)
        spacing: Distance between gateways for multi-gateway scenarios
    
    Returns:
        Array of shape (n_gateways, 3) with x, y, z coordinates
    """
    if n_gateways == 1:
        positions = np.array([[0, 0, 15]])
    elif n_gateways == 2:
        positions = np.array([
            [-spacing/2, 0, 15],
            [spacing/2, 0, 15]
        ])
    elif n_gateways == 4:
        positions = np.array([
            [-spacing/2, -spacing/2, 15],
            [spacing/2, -spacing/2, 15],
            [-spacing/2, spacing/2, 15],
            [spacing/2, spacing/2, 15]
        ])
    else:
        raise ValueError(f"Unsupported number of gateways: {n_gateways}")
    
    # Validation
    assert positions.shape[0] == n_gateways, f"Expected {n_gateways} gateways, got {positions.shape[0]}"
    return positions

def generate_base_device_positions(base_seed: int = DEFAULT_SEED) -> Dict:
    """
    Generate base device position sets that will be reused across scenarios.
    This ensures scenarios with the same number of devices use identical positions.
    
    Args:
        base_seed: Base random seed to use
    
    Returns:
        Dictionary with position sets for different device counts and types
    """
    position_sets = {}
    
    # Standard uniform distributions for protocol comparison scenarios
    # These will be reused across scenarios testing different protocol features
    
    # 100 devices - uniform 5km area (for baseline, ADR, confirmed, traffic scenarios)
    set_seed(base_seed + 100)
    positions_100 = generate_uniform_square_positions(100, 5000)
    position_sets['uniform_100_5km'] = positions_100
    print(f"📄 Generated standard 100-device positions (5km area) - Shape: {positions_100.shape}")
    
    # 50 devices - uniform 3km area (for SF impact scenario)
    set_seed(base_seed + 50)
    positions_50 = generate_uniform_square_positions(50, 3000)
    position_sets['uniform_50_3km'] = positions_50
    print(f"📄 Generated standard 50-device positions (3km area) - Shape: {positions_50.shape}")
    
    # 200 devices - uniform 3km area (for multi-gateway scenarios)
    set_seed(base_seed + 200)
    positions_200 = generate_uniform_square_positions(200, 3000)
    position_sets['uniform_200_3km'] = positions_200
    print(f"📄 Generated standard 200-device positions (3km area) - Shape: {positions_200.shape}")
    
    # Special topology-specific position sets
    # These are used for scenarios that specifically test topology effects
    
    # 50 devices - near/far rings (for collision/capture effect testing)
    set_seed(base_seed + 20)
    positions_nearfar = generate_near_far_rings(50, 50, 150, 450, 500)
    position_sets['nearfar_50'] = positions_nearfar
    print(f"📄 Generated near/far ring 50-device positions (collision testing) - Shape: {positions_nearfar.shape}")
    
    # 50 devices - radial pattern (for propagation model testing)
    set_seed(base_seed + 51)  # Different from uniform_50 to avoid confusion
    positions_radial = generate_radial_positions(50, 100, 5000)
    position_sets['radial_50'] = positions_radial
    print(f"📄 Generated radial 50-device positions (propagation testing) - Shape: {positions_radial.shape}")
    
    return position_sets

def generate_scenario_positions(base_seed: int = DEFAULT_SEED) -> Dict:
    """
    Generate positions for all scenarios using consistent position sets.
    
    Args:
        base_seed: Base random seed to use
    
    Returns:
        Dictionary with scenario names as keys and position data as values
    """
    # First, generate the base position sets
    print("🏗 Generating base position sets for consistent comparisons...")
    position_sets = generate_base_device_positions(base_seed)
    
    scenarios = {}
    
    print("\n🎯 Assigning positions to scenarios...")
    
    # Protocol comparison scenarios - these use IDENTICAL positions
    # Only protocol settings differ, not node placement
    protocol_scenarios = [
        ('scenario_01_baseline', 'Baseline configuration'),
        ('scenario_02_adr', 'ADR enabled'),
        ('scenario_04_confirmed', 'Confirmed messages'),
        ('scenario_05_traffic', 'Different traffic patterns')
    ]
    
    for scenario_name, description in protocol_scenarios:
        device_positions = position_sets['uniform_100_5km'].copy()
        gateway_positions = get_gateway_positions(1)
        
        scenarios[scenario_name] = {
            'devices': device_positions.shape[0],  # Use actual count
            'gateways': gateway_positions.shape[0],  # Use actual count
            'area_size': 5000,
            'device_positions': device_positions,
            'gateway_positions': gateway_positions,
            'description': description,
            'position_type': 'uniform_100_5km'
        }
        print(f"  ✅ {scenario_name}: {description} ({device_positions.shape[0]} devices, {gateway_positions.shape[0]} gateways)")
    
    # SF Impact scenario - different area size but consistent positions
    device_positions = position_sets['uniform_50_3km'].copy()
    gateway_positions = get_gateway_positions(1)
    
    scenarios['scenario_03_sf_impact'] = {
        'devices': device_positions.shape[0],
        'gateways': gateway_positions.shape[0],
        'area_size': 3000,
        'device_positions': device_positions,
        'gateway_positions': gateway_positions,
        'description': 'Spreading Factor impact testing',
        'position_type': 'uniform_50_3km'
    }
    print(f"  ✅ scenario_03_sf_impact: SF impact testing ({device_positions.shape[0]} devices, {gateway_positions.shape[0]} gateways)")
    
    # Topology-specific scenarios - these NEED different positions by design
    device_positions = position_sets['nearfar_50'].copy()
    gateway_positions = get_gateway_positions(1)
    
    scenarios['scenario_06_collision'] = {
        'devices': device_positions.shape[0],
        'gateways': gateway_positions.shape[0],
        'area_size': 1000,
        'device_positions': device_positions,
        'gateway_positions': gateway_positions,
        'description': 'Collision/capture effect testing (near/far topology)',
        'position_type': 'nearfar_50'
    }
    print(f"  ✅ scenario_06_collision: Collision testing ({device_positions.shape[0]} devices, {gateway_positions.shape[0]} gateways)")
    
    device_positions = position_sets['radial_50'].copy()
    gateway_positions = get_gateway_positions(1)
    
    scenarios['scenario_07_propagation'] = {
        'devices': device_positions.shape[0],
        'gateways': gateway_positions.shape[0],
        'area_size': 10000,
        'device_positions': device_positions,
        'gateway_positions': gateway_positions,
        'description': 'Propagation model testing (radial topology)',
        'position_type': 'radial_50'
    }
    print(f"  ✅ scenario_07_propagation: Propagation testing ({device_positions.shape[0]} devices, {gateway_positions.shape[0]} gateways)")
    
    # Multi-gateway scenarios - these use IDENTICAL device positions
    # Only gateway configuration differs, not device placement
    multi_gw_configs = [
        (1, 'Single gateway'),
        (2, 'Dual gateway'),
        (4, 'Quad gateway')
    ]
    
    shared_device_positions = position_sets['uniform_200_3km'].copy()
    
    for n_gw, description in multi_gw_configs:
        scenario_name = f'scenario_08_multigw_{n_gw}gw'
        gateway_positions = get_gateway_positions(n_gw, spacing=2000)
        
        scenarios[scenario_name] = {
            'devices': shared_device_positions.shape[0],  # Use actual count
            'gateways': gateway_positions.shape[0],  # Use actual count
            'area_size': 3000,
            'device_positions': shared_device_positions.copy(),  # Same device positions!
            'gateway_positions': gateway_positions,
            'description': f'Multi-gateway testing: {description}',
            'position_type': 'uniform_200_3km'
        }
        print(f"  ✅ {scenario_name}: {description} ({shared_device_positions.shape[0]} devices, {gateway_positions.shape[0]} gateways)")
    
    return scenarios

def export_positions_to_csv(scenarios: Dict, output_file: str, base_seed: int):
    """
    Export all scenario positions to a single CSV file with metadata.
    
    Args:
        scenarios: Dictionary with scenario data
        output_file: Output CSV filename
        base_seed: Random seed used for generation
    """
    all_data = []
    
    print("\n📊 Exporting to CSV with validation...")
    
    for scenario_name, data in scenarios.items():
        scenario_data = []
        
        # Add gateway positions
        gateway_count = 0
        for i, gw_pos in enumerate(data['gateway_positions']):
            scenario_data.append({
                'scenario': scenario_name,
                'type': 'gateway',
                'id': i,
                'x': gw_pos[0],
                'y': gw_pos[1],
                'z': gw_pos[2]
            })
            gateway_count += 1
        
        # Add device positions
        device_count = 0
        for i, dev_pos in enumerate(data['device_positions']):
            scenario_data.append({
                'scenario': scenario_name,
                'type': 'enddevice',  # Changed from 'endnode' for consistency
                'id': i,
                'x': dev_pos[0],
                'y': dev_pos[1],
                'z': dev_pos[2]
            })
            device_count += 1
        
        # Validation
        expected_devices = data['devices']
        expected_gateways = data['gateways']
        
        if device_count != expected_devices:
            raise ValueError(f"❌ {scenario_name}: Expected {expected_devices} devices, exported {device_count}")
        if gateway_count != expected_gateways:
            raise ValueError(f"❌ {scenario_name}: Expected {expected_gateways} gateways, exported {gateway_count}")
        
        print(f"  ✅ {scenario_name}: {device_count} devices + {gateway_count} gateways = {len(scenario_data)} total entries")
        all_data.extend(scenario_data)
    
    df = pd.DataFrame(all_data)
    df.to_csv(output_file, index=False, float_format='%.2f')
    print(f"\n✅ Positions exported to {output_file}")
    print(f"📊 Total CSV rows: {len(df)}")
    
    # Create a summary by scenario
    summary = df.groupby(['scenario', 'type']).size().unstack(fill_value=0)
    print(f"\n📋 CSV Content Summary:")
    print(summary)
    
    # Create a metadata file
    metadata_file = output_file.replace('.csv', '_metadata.txt')
    with open(metadata_file, 'w') as f:
        f.write(f"# LoRaWAN Scenario Positions Metadata\n")
        f.write(f"# Generated with seed: {base_seed}\n")
        f.write(f"# Generation strategy: Consistent positions for fair protocol comparison\n\n")
        
        f.write("## CSV Structure:\n")
        f.write("# Columns: scenario, type, id, x, y, z\n")
        f.write("# type: 'gateway' or 'enddevice'\n")
        f.write("# id: Sequential index within each type per scenario\n\n")
        
        f.write("## Per-Scenario Breakdown:\n")
        for scenario_name, data in scenarios.items():
            f.write(f"{scenario_name}:\n")
            f.write(f"  - Devices: {data['devices']} (type='enddevice')\n")
            f.write(f"  - Gateways: {data['gateways']} (type='gateway')\n")
            f.write(f"  - Total entries: {data['devices'] + data['gateways']}\n")
            f.write(f"  - Description: {data.get('description', 'No description')}\n\n")
        
        # Group scenarios by position type
        position_groups = {}
        for scenario_name, data in scenarios.items():
            pos_type = data.get('position_type', 'unknown')
            if pos_type not in position_groups:
                position_groups[pos_type] = []
            position_groups[pos_type].append((scenario_name, data))
        
        f.write("## Position Sharing Strategy:\n\n")
        for pos_type, group_scenarios in position_groups.items():
            f.write(f"### {pos_type.upper()}:\n")
            f.write(f"  Scenarios using identical device positions:\n")
            for scenario_name, data in group_scenarios:
                f.write(f"    - {scenario_name}: {data.get('description', 'No description')}\n")
            f.write(f"  Device count: {group_scenarios[0][1]['devices']}\n")
            f.write(f"  Rationale: {'Fair protocol comparison' if len(group_scenarios) > 1 else 'Topology-specific testing'}\n\n")
    
    print(f"📋 Metadata exported to {metadata_file}")

def main():
    parser = argparse.ArgumentParser(description='Generate LoRaWAN scenario positions with consistent placement')
    parser.add_argument('--output', default='scenario_positions.csv',
                       help='Output CSV filename (default: scenario_positions.csv)')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED,
                       help=f'Random seed (default: {DEFAULT_SEED})')
    parser.add_argument('--validate', action='store_true',
                       help='Run additional validation checks')
    
    args = parser.parse_args()
    
    # Use the provided seed
    seed_to_use = args.seed
    
    print(f"🔧 Generating CONSISTENT positions with seed: {seed_to_use}")
    print("🎯 Strategy: Same device positions for scenarios testing protocol differences")
    print("=" * 80)
    
    # Generate positions for all scenarios
    scenarios = generate_scenario_positions(seed_to_use)
    
    # Export to CSV with validation
    export_positions_to_csv(scenarios, args.output, seed_to_use)
    
    # Additional validation if requested
    if args.validate:
        print("\n🔍 Running additional validation...")
        df = pd.read_csv(args.output)
        
        print(f"📊 CSV validation:")
        print(f"  - Total rows: {len(df)}")
        print(f"  - Unique scenarios: {df['scenario'].nunique()}")
        print(f"  - Device entries: {len(df[df['type'] == 'enddevice'])}")
        print(f"  - Gateway entries: {len(df[df['type'] == 'gateway'])}")
        
        # Check each scenario
        for scenario in df['scenario'].unique():
            scenario_df = df[df['scenario'] == scenario]
            devices = len(scenario_df[scenario_df['type'] == 'enddevice'])
            gateways = len(scenario_df[scenario_df['type'] == 'gateway'])
            print(f"  - {scenario}: {devices} devices, {gateways} gateways, {len(scenario_df)} total")
    
    print("\n✅ Position generation complete!")
    print(f"🔬 Fair comparison enabled: Protocol scenarios use identical device positions")
    print(f"🔍 Note: CSV row count = devices + gateways for each scenario")
    print(f"📝 Use these positions in both ns-3 and OMNeT++ for consistent comparison")

if __name__ == "__main__":
    main()