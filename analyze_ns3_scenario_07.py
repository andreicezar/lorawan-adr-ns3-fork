#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import argparse, csv, io, sys, re, math
import statistics as stats
import pandas as pd

# ---------- small numeric helpers ----------
def _num(x):
    try:
        if x is None: return None
        s = str(x).strip()
        if s == "" or s.upper() in ("NA","N/A","NULL"): return None
        return float(s)
    except Exception:
        return None

def _to_int(x):
    v = _num(x);  return int(v) if v is not None and not math.isnan(v) else None

def _to_float(x):
    v = _num(x);  return float(v) if v is not None and not math.isnan(v) else None

# ---------- CSV parsing for Scenario 07 ----------
def parse_csv07(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    def find(title: str) -> Optional[int]:
        for i, line in enumerate(lines):
            if line.strip() == title:
                return i
        return None

    # locate sections
    i_over = find("OVERALL_STATS")
    i_node = find("PER_NODE_STATS")
    if i_over is None or i_node is None:
        raise RuntimeError(f"{path.name}: expected OVERALL_STATS, PER_NODE_STATS sections")

    def read_kv(start: int, end: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for i in range(start+1, end):
            s = lines[i].strip()
            if not s or "," not in s:
                continue
            k, v = [t.strip() for t in s.split(",", 1)]
            fv = _to_float(v)
            out[k] = fv if fv is not None else v
        return out

    # parse sections
    overall = read_kv(i_over, i_node)

    # PER_NODE table
    node_text = "\n".join(lines[i_node+1:]).strip()
    per_node: List[Dict[str, Any]] = []
    if node_text:
        reader = csv.DictReader(io.StringIO(node_text))
        for row in reader:
            if not row or not any(row.values()):
                continue
            per_node.append({
                "NodeID": _to_int(row.get("NodeID")),
                "Sent": _to_int(row.get("Sent")),
                "Received": _to_int(row.get("Received")),
                "PDR_Percent": _to_float(row.get("PDR_Percent")),
                "Distance_m": _to_float(row.get("Distance_m")),
                "AvgRSSI_dBm": _to_float(row.get("AvgRSSI_dBm")),
                "AvgSNR_dB": _to_float(row.get("AvgSNR_dB")),
                "Position_X": _to_float(row.get("Position_X")),
                "Position_Y": _to_float(row.get("Position_Y")),
                "RSSISamples": _to_int(row.get("RSSISamples")),
            })
    return overall, per_node

# ---------- file discovery ----------
def discover_csvs(inputs: List[str]) -> List[Path]:
    files: List[Path] = []
    for s in inputs:
        p = Path(s)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*_results.csv")))
        else:
            if any(ch in s for ch in "*?[]") and p.parent.exists():
                for q in p.parent.glob(p.name):
                    if q.is_file():
                        files.append(q)
    seen = set(); out: List[Path] = []
    for f in files:
        if f.exists() and f not in seen:
            out.append(f); seen.add(f)
    return out

def discover_default(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    return sorted(base_dir.rglob("*_results.csv"))

# ---------- propagation model inference ----------
def infer_propagation_model_from_path(path: Path) -> Tuple[str, Optional[float]]:
    """Infer propagation model and path loss exponent from file path or name."""
    name = path.name.lower()
    parent = path.parent.name.lower()
    
    # Check for LogDistance with path loss exponent
    logdist_patterns = [
        (r"logdist[_-]?(\d+\.?\d*)", "LogDistance"),
        (r"log[_-]?distance[_-]?(\d+\.?\d*)", "LogDistance"),
        (r"pathloss[_-]?(\d+\.?\d*)", "LogDistance")
    ]
    
    for pattern, model_type in logdist_patterns:
        for text in [name, parent]:
            match = re.search(pattern, text)
            if match:
                try:
                    # Handle cases like "32" -> 3.2, "376" -> 3.76
                    exponent_str = match.group(1)
                    if "." not in exponent_str and len(exponent_str) >= 2:
                        # Convert "32" -> "3.2", "376" -> "3.76"
                        exponent_str = exponent_str[0] + "." + exponent_str[1:]
                    exponent = float(exponent_str)
                    return model_type, exponent
                except:
                    continue
    
    # Check for FreeSpace/Friis
    freespace_patterns = ["freespace", "friis", "free_space"]
    for pattern in freespace_patterns:
        if pattern in name or pattern in parent:
            return "FreeSpace", None
    
    # Default fallback
    return "Unknown", None

# ---------- distance-based analysis ----------
def analyze_distance_performance(per_node: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze performance vs distance for propagation modeling."""
    if not per_node:
        return {}
    
    df = pd.DataFrame(per_node)
    
    # Filter nodes with valid data
    valid_nodes = df.dropna(subset=['Distance_m', 'PDR_Percent', 'AvgRSSI_dBm'])
    
    if valid_nodes.empty:
        return {}
    
    # Distance bins for analysis
    distances = valid_nodes['Distance_m'].values
    min_dist, max_dist = distances.min(), distances.max()
    
    # Create distance bins
    n_bins = min(10, len(valid_nodes) // 3) if len(valid_nodes) >= 9 else 3
    bins = pd.cut(valid_nodes['Distance_m'], bins=n_bins, precision=0)
    
    binned_stats = valid_nodes.groupby(bins, observed=True).agg({
        'PDR_Percent': ['mean', 'std', 'count'],
        'AvgRSSI_dBm': ['mean', 'std'],
        'AvgSNR_dB': ['mean', 'std'],
        'Distance_m': ['mean', 'min', 'max']
    }).round(2)
    
    # Practical range analysis
    successful_nodes = valid_nodes[valid_nodes['PDR_Percent'] > 0]
    failed_nodes = valid_nodes[valid_nodes['PDR_Percent'] == 0]
    
    max_success_dist = successful_nodes['Distance_m'].max() if not successful_nodes.empty else 0
    min_fail_dist = failed_nodes['Distance_m'].min() if not failed_nodes.empty else float('inf')
    
    # RSSI vs distance correlation
    rssi_distance_corr = valid_nodes['AvgRSSI_dBm'].corr(valid_nodes['Distance_m'])
    
    return {
        'distance_bins': binned_stats,
        'max_success_distance': max_success_dist,
        'min_failure_distance': min_fail_dist if min_fail_dist != float('inf') else None,
        'rssi_distance_correlation': rssi_distance_corr,
        'distance_range': (min_dist, max_dist),
        'total_nodes_analyzed': len(valid_nodes)
    }

# ---------- row builders & stats ----------
def build_row(path: Path) -> Dict[str, Any]:
    overall, per_node = parse_csv07(path)
    
    # Infer propagation model from path
    prop_model, path_loss_exp = infer_propagation_model_from_path(path)
    
    # Override with actual model from CSV if available
    csv_model = overall.get("PropagationModel")
    if csv_model:
        prop_model = str(csv_model)
    
    # Basic stats from overall section
    total_sent = _to_int(overall.get("TotalSent", 0))
    total_received = _to_int(overall.get("TotalReceived", 0))
    pdr = _to_float(overall.get("PDR_Percent", 0))
    max_success_dist = _to_float(overall.get("MaxSuccessfulDistance_m"))
    min_fail_dist = _to_float(overall.get("MinFailureDistance_m"))
    overall_avg_rssi = _to_float(overall.get("OverallAvgRSSI_dBm"))
    
    # Node count and advanced analysis
    df = pd.DataFrame(per_node) if per_node else pd.DataFrame()
    nodes = int(df["NodeID"].nunique()) if "NodeID" in df.columns else 0
    
    # Distance and RSSI analysis
    distance_analysis = analyze_distance_performance(per_node)
    
    # RSSI/SNR statistics for received packets
    received_nodes = df[df["Received"] > 0] if not df.empty else pd.DataFrame()
    avg_rssi_received = received_nodes["AvgRSSI_dBm"].mean() if not received_nodes.empty else None
    avg_snr_received = received_nodes["AvgSNR_dB"].mean() if not received_nodes.empty else None
    rssi_std = received_nodes["AvgRSSI_dBm"].std() if not received_nodes.empty else None
    snr_std = received_nodes["AvgSNR_dB"].std() if not received_nodes.empty else None
    
    # Coverage analysis
    coverage_at_1km = len(df[(df["Distance_m"] <= 1000) & (df["PDR_Percent"] > 0)]) if not df.empty else 0
    coverage_at_3km = len(df[(df["Distance_m"] <= 3000) & (df["PDR_Percent"] > 0)]) if not df.empty else 0
    coverage_at_5km = len(df[(df["Distance_m"] <= 5000) & (df["PDR_Percent"] > 0)]) if not df.empty else 0
    
    total_at_1km = len(df[df["Distance_m"] <= 1000]) if not df.empty else 0
    total_at_3km = len(df[df["Distance_m"] <= 3000]) if not df.empty else 0
    total_at_5km = len(df[df["Distance_m"] <= 5000]) if not df.empty else 0
    
    coverage_pct_1km = (100.0 * coverage_at_1km / total_at_1km) if total_at_1km > 0 else None
    coverage_pct_3km = (100.0 * coverage_at_3km / total_at_3km) if total_at_3km > 0 else None
    coverage_pct_5km = (100.0 * coverage_at_5km / total_at_5km) if total_at_5km > 0 else None
    
    return {
        "Configuration": path.parent.name or path.stem,
        "PropagationModel": prop_model,
        "PathLossExp": path_loss_exp,
        "Nodes": nodes,
        "Sent": total_sent or 0,
        "Received": total_received or 0,
        "PDR(%)": pdr,
        "MaxSuccessDist(m)": max_success_dist,
        "MinFailDist(m)": min_fail_dist,
        "AvgRSSI(dBm)": avg_rssi_received,
        "AvgSNR(dB)": avg_snr_received,
        "RSSI_Std": rssi_std,
        "SNR_Std": snr_std,
        "Coverage@1km(%)": coverage_pct_1km,
        "Coverage@3km(%)": coverage_pct_3km,
        "Coverage@5km(%)": coverage_pct_5km,
        "File": str(path),
    }

# ---------- pretty printer (dynamic width) ----------
def print_scoreboard(rows: List[Dict[str, Any]], title="SCENARIO 07 – Propagation Model Testing (ns-3)"):
    if not rows:
        print("No rows to display.")
        return

    conf_w = max(20, min(32, max(len(r.get("Configuration","")) for r in rows)))

    hdr = (
        "Configuration", "Model", "PathLoss", "Nodes", "Sent", "Received", 
        "PDR(%)", "MaxSuccess(m)", "AvgRSSI(dBm)", "AvgSNR(dB)", 
        "Cov@1km(%)", "Cov@3km(%)", "Cov@5km(%)"
    )

    fmt = (
        f"{{:<{conf_w}}} "   # Configuration  
        f"{{:<12}} "         # Model
        f"{{:>8}} "          # PathLoss
        f"{{:>5}} "          # Nodes
        f"{{:>8}} "          # Sent
        f"{{:>9}} "          # Received
        f"{{:>7}} "          # PDR(%)
        f"{{:>12}} "         # MaxSuccess(m)
        f"{{:>12}} "         # AvgRSSI(dBm)
        f"{{:>10}} "         # AvgSNR(dB)
        f"{{:>10}} "         # Cov@1km(%)
        f"{{:>10}} "         # Cov@3km(%)
        f"{{:>10}}"          # Cov@5km(%)
    )

    def fnum(v, d=2):
        return f"{v:.{d}f}" if isinstance(v, (int, float)) else "NA"

    def fint(v):
        return f"{int(v):d}" if isinstance(v, (int, float)) else "NA"

    def fmodel(model, exp):
        if exp is not None:
            return f"{model[:8]}({exp})"
        return f"{model[:11]}"

    header_line = fmt.format(*hdr)
    line = "-" * len(header_line)
    print("\n" + "=" * len(header_line))
    print(title)
    print("=" * len(header_line))
    print(header_line)
    print(line)

    # Sort by propagation model, then path loss exponent
    rows_sorted = sorted(rows, key=lambda r: (
        r.get("PropagationModel", ""), 
        r.get("PathLossExp") or 0
    ))
    
    for r in rows_sorted:
        print(fmt.format(
            r.get("Configuration",""),
            fmodel(r.get("PropagationModel", ""), r.get("PathLossExp")),
            fnum(r.get("PathLossExp")) if r.get("PathLossExp") is not None else "NA",
            fint(r.get("Nodes")),
            fint(r.get("Sent")),
            fint(r.get("Received")),
            fnum(r.get("PDR(%)")),
            fint(r.get("MaxSuccessDist(m)")),
            fnum(r.get("AvgRSSI(dBm)")),
            fnum(r.get("AvgSNR(dB)")),
            fnum(r.get("Coverage@1km(%)")),
            fnum(r.get("Coverage@3km(%)")),
            fnum(r.get("Coverage@5km(%)")),
        ))
    print("=" * len(header_line))

# ---------- detailed analysis printer ----------
def print_detailed_analysis(rows: List[Dict[str, Any]]):
    """Print detailed propagation model comparison."""
    if not rows:
        return
    
    print("\n" + "=" * 80)
    print("DETAILED PROPAGATION MODEL ANALYSIS")
    print("=" * 80)
    
    # Group by model type
    models = {}
    for row in rows:
        model = row.get("PropagationModel", "Unknown")
        if model not in models:
            models[model] = []
        models[model].append(row)
    
    for model, model_rows in models.items():
        print(f"\n🔬 {model} Model:")
        print("-" * 40)
        
        if model == "LogDistance":
            # Sort by path loss exponent
            model_rows.sort(key=lambda r: r.get("PathLossExp", 0))
            for row in model_rows:
                exp = row.get("PathLossExp")
                pdr = row.get("PDR(%)", 0)
                max_dist = row.get("MaxSuccessDist(m)", 0)
                avg_rssi = row.get("AvgRSSI(dBm)")
                print(f"  n={exp:4.2f}: PDR={pdr:6.2f}%, MaxRange={max_dist:4.0f}m, AvgRSSI={avg_rssi:6.2f}dBm")
        else:
            for row in model_rows:
                pdr = row.get("PDR(%)", 0)
                max_dist = row.get("MaxSuccessDist(m)", 0)
                avg_rssi = row.get("AvgRSSI(dBm)")
                print(f"  PDR={pdr:6.2f}%, MaxRange={max_dist:4.0f}m, AvgRSSI={avg_rssi:6.2f}dBm")
    
    # Best performing model analysis
    best_pdr = max(rows, key=lambda r: r.get("PDR(%)", 0))
    best_range = max(rows, key=lambda r: r.get("MaxSuccessDist(m)", 0))
    
    print(f"\n🏆 BEST PERFORMERS:")
    print(f"  Best PDR: {best_pdr.get('PropagationModel')} "
          f"({best_pdr.get('PathLossExp', 'N/A')}) = {best_pdr.get('PDR(%)', 0):.2f}%")
    print(f"  Best Range: {best_range.get('PropagationModel')} "
          f"({best_range.get('PathLossExp', 'N/A')}) = {best_range.get('MaxSuccessDist(m)', 0):.0f}m")

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Scenario 07 – ns-3 Propagation Model Analyzer")
    ap.add_argument("paths", nargs="*", help="CSV files or folders (glob ok). If not given, use --base-dir.")
    ap.add_argument("--base-dir", type=str, default="output/scenario-07-propagation-models",
                    help="Folder to search for *_results.csv (default: ./output/scenario-07-propagation-models)")
    args = ap.parse_args()

    if args.paths:
        csvs = discover_csvs(args.paths)
    else:
        base = Path(args.base_dir)
        csvs = discover_default(base)
        if not csvs:
            print(f"No *_results.csv found under base-dir: {base.resolve()}", file=sys.stderr)
            sys.exit(2)

    rows: List[Dict[str, Any]] = []
    for p in csvs:
        try:
            rows.append(build_row(Path(p)))
        except Exception as e:
            print(f"[WARN] Failed to parse {p}: {e}", file=sys.stderr)

    print_scoreboard(rows)
    print_detailed_analysis(rows)

if __name__ == "__main__":
    main()