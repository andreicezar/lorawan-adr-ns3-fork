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

# ---------- CSV parsing for Scenario 08 ----------
def parse_csv08(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    def find(title: str) -> Optional[int]:
        for i, line in enumerate(lines):
            if line.strip() == title:
                return i
        return None

    # locate sections
    i_overall = find("OVERALL_STATS")
    i_gateway = find("PER_GATEWAY_STATS")
    i_node = find("PER_NODE_STATS")
    
    if i_overall is None:
        raise RuntimeError(f"{path.name}: expected OVERALL_STATS section")

    def read_kv(start: int, end: int) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for i in range(start+1, end):
            if i >= len(lines):
                break
            s = lines[i].strip()
            if not s or "," not in s:
                continue
            k, v = [t.strip() for t in s.split(",", 1)]
            fv = _to_float(v)
            out[k] = fv if fv is not None else v
        return out

    # parse overall stats
    next_section = i_gateway if i_gateway is not None else i_node if i_node is not None else len(lines)
    overall = read_kv(i_overall, next_section)

    # parse gateway stats if present
    per_gateway: List[Dict[str, Any]] = []
    if i_gateway is not None:
        gateway_end = i_node if i_node is not None else len(lines)
        gateway_text = "\n".join(lines[i_gateway+1:gateway_end]).strip()
        if gateway_text and "GatewayID" in gateway_text:
            reader = csv.DictReader(io.StringIO(gateway_text))
            for row in reader:
                if not row or not any(row.values()):
                    continue
                per_gateway.append({
                    "GatewayID": _to_int(row.get("GatewayID")),
                    "RawHearings": _to_int(row.get("RawHearings")),
                    "LoadPercentage": _to_float(row.get("LoadPercentage")),
                    "Position_X": _to_float(row.get("Position_X")),
                    "Position_Y": _to_float(row.get("Position_Y")),
                })

    # parse per-node stats if present
    per_node: List[Dict[str, Any]] = []
    if i_node is not None:
        node_text = "\n".join(lines[i_node+1:]).strip()
        if node_text and "NodeID" in node_text:
            reader = csv.DictReader(io.StringIO(node_text))
            for row in reader:
                if not row or not any(row.values()):
                    continue
                per_node.append({
                    "NodeID": _to_int(row.get("NodeID")),
                    "Sent": _to_int(row.get("Sent")),
                    "RawHearings": _to_int(row.get("RawHearings")),
                    "UniqueReceived": _to_int(row.get("UniqueReceived")),
                    "UniquePDR_Percent": _to_float(row.get("UniquePDR_Percent")),
                    "OwnerGatewayIdx": _to_int(row.get("OwnerGatewayIdx")),
                    "GatewayDistributionUnique": row.get("GatewayDistributionUnique", ""),
                })

    return overall, per_gateway, per_node

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

# ---------- area helpers ----------
def normalize_area(area: str | None) -> Optional[str]:
    if not area:
        return None
    a = area.strip().lower().replace(" ", "")
    # allow 1km..5km and 1x1km..5x5km
    m = re.match(r"^([1-5])(?:x\1)?km$", a)  # 1km or 1x1km
    if m:
        n = m.group(1)
        return f"{n}x{n}km"
    return a  # assume already like 1x1km

def resolve_area_base(base_dir: Path, area: Optional[str]) -> Tuple[Path, Optional[List[str]]]:
    """
    If area is provided, return base_dir_<area>.
    If not and base_dir doesn't exist, but suffixed dirs do exist, return (base_dir, list_of_areas)
    so caller can show a helpful message.
    """
    if area:
        area_norm = normalize_area(area)
        return base_dir.parent / f"{base_dir.name}_{area_norm}", None

    if base_dir.exists():
        return base_dir, None

    # no area and base missing -> list available suffixed dirs
    parent = base_dir.parent
    prefix = base_dir.name + "_"
    options = sorted([d.name.split("_",1)[1] for d in parent.iterdir()
                      if d.is_dir() and d.name.startswith(prefix)])
    return base_dir, options if options else None

# ---------- gateway configuration inference ----------
def infer_gateway_config_from_path(path: Path) -> Tuple[int, str]:
    name = path.name.lower()
    parent = path.parent.name.lower()
    gw_patterns = [
        (r"(\d+)gw", "gateways"),
        (r"gateway[_-]?(\d+)", "gateways"),
        (r"gw[_-]?(\d+)", "gateways")
    ]
    for pattern, _ in gw_patterns:
        for text in (name, parent):
            m = re.search(pattern, text)
            if m:
                try:
                    gw = int(m.group(1))
                    return gw, f"{gw}GW"
                except:  # noqa
                    pass
    return 1, "1GW"

# ---------- load balancing analysis ----------
def analyze_load_balancing(per_gateway: List[Dict[str, Any]], overall: Dict[str, Any]) -> Dict[str, Any]:
    if not per_gateway:
        return {}
    loads = [gw.get("LoadPercentage", 0) for gw in per_gateway]
    raw_hearings = [gw.get("RawHearings", 0) for gw in per_gateway]
    load_mean = stats.mean(loads) if loads else 0
    load_std = stats.stdev(loads) if len(loads) > 1 else 0
    load_cv = (load_std / load_mean) if load_mean > 0 else 0
    total_hearings = sum(raw_hearings)
    hearing_dist = [h / total_hearings * 100 if total_hearings > 0 else 0 for h in raw_hearings]
    ideal_load = 100.0 / len(per_gateway) if per_gateway else 0
    balance_score = sum(abs(load - ideal_load) for load in loads) / len(loads) if loads else 0
    return {
        "load_mean": load_mean,
        "load_std": load_std,
        "load_cv": load_cv,
        "balance_score": balance_score,
        "hearing_distribution": hearing_dist,
        "total_hearings": total_hearings,
        "gateway_count": len(per_gateway)
    }

# ---------- deduplication analysis ----------
def analyze_deduplication(overall: Dict[str, Any]) -> Dict[str, Any]:
    total_raw = _to_int(overall.get("TotalRawHearings", 0))
    unique_packets = _to_int(overall.get("UniquePackets", 0))
    duplicate_packets = _to_int(overall.get("DuplicatePackets", 0))
    dedup_rate = _to_float(overall.get("DeduplicationRate_Percent", 0))
    avg_hearings = _to_float(overall.get("AvgHearingsPerUplink", 0))
    redundancy_factor = avg_hearings if avg_hearings else 1.0
    dedup_efficiency = (duplicate_packets / total_raw * 100) if total_raw > 0 else 0
    return {
        "total_raw_hearings": total_raw,
        "unique_packets": unique_packets,
        "duplicate_packets": duplicate_packets,
        "dedup_rate_percent": dedup_rate,
        "avg_hearings_per_uplink": avg_hearings,
        "redundancy_factor": redundancy_factor,
        "dedup_efficiency": dedup_efficiency
    }

# ---------- row builders & stats ----------
def build_row(path: Path) -> Dict[str, Any]:
    overall, per_gateway, per_node = parse_csv08(path)
    gw_count_inferred, config_name = infer_gateway_config_from_path(path)
    gw_count = _to_int(overall.get("NumberOfGateways", gw_count_inferred))
    total_sent = _to_int(overall.get("TotalSent", 0))
    total_raw = _to_int(overall.get("TotalRawHearings", 0))
    unique_packets = _to_int(overall.get("UniquePackets", 0))
    duplicate_packets = _to_int(overall.get("DuplicatePackets", 0))
    unique_pdr = _to_float(overall.get("UniquePDR_Percent", 0))
    raw_hearings_rate = _to_float(overall.get("RawHearingsRate_Percent", 0))
    dedup_rate = _to_float(overall.get("DeduplicationRate_Percent", 0))
    avg_hearings = _to_float(overall.get("AvgHearingsPerUplink", 0))
    load_variance = _to_float(overall.get("GatewayLoadVariance", 0))
    load_analysis = analyze_load_balancing(per_gateway, overall)
    _ = analyze_deduplication(overall)

    df_nodes = pd.DataFrame(per_node) if per_node else pd.DataFrame()
    node_count = len(df_nodes) if not df_nodes.empty else 0
    successful_nodes = len(df_nodes[df_nodes["UniqueReceived"] > 0]) if not df_nodes.empty else 0
    coverage_percent = (100.0 * successful_nodes / node_count) if node_count > 0 else 0
    node_pdrs = df_nodes["UniquePDR_Percent"].dropna() if not df_nodes.empty else pd.Series(dtype=float)
    avg_node_pdr = node_pdrs.mean() if not node_pdrs.empty else 0
    pdr_std = node_pdrs.std() if len(node_pdrs) > 1 else 0
    
    return {
        "Configuration": path.parent.name or path.stem,
        "Gateways": gw_count,
        "Nodes": node_count,
        "TotalSent": total_sent,
        "RawHearings": total_raw,
        "UniquePackets": unique_packets,
        "Duplicates": duplicate_packets,
        "UniquePDR(%)": unique_pdr,
        "RawHearingRate(%)": raw_hearings_rate,
        "DedupRate(%)": dedup_rate,
        "AvgHearings/Uplink": avg_hearings,
        "LoadVariance": load_variance,
        "BalanceScore": load_analysis.get("balance_score", 0),
        "Coverage(%)": coverage_percent,
        "AvgNodePDR(%)": avg_node_pdr,
        "PDR_Std": pdr_std,
        "File": str(path),
    }

# ---------- pretty printer ----------
def print_scoreboard(rows: List[Dict[str, Any]], title="SCENARIO 08 – Multi-Gateway Coordination (ns-3)"):
    if not rows:
        print("No rows to display.")
        return
    conf_w = max(15, min(25, max(len(r.get("Configuration","")) for r in rows)))
    hdr = (
        "Configuration", "GWs", "Nodes", "Sent", "Raw", "Unique", 
        "UniquePDR(%)", "DedupRate(%)", "AvgHear/Up", "Balance", "Coverage(%)"
    )
    fmt = (
        f"{{:<{conf_w}}} "
        f"{{:>3}} {{:>5}} {{:>6}} {{:>8}} {{:>8}} {{:>11}} {{:>11}} {{:>10}} {{:>8}} {{:>11}}"
    )
    def fnum(v, d=2): return f"{v:.{d}f}" if isinstance(v, (int, float)) else "NA"
    def fint(v):       return f"{int(v):d}" if isinstance(v, (int, float)) else "NA"
    header_line = fmt.format(*hdr)
    line = "-" * len(header_line)
    print("\n" + "=" * len(header_line))
    print(title)
    print("=" * len(header_line))
    print(header_line)
    print(line)
    rows_sorted = sorted(rows, key=lambda r: (r.get("Gateways", 0), r.get("Configuration", "")))
    for r in rows_sorted:
        print(fmt.format(
            r.get("Configuration",""),
            fint(r.get("Gateways")), fint(r.get("Nodes")), fint(r.get("TotalSent")),
            fint(r.get("RawHearings")), fint(r.get("UniquePackets")),
            fnum(r.get("UniquePDR(%)")), fnum(r.get("DedupRate(%)")),
            fnum(r.get("AvgHearings/Uplink")), fnum(r.get("BalanceScore")), fnum(r.get("Coverage(%)")),
        ))
    print("=" * len(header_line))

# ---------- detailed analysis printer ----------
def print_detailed_analysis(rows: List[Dict[str, Any]]):
    if not rows: return
    print("\n" + "=" * 80)
    print("DETAILED MULTI-GATEWAY ANALYSIS")
    print("=" * 80)
    gw_groups = {}
    for row in rows:
        gw_groups.setdefault(row.get("Gateways", 1), []).append(row)
    for gw_count, gw_rows in sorted(gw_groups.items()):
        print(f"\n🏗️ {gw_count} Gateway Configuration:")
        print("-" * 40)
        for row in gw_rows:
            config = row.get("Configuration", "Unknown")
            unique_pdr = row.get("UniquePDR(%)", 0)
            dedup_rate = row.get("DedupRate(%)", 0)
            balance = row.get("BalanceScore", 0)
            coverage = row.get("Coverage(%)", 0)
            avg_hearings = row.get("AvgHearings/Uplink", 0)
            print(f"  {config}:")
            print(f"    Unique PDR: {unique_pdr:6.2f}% | Coverage: {coverage:6.2f}%")
            print(f"    Dedup Rate: {dedup_rate:6.2f}% | Avg Hearings/Uplink: {avg_hearings:5.2f}")
            print(f"    Load Balance Score: {balance:6.2f} (lower = better balanced)")
    if len(gw_groups) > 1:
        print(f"\n📊 COMPARATIVE ANALYSIS:")
        print("-" * 40)
        best_pdr = max(rows, key=lambda r: r.get("UniquePDR(%)", 0))
        best_cov = max(rows, key=lambda r: r.get("Coverage(%)", 0))
        best_bal = min(rows, key=lambda r: r.get("BalanceScore", float('inf')))
        best_ded = max(rows, key=lambda r: r.get("DedupRate(%)", 0))
        print(f"🏆 Best Unique PDR: {best_pdr.get('Gateways')}GW ({best_pdr.get('Configuration')}) = {best_pdr.get('UniquePDR(%)', 0):.2f}%")
        print(f"🎯 Best Coverage: {best_cov.get('Gateways')}GW ({best_cov.get('Configuration')}) = {best_cov.get('Coverage(%)', 0):.2f}%")
        print(f"⚖️ Best Balance: {best_bal.get('Gateways')}GW ({best_bal.get('Configuration')}) = {best_bal.get('BalanceScore', 0):.2f}")
        print(f"🔄 Best Dedup: {best_ded.get('Gateways')}GW ({best_ded.get('Configuration')}) = {best_ded.get('DedupRate(%)', 0):.2f}%")
        print(f"\n📈 GATEWAY SCALING EFFECTS:")
        for gw_count in sorted(gw_groups.keys()):
            avg_pdr = stats.mean([r.get("UniquePDR(%)", 0) for r in gw_groups[gw_count]])
            avg_hear = stats.mean([r.get("AvgHearings/Uplink", 0) for r in gw_groups[gw_count]])
            print(f"  {gw_count}GW: Avg PDR={avg_pdr:6.2f}%, Avg Redundancy={avg_hear:5.2f}x")

# ---------- main ----------
def main():
    # SCOREBOARD-ONLY main: no context/init banners, no warnings, no detailed analysis.
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(add_help=False)  # keep it quiet
    ap.add_argument("paths", nargs="*", help=argparse.SUPPRESS)
    ap.add_argument("--base-dir", type=str, default="output/scenario-08-multi-gateway", help=argparse.SUPPRESS)
    ap.add_argument("--area", type=str, default=None, help=argparse.SUPPRESS)  # e.g., 1x1km or 1km..5km
    args, _ = ap.parse_known_args()

    # 1) explicit files/folders (silent)
    if args.paths:
        csvs = discover_csvs(args.paths)
    else:
        # 2) resolve area-aware base dir (stay silent if missing/ambiguous)
        base = Path(args.base_dir)
        base_resolved, area_options = resolve_area_base(base, args.area)
        if area_options is not None:
            return  # nothing to print
        csvs = discover_default(base_resolved)

    if not csvs:
        return  # nothing to print

    # Build rows WITHOUT printing anything else
    rows: List[Dict[str, Any]] = []
    for p in csvs:
        try:
            rows.append(build_row(Path(p)))
        except Exception:
            # remain silent on failures to keep output strictly the scoreboard
            pass

    if not rows:
        return  # nothing to print

    # >>> PRINT STRICTLY THE SCOREBOARD <<<
    title = "SCENARIO 08 – Multi-Gateway Coordination (ns-3)"
    if args.area:
        title += f"  (area: {normalize_area(args.area)})"
    print_scoreboard(rows, title=title)


if __name__ == "__main__":
    main()
