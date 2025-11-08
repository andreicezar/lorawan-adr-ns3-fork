#!/usr/bin/env python3
"""
gen_omnet_scenarios.py — generator with:
- run-0x.sh parsing (sub-scenarios + numeric defaults)
- per-scenario overrides (S04/S05/S06/S07/S08)
- sendInterval + sim-time-limit filling
- ADR/SF/TP toggles
- RESULT file naming
- NEW: constraint area auto-fit from positions in the template
"""
import argparse, re
from pathlib import Path

# -------- run_config parsing --------
RUNCFG_RE = re.compile(
    r'''run_config\s+
        "([^"]+)"\s+           # name
        "?(true|false)"?\s+    # initSF
        "?(true|false)"?\s+    # initTP
        "?(true|false)"?\s*    # enableADR
        (?:\s+([0-9]+)\s+([0-9]+))?  # targetSF targetTP (optional)
    ''', re.VERBOSE | re.IGNORECASE
)

# -------- INI edit helpers --------
RE_OUT_VEC = re.compile(r'^(?!\s*#)\s*output-vector-file\s*=.*$', re.MULTILINE)
RE_OUT_SCA = re.compile(r'^(?!\s*#)\s*output-scalar-file\s*=.*$', re.MULTILINE)
RE_ADR_SERVER = re.compile(r'^(?!\s*#)\s*(\*\*\.networkServer\.\*\*\.evaluateADRinServer)\s*=\s*(true|false)\s*$', re.MULTILINE)
RE_ADR_NODE   = re.compile(r'^(?!\s*#)\s*(\*\*\.loRaNodes\[\*\]\.\*\*\.evaluateADRinNode)\s*=\s*(true|false)\s*$', re.MULTILINE)
RE_ANY_INIT_SF = re.compile(r'^(?!\s*#)\s*[^#\n]*\binitialLoRaSF\b\s*=.*$', re.MULTILINE)
RE_ANY_INIT_TP = re.compile(r'^(?!\s*#)\s*[^#\n]*\binitialLoRaTP\b\s*=.*$', re.MULTILINE)

RE_NUM_NODES = re.compile(r'^(?!\s*#)\s*\*\*\.numberOfNodes\s*=\s*\d+\s*$', re.MULTILINE)
RE_NUM_GW    = re.compile(r'^(?!\s*#)\s*\*\*\.numberOfGateways\s*=\s*\d+\s*$', re.MULTILINE)
RE_SIM_TIME  = re.compile(r'^(?!\s*#)\s*sim-time-limit\s*=\s*[\d\.]+\s*(s|min|h)\s*$', re.MULTILINE)

# PacketForwarder wildcard settings for gateways
RE_GW_PF_DESTADDR = re.compile(r'^(?!\s*#)\s*\*\*\.loRaGW\[\*\]\.packetForwarder\.destAddresses\s*=.*$', re.MULTILINE)
RE_GW_PF_DESTPORT = re.compile(r'^(?!\s*#)\s*\*\*\.loRaGW\[\*\]\.packetForwarder\.destPort\s*=.*$', re.MULTILINE)
RE_GW_PF_LOCALPORT = re.compile(r'^(?!\s*#)\s*\*\*\.loRaGW\[\*\]\.packetForwarder\.localPort\s*=.*$', re.MULTILINE)
RE_GW_PF_INDEXNUM = re.compile(r'^(?!\s*#)\s*\*\*\.loRaGW\[\*\]\.packetForwarder\.indexNumber\s*=.*$', re.MULTILINE)

# sendInterval / confirmation keys (best effort)
SEND_INTERVAL_KEYS = [
    r'\*\*\.app\[\*\]\.sendInterval',
    r'\*\*\.loRaNodes\[\*\]\.\*\*\.sendInterval',
    r'\*\*\.loRaNodes\[\*\]\.\*\*\.packetInterval',
]
CONFIRM_KEYS = [
    r'\*\*\.app\[\*\]\.confirm',
    r'\*\*\.app\[\*\]\.confirmed',
    r'\*\*\.app\[\*\]\.useConfirmed',
    r'\*\*\.app\[\*\]\.requireConfirmation',
    r'\*\*\.networkServer\.\*\*\.confirmUplink',
]

