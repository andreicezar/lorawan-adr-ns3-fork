#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ns-3 — Scenario 01 Analyzer (Baseline variants) — area-aware

Usage examples:
  # auto-reads output/scenario-01-enhanced_1x1km/
  python analyze_ns3_scenario_01.py --area 1x1km

  # same (compact form also works)
  python analyze_ns3_scenario_01.py --area 1km

  # direct folder or files
  python analyze_ns3_scenario_01.py output/scenario-01-enhanced_3x3km
  python analyze_ns3_scenario_01.py output/scenario-01-enhanced_2x2km/*/result_results.csv
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import argparse, csv, re, sys

# -------------------------- defaults --------------------------
DEFAULT_BASE_DIR = Path("output") / "scenario-01-enhanced"

# -------------------------- tiny helpers --------------------------
def _to_int(s: str) -> Optional[int]:
    try:
        return int(float(str(s).strip()))
    except Exception:
        return None

def _to_float(s: str) -> Optional[float]:
    try:
        return float(str(s).strip())
    except Exception:
        return None

def _to_bool(s: str) -> Optional[bool]:
    t = str(s).strip().lower()
    if t in ("1","true","yes","on"): return True
    if t in ("0","false","no","off"): return False
    return None

def fmt_num(x, digits=2):
    return f"{x:.{digits}f}" if isinstance(x, (int,float)) else "NA"

# DR (ns-3) -> SF mapping used by scenario-01 (SF = 12 - DR).
def dr_to_sf(dr: Optional[int]) -> Optional[int]:
    if isinstance(dr, int):
        sf = 12 - dr
        if 7 <= sf <= 12:
            return sf
    return None

# -------------------------- area helpers --------------------------
def normalize_area(area: Optional[str]) -> Optional[str]:
    """
    Accepts '1x1km' or compact '1km'..'5km' and normalizes to 'NxNkm'.
    """
    if not area: return None
    a = area.strip().lower().replace(" ", "")
    m = re.match(r"^([1-5])(?:x\1)?km$", a)  # 1km or 1x1km → 1x1km
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

# -------------------------- discovery --------------------------
def discover_default_csvs(base_dir: Path) -> list[Path]:
    """
    Recursively find results CSVs under base_dir:
      base_dir/<sub-scenario>/*_results.csv
    Accepts 'result_results.csv' or '..._results.csv'.
    """
    if not base_dir.exists():
        return []
    csvs: list[Path] = []
    for pat in ("*_results.csv", "*-results.csv", "result_results.csv"):
        csvs.extend(sorted(base_dir.rglob(pat)))
    # De-dup while preserving order
    seen = set()
    uniq: list[Path] = []
    for f in csvs:
        if f.exists() and f not in seen:
            uniq.append(f); seen.add(f)
    return uniq

def collect_csvs(inputs: List[Path]) -> List[Path]:
    files: List[Path] = []
    for p in inputs:
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("*_results.csv")))
        else:
            if any(ch in str(p) for ch in "*?[]"):
                files.extend([q for q in p.parent.glob(p.name) if q.is_file()])
    # de-dup and keep order
    seen = set()
    uniq: List[Path] = []
    for f in files:
        if f.exists() and f not in seen:
            uniq.append(f); seen.add(f)
    return uniq

# -------------------------- parse ns-3 CSV --------------------------
def parse_ns3_results_csv(path: Path) -> Tuple[Dict[str,Any], Dict[str,Any], List[Dict[str,Any]]]:
    """
    Returns (config, overall, per_node_rows)
      config:   dict from CONFIGURATION block (Init/Default fields)
      overall:  dict from OVERALL_STATS (nums/bools converted)
      per_node: list of dicts from PER_NODE_STATS (with numeric conversion)
    """
    txt = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    def find_idx(title: str) -> Optional[int]:
        for i, line in enumerate(txt):
            if line.strip() == title:
                return i
        return None

    idx_cfg = find_idx("CONFIGURATION")
    idx_over = find_idx("OVERALL_STATS")
    idx_node = find_idx("PER_NODE_STATS")

    if idx_over is None or idx_node is None:
        raise RuntimeError(f"{path.name}: expected OVERALL_STATS and PER_NODE_STATS sections")

    # CONFIGURATION (optional)
    config: Dict[str,Any] = {}
    if idx_cfg is not None:
        i = idx_cfg + 1
        while i < len(txt) and i < idx_over:
            line = txt[i].strip(); i += 1
            if not line: continue
            if "," in line:
                k, v = line.split(",", 1)
                k = k.strip(); v = v.strip()
                if k in ("InitSF","InitTP","EnableADR"):
                    config[k] = _to_bool(v)
                elif k in ("DefaultSF","DefaultTP_dBm"):
                    config[k] = _to_int(v) if k == "DefaultSF" else _to_float(v)
                else:
                    config[k] = v

    # OVERALL_STATS
    overall: Dict[str,Any] = {}
    i = idx_over + 1
    while i < len(txt) and i < idx_node:
        line = txt[i].strip(); i += 1
        if not line: continue
        if "," in line:
            k, v = line.split(",", 1)
            k = k.strip(); val = v.strip()
            if k in ("TotalSent","TotalReceived","TotalADRChanges","ADRRequests","ADRResponses","NodesWithADRChanges"):
                overall[k] = _to_int(val)
            elif k in ("PDR_Percent","DropRate_Percent","AvgSF","TheoreticalToA_ms","TotalAirTime_ms",
                       "ChannelUtilization_Percent","AvgHearingsPerUplink"):
                overall[k] = _to_float(val)
            elif k == "ADR_Enabled":
                overall[k] = _to_bool(val)
            else:
                overall[k] = val

    # PER_NODE_STATS (CSV table)
    per_node: List[Dict[str,Any]] = []
    header: List[str] = []
    j = idx_node + 1
    if j < len(txt):
        header = [h.strip() for h in txt[j].split(",")]
        j += 1
    while j < len(txt):
        line = txt[j].strip(); j += 1
        if not line: continue
        parts = [p.strip() for p in csv.reader([line]).__next__()]
        if len(parts) != len(header):  # tolerate junk
            continue
        row = dict(zip(header, parts))
        for k in ("NodeID","Sent","Received","Drops","ADR_Changes","InitSF_DR","FinalSF_DR"):
            if k in row: row[k] = _to_int(row[k])
        for k in ("PDR_Percent","InitTP_dBm","FinalTP_dBm"):
            if k in row: row[k] = _to_float(row[k])
        per_node.append(row)

    if "ADR_Enabled" not in overall and "EnableADR" in config:
        overall["ADR_Enabled"] = bool(config["EnableADR"])

    return config, overall, per_node

# --------------------- init conditions (from CSV + shell) ---------------------
def extract_init_conditions_from_csv(config: Dict[str,Any], overall: Dict[str,Any], per_node: List[Dict[str,Any]]) -> Dict[str,Any]:
    init: Dict[str,Any] = {}
    init["numberOfNodes"] = len(per_node)
    init["evaluateADRinServer"] = bool(overall.get("ADR_Enabled", False))

    if per_node:
        n0 = per_node[0]
        if n0.get("InitSF_DR") is not None:
            sf0 = dr_to_sf(n0["InitSF_DR"])
            if sf0 is not None:
                init["initialLoRaSF"] = sf0
        if isinstance(n0.get("InitTP_dBm"), (int,float)):
            init["initialLoRaTP_dBm"] = float(n0["InitTP_dBm"])

    if "initialLoRaSF" not in init and isinstance(config.get("DefaultSF"), int):
        init["initialLoRaSF"] = config["DefaultSF"]
    if "initialLoRaTP_dBm" not in init and isinstance(config.get("DefaultTP_dBm"), (int,float)):
        init["initialLoRaTP_dBm"] = float(config["DefaultTP_dBm"])

    ts = overall.get("TotalSent")
    if isinstance(ts, int) and len(per_node) > 0 and ts >= 0:
        init["estimatedPacketsPerDevice"] = int(round(ts / max(1,len(per_node))))

    return init

def extract_init_conditions_from_shell(shell_script_path: Optional[Path]) -> Dict[str,Any]:
    if not shell_script_path or not shell_script_path.exists():
        return {}
    try:
        txt = shell_script_path.read_text(encoding="utf-8")
    except Exception:
        return {}
    init: Dict[str,Any] = {}

    m = re.search(r"\bSIM_TIME\s*=\s*(\d+)", txt)
    if m:
        init["simTime_min"] = int(m.group(1))
        init["simTime_s"] = int(m.group(1)) * 60

    m = re.search(r"\bPACKET_INTERVAL\s*=\s*(\d+)", txt)
    if m:
        init["sendInterval_s"] = int(m.group(1))

    for param, value in re.findall(r"--(\w+)=([^\s\\]+)", txt):
        if param == "simulationTime":
            init["simTime_min"] = int(value)
            init["simTime_s"] = int(value) * 60
        elif param == "packetInterval":
            init["sendInterval_s"] = int(value)
        elif param in ("enableADR", "adrEnabled"):
            init["evaluateADRinServer"] = value.lower() == "true"

    return init

def find_shell_script_near(csv_path: Path) -> Optional[Path]:
    candidates = [
        csv_path.parent / "run-01.sh",
        csv_path.parent.parent / "run-01.sh",
        csv_path.parent.parent.parent / "run-01.sh",
        Path("run-01.sh"),
        Path("scripts/run-01.sh"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def print_init_conditions(label: str, init_from_csv: Dict[str,Any], init_from_shell: Dict[str,Any], source: str):
    merged = dict(init_from_csv)
    merged.update({k:v for k,v in init_from_shell.items() if v is not None})  # shell overrides

    print(f"\n=== INITIALIZATION CONDITIONS: {label} (from {source}) ===")
    print("-"*65)
    core = [
        ("Number of Nodes", "numberOfNodes", ""),
        ("Simulation Time", "simTime_min", "min"),
        ("Send Interval",   "sendInterval_s", "s"),
        ("ADR Enabled",     "evaluateADRinServer", ""),
    ]
    for title, key, unit in core:
        val = merged.get(key, "NOT FOUND")
        unit_s = f" {unit}" if unit and val != "NOT FOUND" else ""
        print(f"{title:<25}: {val}{unit_s}")

    print("-"*30)
    radio = [
        ("Initial SF", "initialLoRaSF", ""),
        ("Initial TP", "initialLoRaTP_dBm", "dBm"),
        ("Estimated pkts/device", "estimatedPacketsPerDevice", ""),
    ]
    for title, key, unit in radio:
        val = merged.get(key, "NOT FOUND")
        unit_s = f" {unit}" if unit and val != "NOT FOUND" else ""
        print(f"{title:<25}: {val}{unit_s}")

    if "simTime_s" in merged and "sendInterval_s" in merged:
        exp_pkts = int(merged["simTime_s"] / max(1, merged["sendInterval_s"]))
        print(f"{'Expected pkts/device':<25}: {exp_pkts}")

    print("="*65)
    return merged

# -------------------------- summarization --------------------------
def summarize_one(csv_path: Path, shell_script: Optional[Path]) -> Dict[str,Any]:
    config, overall, per_node = parse_ns3_results_csv(csv_path)

    init_csv   = extract_init_conditions_from_csv(config, overall, per_node)
    init_shell = extract_init_conditions_from_shell(shell_script) if shell_script else {}
    merged_init = print_init_conditions(csv_path.stem, init_csv, init_shell,
                                        "CSV + run-01.sh" if init_shell else "CSV only")

    res: Dict[str,Any] = {}
    res["Configuration"]   = csv_path.parent.name if csv_path.parent.name else csv_path.stem
    res["Nodes"]           = len(per_node)
    res["SimTime_s"]       = merged_init.get("simTime_s")
    res["Interval_s"]      = merged_init.get("sendInterval_s")
    res["ADR Enabled"]     = bool(overall.get("ADR_Enabled", merged_init.get("evaluateADRinServer", False)))
    res["Initial SF"]      = merged_init.get("initialLoRaSF")
    res["Initial TP (dBm)"]= merged_init.get("initialLoRaTP_dBm")

    res["Total Sent"]      = overall.get("TotalSent")
    res["Total Received"]  = overall.get("TotalReceived")
    if isinstance(res["Total Sent"], int) and res["Total Sent"] > 0 and isinstance(res["Total Received"], int):
        res["Overall PDR (%)"] = 100.0 * res["Total Received"] / res["Total Sent"]
    else:
        res["Overall PDR (%)"] = overall.get("PDR_Percent")

    toa_ms = overall.get("TotalAirTime_ms")
    if isinstance(toa_ms, (int,float)):
        res["Total ToA (s)"] = float(toa_ms) / 1000.0

    finals = []
    for r in per_node:
        sf = dr_to_sf(r.get("FinalSF_DR"))
        if sf is not None:
            finals.append(sf)
    if finals:
        total = len(finals)
        res["Mean SF"]      = sum(finals)/total
        res["SF7-9 (%)"]    = 100.0 * sum(1 for sf in finals if 7 <= sf <= 9) / total
        res["SF10-12 (%)"]  = 100.0 * sum(1 for sf in finals if 10 <= sf <= 12) / total

    final_tps = [r.get("FinalTP_dBm") for r in per_node if isinstance(r.get("FinalTP_dBm"), (int,float))]
    if final_tps:
        res["Mean Final TP (dBm)"] = sum(final_tps)/len(final_tps)

    if isinstance(overall.get("ADRResponses"), int):
        res["ADR Cmds"]           = overall["ADRResponses"]
        res["ADR Cmds (ED recv)"] = overall["ADRResponses"]
        res["ADR Cmds (NS sent)"] = overall["ADRResponses"]
    elif isinstance(overall.get("TotalADRChanges"), int):
        res["ADR Cmds"] = overall["TotalADRChanges"]

    for missing in ("Collisions","GW Rx Started","GW Rx OK","GW RxOK (%)",
                    "Mean SNIR (dB)","Median SNIR (dB)",
                    "Mean RSSI (dBm)","Median RSSI (dBm)"):
        res[missing] = None

    res["_overall_raw"] = overall
    res["_config_raw"]  = config
    return res

# -------------------------- printing --------------------------
def print_context_table(rows: List[Dict[str,Any]]) -> None:
    print("\n" + "="*100)
    print("SCENARIO 01 - ns-3 LoRaWAN ANALYSIS RESULTS (context)")
    print("="*100)
    header = ("Configuration","Nodes","SimTime_s","Interval_s","ADR Enabled","Initial SF","Initial TP (dBm)")
    fmt = "{:<40} {:>5} {:>10} {:>11} {:>11} {:>10} {:>17}"
    print(fmt.format(*header))
    for r in rows:
        row = (
            r.get("Configuration",""),
            r.get("Nodes","NA"),
            f"{r.get('SimTime_s','NA'):.1f}" if isinstance(r.get("SimTime_s"), (int,float)) else "NA",
            f"{r.get('Interval_s','NA'):.1f}" if isinstance(r.get("Interval_s"), (int,float)) else "NA",
            str(r.get("ADR Enabled","NA")),
            r.get("Initial SF","NA"),
            f"{r.get('Initial TP (dBm)','NA'):.1f}" if isinstance(r.get("Initial TP (dBm)"), (int,float)) else "NA",
        )
        print(fmt.format(*row))
    print("="*100)

def print_scoreboard(rows: List[Dict[str,Any]]) -> None:
    keys = [
        "Total Sent", "Total Received", "Overall PDR (%)",
        "Collisions", "GW Rx Started", "GW Rx OK", "GW RxOK (%)",
        "Total ToA (s)", "Mean SF", "SF7-9 (%)", "SF10-12 (%)",
        "Mean SNIR (dB)", "Median SNIR (dB)",
        "Mean RSSI (dBm)", "Median RSSI (dBm)",
        "ADR Cmds", "ADR Cmds (ED recv)", "ADR Cmds (NS sent)"
    ]
    labels = {
        "Total Sent":"Total Sent",
        "Total Received":"Total Received",
        "Overall PDR (%)":"PDR (%)",
        "Collisions":"Collisions",
        "GW Rx Started":"GW Rx Started",
        "GW Rx OK":"GW Rx OK",
        "GW RxOK (%)":"RxOK (%)",
        "Total ToA (s)":"Total ToA (s)",
        "Mean SF":"Mean SF",
        "SF7-9 (%)":"SF7-9 (%)",
        "SF10-12 (%)":"SF10-12 (%)",
        "Mean SNIR (dB)":"Mean SNIR (dB)",
        "Median SNIR (dB)":"Median SNIR (dB)",
        "Mean RSSI (dBm)":"Mean RSSI (dBm)",
        "Median RSSI (dBm)":"Median RSSI (dBm)",
        "ADR Cmds":"ADR Cmds",
        "ADR Cmds (ED recv)":"ADR Cmds (ED recv)",
        "ADR Cmds (NS sent)":"ADR Cmds (NS sent)",
    }
    print("\n" + "="*120)
    print("SCENARIO 01 - Scoreboard (per configuration)")
    print("="*120)
    for r in rows:
        print(f"\n[{r.get('Configuration','')}]")
        for k in keys:
            print(f"  {labels[k]:<20}: {fmt_num(r.get(k))}")
    print("="*120)

# -------------------------- main --------------------------
def main():
    ap = argparse.ArgumentParser(description="Analyze ns-3 Scenario 01 (Baseline variants) — area-aware")
    ap.add_argument("paths", nargs="*", help="(optional) CSV files or directories containing '*_results.csv'")
    ap.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR,
                    help="Root folder that contains sub-scenarios (default: output/scenario-01-enhanced)")
    ap.add_argument("--shell-script", type=Path, default=None,
                    help="run-01.sh to enrich init conditions (optional)")
    ap.add_argument("--area", type=str, default=None,
                    help="Area suffix (e.g., 1x1km, 2x2km, 3x3km). Also accepts 1km..5km.")
    args = ap.parse_args()

    # 1) explicit paths win
    inputs = [Path(p) for p in args.paths]
    if inputs:
        files = collect_csvs(inputs)
    else:
        # 2) resolve area-aware base dir
        base_resolved, area_options = resolve_area_base(args.base_dir, args.area)
        if area_options is not None:
            print(f"No CSV files found under: {args.base_dir.resolve()}")
            if area_options:
                print("Available area folders:")
                for a in area_options:
                    print(f"  - {args.base_dir.name}_{a}")
                print("\nHint: pass --area <one of the above>, e.g.:")
                print(f"  python3 {Path(sys.argv[0]).name} --area {area_options[0]}")
            sys.exit(2)
        files = discover_default_csvs(base_resolved)

    if not files:
        print(f"No CSV files found.", file=sys.stderr)
        print(f"Looked under: {args.base_dir.resolve()}" + (f" (resolved: {base_resolved.resolve()})" if not inputs else ""))
        if inputs:
            print("Also checked provided paths:")
            for p in inputs: print(f"  - {p}")
        sys.exit(2)

    # Prefer user-provided shell script; else try near base dir; else near first CSV
    shell_path = args.shell_script or find_shell_script_near(args.base_dir) or find_shell_script_near(files[0])

    rows: List[Dict[str,Any]] = []
    for f in files:
        try:
            rows.append(summarize_one(f, shell_path or find_shell_script_near(f)))
        except Exception as e:
            print(f"[WARN] Failed to parse {f}: {e}", file=sys.stderr)

    if not rows:
        print("No results parsed.", file=sys.stderr)
        sys.exit(3)

    print_context_table(rows)
    print_scoreboard(rows)

if __name__ == "__main__":
    main()
