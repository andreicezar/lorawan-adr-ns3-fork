#!/usr/bin/env python3
"""
Update OMNeT++ .ini files to use new positions from a CSV, without touching any
other settings.

This version updates:
  - Positions:
      **.loRaGW[<id>].**.initialX/Y/Z
      **.loRaNodes[<id>].**.initialX/Y/Z
  - Constraint area:
      **.constraintAreaMin/Max X/Y/Z
  - Paths (adds exactly one extra '../' for relative paths):
      * energy / cloud config lines:
          **.loRaNodes[*].LoRaNic.radio.energyConsumer.configFile = xmldoc("../../energyConsumptionParameters.xml")
          **.ipv4Delayer.config = xmldoc("../../cloudDelays.xml")
      * RESULTS FILES (NEW):
          output-scalar-file = "results/omnetpp-scenario-01-s${runnumber}.sca"  -> "../results/..."
          output-vector-file = "results/omnetpp-scenario-01-s${runnumber}.vec"  -> "../results/..."
"""

import argparse
import csv
import glob
import os
import re
from collections import defaultdict
from typing import Dict, Tuple, List

# ---------- CSV parsing ----------

def load_positions(csv_path: str, scenario_name: str):
    gw_pos: Dict[int, Tuple[float,float,float]] = {}
    node_pos: Dict[int, Tuple[float,float,float]] = {}

    minx = miny = minz = float("inf")
    maxx = maxy = maxz = float("-inf")

    with open(csv_path, newline="") as f:
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample) if sample else csv.excel
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(f, dialect)

        first = next(reader, None)
        if first is None:
            raise ValueError("CSV appears to be empty.")

        header = [c.strip().lower() for c in first]
        has_header = set(["scenario","type","id","x","y","z"]).issubset(header)
        if has_header:
            cols = {name: header.index(name) for name in ["scenario","type","id","x","y","z"]}
        else:
            cols = {"scenario":0, "type":1, "id":2, "x":3, "y":4, "z":5}
            # treat first row as data
            reader = [first] + list(reader)

        for row in reader:
            try:
                scen = row[cols["scenario"]].strip()
                if scen != scenario_name:
                    continue
                t = row[cols["type"]].strip().lower()
                idx = int(float(row[cols["id"]]))
                x = float(row[cols["x"]]); y = float(row[cols["y"]]); z = float(row[cols["z"]])
            except Exception:
                continue

            if t == "gateway":
                gw_pos[idx] = (x,y,z)
            elif t in ("enddevice","node","ed"):
                node_pos[idx] = (x,y,z)

            minx, miny, minz = min(minx,x), min(miny,y), min(minz,z)
            maxx, maxy, maxz = max(maxx,x), max(maxy,y), max(maxz,z)

    if not gw_pos and not node_pos:
        raise ValueError(f"No rows found in '{csv_path}' for scenario '{scenario_name}'.")

    # reasonable Z bounds
    minz = min(0.0, minz)
    maxz = max(20.0, maxz)
    return gw_pos, node_pos, (minx, miny, minz, maxx, maxy, maxz)

# ---------- INI line regexes (positions & area) ----------

RX_GW_LINE = re.compile(r"""
    ^(?P<prefix>\s*\*\*\.loRaGW\[(?P<idx>\d+)\]\.\*\*\.initial(?P<axis>[XYZ])\s*=\s*)
    (?P<val>[-+]?[\d\.]+)
    (?P<unit>m)\s*$
""", re.VERBOSE)

RX_NODE_LINE = re.compile(r"""
    ^(?P<prefix>\s*\*\*\.loRaNodes\[(?P<idx>\d+)\]\.\*\*\.initial(?P<axis>[XYZ])\s*=\s*)
    (?P<val>[-+]?[\d\.]+)
    (?P<unit>m)\s*$
""", re.VERBOSE)

RX_AREA_LINE = re.compile(r"""
    ^(?P<prefix>\s*\*\*\.constraintArea(?P<which>Min|Max)(?P<axis>[XYZ])\s*=\s*)
    (?P<val>[-+]?[\d\.]+)
    (?P<unit>m)\s*$
""", re.VERBOSE)

