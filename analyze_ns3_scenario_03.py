#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import argparse, csv, io, math, re, sys

# ------------------------------------------------------------------------------------
# Fixed repo hierarchy (WSL Linux paths). No "scripts/run-03.sh" guessing anywhere.
# ------------------------------------------------------------------------------------
REPO_ROOT_DEFAULT = Path("/home/andrei/development/ns3-comparison-clean/ns-3-dev")
DEFAULT_BASE_DIR  = REPO_ROOT_DEFAULT / "output" / "scenario-03-sf-impact"
DEFAULT_SHELL     = REPO_ROOT_DEFAULT / "scratch" / "scenario-03-sf-impact" / "run-03.sh"

# ------------------------------- UNC -> Linux normalizer -------------------------------
def wsl_unc_to_linux(p: str) -> str:
    if not p:
        return p
    s = p.strip()
    if s.startswith("\\\\wsl.localhost\\Ubuntu-22.04") or s.startswith("\\\\wsl$\\Ubuntu-22.04"):
        s = s.replace("\\", "/")
        s = s.split("Ubuntu-22.04", 1)[1]
        if not s.startswith("/"):
            s = "/" + s
        return s
    return s

# ------------------------------- discovery of CSVs ------------------------------------
def discover_default_csvs(base_dir: Path) -> List[Path]:
    if not base_dir.exists():
        return []
    csvs: List[Path] = []
    for pat in ("*_results.csv", "*-results.csv", "result_results.csv"):
        csvs.extend(sorted(base_dir.rglob(pat)))
    seen = set(); uniq: List[Path] = []
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
    seen = set(); uniq: List[Path] = []
    for f in files:
        if f.exists() and f not in seen:
            uniq.append(f); seen.add(f)
    return uniq

# ------------------------------- helpers ----------------------------------------------
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

# ------------------------------- shell parsing ----------------------------------------
def extract_init_from_shell(shell_path: Optional[Path]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not shell_path or not shell_path.exists():
        return out
    txt = shell_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"--simulationTime=(\d+)", txt)
    if m:
        out["simTime_min"] = int(m.group(1)); out["simTime_s"] = out["simTime_min"] * 60
    m = re.search(r"--packetInterval=(\d+)", txt)
    if m:
        out["sendInterval_s"] = int(m.group(1))
    m = re.search(r"--nDevices=(\d+)", txt)
    if m:
        out["numberOfNodes"] = int(m.group(1))
    out["evaluateADRinServer"] = False
    return out

def print_init_snapshot(init: Dict[str, Any], source: str):
    print("\n=== INITIALIZATION SNAPSHOT (Scenario 03) — from {} ===".format(source))
    print("-"*70)
    def _line(label, key, unit=""):
        val = init.get(key, "NOT FOUND")
        unit_s = f" {unit}" if unit and val != "NOT FOUND" else ""
        print(f"{label:<28}: {val}{unit_s}")
    _line("Simulation Time", "simTime_min", "min")
    _line("Send Interval", "sendInterval_s", "s")
    _line("Number of Nodes", "numberOfNodes", "")
    _line("ADR Enabled", "evaluateADRinServer", "")
    print("="*70)

