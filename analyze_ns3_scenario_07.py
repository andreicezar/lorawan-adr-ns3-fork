#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import argparse, csv, io, sys, re, math
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

    i_over = find("OVERALL_STATS")
    i_node = find("PER_NODE_STATS")
    if i_over is None or i_node is None:
        raise RuntimeError(f"{path.name}: expected OVERALL_STATS, PER_NODE_STATS sections")

    def read_kv(start: int, end: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for i in range(start+1, min(end, len(lines))):
            s = lines[i].strip()
            if not s or "," not in s:
                continue
            k, v = [t.strip() for t in s.split(",", 1)]
            fv = _to_float(v)
            out[k] = fv if fv is not None else v
        return out

    overall = read_kv(i_over, i_node)

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

# ---------- discovery ----------
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

# ---------- area helpers ----------
def normalize_area(area: Optional[str]) -> Optional[str]:
    if not area:
        return None
    a = area.strip().lower().replace(" ", "")
    m = re.match(r"^([1-5])(?:x\1)?km$", a)  # supports 1km or 1x1km
    return f"{m.group(1)}x{m.group(1)}km" if m else a

def area_side_km(area: Optional[str]) -> Optional[float]:
    """Return the side length in km from strings like '4x4km' or '4km'. None if unknown."""
    if not area: return None
    a = normalize_area(area)
    m = re.match(r"^([1-5])x\1km$", a)
    if m:
        return float(m.group(1))
    m = re.match(r"^([1-5])km$", a)
    if m:
        return float(m.group(1))
    return None

def resolve_area_base(base_dir: Path, area: Optional[str]) -> Tuple[Path, Optional[List[str]]]:
    if area:
        return base_dir.parent / f"{base_dir.name}_{normalize_area(area)}", None
    if base_dir.exists():
        return base_dir, None
    parent = base_dir.parent
    prefix = base_dir.name + "_"
    options = sorted([d.name.split("_",1)[1] for d in parent.iterdir()
                      if d.is_dir() and d.name.startswith(prefix)])
    return base_dir, options if options else None

# ---------- inference ----------
def infer_propagation_model_from_path(path: Path) -> Tuple[str, Optional[float]]:
    name = path.name.lower()
    parent = path.parent.name.lower()
    logdist_patterns = [
        (r"logdist[_-]?(\d+\.?\d*)", "LogDistance"),
        (r"log[_-]?distance[_-]?(\d+\.?\d*)", "LogDistance"),
        (r"pathloss[_-]?(\d+\.?\d*)", "LogDistance")
    ]
    for pattern, model_type in logdist_patterns:
        for text in (name, parent):
            match = re.search(pattern, text)
            if match:
                try:
                    exponent_str = match.group(1)
                    if "." not in exponent_str and len(exponent_str) >= 2:
                        exponent_str = exponent_str[0] + "." + exponent_str[1:]
                    exponent = float(exponent_str)
                    return model_type, exponent
                except:
                    continue
    for key in ("freespace", "friis", "free_space"):
        if key in name or key in parent:
            return "FreeSpace", None
    return "Unknown", None

# ---------- distance-binned stats (optional) ----------
def analyze_distance_performance(per_node: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not per_node:
        return {}
    df = pd.DataFrame(per_node)
    valid_nodes = df.dropna(subset=['Distance_m', 'PDR_Percent', 'AvgRSSI_dBm'])
    if valid_nodes.empty:
        return {}
    distances = valid_nodes['Distance_m'].values
    min_dist, max_dist = distances.min(), distances.max()
    n_bins = min(10, len(valid_nodes) // 3) if len(valid_nodes) >= 9 else 3
    bins = pd.cut(valid_nodes['Distance_m'], bins=n_bins, precision=0)
    binned_stats = valid_nodes.groupby(bins, observed=True).agg({
        'PDR_Percent': ['mean', 'std', 'count'],
        'AvgRSSI_dBm': ['mean', 'std'],
        'AvgSNR_dB': ['mean', 'std'],
        'Distance_m': ['mean', 'min', 'max']
    }).round(2)
    successful_nodes = valid_nodes[valid_nodes['PDR_Percent'] > 0]
    failed_nodes = valid_nodes[valid_nodes['PDR_Percent'] == 0]
    max_success_dist = successful_nodes['Distance_m'].max() if not successful_nodes.empty else 0
    min_fail_dist = failed_nodes['Distance_m'].min() if not failed_nodes.empty else float('inf')
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
def build_row(path: Path, side_km: Optional[float]) -> Dict[str, Any]:
    """
    side_km: deployment square side (e.g., 4 for 4x4km). If provided,
             coverage thresholds beyond side_km are reported as NA.
    """
    overall, per_node = parse_csv07(path)

    # Infer model from path; override if CSV carries explicit model
    prop_model, path_loss_exp = infer_propagation_model_from_path(path)
    csv_model = overall.get("PropagationModel")
    if csv_model:
        prop_model = str(csv_model)

    total_sent = _to_int(overall.get("TotalSent", 0))
    total_received = _to_int(overall.get("TotalReceived", 0))
    pdr = _to_float(overall.get("PDR_Percent", 0))
    max_success_dist = _to_float(overall.get("MaxSuccessfulDistance_m"))
    min_fail_dist = _to_float(overall.get("MinFailureDistance_m"))

    df = pd.DataFrame(per_node) if per_node else pd.DataFrame()
    nodes = int(df["NodeID"].nunique()) if "NodeID" in df.columns else 0

    # Coverage thresholds (km)
    thresholds_km = [1.0, 3.0, 5.0]
    cov_vals: Dict[float, Optional[float]] = {t: None for t in thresholds_km}
    if not df.empty and "Distance_m" in df.columns and "PDR_Percent" in df.columns:
        for t in thresholds_km:
            # If area is known and this threshold exceeds the deployment side, mark NA
            if side_km is not None and t > side_km:
                cov_vals[t] = None
                continue
            denom = len(df[df["Distance_m"] <= (t * 1000.0)])
            if denom > 0:
                num = len(df[(df["Distance_m"] <= (t * 1000.0)) & (df["PDR_Percent"] > 0)])
                cov_vals[t] = 100.0 * num / denom
            else:
                cov_vals[t] = None

    # Received-only averages
    received_nodes = df[df["Received"] > 0] if not df.empty else pd.DataFrame()
    avg_rssi_received = received_nodes["AvgRSSI_dBm"].mean() if not received_nodes.empty else None
    avg_snr_received = received_nodes["AvgSNR_dB"].mean() if not received_nodes.empty else None

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
        "Coverage@1km(%)": cov_vals[1.0],
        "Coverage@3km(%)": cov_vals[3.0],
        "Coverage@5km(%)": cov_vals[5.0],
        "File": str(path),
    }

# ---------- pretty printer ----------
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

    def fnum(v, d=2): return f"{v:.{d}f}" if isinstance(v, (int, float)) else "NA"
    def fint(v):       return f"{int(v):d}" if isinstance(v, (int, float)) else "NA"

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

# ---------- detailed analysis (unchanged) ----------
def print_detailed_analysis(rows: List[Dict[str, Any]]):
    if not rows: return
    print("\n" + "=" * 80)
    print("DETAILED PROPAGATION MODEL ANALYSIS")
    print("=" * 80)

    models: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        models.setdefault(row.get("PropagationModel","Unknown"), []).append(row)

    for model, model_rows in models.items():
        print(f"\n🔬 {model} Model:")
        print("-" * 40)
        if model == "LogDistance":
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

    best_pdr = max(rows, key=lambda r: r.get("PDR(%)", 0))
    best_range = max(rows, key=lambda r: r.get("MaxSuccessDist(m)", 0))
    print(f"\n🏆 BEST PERFORMERS:")
    print(f"  Best PDR: {best_pdr.get('PropagationModel')} "
          f"({best_pdr.get('PathLossExp', 'N/A')}) = {best_pdr.get('PDR(%)', 0):.2f}%")
    print(f"  Best Range: {best_range.get('PropagationModel')} "
          f"({best_range.get('PathLossExp', 'N/A')}) = {best_range.get('MaxSuccessDist(m)', 0):.0f}m")

# ---------- main ----------
def main():
    # SCOREBOARD-ONLY main: no context/init banners, no warnings.
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(add_help=False)  # stay quiet
    ap.add_argument("paths", nargs="*", help=argparse.SUPPRESS)
    ap.add_argument("--base-dir", type=str, default="output/scenario-07-propagation-models", help=argparse.SUPPRESS)
    ap.add_argument("--area", type=str, default=None, help=argparse.SUPPRESS)  # e.g., 1x1km or 1km..5km
    args, _ = ap.parse_known_args()

    # 1) explicit files/folders
    if args.paths:
        csvs = discover_csvs(args.paths)
        side_km = area_side_km(None)
    else:
        # 2) resolve area-aware base dir (silent on missing)
        base = Path(args.base_dir)
        base_resolved, area_options = resolve_area_base(base, args.area)
        if area_options is not None:
            return  # nothing to print
        csvs = discover_default(base_resolved)
        if not csvs:
            return  # nothing to print
        side_km = area_side_km(args.area)

    if not csvs:
        return  # nothing to print

    rows: List[Dict[str, Any]] = []
    for p in csvs:
        try:
            rows.append(build_row(Path(p), side_km))
        except Exception:
            # remain silent to keep output strictly the scoreboard
            pass

    if not rows:
        return  # nothing to print

    # >>> PRINT STRICTLY THE SCOREBOARD <<<
    title = "SCENARIO 07 – Propagation Model Testing (ns-3)"
    if args.area:
        title += f"  (area: {normalize_area(args.area)})"
    print_scoreboard(rows, title=title)


if __name__ == "__main__":
    main()