# ---------- Path assignments to fix ----------
# Existing: energy/cloud configs
RX_FILEPATH_ASSIGN = re.compile(r"""
    ^(?P<prefix>\s*[^#\s].*?\b(
        configFile
        |cloud[^=\s]*File
        |cloud[^=\s]*Config
        |[^=\s]*\.config
    )\b\s*=\s*)
    (?P<rhs>.+?)\s*$
""", re.IGNORECASE | re.VERBOSE)

# NEW: result file outputs
RX_OUTPUT_ASSIGN = re.compile(r"""
    ^(?P<prefix>\s*output-(?:scalar|vector)-file\s*=\s*)
    (?P<rhs>.+?)\s*$
""", re.IGNORECASE | re.VERBOSE)

# RHS forms
RX_XMLDOC = re.compile(r'^\s*xmldoc\(\s*(["\'])(?P<p>[^"\']+)\1\s*\)\s*$', re.IGNORECASE)
RX_QUOTED = re.compile(r'^\s*(["\'])(?P<p>[^"\']+)\1\s*$')
RX_BARE   = re.compile(r'^\s*(?P<p>[^"\']\S*)\s*$')

def is_relative_path(p: str) -> bool:
    p2 = p.strip()
    if not p2: return False
    if re.match(r"^[A-Za-z]:", p2): return False   # Windows drive (C:\)
    if p2.startswith("/") or p2.startswith("\\"): return False
    return True

def add_one_up(p: str) -> str:
    # Always add exactly one more "../" (or "..\"), normalized to forward slashes
    if p.startswith("../") or p.startswith("..\\"):
        return "../" + p
    return "../" + p

def rewrite_rhs_bumping_one_up(rhs: str) -> str:
    """Return rhs with one more ../ added only to a relative path.
       Handles xmldoc("path"), "path", 'path', and bare paths.
       Also removes accidental '../' prefix before xmldoc( ... ) if present.
    """
    rhs = rhs.strip()
    # Fix malformed '../xmldoc("...")' -> 'xmldoc("...")' before editing
    if rhs.lower().startswith("../xmldoc("):
        rhs = rhs[3:]

    m = RX_XMLDOC.match(rhs)
    if m:
        path = m.group('p')
        if is_relative_path(path):
            newp = add_one_up(path)
            # Preserve original quote type used
            quote = '"' if '"' in rhs and ("'" not in rhs or rhs.index('"') < rhs.index("'")) else "'"
            return f'xmldoc({quote}{newp}{quote})'
        return rhs

    m = RX_QUOTED.match(rhs)
    if m:
        q = m.group(1); path = m.group('p')
        if is_relative_path(path):
            return f'{q}{add_one_up(path)}{q}'
        return rhs

    m = RX_BARE.match(rhs)
    if m:
        path = m.group('p')
        if is_relative_path(path):
            return add_one_up(path)
        return rhs

    # Unknown form → leave as-is
    return rhs

def fmt_axis(axis: str, value: float, is_gateway: bool=False) -> str:
    if axis in ("X","Y"):
        return f"{value:.2f}"
    return f"{value:.1f}"

# ---------- Main updater ----------

