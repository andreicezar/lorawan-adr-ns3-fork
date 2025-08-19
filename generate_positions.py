#!/usr/bin/env python3
"""
Generate consistent device and gateway positions for all ns-3 LoRaWAN scenarios.
These positions can be used in both ns-3 and OMNeT++ FLoRa for fair comparison.
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

def generate_scenario_positions(base_seed: int = DEFAULT_SEED) -> Dict:
    """
    Generate positions for all scenarios.
    
    Args:
        base_seed: Base random seed to use
    
    Returns:
        Dictionary with scenario names as keys and position data as values
    """
    scenarios = {}
    
    # Reset seed for each scenario to ensure consistency
    
    # Scenario 1: Baseline (100 devices, 1 gateway, 5km area assumed)
    set_seed(base_seed + 1)
    scenarios['scenario_01_baseline'] = {
        'devices': 100,
        'gateways': 1,
        'area_size': 5000,
        'device_positions': generate_uniform_square_positions(100, 5000),
        'gateway_positions': get_gateway_positions(1)
    }
    
    # Scenario 2: ADR Comparison (100 devices, 1 gateway, 5km area)
    set_seed(base_seed + 2)
    scenarios['scenario_02_adr'] = {
        'devices': 100,
        'gateways': 1,
        'area_size': 5000,
        'device_positions': generate_uniform_square_positions(100, 5000),
        'gateway_positions': get_gateway_positions(1)
    }
    
    # Scenario 3: SF Impact (50 devices, 1 gateway, 3km area)
    set_seed(base_seed + 3)
    scenarios['scenario_03_sf_impact'] = {
        'devices': 50,
        'gateways': 1,
        'area_size': 3000,
        'device_positions': generate_uniform_square_positions(50, 3000),
        'gateway_positions': get_gateway_positions(1)
    }
    
    # Scenario 4: Confirmed Messages (100 devices, 1 gateway, 5km area)
    set_seed(base_seed + 4)
    scenarios['scenario_04_confirmed'] = {
        'devices': 100,
        'gateways': 1,
        'area_size': 5000,
        'device_positions': generate_uniform_square_positions(100, 5000),
        'gateway_positions': get_gateway_positions(1)
    }
    
    # Scenario 5: Traffic Patterns (100 devices, 1 gateway, 5km area)
    set_seed(base_seed + 5)
    scenarios['scenario_05_traffic'] = {
        'devices': 100,
        'gateways': 1,
        'area_size': 5000,
        'device_positions': generate_uniform_square_positions(100, 5000),
        'gateway_positions': get_gateway_positions(1)
    }
    
    # Scenario 6: Collision Capture (20 devices, 1 gateway, near/far rings)
    set_seed(base_seed + 6)
    scenarios['scenario_06_collision'] = {
        'devices': 20,
        'gateways': 1,
        'area_size': 1000,  # effective area
        'device_positions': generate_near_far_rings(20, 50, 150, 450, 500),
        'gateway_positions': get_gateway_positions(1)
    }
    
    # Scenario 7: Propagation Models (50 devices, 1 gateway, radial 100-5000m)
    set_seed(base_seed + 7)
    scenarios['scenario_07_propagation'] = {
        'devices': 50,
        'gateways': 1,
        'area_size': 10000,  # diameter
        'device_positions': generate_radial_positions(50, 100, 5000),
        'gateway_positions': get_gateway_positions(1)
    }
    
    # Scenario 8: Multi-Gateway (200 devices, multiple gateway configs)
    # We'll generate for all three configurations
    for n_gw in [1, 2, 4]:
        set_seed(base_seed + 8 + n_gw)
        scenarios[f'scenario_08_multigw_{n_gw}gw'] = {
            'devices': 200,
            'gateways': n_gw,
            'area_size': 3000,
            'device_positions': generate_uniform_square_positions(200, 3000),
            'gateway_positions': get_gateway_positions(n_gw, spacing=2000)
        }
    
    return scenarios

def export_positions_to_csv(scenarios: Dict, output_file: str):
    """
    Export all scenario positions to a single CSV file.
    
    Args:
        scenarios: Dictionary with scenario data
        output_file: Output CSV filename
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
    print(f"✅ Positions exported to {output_file}")
    
    # Print summary
    print("\n📊 Summary of generated positions:")
    for scenario_name, data in scenarios.items():
        print(f"  {scenario_name}: {data['devices']} devices, {data['gateways']} gateway(s)")

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
        
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Plot devices
        dev_pos = data['device_positions']
        ax.scatter(dev_pos[:, 0], dev_pos[:, 1], s=20, alpha=0.6, 
                  label=f"End Devices ({data['devices']})")
        
        # Plot gateways
        gw_pos = data['gateway_positions']
        ax.scatter(gw_pos[:, 0], gw_pos[:, 1], s=200, marker='^', 
                  color='red', label=f"Gateway(s) ({data['gateways']})")
        
        ax.set_xlabel('X Position (m)')
        ax.set_ylabel('Y Position (m)')
        ax.set_title(f'{scenario_name} - Device Placement')
        ax.legend()
        ax.grid(True, alpha=0.3)
        ax.axis('equal')
        
        plt.tight_layout()
        plt.savefig(f'{scenario_name}_topology.png', dpi=100)
        plt.close()
        print(f"  📈 Visualization saved: {scenario_name}_topology.png")
    except ImportError:
        pass  # matplotlib not available

def main():
    parser = argparse.ArgumentParser(description='Generate LoRaWAN scenario positions')
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
    
    print(f"🔧 Generating positions with seed: {seed_to_use}")
    print("=" * 60)
    
    # Generate positions for all scenarios
    scenarios = generate_scenario_positions(seed_to_use)
    
    # Export based on format choice
    if args.format in ['csv', 'both']:
        export_positions_to_csv(scenarios, args.output)
    
    if args.format in ['txt', 'both']:
        print(f"\n📁 Exporting individual position files to {args.output_dir}/")
        export_positions_per_scenario(scenarios, args.output_dir, seed_to_use)
    
    # Create visualizations if requested
    if args.visualize:
        print("\n🎨 Creating topology visualizations...")
        for name, data in scenarios.items():
            visualize_scenario(name, data)
    
    print("\n✅ Position generation complete!")
    print(f"📍 Use these positions in both ns-3 and OMNeT++ for consistent comparison")
    print(f"💡 In ns-3, use: RngSeedManager::SetSeed({seed_to_use})")

if __name__ == "__main__":
    main()