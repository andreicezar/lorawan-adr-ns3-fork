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

# ---------- CSV parsing for Scenario 06 ----------
def parse_csv06(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    def find(title: str) -> Optional[int]:
        for i, line in enumerate(lines):
            if line.strip() == title:
                return i
        return None

    # locate sections if present
    i_over = find("OVERALL_STATS")
    i_cap  = find("CAPTURE_EFFECT_ANALYSIS")
    i_intf = find("INTERFERENCE_STATS")
    i_node = find("PER_NODE_STATS")
    if i_over is None or i_cap is None or i_node is None:
        raise RuntimeError(f"{path.name}: expected OVERALL_STATS, CAPTURE_EFFECT_ANALYSIS, PER_NODE_STATS sections")

    # helper: next section start > idx
    candidates = [i for i in [i_cap, i_intf, i_node] if i is not None]
    def next_after(idx: int) -> int:
        nxt = [j for j in candidates if j is not None and j > idx]
        return min(nxt) if nxt else len(lines)

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

    # sections (robust to optional INTERFERENCE_STATS position)
    overall = read_kv(i_over, next_after(i_over))
    capture = read_kv(i_cap,  next_after(i_cap))
    interference = {}
    if i_intf is not None:
        interference = read_kv(i_intf, next_after(i_intf))

    # PER_NODE table
    node_text = "\n".join(lines[i_node+1:]).strip()
    per_node: List[Dict[str, Any]] = []
    if node_text:
        reader = csv.DictReader(io.StringIO(node_text))
        for row in reader:
            if not row or not any(row.values()):
                continue
            # accept either "Losses" (new) or "Collisions" (old)
            losses = row.get("Losses")
            if losses is None:
                losses = row.get("Collisions")
            per_node.append({
                "NodeID": _to_int(row.get("NodeID")),
                "Sent": _to_int(row.get("Sent")),
                "Received": _to_int(row.get("Received")),
                "PDR_Percent": _to_float(row.get("PDR_Percent")),
                "Losses": _to_int(losses),
                "Distance_m": _to_float(row.get("Distance_m")),
                "Cohort": (row.get("Cohort") or "").strip(),
                "Position_X": _to_float(row.get("Position_X")),
                "Position_Y": _to_float(row.get("Position_Y")),
                "EstimatedRSSI_dBm": _to_float(row.get("EstimatedRSSI_dBm")),
            })
    return overall, capture, interference, per_node

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

# ---------- helpers to infer SF/interval/simtime ----------
_SF_RX = re.compile(r"sf[_-]?(\d+)", re.I)
def infer_sf_from_name(path: Path) -> Optional[int]:
    m = _SF_RX.search(path.stem)
    return int(m.group(1)) if m else None

# From run-06.sh / scenario: equal ~120 packets per device (duty-cycle aware)
SF_INTERVALS = {7:90, 8:95, 9:100, 10:150, 11:200, 12:260}

def estimate_sim_minutes_from_df(df: pd.DataFrame, interval_s: Optional[int]) -> Optional[float]:
    if interval_s in (None, 0):
        return None
    if "Sent" not in df.columns:
        return None
    # avg sent per node * (interval_s / 60)
    try:
        avg_tx = float(df["Sent"].mean())
        return avg_tx * (interval_s / 60.0)
    except Exception:
        return None

# ---------- row builders & stats ----------
def cohort_pdr(per_node: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    near = [r["PDR_Percent"] for r in per_node if r.get("Cohort") == "NEAR" and isinstance(r.get("PDR_Percent"), (int,float))]
    far  = [r["PDR_Percent"] for r in per_node if r.get("Cohort") == "FAR"  and isinstance(r.get("PDR_Percent"), (int,float))]
    near_pdr = sum(near)/len(near) if near else None
    far_pdr  = sum(far)/len(far)   if far  else None
    return near_pdr, far_pdr

def build_row(path: Path) -> Dict[str, Any]:
    overall, capture, interference, per_node = parse_csv06(path)
    df = pd.DataFrame(per_node) if per_node else pd.DataFrame()

    # SF/interval mapping
    sf = infer_sf_from_name(path)
    interval_s = SF_INTERVALS.get(sf) if sf in SF_INTERVALS else None

    # totals
    sent = int(df["Sent"].sum()) if "Sent" in df.columns else _to_int(overall.get("TotalSent"))
    recv = int(df["Received"].sum()) if "Received" in df.columns else _to_int(overall.get("TotalReceived"))
    sent = sent or 0
    recv = recv or 0
    dropped = max(0, sent - recv)
    pdr = (100.0 * recv / sent) if sent > 0 else 0.0

    # interference / under-sensitivity (from INTERFERENCE_STATS)
    rxok_tot   = _to_int(interference.get("RxOk_Total"))
    interf_tot = _to_int(interference.get("Lost_Interference_Total"))
    unders_tot = _to_int(interference.get("Lost_UnderSensitivity_Total"))

    # simple rates (as % of Sent)
    interf_rate = (100.0 * interf_tot / sent) if sent and interf_tot is not None else None
    unders_rate = (100.0 * unders_tot / sent) if sent and unders_tot is not None else None

    # nodes & sim time
    nodes = int(df["NodeID"].nunique()) if "NodeID" in df.columns else None
    sim_min = estimate_sim_minutes_from_df(df, interval_s)

    # capture cohort PDRs
    near_pdr = _to_float(capture.get("NearCohortPDR_Percent"))
    far_pdr  = _to_float(capture.get("FarCohortPDR_Percent"))
    if near_pdr is None or far_pdr is None:
        c_near, c_far = cohort_pdr(per_node)
        near_pdr = near_pdr if near_pdr is not None else c_near
        far_pdr  = far_pdr  if far_pdr  is not None else c_far
    cap_delta = (near_pdr - far_pdr) if (isinstance(near_pdr,(int,float)) and isinstance(far_pdr,(int,float))) else None

    # optional cross-checks (not printed, but could be logged)
    if "Losses" in df.columns:
        sum_losses = int(df["Losses"].fillna(0).sum())
        # You could assert/print if |sum_losses - dropped| is large.

    return {
        "Configuration": (path.parent.name or path.stem),
        "SF": sf,
        "Nodes": nodes,
        "Interval_s": interval_s,
        "SimTime_min": sim_min,
        "Sent": sent,
        "Received": recv,
        "Dropped": dropped,
        "PDR(%)": pdr,
        "NearPDR(%)": near_pdr,
        "FarPDR(%)":  far_pdr,
        "CaptureΔ(%)": cap_delta,
        # new (collision/interference visibility)
        "RxOk_Tot": rxok_tot,
        "Interf_Tot": interf_tot,
        "UnderSens_Tot": unders_tot,
        "InterfRate(%)": interf_rate,
        "UnderSensRate(%)": unders_rate,
        "File": str(path),
    }

# ---------- pretty printer (dynamic width) ----------
def print_scoreboard(rows: List[Dict[str, Any]], title="SCENARIO 06 — Collision & Capture (ns-3)"):
    if not rows:
        print("No rows to display.")
        return

    conf_w = max(28, min(64, max(len(r.get("Configuration","")) for r in rows)))

    hdr = (
        "Configuration","SF","Nodes","Interval_s","SimTime_min",
        "Sent","Received","Dropped","PDR(%)","NearPDR(%)","FarPDR(%)","CaptureΔ(%)",
        "Interf_Tot","UnderSens_Tot"
    )

    # 14 placeholders to match 14 headers
    fmt = (
        f"{{:<{conf_w}}} "  # Configuration
        f"{{:>2}} "         # SF
        f"{{:>5}} "         # Nodes
        f"{{:>10}} "        # Interval_s
        f"{{:>11}} "        # SimTime_min
        f"{{:>8}} "         # Sent
        f"{{:>9}} "         # Received
        f"{{:>8}} "         # Dropped
        f"{{:>7}} "         # PDR(%)
        f"{{:>10}} "        # NearPDR(%)
        f"{{:>9}} "         # FarPDR(%)
        f"{{:>10}} "        # CaptureΔ(%)
        f"{{:>11}} "        # Interf_Tot
        f"{{:>15}}"         # UnderSens_Tot
    )

    def fnum(v, d=2):
        return f"{v:.{d}f}" if isinstance(v, (int, float)) else "NA"

    def fint(v):
        return f"{int(v):d}" if isinstance(v, (int, float)) else "NA"

    header_line = fmt.format(*hdr)
    line = "-" * len(header_line)
    print("\n" + "=" * len(header_line))
    print(title)
    print("=" * len(header_line))
    print(header_line)
    print(line)

    rows_sorted = sorted(rows, key=lambda r: (r.get("SF") is None, r.get("SF")))
    for r in rows_sorted:
        print(fmt.format(
            r.get("Configuration",""),
            r.get("SF",""),
            fint(r.get("Nodes")),
            r.get("Interval_s","NA"),
            fnum(r.get("SimTime_min")),
            fint(r.get("Sent")),
            fint(r.get("Received")),
            fint(r.get("Dropped")),
            fnum(r.get("PDR(%)")),
            fnum(r.get("NearPDR(%)")),
            fnum(r.get("FarPDR(%)")),
            fnum(r.get("CaptureΔ(%)")),
            fint(r.get("Interf_Tot")),
            fint(r.get("UnderSens_Tot")),
        ))
    print("=" * len(header_line))


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description="Scenario 06 — ns-3 Collision & Capture Analyzer")
    ap.add_argument("paths", nargs="*", help="CSV files or folders (glob ok). If not given, use --base-dir.")
    ap.add_argument("--base-dir", type=str, default="output/scenario-06-collision-capture",
                    help="Folder to search for *_results.csv (default: ./output/scenario-06-collision-capture)")
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

if __name__ == "__main__":
    main()
