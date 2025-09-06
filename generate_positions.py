#!/usr/bin/env python3
"""
Generate consistent device and gateway positions for LoRaWAN scenarios.

NEW:
- Multi-output support via --ranges-km (default: 1,2,3,4,5) to generate
  1x1km, 2x2km, 3x3km, 4x4km, 5x5km CSV files in one run.
- Each area size gets its own CSV + metadata file:
  scenario_positions_1x1km.csv ... scenario_positions_5x5km.csv
"""

import numpy as np
import pandas as pd
import os
from typing import List, Tuple, Dict
import argparse
import math

# Default seed for reproducibility (same as you'd use in ns-3)
DEFAULT_SEED = 12345

# Keep gateway spacing roughly similar to original intent (2000 for 3000m area ~= 0.667)
GATEWAY_SPACING_FACTOR = 2.0 / 3.0  # spacing = factor * area_size

# ------------------------------
# RNG / utils
# ------------------------------
def set_seed(seed: int):
    np.random.seed(seed)

def km_to_m(km: float) -> float:
    return float(km) * 1000.0

# ------------------------------
# Position generators
# ------------------------------
def generate_uniform_square_positions(n_devices: int, area_size: float,
                                     min_distance: float = 10.0) -> np.ndarray:
    """
    Generate uniformly distributed device positions in a square area of side 'area_size' (meters).
    Avoids a small radius from the center to prevent overlap with gateway if placed at/near center.
    """
    positions = np.zeros((n_devices, 3))
    half_size = area_size / 2

    for i in range(n_devices):
        while True:
            x = np.random.uniform(-half_size, half_size)
            y = np.random.uniform(-half_size, half_size)
            if math.hypot(x, y) >= min_distance:
                break
        positions[i] = [x, y, 1.5]  # ED at 1.5m
    return positions

def generate_radial_positions(n_devices: int, min_radius: float, max_radius: float) -> np.ndarray:
    positions = np.zeros((n_devices, 3))
    for i in range(n_devices):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(min_radius, max_radius)
        positions[i] = [radius * np.cos(angle), radius * np.sin(angle), 1.5]
    return positions

def generate_near_far_rings(n_devices: int, near_min: float, near_max: float,
                            far_min: float, far_max: float) -> np.ndarray:
    positions = np.zeros((n_devices, 3))
    half = n_devices // 2
    # near ring
    for i in range(half):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(near_min, near_max)
        positions[i] = [radius * np.cos(angle), radius * np.sin(angle), 1.5]
    # far ring
    for i in range(half, n_devices):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(far_min, far_max)
        positions[i] = [radius * np.cos(angle), radius * np.sin(angle), 1.5]
    return positions

def get_gateway_positions(n_gateways: int, spacing: float) -> np.ndarray:
    """
    spacing: distance between gateways horizontally/vertically (meters).
    For 1 GW: at origin; 2 GW: left/right; 4 GW: at corners of a square with given spacing.
    """
    if n_gateways == 1:
        positions = np.array([[0, 0, 15]])
    elif n_gateways == 2:
        positions = np.array([[-spacing/2, 0, 15],
                              [ spacing/2, 0, 15]])
    elif n_gateways == 4:
        positions = np.array([[-spacing/2, -spacing/2, 15],
                              [ spacing/2, -spacing/2, 15],
                              [-spacing/2,  spacing/2, 15],
                              [ spacing/2,  spacing/2, 15]])
    else:
        raise ValueError(f"Unsupported number of gateways: {n_gateways}")
    return positions