# ------------------------------- CSV parsing ------------------------------------------
def parse_ns3_results_csv(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Parses:
      OVERALL_STATS
      PER_NODE_STATS
      INTERFERENCE_STATS (optional)
    Normalizes totals & rates for collisions/undersensitivity as in newer exporters.
    """
    txt = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    def find_idx(title: str) -> Optional[int]:
        for i, line in enumerate(txt):
            if line.strip() == title:
                return i
        return None

    idx_over = find_idx("OVERALL_STATS")
    idx_node = find_idx("PER_NODE_STATS")
    idx_intr = find_idx("INTERFERENCE_STATS")

    if idx_over is None or idx_node is None:
        raise RuntimeError(f"{path.name}: expected OVERALL_STATS and PER_NODE_STATS sections")

    overall: Dict[str, Any] = {}

    # OVERALL_STATS
    i = idx_over + 1
    end_over = idx_node if idx_node is not None else len(txt)
    while i < len(txt) and i < end_over:
        line = txt[i].strip(); i += 1
        if not line or "," not in line:
            continue
        k, v = line.split(",", 1)
        k = k.strip(); v = v.strip()
        if k in ("SpreadingFactor", "TotalSent", "TotalReceived",
                 "TotalCollisions", "TotalUnderSensitivity", "TotalInterference"):
            overall[k] = _to_int(v); continue
        if k in ("PDR_Percent", "DropRate_Percent", "TotalAirTime_ms",
                 "TheoreticalAirTimePerPacket_ms", "ChannelUtilization_Percent",
                 "AirtimeScale_vs_SF7", "CollisionRate_Percent",
                 "UnderSensitivityRate_Percent", "InterferenceRate_Percent"):
            overall[k] = _to_float(v); continue
        fv = _to_float(v); overall[k] = fv if fv is not None else v

    # PER_NODE_STATS
    header_line_idx = idx_node + 1
    next_boundary = idx_intr if (idx_intr is not None and idx_intr > header_line_idx) else len(txt)
    csv_text = "\n".join(txt[header_line_idx:next_boundary]).strip()

    rows: List[Dict[str, Any]] = []
    if csv_text:
        reader = csv.DictReader(io.StringIO(csv_text))
        for r in reader:
            if not r or not any(r.values()):
                continue
            row: Dict[str, Any] = {}
            for k, v in r.items():
                kk = (k or "").strip(); vv = (v or "").strip()
                if kk in ("NodeID","Sent","Received","Collisions","Interference"):
                    row[kk] = _to_int(vv)
                elif kk in ("PDR_Percent","AirTime_ms","AvgRSSI_dBm","AvgSNR_dB","Distance_m"):
                    row[kk] = _to_float(vv)
                else:
                    row[kk] = vv
            rows.append(row)

    # INTERFERENCE_STATS (optional)
    if idx_intr is not None:
        j = idx_intr + 1
        while j < len(txt):
            line = txt[j].strip(); j += 1
            if not line or "," not in line:
                continue
            k, v = [s.strip() for s in line.split(",", 1)]
            if k in ("RxOk_Total", "Lost_Interference_Total", "Lost_UnderSensitivity_Total"):
                overall[k] = _to_int(v)
            else:
                fv = _to_float(v)
                overall[k] = fv if fv is not None else v

    # Normalize aliases / compute missing rates
    collisions_total = (overall.get("TotalCollisions")
                        if overall.get("TotalCollisions") is not None
                        else overall.get("Lost_Interference_Total"))
    undersens_total = (overall.get("TotalUnderSensitivity")
                       if overall.get("TotalUnderSensitivity") is not None
                       else overall.get("Lost_UnderSensitivity_Total"))
    if collisions_total is None and overall.get("TotalInterference") is not None:
        collisions_total = overall.get("TotalInterference")

    overall["Collisions_Total"] = collisions_total
    overall["UnderSensitivity_Total"] = undersens_total

    denom = overall.get("TotalSent") or 0
    if overall.get("CollisionRate_Percent") is None and collisions_total is not None and denom > 0:
        overall["CollisionRate_Percent"] = 100.0 * float(collisions_total) / float(denom)
    if overall.get("UnderSensitivityRate_Percent") is None and undersens_total is not None and denom > 0:
        overall["UnderSensitivityRate_Percent"] = 100.0 * float(undersens_total) / float(denom)

    return overall, rows

# ------------------------------- summarize & print ------------------------------------
def summarize_one(csv_path: Path) -> Dict[str, Any]:
    overall, per_node = parse_ns3_results_csv(csv_path)
    res: Dict[str, Any] = {}
    res["Configuration"] = csv_path.parent.name or csv_path.stem
    res["Sent"] = overall.get("TotalSent")
    res["Received"] = overall.get("TotalReceived")
    res["PDR (%)"] = overall.get("PDR_Percent")
    res["Utilization (%)"] = overall.get("ChannelUtilization_Percent")
    res["SF"] = overall.get("SpreadingFactor")

    res["Collisions"] = overall.get("Collisions_Total", 0)
    res["UnderSens"]  = overall.get("UnderSensitivity_Total", 0)
    res["Collision Rate (%)"] = overall.get("CollisionRate_Percent", 0.0)
    res["UnderSens Rate (%)"] = overall.get("UnderSensitivityRate_Percent",
                                            overall.get("InterferenceRate_Percent", 0.0))

    def _avg(col: str) -> Optional[float]:
        vals = [r.get(col) for r in per_node if isinstance(r.get(col), (int,float))]
        return (sum(vals)/len(vals)) if vals else None

    res["Avg RSSI (dBm)"] = _avg("AvgRSSI_dBm")
    res["Avg SNIR (dB)"]  = _avg("AvgSNR_dB")
    res["Avg TP (dBm)"]   = 14.0
    res["ΣNode Collisions"]   = sum([r.get("Collisions") or 0 for r in per_node]) if per_node else None
    res["ΣNode Interference"] = sum([r.get("Interference") or 0 for r in per_node]) if per_node else None
    return res

def fmt_cell(v, dec):
    if v is None:
        return "NA"
    if isinstance(v, int) and (dec is None or dec == 0):
        return str(v)
    if isinstance(v, float):
        if dec is None:
            if abs(v - round(v)) < 1e-9:
                return str(int(round(v)))
            return f"{v:.2f}"
        return f"{v:.{dec}f}"
    return str(v)

def print_sf_table(rows: List[Dict[str, Any]], title_suffix: str = "") -> None:
    columns = [
        ("Config",        "Configuration",    None, 12),
        ("Sent",          "Sent",             None, 6),
        ("Received",      "Received",         None, 8),
        ("PDR(%)",        "PDR (%)",          2,    7),
        ("Util(%)",       "Utilization (%)",  2,    7),
        ("Coll",          "Collisions",       None, 6),
        ("U-sens",        "UnderSens",        None, 7),
        ("CollRate(%)",   "Collision Rate (%)", 2, 12),
        ("USRate(%)",     "UnderSens Rate (%)", 2, 11),
        ("Avg RSSI",      "Avg RSSI (dBm)",   2,    9),
        ("Avg SNIR",      "Avg SNIR (dB)",    2,    9),
        ("SF",            "SF",               None, 4),
        ("TP(dBm)",       "Avg TP (dBm)",     1,    7),
    ]
    rows_sorted = sorted(rows, key=lambda r: r.get("SF", 99))
    print("\n" + "="*130)
    title = "SCENARIO 03 — Spreading Factor Impact (ns-3) — SCOREBOARD"
    if title_suffix:
        title += f" {title_suffix}"
    print(title)
    print("="*130)

    header_parts = []
    for hdr, _, _, width in columns:
        header_parts.append(hdr.ljust(width) if hdr == "Config" else hdr.rjust(width))
    print(" ".join(header_parts))
    print("-" * 130)

    for r in rows_sorted:
        row_parts = []
        for hdr, key, dec, width in columns:
            val = fmt_cell(r.get(key), dec)
            row_parts.append(val.ljust(width) if hdr == "Config" else val.rjust(width))
        print(" ".join(row_parts))
    print("="*130)

def print_init_conditions_per_scenario(rows: List[Dict[str, Any]], init: Dict[str, Any]) -> None:
    rows_sorted = sorted(rows, key=lambda r: r.get("SF", 99))
    for r in rows_sorted:
        sf = r.get("SF", "unknown")
        print(f"\n=== INITIALIZATION CONDITIONS: scenario-03-baseline-sf{sf} ===")
        print("-" * 65)
        def line(lbl, key, unit=""):
            val = init.get(key, "NOT FOUND")
            u = f" {unit}" if unit and val != 'NOT FOUND' else ""
            print(f"{lbl:<25}: {val}{u}")
        line("Number of Nodes", "numberOfNodes")
        line("Simulation Time", "simTime_min", "min")
        line("Send Interval", "sendInterval_s", "s")
        line("ADR Enabled", "evaluateADRinServer")
        print("-" * 30)
        print(f"{'Initial SF':<25}: {sf}")
        print(f"{'Initial TP':<25}: 14.0 dBm")
        print(f"{'Bandwidth':<25}: 125000.0 Hz")
        print(f"{'Coding Rate':<25}: 4")
        print(f"{'Max TX Duration':<25}: 4.0 s")
        print(f"{'Path Loss Sigma':<25}: 4.0 dB")
        if init.get("simTime_s") and init.get("sendInterval_s") and init["sendInterval_s"] > 0:
            expected = int(init["simTime_s"] / init["sendInterval_s"])
            print(f"{'Expected pkts/device':<25}: {expected}")
        print("=" * 65)

def print_per_node_global_avgs(files: list[Path]) -> None:
    from statistics import mean
    print("\n=== PER_NODE_AVERAGES (across all nodes in each CSV) ===")
    for f in sorted(files):
        try:
            overall, per_node = parse_ns3_results_csv(f)
            rssi_vals = [r.get("AvgRSSI_dBm") for r in per_node if isinstance(r.get("AvgRSSI_dBm"), (int,float))]
            snir_vals = [r.get("AvgSNR_dB") for r in per_node if isinstance(r.get("AvgSNR_dB"), (int,float))]
            avg_rssi = mean(rssi_vals) if rssi_vals else None
            avg_snir = mean(snir_vals) if snir_vals else None
            lab = f.parent.name or f.stem
            a = lambda v: ("NA" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v)))
            print(f"- {lab:<16} AvgRSSI_dBm={a(avg_rssi)}  AvgSNIR_dB={a(avg_snir)}")
        except Exception as e:
            print(f"- {f.name}: parse error: {e}")

# ------------------------------- area helpers ------------------------------------------
def normalize_area(area: Optional[str]) -> Optional[str]:
    """Accepts '1x1km' or compact '1km'..'5km' and normalizes to 'NxNkm'."""
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

# ------------------------------- main -----------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Analyze ns-3 Scenario 03 (SF Impact) CSV results")
    ap.add_argument("paths", nargs="*", help="(optional) CSV files or directories containing '*_results.csv'")
    ap.add_argument("--base-dir", type=str, default=str(DEFAULT_BASE_DIR),
                    help=f"Root folder containing sub-scenarios (default: {DEFAULT_BASE_DIR})")
    ap.add_argument("--shell-script", type=str, default=str(DEFAULT_SHELL),
                    help=f"Path to run-03.sh (default: {DEFAULT_SHELL})")
    ap.add_argument("--area", type=str, default=None,
                    help="Area suffix (e.g., 1x1km, 2x2km, 3x3km). Also accepts 1km..5km.")
    args = ap.parse_args()

    base_dir = Path(wsl_unc_to_linux(args.base_dir))
    shell_arg = Path(wsl_unc_to_linux(args.shell_script)) if args.shell_script else None

    # 1) explicit paths win
    inputs = [Path(wsl_unc_to_linux(p)) for p in args.paths] if args.paths else []
    if inputs:
        files = collect_csvs(inputs)
    else:
        # 2) resolve area-aware base dir
        base_resolved, area_options = resolve_area_base(base_dir, args.area)
        if area_options is not None:
            print(f"No CSV files found under: {base_dir.resolve()}")
            if area_options:
                print("Available area folders:")
                for a in area_options:
                    print(f"  - {base_dir.name}_{a}")
                print("\nHint: pass --area <one of the above>, e.g.:")
                print(f"  python3 {Path(sys.argv[0]).name} --area {area_options[0]}")
            sys.exit(2)
        files = discover_default_csvs(base_resolved)

    if not files:
        print(f"No CSV files found. Looked under: {base_dir.resolve()}")
        if inputs:
            print("Also checked provided paths:")
            for p in inputs: print(f"  - {p}")
        sys.exit(2)

    # init
    try:
        overall0, per_node0 = parse_ns3_results_csv(files[0])
    except Exception as e:
        overall0, per_node0 = {}, []
        print(f"[WARN] Could not parse first CSV for init fallback: {e}", file=sys.stderr)

    shell = shell_arg if (shell_arg and shell_arg.exists()) else None
    init = extract_init_from_shell(shell)
    if "numberOfNodes" not in init and per_node0:
        init["numberOfNodes"] = len(per_node0)
    print_init_snapshot(init, shell.name if shell else "CSV fallback")

    rows: List[Dict[str, Any]] = []
    for f in files:
        try:
            rows.append(summarize_one(f))
        except Exception as e:
            print(f"[WARN] Failed to parse {f}: {e}", file=sys.stderr)

    if not rows:
        print("No results parsed.", file=sys.stderr); sys.exit(3)

    title_suffix = ""
    if args.area:
        title_suffix = f"(area: {normalize_area(args.area)})"

    print_init_conditions_per_scenario(rows, init)
    print_per_node_global_avgs(files)
    print_sf_table(rows, title_suffix=title_suffix)

if __name__ == "__main__":
    main()