# Propagation model hints (S07)
RE_PATHLOSS_EXP = [
    re.compile(r'^(?!\s*#)\s*\*\*\.path[Ll]oss(Exponent|Alpha)\s*=\s*[\d\.]+\s*$', re.MULTILINE),
    re.compile(r'^(?!\s*#)\s*\*\*\.radioMedium\..*path[Ll]oss(Exponent|Alpha)\s*=\s*[\d\.]+\s*$', re.MULTILINE),
]
RE_PROP_MODEL = re.compile(r'^(?!\s*#)\s*\*\*\.propagationModel\s*=\s*".*"', re.MULTILINE)
RE_MAX_DISTANCE = re.compile(r'^(?!\s*#)\s*\*\*\.maxDistance\s*=\s*[\d\.]+m\s*$', re.MULTILINE)

# Constraint area keys
RE_CA_MINX = re.compile(r'^(?!\s*#)\s*\*\*\.constraintAreaMinX\s*=\s*[-\d\.]+m\s*$', re.MULTILINE)
RE_CA_MINY = re.compile(r'^(?!\s*#)\s*\*\*\.constraintAreaMinY\s*=\s*[-\d\.]+m\s*$', re.MULTILINE)
RE_CA_MINZ = re.compile(r'^(?!\s*#)\s*\*\*\.constraintAreaMinZ\s*=\s*[-\d\.]+m\s*$', re.MULTILINE)
RE_CA_MAXX = re.compile(r'^(?!\s*#)\s*\*\*\.constraintAreaMaxX\s*=\s*[-\d\.]+m\s*$', re.MULTILINE)
RE_CA_MAXY = re.compile(r'^(?!\s*#)\s*\*\*\.constraintAreaMaxY\s*=\s*[-\d\.]+m\s*$', re.MULTILINE)
RE_CA_MAXZ = re.compile(r'^(?!\s*#)\s*\*\*\.constraintAreaMaxZ\s*=\s*[-\d\.]+m\s*$', re.MULTILINE)

# -------- utilities --------
def infer_scenario_label(template_path: Path) -> str:
    stem = template_path.stem
    if stem.startswith("omnetpp-"):
        stem = stem[len("omnetpp-"):]
    return stem

def scenario_prefix_from_label(label: str) -> str:
    m = re.match(r'(scenario-\d+)', label)
    return m.group(1) if m else label

def set_or_append(pattern, replacement_line, text, key_hint=None):
    new_text, n = pattern.subn(replacement_line, text)
    if n == 0:
        comment = f"\n# Appended by generator{f' ({key_hint})' if key_hint else ''}\n"
        new_text = new_text.rstrip() + comment + replacement_line + "\n"
    return new_text

def comment_out_all(pattern, text, note):
    def repl(m): return "# " + note + ": " + m.group(0)
    return pattern.sub(repl, text)

def append_line(text, line, note=None):
    comment = f"\n# Appended by generator{f' ({note})' if note else ''}\n"
    return text.rstrip() + comment + line + "\n"

def set_first_matching_key(text, key_patterns, value_str, note):
    replaced = False
    for pat_str in key_patterns:
        pat = re.compile(rf'^(?!\s*#)\s*({pat_str})\s*=\s*.*$', re.MULTILINE)
        new_text, n = pat.subn(rf'\1 = {value_str}', text)
        if n > 0:
            text = new_text
            replaced = True
    if not replaced:
        exemplar = re.sub(r'\\', '', key_patterns[0])  # pretty
        text = append_line(text, f'{exemplar} = {value_str}', note)
    return text

def has_send_interval(text: str) -> bool:
    for key_pat in SEND_INTERVAL_KEYS:
        pat = re.compile(rf'^(?!\s*#)\s*{key_pat}\s*=', re.MULTILINE)
        if pat.search(text):
            return True
    return False

# -------- sub-scenarios from run-*.sh --------
def extract_subscenarios_from_run_sh(run_sh: Path):
    txt = run_sh.read_text(encoding="utf-8", errors="ignore")
    start = re.search(r'^\s*run_all_scenarios\s*\(\)\s*\{', txt, re.MULTILINE)
    if not start:
        raise RuntimeError("run_all_scenarios() not found in run-0x.sh")
    body = txt[start.end():]
    end = re.search(r'^\}', body, re.MULTILINE)
    if not end:
        raise RuntimeError("Could not find end of run_all_scenarios() in run-0x.sh")
    body = body[:end.start()]

    out = []
    for m in RUNCFG_RE.finditer(body):
        out.append({
            "name": m.group(1).strip(),
            "init_sf": m.group(2).lower() == "true",
            "init_tp": m.group(3).lower() == "true",
            "enable_adr": m.group(4).lower() == "true",
            "target_sf": int(m.group(5)) if m.group(5) else 10,
            "target_tp": int(m.group(6)) if m.group(6) else 14,
        })
    if not out:
        raise RuntimeError("No run_config entries found in run_all_scenarios().")
    return out