# ------------------------------
# Base sets (parameterized by area)
# ------------------------------
def generate_base_device_positions_for_area(area_size_m: float,
                                            base_seed: int = DEFAULT_SEED) -> Dict[str, np.ndarray]:
    """
    Create the base position sets for a chosen area size (meters).
    Counts are kept the same as the original script; only area scales.
    """
    position_sets = {}

    # 100 devices - uniform area_size (for baseline, ADR, confirmed, traffic)
    set_seed(base_seed + 100)
    positions_100 = generate_uniform_square_positions(100, area_size_m)
    position_sets[f'uniform_100_{int(area_size_m)}m'] = positions_100

    # 50 devices - uniform area_size (SF impact)
    set_seed(base_seed + 50)
    positions_50 = generate_uniform_square_positions(50, area_size_m)
    position_sets[f'uniform_50_{int(area_size_m)}m'] = positions_50

    # 200 devices - uniform area_size (multi-gateway)
    set_seed(base_seed + 200)
    positions_200 = generate_uniform_square_positions(200, area_size_m)
    position_sets[f'uniform_200_{int(area_size_m)}m'] = positions_200

    # near/far rings: radii scaled loosely with area (keep structure recognizable)
    # Keep near ring ~1–3% of area size; far ring ~15–20% of area size
    # (These are heuristics to stay proportional across sizes.)
    set_seed(base_seed + 20)
    near_min = 0.01 * area_size_m
    near_max = 0.03 * area_size_m
    far_min  = 0.15 * area_size_m
    far_max  = 0.20 * area_size_m
    positions_nearfar = generate_near_far_rings(50, near_min, near_max, far_min, far_max)
    position_sets[f'nearfar_50_{int(area_size_m)}m'] = positions_nearfar

    # radial: from 3% up to 80% of area size
    set_seed(base_seed + 51)
    positions_radial = generate_radial_positions(50, 0.03 * area_size_m, 0.80 * area_size_m)
    position_sets[f'radial_50_{int(area_size_m)}m'] = positions_radial

    return position_sets

def generate_scenario_positions_for_area(area_size_m: float,
                                         base_seed: int = DEFAULT_SEED) -> Dict:
    """
    Build the scenarios dictionary for a specific square area size (meters).
    Gateway spacing scales with area size.
    """
    position_sets = generate_base_device_positions_for_area(area_size_m, base_seed)
    scenarios = {}

    spacing = GATEWAY_SPACING_FACTOR * area_size_m

    # Protocol comparison scenarios (identical positions across those)
    proto_100_key = f'uniform_100_{int(area_size_m)}m'
    dev_pos = position_sets[proto_100_key].copy()
    gw_pos_1 = get_gateway_positions(1, spacing=spacing)
    for name, desc in [
        ('scenario_01_baseline', 'Baseline configuration'),
        ('scenario_02_adr', 'ADR enabled'),
        ('scenario_04_confirmed', 'Confirmed messages'),
        ('scenario_05_traffic', 'Different traffic patterns'),
    ]:
        scenarios[name] = {
            'devices': dev_pos.shape[0],
            'gateways': gw_pos_1.shape[0],
            'area_size': area_size_m,
            'device_positions': dev_pos.copy(),
            'gateway_positions': gw_pos_1.copy(),
            'description': desc,
            'position_type': proto_100_key
        }

    # SF impact scenario (50 devices)
    proto_50_key = f'uniform_50_{int(area_size_m)}m'
    dev_pos_50 = position_sets[proto_50_key].copy()
    scenarios['scenario_03_sf_impact'] = {
        'devices': dev_pos_50.shape[0],
        'gateways': gw_pos_1.shape[0],
        'area_size': area_size_m,
        'device_positions': dev_pos_50.copy(),
        'gateway_positions': gw_pos_1.copy(),
        'description': 'Spreading Factor impact testing',
        'position_type': proto_50_key
    }

    # Topology-specific (near/far, radial)
    nearfar_key = f'nearfar_50_{int(area_size_m)}m'
    dev_nf = position_sets[nearfar_key].copy()
    scenarios['scenario_06_collision'] = {
        'devices': dev_nf.shape[0],
        'gateways': gw_pos_1.shape[0],
        'area_size': area_size_m,
        'device_positions': dev_nf.copy(),
        'gateway_positions': gw_pos_1.copy(),
        'description': 'Collision/capture effect testing (near/far topology)',
        'position_type': nearfar_key
    }

    radial_key = f'radial_50_{int(area_size_m)}m'
    dev_rad = position_sets[radial_key].copy()
    scenarios['scenario_07_propagation'] = {
        'devices': dev_rad.shape[0],
        'gateways': gw_pos_1.shape[0],
        'area_size': area_size_m,
        'device_positions': dev_rad.copy(),
        'gateway_positions': gw_pos_1.copy(),
        'description': 'Propagation model testing (radial topology)',
        'position_type': radial_key
    }

    # Multi-gateway (identical devices, different gateway layouts)
    proto_200_key = f'uniform_200_{int(area_size_m)}m'
    shared_dev = position_sets[proto_200_key].copy()
    for n_gw, desc in [(1, 'Single gateway'), (2, 'Dual gateway'), (4, 'Quad gateway')]:
        scenarios[f'scenario_08_multigw_{n_gw}gw'] = {
            'devices': shared_dev.shape[0],
            'gateways': n_gw,
            'area_size': area_size_m,
            'device_positions': shared_dev.copy(),
            'gateway_positions': get_gateway_positions(n_gw, spacing=spacing),
            'description': f'Multi-gateway testing: {desc}',
            'position_type': proto_200_key
        }

    return scenarios

