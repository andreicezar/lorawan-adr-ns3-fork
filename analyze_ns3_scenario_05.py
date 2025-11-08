#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import argparse, csv, io, sys, math, statistics
import re
import pandas as pd

# ----------------------- parsing helpers -----------------------
def _num(x):
    try:
        if x is None: return None
        s = str(x).strip()
        if s == "": return None
        if s.upper() in ("NA","N/A","NULL"): return None
        return float(s)
    except Exception:
        return None

def _to_int(x):
    v = _num(x);  return int(v) if v is not None and not math.isnan(v) else None

def _to_float(x):
    v = _num(x);  return float(v) if v is not None and not math.isnan(v) else None

# ----------------------- CSV parsing ---------------------------
def parse_csv(path: Path):
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    def find(title: str) -> Optional[int]:
        for i, line in enumerate(lines):
            if line.strip() == title:
                return i
        return None

    i_over = find("OVERALL_STATS")
    i_node = find("PER_NODE_STATS")
    if i_over is None or i_node is None:
        raise RuntimeError(f"{path.name}: expected OVERALL_STATS and PER_NODE_STATS sections")

    overall: Dict[str, Any] = {}
    i = i_over + 1
    while i < i_node:
        s = lines[i].strip(); i += 1
        if not s or "," not in s:
            continue
        k, v = [t.strip() for t in s.split(",", 1)]
        if k in ("PacketInterval_s", "TotalSent", "TotalReceived", "PDR_Percent",
                 "PacketsDropped_SentMinusReceived", "ChannelUtilization_Percent"):
            overall[k] = _to_float(v)
        else:
            fv = _to_float(v); overall[k] = fv if fv is not None else v

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
                "AirTime_ms": _to_float(row.get("AirTime_ms")),
                "DutyCycleUsage_Percent": _to_float(row.get("DutyCycleUsage_Percent")) if row.get("DutyCycleUsage_Percent") is not None else None,
                "TransmissionCount": _to_int(row.get("TransmissionCount")),
            })
    return overall, per_node

# ----------------------- discovery -----------------------------
def discover_csvs(inputs: List[str]) -> List[Path]:
    files: List[Path] = []
    for s in inputs:
        p = Path(s)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*_results.csv")))
        else:
            # simple glob support
            if any(ch in s for ch in "*?[]") and p.parent.exists():
                for q in p.parent.glob(p.name):
                    if q.is_file():
                        files.append(q)
    # de-dup, keep order
    seen = set(); uniq: List[Path] = []
    for f in files:
        if f.exists() and f not in seen:
            uniq.append(f); seen.add(f)
    return uniq

def discover_default(base_dir: Path) -> List[Path]:
    # Look under base_dir for any *_results.csv (recursive)
    if not base_dir.exists():
        return []
    return sorted(base_dir.rglob("*_results.csv"))

# ----------------------- area helpers --------------------------
def normalize_area(area: Optional[str]) -> Optional[str]:
    """
    Accepts '1x1km' or compact '1km'..'5km' and normalizes to 'NxNkm'.
    """
    if not area: return None
    a = area.strip().lower().replace(" ", "")
    m = re.match(r"^([1-5])(?:x\1)?km$", a)  # 1km or 1x1km
    return f"{m.group(1)}x{m.group(1)}km" if m else a

def resolve_area_base(base_dir: Path, area: Optional[str]) -> tuple[Path, Optional[List[str]]]:
    """
    If area is provided, return base_dir_<area>.
    If not and base_dir doesn't exist but suffixed dirs do, return suggestions.
    """
    if area:
        return base_dir.parent / f"{base_dir.name}_{normalize_area(area)}", None
    if base_dir.exists():
        return base_dir, None
    parent = base_dir.parent
    prefix = base_dir.name + "_"
    options = sorted([d.name.split("_",1)[1] for d in parent.iterdir()
                      if d.is_dir() and d.name.startswith(prefix)])
    return base_dir, options if options else None