# -------- globals from run-*.sh --------
def extract_globals_from_run_sh(run_sh: Path):
    txt = run_sh.read_text(encoding="utf-8", errors="ignore")

    def first_int(patterns):
        for p in patterns:
            m = re.search(p, txt, re.MULTILINE | re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    n_devices = first_int([r'--nDevices\s*=\s*([0-9]+)', r'^\s*(?:NDEV|N_DEV|NUM_DEVICES|NODES)\s*=\s*([0-9]+)\s*$', r'Config:?\s*([0-9]+)\s*devices'])
    n_gateways = first_int([r'--nGateways\s*=\s*([0-9]+)', r'^\s*(?:NGW|N_GW|NUM_GATEWAYS|GATEWAYS)\s*=\s*([0-9]+)\s*$', r'Config:?.*?([0-9]+)\s*gateway'])
    sim_minutes = first_int([r'--simulationTime\s*=\s*([0-9]+)', r'^\s*(?:SIM_MIN|SIMULATION_TIME|SIMTIME|SIM_TIME)\s*=\s*([0-9]+)\s*$', r'Config:?.*?([0-9]+)\s*min'])
    pkt_interval = first_int([r'--packetInterval\s*=\s*([0-9]+)', r'^\s*(?:PACKET_INTERVAL|PKT_INTERVAL|INTERVAL)\s*=\s*([0-9]+)\s*$', r'Config:?.*?interval\s*([0-9]+)\s*s'])
    max_distance = first_int([r'--maxDistance\s*=\s*([0-9]+)', r'^\s*(?:MAX_DISTANCE|MAXDIST|RANGE)\s*=\s*([0-9]+)\s*$'])

    # S05 footer hints
    s5_map = {}
    for label in ("LOW", "MEDIUM", "HIGH"):
        mm = re.search(rf'interval-(\d+)s/.*\({label}\s+traffic', txt, re.IGNORECASE)
        if mm:
            s5_map[label.lower()] = int(mm.group(1))
    return {
        "n_devices": n_devices,
        "n_gateways": n_gateways,
        "sim_minutes": sim_minutes,
        "packet_interval": pkt_interval,
        "max_distance": max_distance,
        "s5_intervals": s5_map or None,
        "raw": txt,
    }

def parse_assoc_array(txt: str, name: str):
    m = re.search(rf'declare -A\s+{name}\s*=\(\s*(.*?)\)', txt, re.S)
    if not m:
        return None
    body = m.group(1)
    out = {}
    for k, v in re.findall(r'\[\s*([0-9]+)\s*\]\s*=\s*([0-9]+)', body):
        out[int(k)] = int(v)
    return out

# -------- positions → constraint area --------
def parse_node_positions_from_ini(text: str):
    # Matches: **.loRaNodes[123].**.initialX / initialY = <number>m
    x_pat = re.compile(r'\*\*\.loRaNodes\[\d+\]\.\*+\.initialX\s*=\s*([-0-9.]+)m')
    y_pat = re.compile(r'\*\*\.loRaNodes\[\d+\]\.\*+\.initialY\s*=\s*([-0-9.]+)m')
    xs = [float(v) for v in x_pat.findall(text)]
    ys = [float(v) for v in y_pat.findall(text)]
    if xs and ys:
        return (min(xs), max(xs), min(ys), max(ys))
    return None


def fit_constraint_area(text: str):
    bounds = parse_node_positions_from_ini(text)
    if not bounds:
        return text
    minx, maxx, miny, maxy = bounds
    width  = maxx - minx
    height = maxy - miny
    pad = max(500.0, 0.10 * max(width, height))  # ≥500 m or 10%
    ca_minx = minx - pad
    ca_maxx = maxx + pad
    ca_miny = miny - pad
    ca_maxy = maxy + pad

    def fmt(v):  # round to 0.01 m then print with 'm'
        return f"{round(v, 2)}m"

    out = text
    out = set_or_append(RE_CA_MINX, f"**.constraintAreaMinX = {fmt(ca_minx)}", out, "constraintAreaMinX")
    out = set_or_append(RE_CA_MINY, f"**.constraintAreaMinY = {fmt(ca_miny)}", out, "constraintAreaMinY")
    out = set_or_append(RE_CA_MAXX, f"**.constraintAreaMaxX = {fmt(ca_maxx)}", out, "constraintAreaMaxX")
    out = set_or_append(RE_CA_MAXY, f"**.constraintAreaMaxY = {fmt(ca_maxy)}", out, "constraintAreaMaxY")
    # leave Z as-is
    return out

# -------- per-scenario handlers --------
def apply_pathloss_exponent(text: str, exponent: float) -> str:
    replaced = False
    for pat in RE_PATHLOSS_EXP:
        new_text, n = pat.subn(lambda m: re.sub(r'=\s*[\d\.]+', f'= {exponent}', m.group(0)), text)
        if n>0:
            text = new_text; replaced = True
    if not replaced:
        text = append_line(text, f'**.pathLossExponent = {exponent}', 'pathloss exponent')
    return text

def set_send_interval(text: str, interval_seconds: int) -> str:
    return set_first_matching_key(text, SEND_INTERVAL_KEYS, f'{interval_seconds}s', 'sendInterval')

def per_sub_overrides(prefix: str, sub: dict, base_text: str, gcfg: dict) -> str:
    out = base_text
    name = sub['name']
    scen_num = prefix.split('-')[1] if '-' in prefix else None

    # S04
    if scen_num == '04':
        is_conf = (name.lower() == 'confirmed')
        val = 'true' if is_conf else 'false'
        out = set_first_matching_key(out, CONFIRM_KEYS, val, 'confirmed uplink')

    # S05
    if scen_num == '05':
        lname = name.lower()
        intervals = (gcfg.get('s5_intervals') or {'high':60, 'medium':300, 'low':600})
        if 'high' in lname:
            interval, sim_min = intervals.get('high',60), 40
        elif 'medium' in lname:
            interval, sim_min = intervals.get('medium',300), 200
        elif 'low' in lname:
            interval, sim_min = intervals.get('low',600), 400
        else:
            interval = gcfg.get('packet_interval') or 300
            sim_min = gcfg.get('sim_minutes') or 200
        out = set_send_interval(out, interval)
        out = set_or_append(RE_SIM_TIME, f"sim-time-limit = {sim_min}min", out, "sim-time-limit (S05)")

    # S06
    if scen_num == '06':
        txt = gcfg.get('raw', '')
        sf_int = parse_assoc_array(txt, 'SF_INTERVALS') or {}
        sf_sim = parse_assoc_array(txt, 'SF_SIMTIMES') or {}
        t_sf = sub.get('target_sf', 10)
        interval = sf_int.get(t_sf, gcfg.get('packet_interval') or 150)
        sim_min = sf_sim.get(t_sf, int((120 * interval + 59) // 60))
        out = set_send_interval(out, interval)
        out = set_or_append(RE_SIM_TIME, f"sim-time-limit = {sim_min}min", out, "sim-time-limit (S06)")

    # S07
    if scen_num == '07':
        lname = name.lower()
        if lname.startswith('logdist-'):
            try:
                suffix = lname.split('-',1)[1]
                exp = float(suffix) / (10.0 if len(suffix)==2 else 100.0)
            except Exception:
                exp = 3.5
            out = apply_pathloss_exponent(out, exp)
            out = set_or_append(RE_PROP_MODEL, '**.propagationModel = "logdistance"', out, 'propagation model')
            out = append_line(out, f'# Propagation model hint: LogDistance(n={exp})', 'S07 model')
        elif lname == 'freespace':
            out = set_or_append(RE_PROP_MODEL, '**.propagationModel = "freespace"', out, 'propagation model')
            out = append_line(out, '# Propagation model hint: FreeSpace', 'S07 model')
        if gcfg.get('max_distance'):
            val = f"{gcfg['max_distance']}m"
            out = set_or_append(RE_MAX_DISTANCE, f"**.maxDistance = {val}", out, 'maxDistance')

    # S08
    if scen_num == '08':
        m = re.match(r'^(\d+)gw$', name, re.I)
        if m:
            out = set_or_append(RE_NUM_GW, f"**.numberOfGateways = {int(m.group(1))}", out, 'numberOfGateways (S08)')
            # Ensure ALL gateways have PacketForwarder params (avoid interactive prompts)
            out = set_or_append(RE_GW_PF_DESTADDR,
                '**.loRaGW[*].packetForwarder.destAddresses = "networkServer"', out, 'S08 PF destAddresses')
            out = set_or_append(RE_GW_PF_DESTPORT,
                '**.loRaGW[*].packetForwarder.destPort = 1000', out, 'S08 PF destPort')
            out = set_or_append(RE_GW_PF_LOCALPORT,
                '**.loRaGW[*].packetForwarder.localPort = 2000 + parentIndex()', out, 'S08 PF localPort')
            out = set_or_append(RE_GW_PF_INDEXNUM,
                '**.loRaGW[*].packetForwarder.indexNumber = parentIndex()', out, 'S08 PF indexNumber')



    return out

# -------- core apply --------
def apply_overrides(base_text: str, scenario_label: str, sub: dict, gcfg: dict, scen_prefix: str) -> str:
    out = base_text
    base_name = f"{scenario_label}-{sub['name']}"

    # result files
    out = set_or_append(RE_OUT_VEC, f"output-vector-file = ../results/{base_name}-s${{runnumber}}.vec", out, "output-vector-file")
    out = set_or_append(RE_OUT_SCA, f"output-scalar-file = ../results/{base_name}-s${{runnumber}}.sca", out, "output-scalar-file")

    # ADR server + node ADR off
    out = set_or_append(RE_ADR_SERVER, rf"\1 = {'true' if sub['enable_adr'] else 'false'}", out, "ADR server")
    out = set_or_append(RE_ADR_NODE, r"\1 = false", out, "ADR node off")

    # SF/TP init
    out = comment_out_all(RE_ANY_INIT_SF, out, "disabled by sub-scenario")
    if sub["init_sf"]:
        out = append_line(out, f'**.loRaNodes[*].**initialLoRaSF = {sub["target_sf"]}', "initial SF")
    out = comment_out_all(RE_ANY_INIT_TP, out, "disabled by sub-scenario")
    if sub["init_tp"]:
        out = append_line(out, f'**.loRaNodes[*].**initialLoRaTP = {sub["target_tp"]} dBm', "initial TP")

    # Global numeric knobs
    if gcfg.get("n_devices"):   out = set_or_append(RE_NUM_NODES, f"**.numberOfNodes = {gcfg['n_devices']}", out, "numberOfNodes")
    if gcfg.get("n_gateways"):  out = set_or_append(RE_NUM_GW,    f"**.numberOfGateways = {gcfg['n_gateways']}", out, "numberOfGateways")
    if gcfg.get("sim_minutes"): out = set_or_append(RE_SIM_TIME,  f"sim-time-limit = {gcfg['sim_minutes']}min", out, "sim-time-limit")

    # Scenario-specific
    out = per_sub_overrides(scen_prefix, sub, out, gcfg)

    # If we have a global packet_interval and no sendInterval was set, set it
    if gcfg.get("packet_interval") and not has_send_interval(out):
        out = set_send_interval(out, gcfg["packet_interval"])

    # NEW: auto-fit constraint area based on explicit positions in the template
    out = fit_constraint_area(out)

    return out

# -------- main --------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Baseline INI (with positions) to copy & edit.")
    ap.add_argument("--run-sh", required=True, help="Path to run-0x.sh to parse sub-scenarios & numeric defaults from.")
    ap.add_argument("--outdir", default="generated-ini", help="Directory for generated INIs.")
    ap.add_argument("--scenario-prefix", default=None,
                    help="Override filename prefix (e.g., 'scenario-01'). Default inferred from template.")
    args = ap.parse_args()

    template_path = Path(args.template)
    run_sh_path = Path(args.run_sh)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    scenario_label = infer_scenario_label(template_path)
    scenario_prefix = args.scenario_prefix or scenario_prefix_from_label(scenario_label)
    base_text = template_path.read_text(encoding="utf-8")
    subs = extract_subscenarios_from_run_sh(run_sh_path)
    gcfg = extract_globals_from_run_sh(run_sh_path)

    for sub in subs:
        edited = apply_overrides(base_text, scenario_label, sub, gcfg, scenario_prefix)
        out_path = outdir / f"omnetpp-{scenario_prefix}-{sub['name']}.ini"
        out_path.write_text(edited, encoding="utf-8")
        print(f"✅ Wrote {out_path}")

    print(f"\nAll done. Files in: {outdir.resolve()}")
    print(f"Scenario label (for result files): {scenario_label}")
    print(f"Filename prefix: {scenario_prefix}")
    print("Inferred from run shell:", {k:v for k,v in gcfg.items() if k!='raw'})

if __name__ == "__main__":
    main()
