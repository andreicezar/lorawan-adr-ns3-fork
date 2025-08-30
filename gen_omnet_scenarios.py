#!/usr/bin/env python3
# gen_omnet_scenarios_from_runsh.py
import argparse, re
from pathlib import Path

RUNCFG_RE = re.compile(
    r'''run_config\s+
        "([^"]+)"\s+           # name
        "?(true|false)"?\s+    # initSF
        "?(true|false)"?\s+    # initTP
        "?(true|false)"?\s*    # enableADR
        (?:\s+([0-9]+)\s+([0-9]+))?  # targetSF targetTP (optional)
    ''', re.VERBOSE | re.IGNORECASE
)

def infer_scenario_label(template_path: Path) -> str:
    stem = template_path.stem
    if stem.startswith("omnetpp-"):
        stem = stem[len("omnetpp-"):]
    return stem  # e.g., 'scenario-01-baseline'

def scenario_prefix_from_label(label: str) -> str:
    m = re.match(r'(scenario-\d+)', label)   # 'scenario-01-baseline' -> 'scenario-01'
    return m.group(1) if m else label

def extract_subscenarios_from_run_sh(run_sh: Path):
    txt = run_sh.read_text(encoding="utf-8", errors="ignore")
    start = re.search(r'^\s*run_all_scenarios\s*\(\)\s*\{', txt, re.MULTILINE)
    if not start:
        raise RuntimeError("run_all_scenarios() not found in run-01.sh")
    body = txt[start.end():]
    end = re.search(r'^\}', body, re.MULTILINE)
    if not end:
        raise RuntimeError("Could not find end of run_all_scenarios() in run-01.sh")
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

# ---------- patterns ----------
RE_OUT_VEC = re.compile(r'^(?!\s*#)\s*output-vector-file\s*=.*$', re.MULTILINE)
RE_OUT_SCA = re.compile(r'^(?!\s*#)\s*output-scalar-file\s*=.*$', re.MULTILINE)
RE_ADR_SERVER = re.compile(r'^(?!\s*#)\s*(\*\*\.networkServer\.\*\*\.evaluateADRinServer)\s*=\s*(true|false)\s*$', re.MULTILINE)
RE_ADR_NODE   = re.compile(r'^(?!\s*#)\s*(\*\*\.loRaNodes\[\*\]\.\*\*\.evaluateADRinNode)\s*=\s*(true|false)\s*$', re.MULTILINE)
RE_ANY_INIT_SF = re.compile(r'^(?!\s*#)\s*[^#\n]*\binitialLoRaSF\b\s*=.*$', re.MULTILINE)
RE_ANY_INIT_TP = re.compile(r'^(?!\s*#)\s*[^#\n]*\binitialLoRaTP\b\s*=.*$', re.MULTILINE)

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

def apply_overrides(base_text: str, scenario_label: str, sub: dict) -> str:
    out = base_text
    base_name = f"{scenario_label}-{sub['name']}"  # for result files

    # result files
    out = set_or_append(RE_OUT_VEC, f"output-vector-file = ../results/{base_name}-s${{runnumber}}.vec", out, "output-vector-file")
    out = set_or_append(RE_OUT_SCA, f"output-scalar-file = ../results/{base_name}-s${{runnumber}}.sca", out, "output-scalar-file")

    # ADR server and force node ADR off
    out = set_or_append(RE_ADR_SERVER, rf"\1 = {'true' if sub['enable_adr'] else 'false'}", out, "ADR server")
    out = set_or_append(RE_ADR_NODE, r"\1 = false", out, "ADR node off")

    # SF/TP init (no empty strings; either remove lines or set explicit values)
    out = comment_out_all(RE_ANY_INIT_SF, out, "disabled by sub-scenario")
    if sub["init_sf"]:
        out = append_line(out, f'**.loRaNodes[*].**initialLoRaSF = {sub["target_sf"]}', "initial SF")

    out = comment_out_all(RE_ANY_INIT_TP, out, "disabled by sub-scenario")
    if sub["init_tp"]:
        out = append_line(out, f'**.loRaNodes[*].**initialLoRaTP = {sub["target_tp"]} dBm', "initial TP")

    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, help="Baseline INI (with positions) to copy & edit.")
    ap.add_argument("--run-sh", required=True, help="Path to run-01.sh to parse sub-scenarios from.")
    ap.add_argument("--outdir", default="generated-ini", help="Directory for generated INIs.")
    ap.add_argument("--scenario-prefix", default=None,
                    help="Override filename prefix (e.g., 'scenario-01'). Default inferred from template.")
    args = ap.parse_args()

    template_path = Path(args.template)
    run_sh_path = Path(args.run_sh)
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    scenario_label = infer_scenario_label(template_path)           # e.g., 'scenario-01-baseline'
    scenario_prefix = args.scenario_prefix or scenario_prefix_from_label(scenario_label)  # 'scenario-01'
    base_text = template_path.read_text(encoding="utf-8")
    subs = extract_subscenarios_from_run_sh(run_sh_path)

    for sub in subs:
        edited = apply_overrides(base_text, scenario_label, sub)
        # ✅ Filename now includes the scenario index/prefix
        out_path = outdir / f"omnetpp-{scenario_prefix}-{sub['name']}.ini"
        out_path.write_text(edited, encoding="utf-8")
        print(f"✅ Wrote {out_path}")

    print(f"\nAll done. Files in: {outdir.resolve()}")
    print(f"Scenario label (for result files): {scenario_label}")
    print(f"Filename prefix: {scenario_prefix}")

if __name__ == "__main__":
    main()
