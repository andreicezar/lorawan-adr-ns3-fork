#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from pathlib import Path
from typing import List, Optional

import pandas as pd
import matplotlib
matplotlib.use('Agg')  # non-interactive backend
import matplotlib.pyplot as plt

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def detect_area_tag(csv_path: Path) -> str:
    """
    Try to extract an area tag from filename, e.g.:
      scenario_positions_1x1km.csv -> 1x1km
      scenario_positions_2x2km.csv -> 2x2km
      scenario_positions_3km.csv   -> 3x3km (normalize 3km -> 3x3km)
    Fallback: 'default'
    """
    name = csv_path.stem.lower()
    m = re.search(r"(?:_|-)([1-5])(?:x\1)?km$", name)
    if m:
        n = m.group(1)
        return f"{n}x{n}km"
    m2 = re.search(r"(?:_|-)([1-5])km$", name)
    if m2:
        n = m2.group(1)
        return f"{n}x{n}km"
    return "default"

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def fint(v) -> str:
    try:
        return f"{int(v)}"
    except Exception:
        return "NA"

def fnum(v, d=2) -> str:
    try:
        return f"{float(v):.{d}f}"
    except Exception:
        return "NA"

# -------------------------------------------------------------------
# Core plotting (single CSV)
# -------------------------------------------------------------------
def plot_scenario_positions_2d(df: pd.DataFrame, out_dir: Path) -> None:
    """Combined overview plot across all scenarios in the CSV."""
    ensure_dir(out_dir)

    scenarios = df['scenario'].unique()
    types = df['type'].unique()

    type_markers = {'gateway': 's', 'endnode': 'o'}
    type_colors  = {'gateway': 'red', 'endnode': 'blue'}

    # fallback assignments for unexpected types
    available_markers = ['o','s','^','D','v','<','>','p','*','h','H','+','x']
    available_colors  = ['blue','red','green','orange','purple','brown','pink','gray','olive','cyan']
    for i, t in enumerate(types):
        if t not in type_markers:
            type_markers[t] = available_markers[i % len(available_markers)]
        if t not in type_colors:
            type_colors[t] = available_colors[i % len(available_colors)]

    n = len(scenarios)
    if n <= 4:
        cols = min(2, n)
        rows = (n + cols - 1) // cols
    else:
        cols = 3
        rows = (n + 2) // 3

    fig, axes = plt.subplots(rows, cols, figsize=(8*cols, 6*rows))
    fig.suptitle('2D Node Positions by Scenario\n(Colors/Markers=Type, Size=Height)', fontsize=16, fontweight='bold')

    # normalize axes to iterable
    if n == 1:
        axes = [axes]  # type: ignore
    elif rows == 1:
        axes = axes if isinstance(axes, list) else [axes]
    else:
        axes = axes.flatten()  # type: ignore

    for i, scen in enumerate(scenarios):
        ax = axes[i] if i < len(axes) else None
        if ax is None:
            continue
        sd = df[df['scenario'] == scen]

        # per-type scatters
        for t in types:
            td = sd[sd['type'] == t]
            if td.empty:
                continue
            zmin, zmax = sd['z'].min(), sd['z'].max()
            if zmax > zmin:
                sizes = 50 + (td['z'] - zmin) / (zmax - zmin) * 100
            else:
                sizes = 75
            ax.scatter(
                td['x'], td['y'],
                c=type_colors.get(t, 'gray'),
                marker=type_markers.get(t, 'o'),
                s=sizes, alpha=0.7, edgecolors='black', linewidth=0.5,
                label=f'{t} (z≈{fint(td["z"].iloc[0])}m)'
            )

        ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)')
        ax.set_title(f'{scen}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')

        # quick stats
        stats_text = f"Nodes: {len(sd)}\n"
        for t in types:
            count = len(sd[sd['type'] == t])
            if count:
                stats_text += f"{t}: {count}\n"
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                va='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    # hide unused axes
    for j in range(len(scenarios), len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    out_file = out_dir / 'all_scenarios_combined.png'
    plt.savefig(out_file, dpi=300, bbox_inches='tight'); plt.close()
    print(f"  ✓ Combined plot: {out_file}")

def plot_individual_scenarios_2d(df: pd.DataFrame, out_dir: Path) -> None:
    """One detailed plot per scenario."""
    ensure_dir(out_dir)

    scenarios = df['scenario'].unique()
    types = df['type'].unique()

    type_markers = {'gateway': 's', 'endnode': 'o'}
    type_colors  = {'gateway': 'red', 'endnode': 'blue'}

    for scen in scenarios:
        sd = df[df['scenario'] == scen]
        fig, ax = plt.subplots(figsize=(12, 10))

        for t in types:
            td = sd[sd['type'] == t]
            if td.empty:
                continue
            zmin, zmax = sd['z'].min(), sd['z'].max()
            sizes = 60 + (td['z'] - zmin) / (max(zmax - zmin, 1e-9)) * 120 if zmax > zmin else 100
            sc = ax.scatter(
                td['x'], td['y'],
                c=type_colors.get(t, 'gray'),
                marker=type_markers.get(t, 'o'),
                s=sizes, alpha=0.7, edgecolors='black', linewidth=0.8,
                label=f'{t} (z≈{fint(td["z"].iloc[0])}m)'
            )
            # annotate IDs
            for _, row in td.iterrows():
                ax.annotate(f'ID:{row["id"]}', (row['x'], row['y']),
                            xytext=(5, 5), textcoords='offset points',
                            fontsize=8, alpha=0.8)

        ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)')
        ax.set_title(f'Node Layout - {scen}\n(Marker size indicates height, IDs shown)',
                     fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')
        ax.legend(fontsize=12)

        span_x = sd['x'].max() - sd['x'].min()
        span_y = sd['y'].max() - sd['y'].min()
        stats_text = f"Total Nodes: {len(sd)}\nArea: {span_x:.0f}m × {span_y:.0f}m\n"
        for t in types:
            c = len(sd[sd['type'] == t])
            if c:
                stats_text += f"{t.title()}s: {c}\n"
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes,
                va='top', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))

        out_file = out_dir / f'scenario_{str(scen).replace(" ", "_")}_detailed.png'
        plt.savefig(out_file, dpi=300, bbox_inches='tight'); plt.close()
        print(f"  ✓ Detailed plot:  {out_file}")

