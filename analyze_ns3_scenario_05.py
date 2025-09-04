
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

# ----------------------- printing ------------------------------
def print_table(rows: List[Dict[str, Any]]) -> None:
    columns = [
    ("Config",        "Config",            None, 18),
    ("Int(s)",        "Interval (s)",      None,  6),
    ("Sent",          "Sent",              None,  7),
    ("Recv",          "Received",          None,  7),
    ("Drop",          "Dropped",           None,  6),
    ("PDR(%)",        "PDR (%)",             2,   7),
    ("Busy(%)",       "Utilization (%)",     3,   9),
    ("Avg Sends/Node","AvgTx",               2,  14),
]


    def _key(r):
        iv = r.get("Interval (s)")
        return iv if isinstance(iv, int) else 10**9
    rows_sorted = sorted(rows, key=_key)

    print("\n" + "="*100)
    print("SCENARIO 05 — Traffic Pattern Variation (ns-3) — SCOREBOARD")
    print("="*100)

    header_parts = [
        (hdr.ljust(width) if hdr == "Config" else hdr.rjust(width))
        for hdr, _, _, width in columns
    ]
    print(" ".join(header_parts))
    print("-" * 100)

    for r in rows_sorted:
        row_parts = []
        for hdr, key, dec, width in columns:
            val = r.get(key)
            if val is None:
                s = ""
            elif isinstance(val, float):
                if dec is not None:
                    s = f"{val:.{dec}f}"
                else:
                    s = str(int(round(val))) if abs(val - round(val)) < 1e-9 else f"{val:.2f}"
            else:
                s = str(val)
            row_parts.append(s.ljust(width) if hdr == "Config" else s.rjust(width))
        print(" ".join(row_parts))

    print("="*100)

def print_summaries(paths: List[Path], pdr_threshold: float) -> None:
    print("\nSIMPLE SUMMARIES (per CSV)")
    print("---------------------------")
    for p in paths:
        overall, per_node = parse_csv(p)
        row = summarize_row(p)
        mn, md, mx = node_pdr_stats(per_node)
        low = count_low_pdr(per_node, pdr_threshold)
        nodes = row.get("Nodes")
        util = row.get("Utilization (%)")
        util_s = (f"{util:.3f}%" if isinstance(util, float) else "NA")
        pdr_s  = (f"{row.get('PDR (%)'):.2f}%" if isinstance(row.get('PDR (%)'), float) else "NA")
        avg_tx = (f"{row.get('AvgTx'):.2f}" if isinstance(row.get('AvgTx'), float) else "NA")
        dro    = (str(row.get("Dropped")) if row.get("Dropped") is not None else "NA")
        mn_s   = (f"{mn:.2f}%" if isinstance(mn, float) else "NA")
        md_s   = (f"{md:.2f}%" if isinstance(md, float) else "NA")
        mx_s   = (f"{mx:.2f}%" if isinstance(mx, float) else "NA")
        low_s  = f"{low}" if isinstance(low, int) else "NA"
        nodes_s= f"{nodes}" if nodes is not None else "NA"

        print(
            f"{p.parent.name or p.stem}: "
            f"Busy {util_s}, PDR {pdr_s}, Dropped {dro}, "
            f"Avg Sends/Node {avg_tx}, "
            f"Low-PDR(<{pdr_threshold:.0f}%) nodes: {low_s}/{nodes_s}, "
            f"PDR(min/med/max): {mn_s}/{md_s}/{mx_s}"
        )

def print_common_scoreboard(rows):
    print("\n" + "="*130)
    print("SCENARIO 05 — Unified Scoreboard")
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
        "Nodes": nodes,                          # <-- NEW
        "Interval_s": int(interval_s) if interval_s is not None else None,
        "SimTime_min": sim_min,
        "Sent": sent,
        "Received": recv,
        "Dropped": drop,
        "PDR(%)": pdr,
    }
# ----------------------- ns-3 specific tweaks ------------------

# helper: infer interval from filename like “…_interval60s_…”
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

# ----------------------- main ---------------------------------
def main():
    ap = argparse.ArgumentParser(description="Scenario 05 — Simple Analyzer")
    ap.add_argument("paths", nargs="*", help="CSV files or folders (glob ok). If not given, we'll use --base-dir.")
    ap.add_argument("--base-dir", type=str, default="output/scenario-05-traffic-patterns",
                    help="Folder to search for *_results.csv when no paths are given (default: ./output/scenario-05-traffic-patterns)")
    ap.add_argument("--pdr-threshold", type=float, default=80.0, help="PDR%% threshold for low-PDR node count (default: 80)")
    args = ap.parse_args()

    if args.paths:
        csvs = discover_csvs(args.paths)
    else:
        base = Path(args.base_dir)
        csvs = discover_default(base)
        if not csvs:
            print(f"No *_results.csv found under base-dir: {base.resolve()}", file=sys.stderr)
            sys.exit(2)

    # keep your existing per-file summaries if you still want the old table
    rows = [summarize_row(p) for p in csvs]

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

    # print the unified scoreboard
    print_common_scoreboard(common_rows)


if __name__ == "__main__":
    main()