# ----------------------- summarization -------------------------
def summarize_row(path: Path) -> Dict[str, Any]:
    overall, per_node = parse_csv(path)

    interval = int(overall.get("PacketInterval_s")) if overall.get("PacketInterval_s") is not None else None
    total_sent = int(overall.get("TotalSent")) if overall.get("TotalSent") is not None else None
    total_recv = int(overall.get("TotalReceived")) if overall.get("TotalReceived") is not None else None
    dropped = (int(overall.get("PacketsDropped_SentMinusReceived"))
               if overall.get("PacketsDropped_SentMinusReceived") is not None
               else (total_sent - total_recv) if (total_sent is not None and total_recv is not None) else None)
    util = overall.get("ChannelUtilization_Percent")

    nodes = len(per_node) if per_node else None
    avg_tx = None
    if nodes and total_sent is not None and nodes > 0:
        avg_tx = total_sent / nodes

    row = {
        "Config": path.parent.name or path.stem,
        "Interval (s)": interval,
        "Sent": total_sent,
        "Received": total_recv,
        "Dropped": dropped,
        "PDR (%)": float(overall.get("PDR_Percent")) if overall.get("PDR_Percent") is not None else None,
        "Utilization (%)": util,
        "AvgTx": avg_tx,
        "Nodes": nodes,
    }
    return row

