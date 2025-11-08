#!/usr/bin/env python3
"""
Unified ns-3 LoRaWAN Results Analyzer
Supports two data formats:
1. NEW: *_packets.csv files (packet-level detailed tracking)
2. OLD: Distance folders (10m/, 20m/, etc.) with run.log/global_performance.txt
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sys
import re

# Configuration
OUTPUT_DIR = Path("output")
PLOTS_DIR = OUTPUT_DIR / "plots"
PLOTS_DIR.mkdir(exist_ok=True)

# Plot style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 8)
plt.rcParams['font.size'] = 11


# =============================================================================
# FORMAT 1: NEW PACKET-LEVEL CSV FILES
# =============================================================================

def find_packet_csv_files(directory):
    """Find all *_packets.csv files."""
    files = list(directory.glob("*_packets.csv"))
    return files


def load_packet_csv_data(files):
    """Load and concatenate packet CSV files."""
    if not files:
        return None
    
    dfs = []
    for file in files:
        try:
            df = pd.read_csv(file)
            dfs.append(df)
        except Exception as e:
            print(f"✗ Error reading {file.name}: {e}")
    
    if not dfs:
        return None
    
    return pd.concat(dfs, ignore_index=True)


def aggregate_packet_data(df):
    """Aggregate final values per distance across seeds."""
    final_values = df.sort_values(['distance_m', 'seed', 'packet_seq']).groupby(
        ['distance_m', 'seed']
    ).last().reset_index()
    
    agg = final_values.groupby('distance_m').agg({
        'rssi_mean_dbm': ['mean', 'std'],
        'rssi_std_dbm': ['mean', 'std'],
        'snr_mean_db': ['mean', 'std'],
        'snr_std_db': ['mean', 'std'],  # ✅ FIXED: was 'snr_std_dbm'
        'pdr_percent': ['mean', 'std'],
        'latency_p50_ms': ['mean', 'std'],
        'latency_p90_ms': ['mean', 'std'],
        'energy_per_tx_mj': ['mean', 'std'],
        'packets_sent': 'mean',
        'packets_received': 'mean',
    }).reset_index()
    
    agg.columns = ['_'.join(col).strip('_') for col in agg.columns.values]
    agg.rename(columns={'distance_m': 'distance_m'}, inplace=True)
    
    return agg


# =============================================================================
# FORMAT 2: OLD DISTANCE FOLDER STRUCTURE
# =============================================================================

def extract_from_log(log_file):
    """Extract sent/received counts from run.log."""
    sent = recv = None
    
    try:
        with open(log_file, "r") as f:
            for line in f:
                if "Global MAC performance" in line:
                    match = re.search(r":\s+([\d.]+)\s+([\d.]+)", line)
                    if match:
                        sent = int(float(match.group(1)))
                        recv = int(float(match.group(2)))
                        break
    except:
        pass
    
    return sent, recv


def extract_from_global_perf(perf_file):
    """Extract from global_performance.txt."""
    sent = recv = None
    
    try:
        with open(perf_file, "r") as f:
            content = f.read()
            match = re.search(r"(\d+)\s+(\d+)", content)
            if match:
                sent = int(match.group(1))
                recv = int(match.group(2))
    except:
        pass
    
    return sent, recv


def extract_from_packet_details_csv(csv_file):
    """Count packets from packet_details.csv."""
    try:
        df = pd.read_csv(csv_file)
        sent = len(df[df['event_type'].str.contains('TX', na=False)])
        recv = len(df[df['event_type'] == 'RX_SUCCESS'])
        return sent, recv
    except:
        return None, None


def extract_from_snr_log(csv_file):
    """Extract RSSI and SNR statistics from snr_log.csv."""
    try:
        df = pd.read_csv(csv_file)
        return {
            'rssi_mean': df['rssi_dbm'].mean(),
            'rssi_std': df['rssi_dbm'].std(),
            'snr_mean': df['snr_db'].mean(),
            'snr_std': df['snr_db'].std(),
        }
    except:
        return None


def extract_counts_from_folder(dist_dir):
    """Extract all metrics from a distance folder."""
    result = {'distance_m': None, 'sent': None, 'received': None}
    
    # Try extracting packet counts
    for extract_func, file_name in [
        (extract_from_log, "run.log"),
        (extract_from_global_perf, "global-performance.txt"),
        (extract_from_packet_details_csv, "packet_details.csv")
    ]:
        file_path = dist_dir / file_name
        if file_path.exists():
            sent, recv = extract_func(file_path)
            if sent is not None:
                result['sent'] = sent
                result['received'] = recv
                break
    
    # Try extracting RSSI/SNR
    snr_file = dist_dir / "snr_log.csv"
    if snr_file.exists():
        snr_data = extract_from_snr_log(snr_file)
        if snr_data:
            result.update(snr_data)
    
    return result


def scan_distance_folders(directory):
    """Scan for distance-based folder structure (10m/, 20m/, etc.)."""
    results = []
    dist_pattern = re.compile(r"^(\d+)m$")
    
    for dist_dir in sorted(directory.iterdir()):
        if not dist_dir.is_dir():
            continue
        
        match = dist_pattern.match(dist_dir.name)
        if not match:
            continue
        
        distance = int(match.group(1))
        data = extract_counts_from_folder(dist_dir)
        
        if data['sent'] is not None:
            data['distance_m'] = distance
            results.append(data)
    
    if not results:
        return None
    
    df = pd.DataFrame(results).sort_values("distance_m")
    df['pdr_percent'] = (df['received'] / df['sent'] * 100)
    
    return df


# =============================================================================
# PLOTTING FUNCTIONS (UNIFIED)
# =============================================================================

def plot_rssi_snr_combined(df, data_type):
    """Plot RSSI and SNR side by side."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # RSSI Plot
    ax = axes[0]
    if data_type == 'packet_csv':
        distances = df['distance_m']
        ax.errorbar(distances, df['rssi_mean_dbm_mean'], 
                   yerr=df['rssi_mean_dbm_std'],
                   fmt='o-', color='steelblue', linewidth=2.5,
                   markersize=10, capsize=6, capthick=2)
    else:
        ax.plot(df['distance_m'], df['rssi_mean'], 
               'o-', color='steelblue', linewidth=2.5, markersize=10)
    
    ax.set_xlabel('Distance (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('RSSI (dBm)', fontsize=12, fontweight='bold')
    ax.set_title('RSSI vs Distance', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    # SNR Plot
    ax = axes[1]
    if data_type == 'packet_csv':
        ax.errorbar(distances, df['snr_mean_db_mean'],
                   yerr=df['snr_mean_db_std'],
                   fmt='o-', color='forestgreen', linewidth=2.5,
                   markersize=10, capsize=6, capthick=2)
    else:
        if 'snr_mean' in df.columns:
            ax.plot(df['distance_m'], df['snr_mean'],
                   'o-', color='forestgreen', linewidth=2.5, markersize=10)
    
    ax.axhline(-7.5, color='red', linestyle='--', linewidth=2, 
              label='SF7 Requirement (-7.5 dB)')
    ax.set_xlabel('Distance (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('SNR (dB)', fontsize=12, fontweight='bold')
    ax.set_title('SNR vs Distance', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / 'rssi_snr_vs_distance.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {PLOTS_DIR / 'rssi_snr_vs_distance.png'}")
    plt.close()


def plot_pdr_and_packets(df, data_type):
    """Plot PDR and packet counts."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    # PDR Plot
    ax = axes[0]
    if data_type == 'packet_csv':
        distances = df['distance_m']
        ax.errorbar(distances, df['pdr_percent_mean'],
                   yerr=df['pdr_percent_std'],
                   fmt='o-', color='navy', linewidth=2.5,
                   markersize=10, capsize=6, capthick=2)
    else:
        ax.plot(df['distance_m'], df['pdr_percent'],
               'o-', color='navy', linewidth=2.5, markersize=10)
    
    ax.axhline(100, color='green', linestyle='--', linewidth=1.5, alpha=0.5,
              label='100% PDR')
    ax.set_xlabel('Distance (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Packet Delivery Rate (%)', fontsize=12, fontweight='bold')
    ax.set_title('PDR vs Distance', fontsize=14, fontweight='bold')
    ax.set_ylim([0, 105])
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    # Packet Counts Plot
    ax = axes[1]
    if data_type == 'packet_csv':
        ax.plot(distances, df['packets_sent_mean'], 
               marker='o', linewidth=2, markersize=8, label='Sent')
        ax.plot(distances, df['packets_received_mean'],
               marker='s', linewidth=2, markersize=8, label='Received')
    else:
        ax.plot(df['distance_m'], df['sent'],
               marker='o', linewidth=2, markersize=8, label='Sent')
        ax.plot(df['distance_m'], df['received'],
               marker='s', linewidth=2, markersize=8, label='Received')
    
    ax.set_xlabel('Distance (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Number of Packets', fontsize=12, fontweight='bold')
    ax.set_title('Packets Sent/Received vs Distance', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / 'pdr_packets_vs_distance.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {PLOTS_DIR / 'pdr_packets_vs_distance.png'}")
    plt.close()


def plot_latency(df):
    """Plot latency percentiles (only for packet CSV format)."""
    if 'latency_p50_ms_mean' not in df.columns:
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    distances = df['distance_m']
    ax.errorbar(distances, df['latency_p50_ms_mean'],
               yerr=df['latency_p50_ms_std'],
               fmt='o-', color='purple', linewidth=2.5,
               markersize=10, capsize=6, capthick=2,
               label='Latency P50')
    
    ax.errorbar(distances, df['latency_p90_ms_mean'],
               yerr=df['latency_p90_ms_std'],
               fmt='s--', color='orange', linewidth=2.5,
               markersize=8, capsize=6, capthick=2,
               label='Latency P90')
    
    ax.set_xlabel('Distance (m)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Latency (ms)', fontsize=12, fontweight='bold')
    ax.set_title('End-to-End Latency vs Distance', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=10)
    
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / 'latency_vs_distance.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {PLOTS_DIR / 'latency_vs_distance.png'}")
    plt.close()


def plot_packet_evolution(df_raw):
    """Plot packet-by-packet evolution (only for packet CSV format)."""
    if df_raw is None or 'packet_seq' not in df_raw.columns:
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    
    distances = sorted(df_raw['distance_m'].unique())
    colors = plt.cm.viridis(np.linspace(0, 1, len(distances)))
    
    for idx, distance in enumerate(distances):
        dist_data = df_raw[df_raw['distance_m'] == distance]
        color = colors[idx]
        
        grouped = dist_data.groupby('packet_seq').agg({
            'rssi_mean_dbm': 'mean',
            'snr_mean_db': 'mean',
            'pdr_percent': 'mean',
            'latency_p50_ms': 'mean'
        }).reset_index()
        
        axes[0, 0].plot(grouped['packet_seq'], grouped['rssi_mean_dbm'],
                       'o-', color=color, label=f'{int(distance)}m',
                       linewidth=2, markersize=4)
        axes[0, 1].plot(grouped['packet_seq'], grouped['snr_mean_db'],
                       'o-', color=color, linewidth=2, markersize=4)
        axes[1, 0].plot(grouped['packet_seq'], grouped['pdr_percent'],
                       'o-', color=color, linewidth=2, markersize=4)
        axes[1, 1].plot(grouped['packet_seq'], grouped['latency_p50_ms'],
                       'o-', color=color, linewidth=2, markersize=4)
    
    axes[0, 0].set_xlabel('Packet Sequence', fontweight='bold')
    axes[0, 0].set_ylabel('Cumulative Mean RSSI (dBm)', fontweight='bold')
    axes[0, 0].set_title('RSSI Evolution', fontweight='bold')
    axes[0, 0].grid(True, alpha=0.3)
    axes[0, 0].legend(title='Distance', fontsize=8, ncol=2)
    
    axes[0, 1].set_xlabel('Packet Sequence', fontweight='bold')
    axes[0, 1].set_ylabel('Cumulative Mean SNR (dB)', fontweight='bold')
    axes[0, 1].set_title('SNR Evolution', fontweight='bold')
    axes[0, 1].axhline(-7.5, color='red', linestyle='--', linewidth=1)
    axes[0, 1].grid(True, alpha=0.3)
    
    axes[1, 0].set_xlabel('Packet Sequence', fontweight='bold')
    axes[1, 0].set_ylabel('Cumulative PDR (%)', fontweight='bold')
    axes[1, 0].set_title('PDR Evolution', fontweight='bold')
    axes[1, 0].set_ylim([0, 105])
    axes[1, 0].grid(True, alpha=0.3)
    
    axes[1, 1].set_xlabel('Packet Sequence', fontweight='bold')
    axes[1, 1].set_ylabel('Cumulative Latency P50 (ms)', fontweight='bold')
    axes[1, 1].set_title('Latency Evolution', fontweight='bold')
    axes[1, 1].grid(True, alpha=0.3)
    
    plt.suptitle('Packet-by-Packet Metric Evolution per Distance',
                 fontsize=15, fontweight='bold')
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / 'packet_evolution.png', dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {PLOTS_DIR / 'packet_evolution.png'}")
    plt.close()


def generate_summary_table(df, data_type):
    """Generate and print summary statistics table."""
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    
    if data_type == 'packet_csv':
        table = df[['distance_m', 'rssi_mean_dbm_mean', 'rssi_mean_dbm_std',
                   'snr_mean_db_mean', 'snr_mean_db_std',
                   'pdr_percent_mean', 'pdr_percent_std']].copy()
        table.columns = ['Distance(m)', 'RSSI(dBm)', 'RSSI_std',
                        'SNR(dB)', 'SNR_std', 'PDR(%)', 'PDR_std']
    else:
        cols = ['distance_m', 'pdr_percent', 'sent', 'received']
        if 'rssi_mean' in df.columns:
            cols.extend(['rssi_mean', 'snr_mean'])
        table = df[cols].copy()
        table.columns = ['Distance(m)', 'PDR(%)', 'Sent', 'Received'] + \
                       (['RSSI(dBm)', 'SNR(dB)'] if len(cols) > 4 else [])
    
    print(table.to_string(index=False, float_format='%.2f'))
    print("="*80 + "\n")
    
    # Save to CSV
    table.to_csv(PLOTS_DIR / 'summary_statistics.csv', index=False, float_format='%.2f')
    print(f"✓ Saved: {PLOTS_DIR / 'summary_statistics.csv'}")


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """Main analysis pipeline with auto-detection."""
    print("\n" + "="*80)
    print("ns-3 LoRaWAN Unified Results Analyzer")
    print("="*80 + "\n")
    
    # Try Format 1: Packet CSV files
    packet_files = find_packet_csv_files(OUTPUT_DIR)
    
    if packet_files:
        print(f"✓ Detected FORMAT 1: Packet-level CSV files ({len(packet_files)} files)")
        for f in packet_files:
            print(f"  - {f.name}")
        
        df_raw = load_packet_csv_data(packet_files)
        if df_raw is not None:
            print(f"✓ Loaded {len(df_raw)} packet records")
            print(f"  Scenarios: {df_raw['scenario'].unique()}")
            print(f"  Distances: {sorted(df_raw['distance_m'].unique())} m")
            print(f"  Seeds: {sorted(df_raw['seed'].unique())}")
            
            print("\nAggregating results by distance...")
            df_agg = aggregate_packet_data(df_raw)
            
            print("\nGenerating plots...")
            plot_rssi_snr_combined(df_agg, 'packet_csv')
            plot_pdr_and_packets(df_agg, 'packet_csv')
            plot_latency(df_agg)
            plot_packet_evolution(df_raw)
            
            generate_summary_table(df_agg, 'packet_csv')
            
            print("\n" + "="*80)
            print(f"✓ Analysis complete! All plots saved to: {PLOTS_DIR}/")
            print("="*80 + "\n")
            return
    
    # Try Format 2: Distance folders
    print("Checking for FORMAT 2: Distance folders (10m/, 20m/, etc.)...")
    df_folders = scan_distance_folders(OUTPUT_DIR)
    
    if df_folders is not None:
        print(f"✓ Detected FORMAT 2: Distance folder structure")
        print(f"✓ Found {len(df_folders)} distance points: {df_folders['distance_m'].tolist()}")
        
        print("\nGenerating plots...")
        plot_rssi_snr_combined(df_folders, 'folder')
        plot_pdr_and_packets(df_folders, 'folder')
        
        generate_summary_table(df_folders, 'folder')
        
        print("\n" + "="*80)
        print(f"✓ Analysis complete! All plots saved to: {PLOTS_DIR}/")
        print("="*80 + "\n")
        return
    
    # No data found
    print("\n✗ No simulation results found!")
    print(f"\nSearched in: {OUTPUT_DIR.absolute()}")
    print("\nExpected formats:")
    print("  FORMAT 1: *_packets.csv files (baseline_seed0_packets.csv, etc.)")
    print("  FORMAT 2: Distance folders (10m/, 20m/, 100m/, etc.)")
    print("\nPlease run simulations first!")
    sys.exit(1)


if __name__ == "__main__":
    main()