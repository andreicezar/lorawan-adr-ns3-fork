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
    positions = np.zeros((n_devices, 3))
    
    for i in range(n_devices):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(min_radius, max_radius)
        positions[i] = [
            radius * np.cos(angle),
            radius * np.sin(angle),
            1.5
        ]
    
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
        return np.array([[0, 0, 15]])
    elif n_gateways == 2:
        return np.array([
            [-spacing/2, 0, 15],
            [spacing/2, 0, 15]
        ])
    elif n_gateways == 4:
        return np.array([
            [-spacing/2, -spacing/2, 15],
            [spacing/2, -spacing/2, 15],
            [-spacing/2, spacing/2, 15],
            [spacing/2, spacing/2, 15]
        ])
    else:
        raise ValueError(f"Unsupported number of gateways: {n_gateways}")

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
    position_sets['uniform_100_5km'] = generate_uniform_square_positions(100, 5000)
    print("🔄 Generated standard 100-device positions (5km area)")
    
    # 50 devices - uniform 3km area (for SF impact scenario)
    set_seed(base_seed + 50)
    position_sets['uniform_50_3km'] = generate_uniform_square_positions(50, 3000)
    print("🔄 Generated standard 50-device positions (3km area)")
    
    # 200 devices - uniform 3km area (for multi-gateway scenarios)
    set_seed(base_seed + 200)
    position_sets['uniform_200_3km'] = generate_uniform_square_positions(200, 3000)
    print("🔄 Generated standard 200-device positions (3km area)")
    
    # Special topology-specific position sets
    # These are used for scenarios that specifically test topology effects
    
    # 20 devices - near/far rings (for collision/capture effect testing)
    set_seed(base_seed + 20)
    position_sets['nearfar_20'] = generate_near_far_rings(20, 50, 150, 450, 500)
    print("🔄 Generated near/far ring 20-device positions (collision testing)")
    
    # 50 devices - radial pattern (for propagation model testing)
    set_seed(base_seed + 51)  # Different from uniform_50 to avoid confusion
    position_sets['radial_50'] = generate_radial_positions(50, 100, 5000)
    print("🔄 Generated radial 50-device positions (propagation testing)")
    
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
    print("📍 Generating base position sets for consistent comparisons...")
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
        scenarios[scenario_name] = {
            'devices': 100,
            'gateways': 1,
            'area_size': 5000,
            'device_positions': position_sets['uniform_100_5km'].copy(),  # Same positions!
            'gateway_positions': get_gateway_positions(1),
            'description': description,
            'position_type': 'uniform_100_5km'
        }
        print(f"  ✅ {scenario_name}: {description} (shared 100-device positions)")
    
    # SF Impact scenario - different area size but consistent positions
    scenarios['scenario_03_sf_impact'] = {
        'devices': 50,
        'gateways': 1,
        'area_size': 3000,
        'device_positions': position_sets['uniform_50_3km'].copy(),
        'gateway_positions': get_gateway_positions(1),
        'description': 'Spreading Factor impact testing',
        'position_type': 'uniform_50_3km'
    }
    print(f"  ✅ scenario_03_sf_impact: SF impact testing (dedicated 50-device positions)")
    
    # Topology-specific scenarios - these NEED different positions by design
    scenarios['scenario_06_collision'] = {
        'devices': 20,
        'gateways': 1,
        'area_size': 1000,
        'device_positions': position_sets['nearfar_20'].copy(),
        'gateway_positions': get_gateway_positions(1),
        'description': 'Collision/capture effect testing (near/far topology)',
        'position_type': 'nearfar_20'
    }
    print(f"  ✅ scenario_06_collision: Collision testing (special near/far topology)")
    
    scenarios['scenario_07_propagation'] = {
        'devices': 50,
        'gateways': 1,
        'area_size': 10000,
        'device_positions': position_sets['radial_50'].copy(),
        'gateway_positions': get_gateway_positions(1),
        'description': 'Propagation model testing (radial topology)',
        'position_type': 'radial_50'
    }
    print(f"  ✅ scenario_07_propagation: Propagation testing (special radial topology)")
    
    # Multi-gateway scenarios - these use IDENTICAL device positions
    # Only gateway configuration differs, not device placement
    multi_gw_configs = [
        (1, 'Single gateway'),
        (2, 'Dual gateway'),
        (4, 'Quad gateway')
    ]
    
    for n_gw, description in multi_gw_configs:
        scenario_name = f'scenario_08_multigw_{n_gw}gw'
        scenarios[scenario_name] = {
            'devices': 200,
            'gateways': n_gw,
            'area_size': 3000,
            'device_positions': position_sets['uniform_200_3km'].copy(),  # Same device positions!
            'gateway_positions': get_gateway_positions(n_gw, spacing=2000),
            'description': f'Multi-gateway testing: {description}',
            'position_type': 'uniform_200_3km'
        }
        print(f"  ✅ {scenario_name}: {description} (shared 200-device positions)")
    
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
    
    for scenario_name, data in scenarios.items():
        # Add gateway positions
        for i, gw_pos in enumerate(data['gateway_positions']):
            all_data.append({
                'scenario': scenario_name,
                'type': 'gateway',
                'id': i,
                'x': gw_pos[0],
                'y': gw_pos[1],
                'z': gw_pos[2]
            })
        
        # Add device positions
        for i, dev_pos in enumerate(data['device_positions']):
            all_data.append({
                'scenario': scenario_name,
                'type': 'endnode',
                'id': i,
                'x': dev_pos[0],
                'y': dev_pos[1],
                'z': dev_pos[2]
            })
    
    df = pd.DataFrame(all_data)
    df.to_csv(output_file, index=False, float_format='%.2f')
    print(f"\n✅ Positions exported to {output_file}")
    
    # Create a metadata file
    metadata_file = output_file.replace('.csv', '_metadata.txt')
    with open(metadata_file, 'w') as f:
        f.write(f"# LoRaWAN Scenario Positions Metadata\n")
        f.write(f"# Generated with seed: {base_seed}\n")
        f.write(f"# Generation strategy: Consistent positions for fair protocol comparison\n\n")
        
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
    
    # Print summary with position sharing info
    print("\n📊 Summary of generated positions:")
    position_groups = {}
    for scenario_name, data in scenarios.items():
        pos_type = data.get('position_type', 'unknown')
        if pos_type not in position_groups:
            position_groups[pos_type] = []
        position_groups[pos_type].append(scenario_name)
    
    for pos_type, scenario_list in position_groups.items():
        print(f"\n  {pos_type.upper()}: {len(scenario_list)} scenario(s)")
        for scenario_name in scenario_list:
            data = scenarios[scenario_name]
            shared_indicator = "🔗" if len(scenario_list) > 1 else "🎯"
            print(f"    {shared_indicator} {scenario_name}: {data['devices']} devices, {data['gateways']} gateway(s)")