def update_ini_file(in_path: str, out_path: str, gw_pos, node_pos, bbox):
    with open(in_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    minx, miny, minz, maxx, maxy, maxz = bbox
    cnt = defaultdict(int)
    new_lines: List[str] = []

    for line in lines:
        # Gateways
        m = RX_GW_LINE.match(line)
        if m:
            idx = int(m.group("idx")); axis = m.group("axis")
            if idx in gw_pos:
                x,y,z = gw_pos[idx]
                val = {"X":x, "Y":y, "Z":z}[axis]
                new_val = fmt_axis(axis, val, is_gateway=True)
                new_lines.append(f"{m.group('prefix')}{new_val}{m.group('unit')}")
                cnt[f"gw_{axis}"] += 1
                continue
            new_lines.append(line); continue

        # Nodes
        m = RX_NODE_LINE.match(line)
        if m:
            idx = int(m.group("idx")); axis = m.group("axis")
            if idx in node_pos:
                x,y,z = node_pos[idx]
                val = {"X":x, "Y":y, "Z":z}[axis]
                new_val = fmt_axis(axis, val, is_gateway=False)
                new_lines.append(f"{m.group('prefix')}{new_val}{m.group('unit')}")
                cnt[f"node_{axis}"] += 1
                continue
            new_lines.append(line); continue

        # Constraint area
        m = RX_AREA_LINE.match(line)
        if m:
            which = m.group("which"); axis = m.group("axis")
            val = {
                ("Min","X"): minx, ("Min","Y"): miny, ("Min","Z"): minz,
                ("Max","X"): maxx, ("Max","Y"): maxy, ("Max","Z"): maxz,
            }[(which, axis)]
            sval = f"{val:.2f}" if axis in ("X","Y") else (f"{val:.0f}" if abs(val-round(val))<1e-6 else f"{val:.1f}")
            new_lines.append(f"{m.group('prefix')}{sval}{m.group('unit')}")
            cnt[f"area_{which}{axis}"] += 1
            continue

        # Results output files (NEW): add one "../" to relative paths
        m = RX_OUTPUT_ASSIGN.match(line)
        if m:
            prefix = m.group("prefix")
            rhs    = m.group("rhs")
            new_rhs = rewrite_rhs_bumping_one_up(rhs)
            new_lines.append(f"{prefix}{new_rhs}")
            if new_rhs != rhs:
                cnt["results_bumped"] += 1
            continue

        # Energy/cloud path params: add one "../" inside relative paths
        m = RX_FILEPATH_ASSIGN.match(line)
        if m:
            prefix = m.group("prefix")
            rhs    = m.group("rhs")
            new_rhs = rewrite_rhs_bumping_one_up(rhs)
            new_lines.append(f"{prefix}{new_rhs}")
            if new_rhs != rhs:
                cnt["paths_bumped"] += 1
            continue

        # Anything else untouched
        new_lines.append(line)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(new_lines) + "\n")

    print(f"✔ Updated '{os.path.basename(in_path)}' → '{out_path}' "
          f"(GW lines: {sum(v for k,v in cnt.items() if k.startswith('gw_'))}, "
          f"Node lines: {sum(v for k,v in cnt.items() if k.startswith('node_'))}, "
          f"Area lines: {sum(v for k,v in cnt.items() if k.startswith('area_'))}, "
          f"Result paths bumped: {cnt.get('results_bumped',0)}, "
          f"Other paths bumped: {cnt.get('paths_bumped',0)})")

# ---------- CLI ----------

def main():
    ap = argparse.ArgumentParser(description="Update OMNeT++ INI positions + constraint area; also bump relative file paths (energy/cloud + results) by one '../'.")
    ap.add_argument("--csv", required=True, help="Positions CSV (scenario,type,id,x,y,z).")
    ap.add_argument("--scenario", required=True, help="Scenario name to pick from the CSV.")
    ap.add_argument("--in", dest="inputs", required=True, nargs="+",
                    help="One or more .ini files or globs (e.g., examples/*.ini).")
    ap.add_argument("--out-dir", required=True, help="Output directory for updated ini files.")
    args = ap.parse_args()

    ini_files: List[str] = []
    for pattern in args.inputs:
        matched = glob.glob(pattern)
        if not matched and os.path.isfile(pattern):
            matched = [pattern]
        ini_files.extend(matched)
    if not ini_files:
        raise SystemExit("No input .ini files found.")

    gw_pos, node_pos, bbox = load_positions(args.csv, args.scenario)

    for ini_path in ini_files:
        base = os.path.basename(ini_path)
        out_path = os.path.join(args.out_dir, base)
        update_ini_file(ini_path, out_path, gw_pos, node_pos, bbox)

if __name__ == "__main__":
    main()