# ------------------------------
# Export
# ------------------------------
def export_positions_to_csv(scenarios: Dict, output_file: str, base_seed: int):
    """
    Export one 'scenarios' dict to CSV + metadata.
    """
    all_rows = []
    for scenario_name, data in scenarios.items():
        # gateways
        for i, gw in enumerate(data['gateway_positions']):
            all_rows.append({
                'scenario': scenario_name, 'type': 'gateway', 'id': i,
                'x': gw[0], 'y': gw[1], 'z': gw[2]
            })
        # devices
        for i, dev in enumerate(data['device_positions']):
            all_rows.append({
                'scenario': scenario_name, 'type': 'enddevice', 'id': i,
                'x': dev[0], 'y': dev[1], 'z': dev[2]
            })

        # validation
        if data['device_positions'].shape[0] != data['devices']:
            raise ValueError(f"{scenario_name}: expected {data['devices']} devices; got {data['device_positions'].shape[0]}")
        if data['gateway_positions'].shape[0] != data['gateways']:
            raise ValueError(f"{scenario_name}: expected {data['gateways']} gateways; got {data['gateway_positions'].shape[0]}")

    df = pd.DataFrame(all_rows)
    df.to_csv(output_file, index=False, float_format='%.2f')

    # metadata
    meta_file = output_file.replace('.csv', '_metadata.txt')
    with open(meta_file, 'w') as f:
        f.write(f"# LoRaWAN Scenario Positions Metadata\n")
        f.write(f"# Generated with seed: {base_seed}\n")
        f.write(f"# Each scenario shares identical device positions where intended for fair comparison.\n\n")
        f.write("## CSV Columns: scenario, type, id, x, y, z\n")
        f.write("## type: 'gateway' or 'enddevice'\n\n")
        for scenario_name, data in scenarios.items():
            f.write(f"{scenario_name}:\n")
            f.write(f"  - Devices: {data['devices']}\n")
            f.write(f"  - Gateways: {data['gateways']}\n")
            f.write(f"  - Area size (m): {data['area_size']}\n")
            f.write(f"  - Description: {data.get('description','')}\n")
            f.write(f"  - Position set: {data.get('position_type','')}\n\n")

def parse_ranges_km(s: str) -> List[float]:
    """
    Parse a comma-separated list like "1,2,3,4,5" into [1.0, 2.0, ...]
    """
    out = []
    for tok in s.split(','):
        tok = tok.strip()
        if not tok:
            continue
        out.append(float(tok))
    if not out:
        raise ValueError("No valid ranges provided.")
    return out

# ------------------------------
# CLI
# ------------------------------
def main():
    parser = argparse.ArgumentParser(description='Generate LoRaWAN scenario positions (multi-size)')
    parser.add_argument('--output', default='scenario_positions.csv',
                        help='(Legacy) single output CSV filename (used if --ranges-km not provided)')
    parser.add_argument('--seed', type=int, default=DEFAULT_SEED,
                        help=f'Random seed (default: {DEFAULT_SEED})')
    parser.add_argument('--ranges-km', type=str, default='1,2,3,4,5',
                        help='Comma-separated square side lengths in km (e.g., "1,2,3,4,5") to emit multiple CSVs')
    parser.add_argument('--single', action='store_true',
                        help='Generate only one CSV using --output and default area of 5 km (legacy behavior)')

    args = parser.parse_args()
    seed_to_use = args.seed

    if args.single:
        # Legacy single-output path (5km default)
        area_size_m = 5000.0
        scenarios = generate_scenario_positions_for_area(area_size_m, seed_to_use)
        export_positions_to_csv(scenarios, args.output, seed_to_use)
        print(f"✅ Wrote single CSV: {args.output}")
        return

    # Multi-output: loop over requested sizes
    try:
        ranges_km = parse_ranges_km(args.ranges_km)
    except Exception as e:
        print(f"Invalid --ranges-km: {e}")
        return

    for km in ranges_km:
        area_m = km_to_m(km)
        scenarios = generate_scenario_positions_for_area(area_m, seed_to_use)
        out_name = f"scenario_positions_{int(km)}x{int(km)}km.csv"
        export_positions_to_csv(scenarios, out_name, seed_to_use)
        print(f"✅ Wrote: {out_name}")

    print("🎉 Done generating multi-size CSVs!")

if __name__ == "__main__":
    main()
