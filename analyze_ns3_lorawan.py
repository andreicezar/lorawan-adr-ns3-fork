#!/usr/bin/env python3
"""
ns-3 LoRaWAN CSV/TXT Output Analyzer
=====================================

Supported filename patterns (case-insensitive, _ and - are equivalent):
- global-performance.txt → analyze_global_performance
- phy-performance.txt → analyze_phy_performance
- device-status.txt → analyze_device_status
- snr-log.csv (or snr_log.csv) → analyze_snr_log_csv
- ed-energy-total.csv → analyze_ed_energy_total_csv
- ed-remaining-energy.csv → analyze_ed_remaining_energy_csv
- packet-details.csv (or packet_details.csv) → analyze_packet_details_csv

Usage:
    python analyze_ns3_lorawan.py --folders runA runB --out plots --export-json
    python analyze_ns3_lorawan.py --folders runA --no-plots
"""

import re
import logging
import argparse
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

warnings.filterwarnings('ignore', category=RuntimeWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Helper Utilities
# ============================================================================

def safe_float(val: Any) -> float:
    """Convert to float, return NaN on error."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return np.nan


def extract_time_seconds(token: str) -> Optional[float]:
    """Extract seconds from token like '+123s' or '123s'."""
    m = re.match(r'\+?(\d+(?:\.\d+)?)s', token.strip())
    if m:
        return float(m.group(1))
    return None


def read_txt_with_time_prefix(filepath: Path) -> pd.DataFrame:
    """
    Read TXT file with format: +<time>s <val1> <val2> ...
    Searches first 3 tokens for time prefix.
    Returns DataFrame with 'time_s' and numeric columns.
    """
    rows = []
    with open(filepath, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            tokens = line.split()
            if not tokens:
                continue
            
            # Search first 3 tokens for time
            time_s = None
            time_idx = None
            for j in range(min(3, len(tokens))):
                t = extract_time_seconds(tokens[j])
                if t is not None:
                    time_s, time_idx = t, j
                    break
            
            if time_s is None:
                logger.warning(f"{filepath.name}:{line_num} - Cannot parse time in first 3 tokens")
                continue
            
            # Extract remaining values (excluding time token)
            values = [safe_float(t) for i, t in enumerate(tokens) if i != time_idx]
            rows.append([time_s] + values)
    
    if not rows:
        logger.warning(f"{filepath.name} - No valid rows found")
        return pd.DataFrame()
    
    max_cols = max(len(r) for r in rows)
    col_names = ['time_s'] + [f'col_{i}' for i in range(max_cols - 1)]
    padded_rows = [r + [np.nan] * (max_cols - len(r)) for r in rows]
    
    df = pd.DataFrame(padded_rows, columns=col_names)
    df = df.dropna(how='all', subset=df.columns[1:])
    
    return df


def read_csv_robust(filepath: Path) -> pd.DataFrame:
    """Read CSV with auto-detection of delimiter."""
    try:
        # Try comma first (most common)
        return pd.read_csv(filepath)
    except Exception:
        pass
    
    # Try sniffing with multiple delimiters
    try:
        return pd.read_csv(filepath, sep='[;,\t]', engine='python')
    except Exception as e:
        logger.error(f"Failed to read {filepath.name}: {e}")
        return pd.DataFrame()


def compute_cdf(data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute CDF for data array."""
    sorted_data = np.sort(data[~np.isnan(data)])
    if len(sorted_data) == 0:
        return np.array([]), np.array([])
    cdf = np.arange(1, len(sorted_data) + 1) / len(sorted_data)
    return sorted_data, cdf


# ============================================================================
# Analyzer Functions
# ============================================================================

def analyze_packet_details_csv(path: Path) -> dict:
    """
    Analyze packet_details.csv for detailed propagation metrics.
    FIX: Keep string columns (event_type, outcome) as strings.
    """
    df = read_csv_robust(path)
    
    if df.empty:
        return {
            'meta': {'path': str(path), 'type': 'packet-details', 'rows': 0},
            'metrics': {},
            'series': {}
        }
    
    # Define numeric columns to coerce
    num_cols = [
        't_s', 'node_id', 'seq_num', 'sf', 'dr', 'frequency_hz', 'tx_power_dbm',
        'distance_m', 'path_loss_db', 'shadowing_db', 'total_loss_db', 'rssi_dbm',
        'noise_floor_dbm', 'interference_dbm', 'snr_db', 'bandwidth_hz'
    ]
    
    # Create numeric view for calculations
    df_num = df.copy()
    present_num = [c for c in num_cols if c in df.columns]
    for c in present_num:
        df_num[c] = pd.to_numeric(df_num[c], errors='coerce')
    
    metrics = {}
    series = {}
    
    # Calculate statistics for numeric columns
    stat_cols = ['path_loss_db', 'shadowing_db', 'total_loss_db', 'rssi_dbm', 
                 'snr_db', 'noise_floor_dbm', 'distance_m']
    
    for col in stat_cols:
        if col in df_num.columns:
            data = df_num[col].dropna()
            if not data.empty:
                metrics[f'{col}_mean'] = float(data.mean())
                metrics[f'{col}_min'] = float(data.min())
                metrics[f'{col}_max'] = float(data.max())
                metrics[f'{col}_std'] = float(data.std())
                series[col] = data.tolist()
    
    # Success rate (keep as string)
    if 'outcome' in df.columns:
        outcome_str = df['outcome'].astype(str).str.upper()
        success_count = int((outcome_str == 'SUCCESS').sum())
        total_count = int(len(df))
        metrics['successful_packets'] = success_count
        metrics['total_packets'] = total_count
        metrics['success_rate_percent'] = float(100 * success_count / total_count) if total_count > 0 else 0.0
    
    # Time series
    if 't_s' in df_num.columns:
        series['time_s'] = df_num['t_s'].dropna().tolist()
    
    # Add all columns as series (preserving strings)
    for col in df.columns:
        if col not in series:
            series[col] = df[col].dropna().tolist()
    
    return {
        'meta': {
            'path': str(path),
            'type': 'packet-details',
            'rows': int(len(df))
        },
        'metrics': metrics,
        'series': series
    }


def analyze_phy_performance(path: Path) -> dict:
    """Analyze phy-performance.txt for PHY layer stats."""
    df = read_txt_with_time_prefix(path)
    
    if df.empty:
        return {
            'meta': {'path': str(path), 'type': 'phy-performance', 'rows': 0},
            'metrics': {},
            'series': {}
        }
    
    col_names = ['time_s', 'sent', 'received', 'interfered', 'no_more_rx', 
                 'under_sens', 'lost_sync', 'other']
    df.columns = col_names[:len(df.columns)]
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    
    total_sent = df['sent'].sum() if 'sent' in df.columns else 0
    total_received = df['received'].sum() if 'received' in df.columns else 0
    phy_pdr = (total_received / total_sent * 100) if total_sent > 0 else 0.0
    
    metrics = {
        'phy_pdr_percent': float(phy_pdr),
        'total_interfered': int(df['interfered'].sum()) if 'interfered' in df.columns else 0,
        'total_under_sensitivity': int(df['under_sens'].sum()) if 'under_sens' in df.columns else 0
    }
    
    series = {col: df[col].tolist() for col in df.columns}
    
    return {
        'meta': {'path': str(path), 'type': 'phy-performance', 'rows': len(df)},
        'metrics': metrics,
        'series': series
    }


def analyze_device_status(path: Path) -> dict:
    """
    Analyze device-status.txt for SF distribution.
    FIXED format: +<time>s <node_id> <x_pos> <y_pos> <data_rate> <tx_power_dbm>
    """
    df = read_txt_with_time_prefix(path)
    
    if df.empty:
        return {
            'meta': {'path': str(path), 'type': 'device-status', 'rows': 0},
            'metrics': {},
            'series': {}
        }
    
    # Correct column names matching ns-3 output
    col_names = ['time_s', 'node_id', 'x_pos', 'y_pos', 'data_rate', 'tx_power_dbm']
    df.columns = col_names[:len(df.columns)]
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    
    # Map DR to SF (EU868): DR5→SF7, DR4→SF8, etc.
    def dr_to_sf(dr):
        mapping = {5: 7, 4: 8, 3: 9, 2: 10, 1: 11, 0: 12}
        return mapping.get(int(dr), 7)
    
    if 'data_rate' in df.columns:
        df['sf'] = df['data_rate'].apply(dr_to_sf)
    else:
        df['sf'] = 7
    
    # SF distribution
    sf_distribution = {}
    if 'sf' in df.columns:
        sf_counts = df['sf'].value_counts().to_dict()
        sf_distribution = {f'SF{int(k)}': int(v) for k, v in sf_counts.items()}
        avg_sf = float(df['sf'].mean())
        dominant_sf = int(df['sf'].mode()[0]) if len(df['sf'].mode()) > 0 else 7
    else:
        avg_sf = 7.0
        dominant_sf = 7
    
    # TX Power statistics
    avg_tx_power = float(df['tx_power_dbm'].mean()) if 'tx_power_dbm' in df.columns else 0.0
    min_tx_power = float(df['tx_power_dbm'].min()) if 'tx_power_dbm' in df.columns else 0.0
    max_tx_power = float(df['tx_power_dbm'].max()) if 'tx_power_dbm' in df.columns else 0.0
    
    metrics = {
        'num_devices': int(df['node_id'].nunique()) if 'node_id' in df.columns else 0,
        'avg_sf': avg_sf,
        'dominant_sf': dominant_sf,
        'sf_distribution': sf_distribution,
        'avg_tx_power_dbm': avg_tx_power,
        'min_tx_power_dbm': min_tx_power,
        'max_tx_power_dbm': max_tx_power
    }
    
    series = {col: df[col].tolist() for col in df.columns}
    
    return {
        'meta': {'path': str(path), 'type': 'device-status', 'rows': len(df)},
        'metrics': metrics,
        'series': series
    }


def analyze_snr_log_csv(path: Path) -> dict:
    """Analyze snr_log.csv focusing on RSSI and SNR."""
    df = read_csv_robust(path)
    
    if df.empty:
        return {
            'meta': {'path': str(path), 'type': 'snr-log', 'rows': 0},
            'metrics': {},
            'series': {}
        }
    
    df = df.apply(pd.to_numeric, errors='coerce')
    
    metrics = {}
    series = {}
    
    stat_cols = {
        'rssi_dbm': 'rssi',
        'snr_db': 'snr',
        'margin_db': 'margin'
    }
    
    for col, prefix in stat_cols.items():
        if col in df.columns:
            data = df[col].dropna()
            if not data.empty:
                metrics[f'{prefix}_mean_dbm' if 'rssi' in col else f'{prefix}_mean_db'] = float(data.mean())
                metrics[f'{prefix}_min_dbm' if 'rssi' in col else f'{prefix}_min_db'] = float(data.min())
                metrics[f'{prefix}_max_dbm' if 'rssi' in col else f'{prefix}_max_db'] = float(data.max())
                metrics[f'{prefix}_std_dbm' if 'rssi' in col else f'{prefix}_std_db'] = float(data.std())
                series[col] = data.tolist()
    
    if 't_s' in df.columns:
        series['time_s'] = df['t_s'].dropna().tolist()
    if 'sf' in df.columns:
        series['sf'] = df['sf'].dropna().tolist()
    
    return {
        'meta': {'path': str(path), 'type': 'snr-log', 'rows': len(df)},
        'metrics': metrics,
        'series': series
    }


def analyze_ed_energy_total_csv(path: Path) -> dict:
    """Analyze ed-energy-total.csv - Total energy consumed."""
    df = read_csv_robust(path)
    
    if df.empty:
        return {
            'meta': {'path': str(path), 'type': 'energy-total', 'rows': 0},
            'metrics': {},
            'series': {}
        }
    
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    
    metrics = {}
    series = {}
    
    if 'total_J' in df.columns:
        total_energy = df['total_J']
        metrics['total_energy_j'] = float(total_energy.iloc[-1]) if len(total_energy) > 0 else 0.0
        metrics['avg_energy_j'] = float(total_energy.mean())
        
        if 't_s' in df.columns and len(df) > 1:
            duration = df['t_s'].max() - df['t_s'].min()
            if duration > 0:
                metrics['avg_power_w'] = float(total_energy.iloc[-1] / duration)
        
        series['total_J'] = total_energy.tolist()
    
    if 't_s' in df.columns:
        series['time_s'] = df['t_s'].tolist()
    
    return {
        'meta': {'path': str(path), 'type': 'energy-total', 'rows': len(df)},
        'metrics': metrics,
        'series': series
    }


def analyze_ed_remaining_energy_csv(path: Path) -> dict:
    """Analyze ed-remaining-energy.csv - Remaining battery energy."""
    df = read_csv_robust(path)
    
    if df.empty:
        return {
            'meta': {'path': str(path), 'type': 'energy-remaining', 'rows': 0},
            'metrics': {},
            'series': {}
        }
    
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    
    metrics = {}
    series = {}
    
    if 'remain_J' in df.columns and len(df) > 0:
        remaining = df['remain_J']
        initial = float(remaining.iloc[0])
        final = float(remaining.iloc[-1])
        
        metrics['initial_energy_j'] = initial
        metrics['final_remaining_j'] = final
        
        if initial != 0:
            consumed = initial - final
            consumed_pct = (consumed / abs(initial)) * 100
            metrics['battery_consumed_percent'] = float(max(0, consumed_pct))
            metrics['energy_consumed_j'] = float(consumed)
        else:
            metrics['battery_consumed_percent'] = 0.0
            metrics['energy_consumed_j'] = 0.0
        
        series['remain_J'] = remaining.tolist()
    
    if 't_s' in df.columns:
        series['time_s'] = df['t_s'].tolist()
    
    return {
        'meta': {'path': str(path), 'type': 'energy-remaining', 'rows': len(df)},
        'metrics': metrics,
        'series': series
    }


def _cumulative_runs(arr):
    """Efficiently compute cumulative run count (O(n))."""
    arr = np.asarray(arr) > 0
    if len(arr) == 0:
        return []
    starts = np.r_[arr[0], (arr[1:] & ~arr[:-1])]
    return np.cumsum(starts).tolist()


def analyze_global_performance(path: Path) -> dict:
    """
    Analyze global-performance.txt for PDR and Throughput.
    FIXED: O(n) cumulative calculation instead of O(n²).
    """
    df = read_txt_with_time_prefix(path)
    
    if df.empty:
        return {
            'meta': {'path': str(path), 'type': 'global-performance', 'rows': 0},
            'metrics': {},
            'series': {}
        }
    
    df.columns = ['time_s', 'packets_sent', 'packets_received']
    df = df.apply(pd.to_numeric, errors='coerce').dropna()
    
    # Count distinct packet events (0→1 transitions)
    sent_series = df['packets_sent'].values
    recv_series = df['packets_received'].values
    
    sent_events = 0
    received_events = 0
    
    if len(df) > 0:
        for i in range(len(sent_series)):
            if sent_series[i] > 0:
                if i == 0 or sent_series[i-1] == 0:
                    sent_events += 1
        
        for i in range(len(recv_series)):
            if recv_series[i] > 0:
                if i == 0 or recv_series[i-1] == 0:
                    received_events += 1
    
    pdr = (received_events / sent_events * 100) if sent_events > 0 else 0.0
    per = 100.0 - pdr
    
    if len(df) > 1:
        sim_duration = df['time_s'].max() - df['time_s'].min()
        throughput = received_events / sim_duration if sim_duration > 0 else 0.0
    else:
        throughput = 0.0
    
    return {
        'meta': {'path': str(path), 'type': 'global-performance', 'rows': len(df)},
        'metrics': {
            'pdr_percent': float(pdr),
            'per_percent': float(per),
            'total_packets_sent': int(sent_events),
            'total_packets_received': int(received_events),
            'throughput_pkt_per_sec': float(throughput)
        },
        'series': {
            'time_s': df['time_s'].tolist(),
            'packets_sent_cumulative': _cumulative_runs(sent_series),
            'packets_received_cumulative': _cumulative_runs(recv_series)
        }
    }


# ============================================================================
# Dispatcher
# ============================================================================

# Standardized dispatcher using hyphenated names
# Note: underscores in actual filenames are automatically converted to hyphens
# during matching, so both "snr_log.csv" and "snr-log.csv" work
DISPATCHER = {
    'global-performance': analyze_global_performance,
    'phy-performance': analyze_phy_performance,
    'device-status': analyze_device_status,
    'snr-log': analyze_snr_log_csv,
    'ed-energy-total': analyze_ed_energy_total_csv,
    'ed-remaining-energy': analyze_ed_remaining_energy_csv,
    'packet-details': analyze_packet_details_csv,
}


def dispatch_analyzer(filepath: Path) -> Optional[dict]:
    """
    Dispatch to appropriate analyzer based on filename pattern.
    
    Filename matching is flexible: underscores and hyphens are treated as equivalent.
    For example, both "snr_log.csv" and "snr-log.csv" will match the 'snr-log' pattern.
    """
    # Normalize: convert underscores to hyphens for consistent matching
    fname_lower = filepath.name.lower().replace('_', '-')
    
    for pattern, analyzer_func in DISPATCHER.items():
        if pattern in fname_lower:
            logger.info(f"Analyzing {filepath.name} with {analyzer_func.__name__}")
            try:
                return analyzer_func(filepath)
            except Exception as e:
                logger.error(f"Error analyzing {filepath.name}: {e}")
                return None
    
    logger.warning(f"No analyzer found for {filepath.name} - skipping")
    return None


# ============================================================================
# Folder Analysis
# ============================================================================

def analyze_folder(folder: Path) -> dict:
    """Analyze all CSV/TXT files in a folder."""
    folder = Path(folder)
    if not folder.exists():
        logger.error(f"Folder not found: {folder}")
        return {'error': f'Folder not found: {folder}'}
    
    logger.info(f"Analyzing folder: {folder.name}")
    
    files = list(folder.glob('*.csv')) + list(folder.glob('*.txt'))
    files = [f for f in files if f.is_file()]
    
    logger.info(f"Found {len(files)} files in {folder.name}")
    
    file_results = {}
    for f in files:
        result = dispatch_analyzer(f)
        if result:
            file_results[f.name] = result
    
    summary_metrics = compute_folder_summary(file_results)
    plot_data = prepare_plot_data(file_results)
    
    return {
        'folder': folder.name,
        'folder_path': str(folder),
        'num_files': len(files),
        'num_analyzed': len(file_results),
        'file_results': file_results,
        'summary_metrics': summary_metrics,
        'plot_data': plot_data
    }


def compute_folder_summary(file_results: Dict[str, dict]) -> dict:
    """
    Compute folder-level summary with FIXED PDR calculation.
    Uses definitive sources: RX from snr-log.csv rows, TX from global-performance.txt.
    """
    summary = {
        'pdr_percent': 0.0,
        'throughput_pkt_per_sec': 0.0,
        'total_packets_sent': 0,
        'total_packets_received': 0,
        'avg_sf': 0.0,
        'dominant_sf': 7,
        'avg_tx_power_dbm': 0.0,
        'min_tx_power_dbm': 0.0,
        'max_tx_power_dbm': 0.0,
        'rssi_mean_dbm': 0.0,
        'snr_mean_dbm': 0.0,
        'margin_mean_db': 0.0,
        'total_energy_consumed_j': 0.0,
        'battery_consumed_percent': 0.0,
        'avg_power_w': 0.0,
        'initial_battery_j': 0.0,
        'final_battery_j': 0.0
    }
    
    # Definitive sources
    rx_from_snr = None
    tx_from_global = None
    t_min, t_max = None, None
    
    rssi_vals, snr_vals, margin_vals, sf_vals = [], [], [], []
    tx_power_vals = []
    
    for fname, res in file_results.items():
        meta = res.get('meta', {})
        metrics = res.get('metrics', {})
        series = res.get('series', {})
        
        # Normalize filename for consistent matching
        fname_normalized = fname.lower().replace('_', '-')
        
        # RX definitive: snr-log.csv row count
        if fname_normalized.startswith('snr-log'):
            rx_from_snr = int(meta.get('rows', 0))
        
        # TX definitive + time window
        if fname_normalized.startswith('global-performance'):
            if 'total_packets_sent' in metrics:
                tx_from_global = int(metrics['total_packets_sent'])
            ts = series.get('time_s', [])
            if ts:
                t_min = ts[0] if t_min is None else min(t_min, ts[0])
                t_max = ts[-1] if t_max is None else max(t_max, ts[-1])
        
        # Signal stats
        if 'rssi_mean_dbm' in metrics:
            rssi_vals.append(metrics['rssi_mean_dbm'])
        if 'snr_mean_db' in metrics:
            snr_vals.append(metrics['snr_mean_db'])
        if 'margin_mean_db' in metrics:
            margin_vals.append(metrics['margin_mean_db'])
        
        # SF stats
        if 'avg_sf' in metrics:
            sf_vals.append(metrics['avg_sf'])
        if 'dominant_sf' in metrics:
            summary['dominant_sf'] = metrics['dominant_sf']
        
        # TX Power stats (from device-status)
        if 'avg_tx_power_dbm' in metrics:
            tx_power_vals.append(metrics['avg_tx_power_dbm'])
        if 'min_tx_power_dbm' in metrics:
            summary['min_tx_power_dbm'] = min(summary['min_tx_power_dbm'], metrics['min_tx_power_dbm']) if summary['min_tx_power_dbm'] > 0 else metrics['min_tx_power_dbm']
        if 'max_tx_power_dbm' in metrics:
            summary['max_tx_power_dbm'] = max(summary['max_tx_power_dbm'], metrics['max_tx_power_dbm'])
        
        # Energy: pick largest/most recent
        for k in ['total_energy_j', 'energy_consumed_j']:
            if k in metrics:
                summary['total_energy_consumed_j'] = max(
                    summary['total_energy_consumed_j'], metrics[k]
                )
        if 'battery_consumed_percent' in metrics:
            summary['battery_consumed_percent'] = metrics['battery_consumed_percent']
        if 'avg_power_w' in metrics:
            summary['avg_power_w'] = metrics['avg_power_w']
        if 'initial_energy_j' in metrics:
            summary['initial_battery_j'] = metrics['initial_energy_j']
        if 'final_remaining_j' in metrics:
            summary['final_battery_j'] = metrics['final_remaining_j']
    
    # Use definitive sources
    summary['total_packets_received'] = rx_from_snr or 0
    summary['total_packets_sent'] = tx_from_global or 0
    
    if summary['total_packets_sent'] > 0:
        summary['pdr_percent'] = 100.0 * summary['total_packets_received'] / summary['total_packets_sent']
    
    # Throughput on receive side
    if t_min is not None and t_max is not None and t_max > t_min and summary['total_packets_received'] > 0:
        summary['throughput_pkt_per_sec'] = summary['total_packets_received'] / (t_max - t_min)
    
    # Averages
    if sf_vals:
        summary['avg_sf'] = float(np.mean(sf_vals))
    if tx_power_vals:
        summary['avg_tx_power_dbm'] = float(np.mean(tx_power_vals))
    if rssi_vals:
        summary['rssi_mean_dbm'] = float(np.mean(rssi_vals))
    if snr_vals:
        summary['snr_mean_db'] = float(np.mean(snr_vals))
    if margin_vals:
        summary['margin_mean_db'] = float(np.mean(margin_vals))
    
    return summary


def prepare_plot_data(file_results: Dict[str, dict]) -> dict:
    """Prepare plot data grouped by metric type."""
    plot_data = {
        'time_series': {},
        'bar_metrics': {}
    }
    
    for fname, result in file_results.items():
        series = result.get('series', {})
        metrics = result.get('metrics', {})
        
        for metric_name, values in series.items():
            if metric_name not in plot_data['time_series']:
                plot_data['time_series'][metric_name] = {}
            plot_data['time_series'][metric_name][fname] = values
        
        for metric_name, value in metrics.items():
            if metric_name not in plot_data['bar_metrics']:
                plot_data['bar_metrics'][metric_name] = {}
            plot_data['bar_metrics'][metric_name][fname] = value
    
    return plot_data


def analyze_many(folders: List[Path]) -> List[dict]:
    """Analyze multiple folders."""
    return [analyze_folder(Path(f)) for f in folders]


# ============================================================================
# Plotting Functions (No explicit styles per spec)
# ============================================================================

def plot_folder_results(folder_report: dict, outdir: Path) -> List[Path]:
    """Generate plots with minimal styling."""
    folder_name = folder_report['folder']
    plot_dir = outdir / folder_name
    plot_dir.mkdir(parents=True, exist_ok=True)
    
    saved_plots = []
    plot_data = folder_report.get('plot_data', {})
    time_series = plot_data.get('time_series', {})
    
    # RSSI over time
    if 'rssi_dbm' in time_series:
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            for fname, values in time_series['rssi_dbm'].items():
                time_values = time_series.get('time_s', {}).get(fname, range(len(values)))
                ax.plot(time_values, values, label=fname)
            
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('RSSI (dBm)')
            ax.set_title(f'RSSI Over Time - {folder_name}')
            ax.legend()
            
            plot_path = plot_dir / 'rssi_time.png'
            plt.tight_layout()
            plt.savefig(plot_path, dpi=100)
            plt.close(fig)
            saved_plots.append(plot_path)
        except Exception as e:
            logger.error(f"Error plotting RSSI: {e}")
    
    # SNR over time
    if 'snr_db' in time_series:
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            for fname, values in time_series['snr_db'].items():
                time_values = time_series.get('time_s', {}).get(fname, range(len(values)))
                ax.plot(time_values, values, label=fname)
            
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('SNR (dB)')
            ax.set_title(f'SNR Over Time - {folder_name}')
            ax.legend()
            
            plot_path = plot_dir / 'snr_time.png'
            plt.tight_layout()
            plt.savefig(plot_path, dpi=100)
            plt.close(fig)
            saved_plots.append(plot_path)
        except Exception as e:
            logger.error(f"Error plotting SNR: {e}")
    
    # Energy consumption
    if 'total_J' in time_series:
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            for fname, values in time_series['total_J'].items():
                time_values = time_series.get('time_s', {}).get(fname, range(len(values)))
                ax.plot(time_values, values, label=fname)
            
            ax.set_xlabel('Time (s)')
            ax.set_ylabel('Total Energy Consumed (J)')
            ax.set_title(f'Energy Consumption - {folder_name}')
            ax.legend()
            
            plot_path = plot_dir / 'energy_consumed.png'
            plt.tight_layout()
            plt.savefig(plot_path, dpi=100)
            plt.close(fig)
            saved_plots.append(plot_path)
        except Exception as e:
            logger.error(f"Error plotting energy: {e}")
    
    # Additional plots omitted for brevity - follow same pattern
    
    logger.info(f"Saved {len(saved_plots)} plots for {folder_name}")
    return saved_plots


def plot_across_folders(all_reports: List[dict], outdir: Path) -> List[Path]:
    """Generate comparative plots."""
    comp_dir = outdir / '_comparisons'
    comp_dir.mkdir(parents=True, exist_ok=True)
    
    saved_plots = []
    folders = [r['folder'] for r in all_reports if 'folder' in r]
    
    kpi_configs = [
        ('pdr_percent', 'PDR (%)', 'Packet Delivery Ratio'),
        ('throughput_pkt_per_sec', 'Throughput (pkt/s)', 'Network Throughput'),
        ('avg_sf', 'Average SF', 'Spreading Factor'),
        ('avg_tx_power_dbm', 'TX Power (dBm)', 'Transmission Power'),
        ('rssi_mean_dbm', 'RSSI (dBm)', 'Mean RSSI'),
        ('snr_mean_db', 'SNR (dB)', 'Mean SNR'),
        ('total_energy_consumed_j', 'Energy (J)', 'Total Energy Consumed'),
    ]
    
    for kpi, ylabel, title in kpi_configs:
        try:
            values = [r.get('summary_metrics', {}).get(kpi, 0.0) for r in all_reports]
            
            if not any(values):
                continue
            
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.bar(range(len(folders)), values)
            ax.set_xticks(range(len(folders)))
            ax.set_xticklabels(folders, rotation=45, ha='right')
            ax.set_ylabel(ylabel)
            ax.set_title(f'{title} Comparison')
            
            plot_path = comp_dir / f'{kpi}.png'
            plt.tight_layout()
            plt.savefig(plot_path, dpi=100)
            plt.close(fig)
            saved_plots.append(plot_path)
            
        except Exception as e:
            logger.error(f"Error plotting {kpi}: {e}")
    
    logger.info(f"Saved {len(saved_plots)} comparison plots")
    return saved_plots


# ============================================================================
# CLI
# ============================================================================

def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze ns-3 LoRaWAN simulation outputs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--folders', nargs='+', required=True,
                       help='Folder paths containing CSV/TXT files')
    parser.add_argument('--out', default='plots',
                       help='Output directory for plots (default: plots)')
    parser.add_argument('--no-plots', action='store_true',
                       help='Skip generating plots')
    parser.add_argument('--export-json', action='store_true',
                       help='Export analysis results as JSON files')
    
    args = parser.parse_args()
    
    logger.info(f"Starting analysis of {len(args.folders)} folder(s)")
    all_reports = analyze_many(args.folders)
    
    if args.export_json:
        for report in all_reports:
            if 'folder' in report:
                json_path = Path(args.out) / report['folder'] / 'report.json'
                json_path.parent.mkdir(parents=True, exist_ok=True)
                with open(json_path, 'w') as f:
                    json.dump(report, f, indent=2)
                logger.info(f"Exported JSON: {json_path}")
    
    if not args.no_plots:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        
        for report in all_reports:
            if 'folder' in report:
                plot_folder_results(report, outdir)
        
        if len(all_reports) > 1:
            plot_across_folders(all_reports, outdir)
        
        logger.info(f"All plots saved to: {outdir}")
    
    # Print summary
    logger.info("\n" + "="*70)
    logger.info("ANALYSIS SUMMARY - PDR, Throughput, SF, TX Power, RSSI, SNR, Energy")
    logger.info("="*70)
    
    for report in all_reports:
        if 'folder' in report:
            folder = report['folder']
            summary = report.get('summary_metrics', {})
            
            logger.info(f"\n📁 {folder}")
            logger.info(f"   Files analyzed: {report['num_analyzed']}/{report['num_files']}")
            
            pdr = summary.get('pdr_percent', 0)
            tp = summary.get('throughput_pkt_per_sec', 0)
            sent = summary.get('total_packets_sent', 0)
            received = summary.get('total_packets_received', 0)
            
            logger.info(f"\n   📊 Delivery Performance:")
            logger.info(f"      PDR: {pdr:.2f}% ({received}/{sent} packets)")
            logger.info(f"      Throughput: {tp:.6f} pkt/s ({tp*60:.3f} pkt/min)")
            
            if summary.get('avg_sf', 0) >= 7:
                logger.info(f"\n   📡 Spreading Factor:")
                logger.info(f"      Average SF: SF{summary.get('avg_sf', 0):.1f}")
                logger.info(f"      Dominant SF: SF{summary.get('dominant_sf', 7)}")
            
            # TX Power
            if summary.get('avg_tx_power_dbm', 0) != 0:
                logger.info(f"\n   📶 Transmission Power:")
                logger.info(f"      Average: {summary.get('avg_tx_power_dbm', 0):.2f} dBm")
                if summary.get('min_tx_power_dbm', 0) != 0 or summary.get('max_tx_power_dbm', 0) != 0:
                    logger.info(f"      Range: {summary.get('min_tx_power_dbm', 0):.2f} - {summary.get('max_tx_power_dbm', 0):.2f} dBm")
            
            if summary.get('rssi_mean_dbm', 0) != 0:
                logger.info(f"\n   📡 Signal Quality:")
                logger.info(f"      Mean RSSI: {summary.get('rssi_mean_dbm', 0):.2f} dBm")
                logger.info(f"      Mean SNR: {summary.get('snr_mean_db', 0):.2f} dB")
            
            if summary.get('total_energy_consumed_j', 0) > 0:
                logger.info(f"\n   🔋 Energy:")
                logger.info(f"      Total consumed: {summary.get('total_energy_consumed_j', 0):.6f} J")
                logger.info(f"      Battery used: {summary.get('battery_consumed_percent', 0):.2f}%")
    
    logger.info("\n" + "="*70)


if __name__ == '__main__':
    main()