def generate_summary_statistics(df: pd.DataFrame) -> None:
    print("  === SUMMARY ===")
    print(f"  Rows          : {len(df)}")
    print(f"  Scenarios     : {len(df['scenario'].unique())}")
    print(f"  Types         : {', '.join(map(str, df['type'].unique()))}")
    print(f"  Unique IDs    : {len(df['id'].unique())}")
    print(f"  X span        : {df['x'].min():.1f} → {df['x'].max():.1f}  (Δ={df['x'].max()-df['x'].min():.1f})")
    print(f"  Y span        : {df['y'].min():.1f} → {df['y'].max():.1f}  (Δ={df['y'].max()-df['y'].min():.1f})")
    print(f"  Z span        : {df['z'].min():.1f} → {df['z'].max():.1f}")

# -------------------------------------------------------------------
# Batch processor for multiple CSVs
# -------------------------------------------------------------------
def discover_csvs(root: Path, pattern: str = "scenario_positions_*km.csv") -> List[Path]:
    return sorted(root.glob(pattern))

def process_one_csv(csv_path: Path, output_root: Path) -> None:
    area = detect_area_tag(csv_path)
    out_dir = output_root / area
    ensure_dir(out_dir)

    print(f"\n🗺️  Processing: {csv_path.name}   (area: {area})")
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"  ✗ Failed to read CSV: {e}")
        return

    # quick validation
    required_cols = {"scenario", "type", "id", "x", "y", "z"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"  ✗ Missing required columns: {sorted(missing)}")
        return

    generate_summary_statistics(df)
    plot_scenario_positions_2d(df, out_dir)
    plot_individual_scenarios_2d(df, out_dir)

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Plot positions for one or more scenario_positions_*.csv files.")
    ap.add_argument("inputs", nargs="*", help="CSV files or folders. If none given, auto-discovers in CWD.")
    ap.add_argument("--out", default="plots", help="Output root directory (default: plots)")
    ap.add_argument("--pattern", default="scenario_positions_*km.csv",
                    help="Filename pattern to auto-discover (default: scenario_positions_*km.csv)")
    args = ap.parse_args()

    output_root = Path(args.out)
    ensure_dir(output_root)

    csvs: List[Path] = []
    if args.inputs:
        for item in args.inputs:
            p = Path(item)
            if p.is_dir():
                csvs.extend(discover_csvs(p, args.pattern))
            elif p.is_file() and p.suffix.lower() == ".csv":
                csvs.append(p)
    else:
        csvs = discover_csvs(Path.cwd(), args.pattern)

    if not csvs:
        print("No CSVs found. Provide paths or place files like 'scenario_positions_1x1km.csv' in the current folder.")
        return

    print(f"Found {len(csvs)} CSV file(s). Output root: {output_root.resolve()}")
    for csv_path in csvs:
        process_one_csv(csv_path, output_root)

    print("\n🎉 Done. Per-area plots are under:", output_root.resolve())

if __name__ == "__main__":
    main()