def export_positions_per_scenario(scenarios: Dict, output_dir: str, base_seed: int):
    """
    Export positions to individual files per scenario (alternative format).
    
    Args:
        scenarios: Dictionary with scenario data
        output_dir: Output directory for individual files
        base_seed: Random seed used for generation
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for scenario_name, data in scenarios.items():
        filename = os.path.join(output_dir, f"{scenario_name}_positions.txt")
        with open(filename, 'w') as f:
            f.write(f"# {scenario_name} positions\n")
            f.write(f"# Format: type,id,x,y,z\n")
            f.write(f"# Description: {data.get('description', 'No description')}\n")
            f.write(f"# Position type: {data.get('position_type', 'unknown')}\n")
            f.write(f"# Devices: {data['devices']}, Gateways: {data['gateways']}\n")
            f.write(f"# Area size: {data['area_size']}m\n")
            f.write(f"# Random seed: {base_seed}\n\n")
            
            # Gateways
            for i, gw_pos in enumerate(data['gateway_positions']):
                f.write(f"gateway,{i},{gw_pos[0]:.2f},{gw_pos[1]:.2f},{gw_pos[2]:.2f}\n")
            
            # End nodes
            for i, dev_pos in enumerate(data['device_positions']):
                f.write(f"endnode,{i},{dev_pos[0]:.2f},{dev_pos[1]:.2f},{dev_pos[2]:.2f}\n")
        
        print(f"  ✅ {scenario_name} -> {filename}")

def visualize_scenario(scenario_name: str, data: Dict):
    """
    Create a simple visualization of device and gateway positions.
    
    Args:
        scenario_name: Name of the scenario
        data: Scenario data with positions
    """
    try:
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot devices
        dev_pos = data['device_positions']
        ax.scatter(dev_pos[:, 0], dev_pos[:, 1], s=30, alpha=0.6, 
                  label=f"End Devices ({data['devices']})", color='blue')
        
        # Plot gateways
        gw_pos = data['gateway_positions']
        ax.scatter(gw_pos[:, 0], gw_pos[:, 1], s=200, marker='^', 
                  color='red', label=f"Gateway(s) ({data['gateways']})", 
                  edgecolors='black', linewidth=2)
        
        # Add position type and description info
        pos_type = data.get('position_type', 'unknown')
        description = data.get('description', 'No description')
        
        ax.set_xlabel('X Position (m)', fontsize=12)
        ax.set_ylabel('Y Position (m)', fontsize=12)
        ax.set_title(f'{scenario_name}\n{description}\nPosition type: {pos_type}', fontsize=14)
        ax.legend(fontsize=11)
        ax.grid(True, alpha=0.3)
        ax.axis('equal')
        
        # Add statistics
        stats_text = f"Devices: {data['devices']}\nGateways: {data['gateways']}\nArea: {data['area_size']}m"
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        plt.savefig(f'{scenario_name}_topology.png', dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  📈 Visualization saved: {scenario_name}_topology.png")
    except ImportError:
        pass  # matplotlib not available

def main():
    parser = argparse.ArgumentParser(description='Generate LoRaWAN scenario positions with consistent placement')
    parser.add_argument('--output', default='scenario_positions.csv',
                       help='Output CSV filename (default: scenario_positions.csv)')
    parser.add_argument('--output-dir', default='positions',
                       help='Output directory for individual files (default: positions)')
    parser.add_argument('--format', choices=['csv', 'txt', 'both'], default='csv',
                       help='Output format (default: csv)')
    parser.add_argument('--visualize', action='store_true',
                       help='Create visualization plots (requires matplotlib)')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED,
                       help=f'Random seed (default: {DEFAULT_SEED})')
    
    args = parser.parse_args()
    
    # Use the provided seed
    seed_to_use = args.seed
    
    print(f"🔧 Generating CONSISTENT positions with seed: {seed_to_use}")
    print("🎯 Strategy: Same device positions for scenarios testing protocol differences")
    print("=" * 80)
    
    # Generate positions for all scenarios
    scenarios = generate_scenario_positions(seed_to_use)
    
    # Export based on format choice
    if args.format in ['csv', 'both']:
        export_positions_to_csv(scenarios, args.output, seed_to_use)
    
    if args.format in ['txt', 'both']:
        print(f"\n📁 Exporting individual position files to {args.output_dir}/")
        export_positions_per_scenario(scenarios, args.output_dir, seed_to_use)
    
    # Create visualizations if requested
    if args.visualize:
        print("\n🎨 Creating topology visualizations...")
        for name, data in scenarios.items():
            visualize_scenario(name, data)
    
    print("\n✅ Position generation complete!")
    print(f"🔬 Fair comparison enabled: Protocol scenarios use identical device positions")
    print(f"📍 Use these positions in both ns-3 and OMNeT++ for consistent comparison")
    print(f"💡 In ns-3, use: RngSeedManager::SetSeed({seed_to_use})")

if __name__ == "__main__":
    main()