def node_pdr_stats(per_node: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    vals = [r.get("PDR_Percent") for r in per_node if isinstance(r.get("PDR_Percent"), (int,float))]
    if not vals:
        return None, None, None
    vals_sorted = sorted(vals)
    mn = vals_sorted[0]
    mx = vals_sorted[-1]
    md = statistics.median(vals_sorted)
    return mn, md, mx

def count_low_pdr(per_node: List[Dict[str, Any]], thr: float) -> int:
    return sum(1 for r in per_node if isinstance(r.get("PDR_Percent"), (int,float)) and r["PDR_Percent"] < thr)

# ----------------------- printing (scoreboard only) ------------------------------
def print_common_scoreboard(rows, title="SCENARIO 05 – Unified Scoreboard"):
    print("\n" + "="*130)
    print(title)
    print("="*130)
    hdr = ("Configuration", "Nodes", "Interval_s", "SimTime_min", "Sent", "Received", "Dropped", "PDR(%)")
    fmt = "{:<36} {:>5} {:>11} {:>12} {:>8} {:>9} {:>8} {:>7}"
    print(fmt.format(*hdr))
    print("-"*130)
    rows_sorted = sorted(rows, key=lambda r: (r.get("Interval_s") is None, r.get("Interval_s")))
    for r in rows_sorted:
        sim_min = r.get("SimTime_min")
        pdr = r.get("PDR(%)")
        nodes = r.get("Nodes")
        sent = r.get("Sent", 0)
        recv = r.get("Received", 0)
        drop = r.get("Dropped", 0)
        print(fmt.format(
            r.get("Configuration",""),
            f"{int(nodes):d}" if isinstance(nodes,(int,float)) else "NA",
            r.get("Interval_s",""),
            f"{sim_min:.2f}" if isinstance(sim_min,(int,float)) else "NA",
            f"{int(sent):d}" if isinstance(sent,(int,float)) else "NA",
            f"{int(recv):d}" if isinstance(recv,(int,float)) else "NA",
            f"{int(drop):d}" if isinstance(drop,(int,float)) else "NA",
            f"{pdr:.2f}" if isinstance(pdr,(int,float)) else "NA",
        ))
    print("="*130)

def build_common_row_ns3(cfg_name, interval_s, df):
    # Nodes: count unique NodeID rows if present
    nodes = None
    if "NodeID" in df.columns:
        try:
            nodes = int(df["NodeID"].nunique())
        except Exception:
            pass

    # Totals from CSV (sum per-node)
    sent = int(df["Sent"].sum())
    recv = int(df["Received"].sum())
    drop = max(0, sent - recv)
    pdr = (100.0 * recv / sent) if sent > 0 else 0.0

    # Estimate sim time from avg transmissions per node
    avg_tx = float(df["TransmissionCount"].mean()) if "TransmissionCount" in df.columns else None
    sim_min = (avg_tx * (interval_s / 60.0)) if (avg_tx is not None and interval_s) else None

    return {
        "Configuration": cfg_name,
        "Nodes": nodes,
        "Interval_s": int(interval_s) if interval_s is not None else None,
        "SimTime_min": sim_min,
        "Sent": sent,
        "Received": recv,
        "Dropped": drop,
        "PDR(%)": pdr,
    }

# ----------------------- ns-3 specific tweaks ------------------
_INTERVAL_RX = re.compile(r"interval[-_]?(\d+)s", re.I)

def infer_interval_seconds_from_name(path: Path):
    m = _INTERVAL_RX.search(path.stem)
    return int(m.group(1)) if m else None

def find_table_header_line(path: Path, header_prefix="NodeID,Sent,Received"):
    """Return 0-based line index where the per-node table header starts."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if line.strip().startswith(header_prefix):
                return i
    return None

def read_ns3_table(path: Path):
    """
    Robust CSV loader for ns-3 result files that may contain preambles/sections.
    Reads from the 'NodeID,Sent,Received,...' header onward.
    """
    start = find_table_header_line(path)
    if start is None:
        # Fallback: try to let pandas skip junk lines
        return pd.read_csv(path, engine="python", on_bad_lines="skip")
    # Read only the per-node table
    return pd.read_csv(path, skiprows=start, engine="python")

# ----------------------- main (modified to print only scoreboard) ---------------------------------
def main():
    ap = argparse.ArgumentParser(description="Scenario 05 – Traffic Pattern Variation Analyzer (ns-3)")
    ap.add_argument("paths", nargs="*", help="CSV files or folders (glob ok). If not given, we'll use --base-dir/--area.")
    ap.add_argument("--base-dir", type=str, default="output/scenario-05-traffic-patterns",
                    help="Folder to search for *_results.csv when no paths are given (default: ./output/scenario-05-traffic-patterns)")
    ap.add_argument("--area", type=str, default=None,
                    help="Area suffix (e.g., 1x1km, 2x2km, 3x3km). Also accepts 1km..5km.")
    ap.add_argument("--pdr-threshold", type=float, default=80.0, help="PDR%% threshold for low-PDR node count (default: 80)")
    args = ap.parse_args()

    # 1) explicit paths win
    if args.paths:
        csvs = discover_csvs(args.paths)
    else:
        # 2) resolve area-aware base dir
        base = Path(args.base_dir)
        base_resolved, area_options = resolve_area_base(base, args.area)
        if area_options is not None:
            print(f"No *_results.csv found under base-dir: {base.resolve()}")
            if area_options:
                print("Available area folders:")
                for a in area_options:
                    print(f"  - {base.name}_{a}")
                print("\nHint: pass --area <one of the above>, e.g.:")
                print(f"  python3 {Path(sys.argv[0]).name} --area {area_options[0]}")
            sys.exit(2)

        csvs = discover_default(base_resolved)
        if not csvs:
            print(f"No *_results.csv found under base-dir: {base_resolved.resolve()}", file=sys.stderr)
            sys.exit(2)

    # REMOVED: old table and summaries
    # rows = [summarize_row(p) for p in csvs]
    # if rows:
    #     print_table(rows)

    # build the unified (apples-to-apples) scoreboard rows
    common_rows = []
    for p in csvs:
        p = Path(p)

        # Load the per-node table safely
        df = read_ns3_table(p)

        # Config name: strip trailing "_results"
        config_name = p.stem[:-8] if p.stem.endswith("_results") else p.stem

        # Infer interval from filename; optionally fall back to a column if you add one later
        interval_seconds = infer_interval_seconds_from_name(p)

        # Build the unified row (uses Sent/Received sums from the per-node table)
        common_rows.append(build_common_row_ns3(config_name, interval_seconds, df))

    # ONLY: print the unified scoreboard (with area in the title if provided)
    title = "SCENARIO 05 – Unified Scoreboard"
    if args.area:
        title += f"  (area: {normalize_area(args.area)})"
    print_common_scoreboard(common_rows, title=title)

if __name__ == "__main__":
    main()