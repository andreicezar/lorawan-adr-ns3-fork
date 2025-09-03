#!/usr/bin/env python3
"""
Analyze ns-3 LoRaWAN Scenario 02 outputs (ADR vs fixed SF12).

Expected file contents (as produced by scenario-02-adr-comparison.cc):
- Header lines (human-readable)
- "OVERALL_STATS" section (key,value per line)
- blank line
- "PER_NODE_STATS" section
- a CSV header row followed by rows for each node

This script:
- Parses the "OVERALL_STATS" and "PER_NODE_STATS" blocks
- NEW: Extracts and prints initialization conditions from CSV or shell script
- Computes a scoreboard for ADR ON vs ADR OFF with deltas
- Prints a compact context table and metrics
"""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import argparse, csv, io, math, sys, re

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
    v = _num(x)
    return int(v) if v is not None and not math.isnan(v) else None

def _to_float(x):
    v = _num(x)
    return float(v) if v is not None and not math.isnan(v) else None

def _to_bool(x):
    if isinstance(x, bool): return x
    if x is None: return None
    t = str(x).strip().lower()
    if t in ("true","1","yes","y","on"): return True
    if t in ("false","0","no","n","off"): return False
    return None

# =============================================================================
# NEW: Extract initialization conditions
# =============================================================================
def extract_init_conditions_from_csv(overall: Dict[str, Any], per_node: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract initialization conditions from ns-3 CSV output"""
    init_conditions = {}
    
    # Basic simulation parameters from OVERALL_STATS
    init_conditions["numberOfNodes"] = len(per_node)
    init_conditions["evaluateADRinServer"] = overall.get("ADR_Enabled", False)
    
    # Try to extract initial conditions from per-node data
    if per_node:
        # Get initial SF and TP from first node (assuming all nodes start the same)
        first_node = per_node[0]
        if isinstance(first_node.get("InitialSF"), int):
            init_conditions["initialLoRaSF"] = first_node["InitialSF"]
        if isinstance(first_node.get("InitialTP_dBm"), (int, float)):
            init_conditions["initialLoRaTP_dBm"] = float(first_node["InitialTP_dBm"])
    
    # Try to infer simulation parameters
    if overall.get("TotalSent") and len(per_node) > 0:
        # Estimate packets per device
        total_sent = overall["TotalSent"]
        packets_per_device = total_sent / len(per_node)
        init_conditions["estimatedPacketsPerDevice"] = int(packets_per_device)
    
    return init_conditions

def extract_init_conditions_from_shell(shell_script_path: Path) -> Dict[str, Any]:
    """Extract initialization conditions from shell run script"""
    init_conditions = {}
    
    if not shell_script_path.exists():
        return init_conditions
    
    try:
        script_content = shell_script_path.read_text(encoding="utf-8")
        
        # Extract simulation time
        sim_time_match = re.search(r"SIM_TIME\s*=\s*(\d+)", script_content)
        if sim_time_match:
            init_conditions["simTime_min"] = int(sim_time_match.group(1))
            init_conditions["simTime_s"] = int(sim_time_match.group(1)) * 60
        
        # Extract packet interval
        pkt_interval_match = re.search(r"PKT_INTERVAL\s*=\s*(\d+)", script_content)
        if pkt_interval_match:
            init_conditions["sendInterval_s"] = int(pkt_interval_match.group(1))
        
        # Extract command line parameters
        cmd_matches = re.findall(r"--(\w+)=([^\s]+)", script_content)
        for param, value in cmd_matches:
            if param == "simulationTime":
                init_conditions["simTime_min"] = int(value)
                init_conditions["simTime_s"] = int(value) * 60
            elif param == "packetInterval":
                init_conditions["sendInterval_s"] = int(value)
            elif param == "adrEnabled":
                init_conditions["evaluateADRinServer"] = value.lower() == "true"
        
    except Exception as e:
        print(f"Warning: Could not parse shell script {shell_script_path}: {e}")
    
    return init_conditions

def find_shell_script(csv_path: Path) -> Optional[Path]:
    """Try to find the corresponding shell script for a CSV file"""
    # Common locations to look for shell scripts
    search_paths = [
        csv_path.parent / "run-02.sh",
        csv_path.parent.parent / "run-02.sh", 
        csv_path.parent.parent.parent / "run-02.sh",
        Path("run-02.sh"),
        Path("scripts/run-02.sh"),
    ]
    
    for path in search_paths:
        if path.exists():
            return path
    return None

def print_init_conditions(config_name: str, init_conditions: Dict[str, Any], source: str = "CSV") -> None:
    """Print initialization conditions in a formatted table"""
    print(f"\n=== INITIALIZATION CONDITIONS: {config_name} (from {source}) ===")
    print("-" * 65)
    
    # Core simulation parameters
    core_params = [
        ("Number of Nodes", "numberOfNodes", ""),
        ("Simulation Time", "simTime_min", "min"),
        ("Send Interval", "sendInterval_s", "s"), 
        ("ADR Enabled", "evaluateADRinServer", ""),
    ]
    
    for label, key, unit in core_params:
        val = init_conditions.get(key, "NOT FOUND")
        unit_str = f" {unit}" if unit and val != "NOT FOUND" else ""
        print(f"{label:<25}: {val}{unit_str}")
    
    print("-" * 30)
    
    # Radio parameters (mostly inferred)
    radio_params = [
        ("Initial SF", "initialLoRaSF", ""),
        ("Initial TP", "initialLoRaTP_dBm", "dBm"),
        ("Estimated pkts/device", "estimatedPacketsPerDevice", ""),
    ]
    
    for label, key, unit in radio_params:
        val = init_conditions.get(key, "NOT FOUND")
        unit_str = f" {unit}" if unit and val != "NOT FOUND" else ""
        print(f"{label:<25}: {val}{unit_str}")
    
    # Calculate expected packets per device if we have timing info
    if "simTime_s" in init_conditions and "sendInterval_s" in init_conditions:
        expected_packets = int(init_conditions["simTime_s"] / init_conditions["sendInterval_s"])
        print(f"{'Expected pkts/device':<25}: {expected_packets}")
    
    # Note about defaults (since ns-3 config is less explicit than OMNeT++)
    print(f"{'Radio defaults':<25}: SF12, 14dBm (inferred)")
    print(f"{'Bandwidth':<25}: 125 kHz (EU868 default)")
    print(f"{'Coding Rate':<25}: 4/5 (LoRaWAN default)")
    
    print("=" * 65)

# =============================================================================
# Original parsing functions
# =============================================================================
def parse_ns3_results_csv(path: Path) -> Tuple[Dict[str,Any], List[Dict[str,Any]]]:
    """
    Returns (overall, per_node_rows) where:
      overall: dict with keys from OVERALL_STATS (converted to numeric/bool where sensible)
      per_node_rows: list of dicts for the per-node table
    """
    txt = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    # locate blocks
    try:
        idx_overall = next(i for i,l in enumerate(txt) if l.strip() == "OVERALL_STATS")
    except StopIteration:
        raise RuntimeError(f"OVERALL_STATS section not found in {path.name}")
    try:
        idx_node = next(i for i,l in enumerate(txt) if l.strip() == "PER_NODE_STATS")
    except StopIteration:
        raise RuntimeError(f"PER_NODE_STATS section not found in {path.name}")

    # Parse overall block: lines after OVERALL_STATS until blank or PER_NODE_STATS
    overall: Dict[str,Any] = {}
    i = idx_overall + 1
    while i < len(txt) and i < idx_node:
        line = txt[i].strip()
        if not line:
            i += 1
            continue
        if "," in line:
            k, v = line.split(",", 1)
            k = k.strip()
            val = v.strip()
            # convert common fields
            if k == "ADR_Enabled":
                overall[k] = _to_bool(val)
            elif k in ("TotalSent","TotalReceived","TotalADRCommands"):
                overall[k] = _to_int(val)
            elif k in ("PDR_Percent","TotalAirTime_ms","AirtimeReduction_vs_SF12_Percent"):
                overall[k] = _to_float(val)
            else:
                # best effort
                nv = _to_float(val)
                overall[k] = nv if nv is not None else val
        i += 1

    # Parse per-node CSV starting at the header line (line after PER_NODE_STATS)
    header_line_idx = idx_node + 1
    # Collect subsequent lines that look like CSV rows (stop only at EOF)
    csv_text = "\n".join(txt[header_line_idx:]).strip()
    if not csv_text:
        raise RuntimeError(f"PER_NODE_STATS table appears empty in {path.name}")

    reader = csv.DictReader(io.StringIO(csv_text))
    rows: List[Dict[str,Any]] = []
    for r in reader:
        if not any((r or {}).values()):  # skip empty
            continue
        # normalize numeric fields
        for k in list(r.keys()):
            if k is None: 
                continue
            kk = k.strip()
            v = (r[k] or "").strip()
            if kk in ("NodeID","Sent","Received","ADR_Changes","InitialSF","FinalSF"):
                r[kk] = _to_int(v)
            elif kk in ("PDR_Percent","InitialTP_dBm","FinalTP_dBm","AirTime_ms"):
                r[kk] = _to_float(v)
            else:
                r[kk] = v
        rows.append(r)
    return overall, rows

def summarize(overall: Dict[str,Any], per_node: List[Dict[str,Any]], csv_path: Path) -> Dict[str,Any]:
    """
    Produce a unified summary similar to the FLoRa analyzer.
    NEW: Also extracts initialization conditions
    """
    res: Dict[str,Any] = {}
    
    # NEW: Extract initialization conditions
    init_conditions = extract_init_conditions_from_csv(overall, per_node)
    
    # Try to find and parse shell script for additional init conditions
    shell_script = find_shell_script(csv_path)
    if shell_script:
        shell_conditions = extract_init_conditions_from_shell(shell_script)
        init_conditions.update(shell_conditions)  # Shell script takes precedence
        source = f"CSV + {shell_script.name}"
    else:
        source = "CSV only"
    
    # Print initialization conditions
    config_name = csv_path.stem
    if "adr" in config_name.lower() and "enabled" in config_name.lower():
        config_label = "scenario-02-adr-enabled"
    elif "fixed" in config_name.lower() and "sf12" in config_name.lower():
        config_label = "scenario-02-fixed-sf12"
    else:
        config_label = config_name
    
    print_init_conditions(config_label, init_conditions, source)
    
    # Store init conditions in result
    res["_init_conditions"] = init_conditions
    
    # Core totals
    res["Nodes"] = len(per_node)
    res["Total Sent"] = overall.get("TotalSent")
    res["Total Received"] = overall.get("TotalReceived")
    if isinstance(res.get("Total Sent"), int) and res["Total Sent"] > 0 and isinstance(res.get("Total Received"), int):
        res["Overall PDR (%)"] = 100.0 * res["Total Received"] / res["Total Sent"]
    else:
        res["Overall PDR (%)"] = overall.get("PDR_Percent")

    # ADR flag & cmds
    res["ADR Enabled"] = overall.get("ADR_Enabled")
    if "TotalADRCommands" in overall:
        res["ADR Cmds"] = overall["TotalADRCommands"]

    # Airtime
    toa_ms = overall.get("TotalAirTime_ms")
    if isinstance(toa_ms, (int,float)):
        res["Total ToA (s)"] = float(toa_ms) / 1000.0
    if "AirtimeReduction_vs_SF12_Percent" in overall:
        res["ToA Reduction vs SF12 (%)"] = float(overall["AirtimeReduction_vs_SF12_Percent"])

    # SF distribution using FINAL SF per node
    final_sfs = [r.get("FinalSF") for r in per_node if isinstance(r.get("FinalSF"), int)]
    if final_sfs:
        total = len(final_sfs)
        mean_sf = sum(final_sfs) / total
        res["Mean SF"] = float(mean_sf)
        s79 = sum(1 for sf in final_sfs if 7 <= sf <= 9)
        s1012 = sum(1 for sf in final_sfs if 10 <= sf <= 12)
        res["SF7-9 (%)"] = 100.0 * s79 / total
        res["SF10-12 (%)"] = 100.0 * s1012 / total

    # Optional: average final TP
    final_tps = [r.get("FinalTP_dBm") for r in per_node if isinstance(r.get("FinalTP_dBm"), (int,float))]
    if final_tps:
        res["Mean Final TP (dBm)"] = sum(final_tps)/len(final_tps)

    # Keep raw references
    res["_overall_raw"] = overall
    res["_per_node_rows"] = per_node
    return res

def fmt_num(x, digits=2):
    return f"{x:.{digits}f}" if isinstance(x, (int,float)) else "NA"

def print_context(rows: List[Dict[str,Any]]):
    print("\n" + "="*100)
    print("SCENARIO 02 - ns-3 LoRaWAN ANALYSIS RESULTS (context)")
    print("="*100)
    header = ("Configuration","Nodes","ADR Enabled","Total Sent","Total Received")
    fmt = "{:<28} {:>5} {:>11} {:>11} {:>15}"
    print(fmt.format(*header))
    for r in rows:
        row = (
            r.get("Configuration",""),
            r.get("Nodes","NA"),
            str(r.get("ADR Enabled","NA")),
            r.get("Total Sent","NA"),
            r.get("Total Received","NA"),
        )
        print(fmt.format(*row))
    print("="*100)

def print_scoreboard(rows: List[Dict[str,Any]]):
    keys = [
        "Total Sent",
        "Total Received",
        "Overall PDR (%)",
        "Total ToA (s)",
        "ToA Reduction vs SF12 (%)",
        "Mean SF",
        "SF7-9 (%)",
        "SF10-12 (%)",
        "ADR Cmds",
        "Mean Final TP (dBm)",
    ]
    labels = {
        "Total Sent":"Total Sent",
        "Total Received":"Total Received",
        "Overall PDR (%)":"PDR (%)",
        "Total ToA (s)":"Total ToA (s)",
        "ToA Reduction vs SF12 (%)":"ToA Red. vs SF12 (%)",
        "Mean SF":"Mean SF",
        "SF7-9 (%)":"SF7-9 (%)",
        "SF10-12 (%)":"SF10-12 (%)",
        "ADR Cmds":"ADR Cmds",
        "Mean Final TP (dBm)":"Mean Final TP (dBm)",
    }

    def is_on(r): return bool(r.get("ADR Enabled", False))
    if len(rows) < 2:
        print("\n=== Scenario 02 - Scoreboard ===")
        for r in rows:
            print(f"\n[{r.get('Configuration','')}]")
            for k in keys:
                print(f"  {labels[k]:<26}: {fmt_num(r.get(k))}")
        return

    row_on  = None
    row_off = None
    for r in rows:
        if is_on(r): row_on = r
        else: row_off = r
    if row_on is None or row_off is None:
        row_on = rows[0]; row_off = rows[1]

    print("\n" + "="*120)
    print("SCENARIO 02 - ADR ON vs ADR OFF (ns-3)")
    print("="*120)
    print(f"{'Metric':<28} {'ADR ON':>18} {'ADR OFF':>18} {'Delta (ON-OFF)':>18}")
    print("-"*120)
    for k in keys:
        a = row_on.get(k, None); b = row_off.get(k, None); delta = None
        if isinstance(a, (int,float)) and isinstance(b, (int,float)):
            delta = a - b
        print(f"{labels[k]:<28} {fmt_num(a,3):>18} {fmt_num(b,3):>18} {fmt_num(delta,3):>18}")
    print("="*120)

def analyze_files(files: List[Path]) -> None:
    results: List[Dict[str,Any]] = []
    for p in files:
        overall, per_node = parse_ns3_results_csv(p)
        summary = summarize(overall, per_node, p)  # Pass path for init condition extraction
        # heuristic config label
        label = p.stem
        if "adr" in label.lower() and "enabled" in label.lower():
            summary["Configuration"] = "scenario-02-adr-enabled"
        elif "fixed" in label.lower() and "sf12" in label.lower():
            summary["Configuration"] = "scenario-02-fixed-sf12"
        else:
            summary["Configuration"] = label
        results.append(summary)

    # context and scoreboard
    print_context(results)
    print_scoreboard(results)

def main():
    ap = argparse.ArgumentParser(description="Analyze ns-3 Scenario 02 (ADR vs Fixed SF12) CSV results")
    ap.add_argument("paths", nargs="+", help="Paths to ns-3 CSV result files")
    ap.add_argument("--shell-script", type=Path, default=None, 
                    help="Path to shell script for additional init conditions")
    args = ap.parse_args()
    
    files = [Path(p) for p in args.paths]
    for f in files:
        if not f.exists():
            print(f"File not found: {f}", file=sys.stderr)
            sys.exit(2)
    
    analyze_files(files)

if __name__ == "__main__":
    main()