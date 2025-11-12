#!/usr/bin/env python3
"""
NS-3 LoRaWAN CSV Analyzer — strict per-model partition, FLoRa colors

Expected CSV header:
  distance,sf,tp,sent,received,plr,der[,z_ed]

Filename pattern (model detection):
  sim_model_<ModelName>_sf<SF>_tp<TP>_dist<D>.csv
e.g. sim_model_LogDistance_sf7_tp14_dist100.csv
     sim_model_OkumuraHata_sf7_tp14_dist100.csv

Outputs (per model, per TP & z):
  <OUT>/<Model>/sf_distance_heatmap_tp{tp}_z{z}m.png
  <OUT>/<Model>/sf_distance_lineplot_tp{tp}_z{z}m.png
  <OUT>/<Model>/sf_distance_table_z{z}m.csv
  <OUT>/<Model>/summary_statistics_z{z}m.csv
  <OUT>/<Model>/results_table_z{z}m.md
If exactly two heights exist for that model & TP:
  <OUT>/<Model>/comparison_heatmap_tp{tp}_z{z1}m_vs_z{z2}m.png
  <OUT>/<Model>/comparison_table_tp{tp}_z{z1}m_vs_z{z2}m.csv
"""

from pathlib import Path
import argparse
from typing import List, Dict, Optional, DefaultDict
from collections import defaultdict
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re
import sys

# -------------------------
# FLoRa-style colors
# -------------------------
FLO_PAL = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']  # SF7..SF12
FLO_MARKERS = ['o', 's', '^', 'D', 'v', 'p']  # SF7..SF12
FLO_CMAP = 'RdYlGn'  # heatmaps

# -------------------------
# Filename -> model parsing
# -------------------------
_MODEL_RX = re.compile(
    r"""(?ix)
        \b           # start at a word boundary
        sim_model_   # literal prefix
        (?P<model>.+?)  # capture model name (non-greedy)
        _sf\d+_tp\d+_dist\d+\.csv$   # rest of pattern
    """
)

def parse_model_from_filename(path: Path) -> Optional[str]:
    m = _MODEL_RX.search(path.name)
    return m.group("model") if m else None

# -------------------------
# File discovery & grouping
# -------------------------
def discover_csvs(inputs: List[str]) -> List[Path]:
    files: List[Path] = []
    for p in inputs:
        P = Path(p)
        if P.is_dir():
            files.extend(sorted(P.rglob("*.csv")))
        elif P.is_file() and P.suffix.lower() == ".csv":
            files.append(P)
        else:
            for g in sorted(Path(".").glob(p)):
                if g.is_file() and g.suffix.lower() == ".csv":
                    files.append(g)
    # de-dup while preserving order
    seen = set()
    unique = []
    for f in files:
        rf = f.resolve()
        if rf not in seen:
            unique.append(f)
            seen.add(rf)
    return unique

def group_files_by_model(files: List[Path]) -> Dict[str, List[Path]]:
    groups: DefaultDict[str, List[Path]] = defaultdict(list)
    for f in files:
        model = parse_model_from_filename(f)
        if model is None:
            print(f"[skip] File does not match pattern (no model detected): {f.name}", file=sys.stderr)
            continue
        groups[model].append(f)
    return dict(groups)

# -------------------------
# CSV loading
# -------------------------
def _to_int(x):
    try:
        return int(x)
    except Exception:
        try:
            return int(float(x))
        except Exception:
            return None

def _to_float(x):
    try:
        return float(x)
    except Exception:
        return None

REQUIRED = ["distance", "sf", "tp", "sent", "received", "plr", "der"]

def load_one_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"{path.name}: missing required columns {missing}")

    for col, caster in [
        ("distance", _to_int), ("sf", _to_int), ("tp", _to_int),
        ("sent", _to_int), ("received", _to_int),
        ("plr", _to_float), ("der", _to_float),
    ]:
        df[col] = df[col].map(caster)

    if "z_ed" in df.columns:
        df["z_ed"] = df["z_ed"].map(_to_int)

    df = df.dropna(subset=["distance", "sf", "tp", "received"], how="any")
    df["distance"] = df["distance"].astype(int)
    df["sf"]       = df["sf"].astype(int)
    df["tp"]       = df["tp"].astype(int)
    df["received"] = df["received"].astype(int)
    if "sent" in df.columns and df["sent"].notna().any():
        df["sent"] = df["sent"].astype("Int64")
    if "z_ed" in df.columns and df["z_ed"].notna().any():
        df["z_ed"] = df["z_ed"].astype(int)

    df["__file__"] = path.name
    return df

def load_group(files: List[Path]) -> pd.DataFrame:
    frames = []
    for p in files:
        try:
            frames.append(load_one_csv(p))
        except Exception as e:
            print(f"[skip:{p.name}] {e}", file=sys.stderr)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

# -------------------------
# Tables & summaries
# -------------------------
def create_sf_distance_table(df: pd.DataFrame) -> pd.DataFrame:
    pivot = df.pivot_table(
        values="received", index="distance", columns="sf",
        aggfunc="sum", fill_value=0
    )
    for sf in range(7, 13):
        if sf not in pivot.columns:
            pivot[sf] = 0
    pivot = pivot[[sf for sf in range(7, 13)]].sort_index()

    def best(row):
        mx = row.max()
        return "None" if mx <= 0 else f"SF{int(row.idxmax())}"

    table = pivot.copy()
    table["Best SF"] = table.apply(best, axis=1)
    table.columns = [f"SF{c}" if isinstance(c, int) else c for c in table.columns]
    return table

def create_summary_statistics(table: pd.DataFrame) -> pd.DataFrame:
    summary = []
    sf_cols = [c for c in table.columns if c.startswith("SF") and c != "Best SF"]
    for sf in sf_cols:
        data = table[sf]
        max_range = 0
        for dist in reversed(table.index):
            if data.loc[dist] > 0:
                max_range = int(dist)
                break
        non_zero = data[data > 0]
        avg_packets = non_zero.mean() if len(non_zero) > 0 else 0
        summary.append({
            "SF": sf,
            "Max Range (m)": max_range,
            "Avg Packets (non-zero)": f"{avg_packets:.1f}",
            "Total Packets": int(data.sum()),
            "Distances Active": int(len(non_zero))
        })
    return pd.DataFrame(summary)

def create_markdown_table(table: pd.DataFrame) -> str:
    lines = []
    lines.append("## Packet Reception by Distance and Spreading Factor")
    lines.append("| Distance | SF7 | SF8 | SF9 | SF10 | SF11 | SF12 | Best SF |")
    lines.append("|----------|-----|-----|-----|------|------|------|---------|")
    for dist in table.index:
        row = table.loc[dist]
        vals = [str(int(row.get(f"SF{i}", 0))) for i in range(7, 13)]
        best = row["Best SF"]
        lines.append(f"| {int(dist)}m | {vals[0]} | {vals[1]} | {vals[2]} | {vals[3]} | {vals[4]} | {vals[5]} | {best} |")
    return "\n".join(lines)

# -------------------------
# Plotting (FLoRa colors & style)
# -------------------------
def heatmap_packets_flora(df: pd.DataFrame, title: str, out_path: Path):
    """
    Seaborn heatmap using FLoRa's 'RdYlGn' colormap, with annotations and grid lines.
    """
    heatmap_data = df.pivot_table(values="received", index="distance", columns="sf", aggfunc="sum", fill_value=0)
    # ensure SF7..SF12 columns exist
    for sf in range(7, 13):
        if sf not in heatmap_data.columns:
            heatmap_data[sf] = 0
    heatmap_data = heatmap_data[[sf for sf in range(7, 13)]].sort_index()

    plt.figure(figsize=(12, 8))
    ax = sns.heatmap(
        heatmap_data,
        annot=True,
        fmt='g',
        cmap=FLO_CMAP,
        cbar_kws={'label': 'Packets Received'},
        linewidths=0.5,
        linecolor='gray'
    )
    ax.set_title(title)
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("Distance (m)")
    ax.set_xticklabels([f"SF{int(c.get_text())}" for c in ax.get_xticklabels()], rotation=0)
    ax.set_yticklabels([f"{int(float(t.get_text()))}" for t in ax.get_yticklabels()], rotation=0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()

def lineplot_packets_flora(df: pd.DataFrame, title: str, out_path: Path):
    """
    Line plot with FLoRa palette + markers; one series per SF.
    """
    # Build table SF7..SF12 columns for consistent ordering
    sub = df.pivot_table(values="received", index="distance", columns="sf", aggfunc="sum", fill_value=0)
    for sf in range(7, 13):
        if sf not in sub.columns:
            sub[sf] = 0
    sub = sub[[sf for sf in range(7, 13)]].sort_index()

    plt.figure(figsize=(14, 8))
    for idx, sf in enumerate(range(7, 13)):
        y = sub[sf].values
        x = sub.index.values
        plt.plot(
            x, y,
            marker=FLO_MARKERS[idx],
            linewidth=2,
            markersize=8,
            label=f"SF{sf}",
            color=FLO_PAL[idx]
        )
    plt.title(title)
    plt.xlabel("Distance (m)")
    plt.ylabel("Packets Received")
    plt.legend()
    plt.grid(True, alpha=0.3, linestyle="--")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()

def comparison_heatmap_two_heights_flora(df: pd.DataFrame, tp: int, z1: int, z2: int, out_path: Path):
    """
    Two side-by-side Seaborn heatmaps (RdYlGn), one per height, with annotations & grid lines.
    """
    fig, axes = plt.subplots(1, 2, figsize=(20, 8))
    for ax, z in zip(axes, [z1, z2]):
        subset = df[(df["tp"] == tp) & (df["z_ed"] == z)]
        if subset.empty:
            ax.axis("off")
            ax.set_title(f"Node Height: {z}m (no data)")
            continue
        heatmap_data = subset.pivot_table(values="received", index="distance", columns="sf", aggfunc="sum", fill_value=0)
        for sf in range(7, 13):
            if sf not in heatmap_data.columns:
                heatmap_data[sf] = 0
        heatmap_data = heatmap_data[[sf for sf in range(7, 13)]].sort_index()

        sns.heatmap(
            heatmap_data,
            annot=True,
            fmt='g',
            cmap=FLO_CMAP,
            cbar_kws={'label': 'Packets Received'},
            linewidths=0.5,
            linecolor='gray',
            ax=ax
        )
        ax.set_title(f"Node Height: {z}m")
        ax.set_xlabel("Spreading Factor")
        ax.set_ylabel("Distance (m)")
        ax.set_xticklabels([f"SF{int(sf)}" for sf in heatmap_data.columns], rotation=0)
        ax.set_yticklabels([f"{int(d)}" for d in heatmap_data.index], rotation=0)

    fig.suptitle(f"LoRa Packet Reception Comparison (TP={tp} dBm)", y=0.98, fontsize=14)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)

def comparison_table_two_heights(df: pd.DataFrame, tp: int, z1: int, z2: int) -> pd.DataFrame:
    rows = []
    distances = sorted(df[df["tp"] == tp]["distance"].unique().tolist())
    for dist in distances:
        row = {"Distance": f"{dist}m"}
        for sf in range(7, 13):
            v1 = df[(df["tp"] == tp) & (df["z_ed"] == z1) & (df["distance"] == dist) & (df["sf"] == sf)]["received"].sum()
            v2 = df[(df["tp"] == tp) & (df["z_ed"] == z2) & (df["distance"] == dist) & (df["sf"] == sf)]["received"].sum()
            row[f"SF{sf}_z{z1}"] = int(v1)
            row[f"SF{sf}_z{z2}"] = int(v2)
            if v1 > 0:
                row[f"SF{sf}_improvement"] = f"{((v2 - v1) / v1) * 100:+.1f}%"
            else:
                row[f"SF{sf}_improvement"] = "∞" if v2 > 0 else "0%"
        rows.append(row)
    return pd.DataFrame(rows)

def print_formatted_table(table: pd.DataFrame, z: Optional[int] = None, model: Optional[str] = None):
    print("\n" + "=" * 100)
    hdr = "SPREADING FACTOR vs DISTANCE - RECEIVED PACKETS ANALYSIS"
    if model: hdr += f" | Model: {model}"
    if z is not None: hdr += f" | Node Height: {z}m"
    print(hdr)
    print("=" * 100)
    df_display = table.copy()
    df_display.index.name = "Distance (m)"
    df_display.index = [f"{int(d)}m" for d in df_display.index]
    print(df_display.to_string())
    print("=" * 100)

# -------------------------
# Per-model analysis
# -------------------------
def analyze_model_group(df_model: pd.DataFrame, model: str, out_dir: Path, z_default: Optional[int]) -> None:
    # Heights for this model
    if "z_ed" in df_model.columns and df_model["z_ed"].notna().any():
        z_values = sorted(df_model["z_ed"].dropna().astype(int).unique().tolist())
    else:
        z_values = [0 if z_default is None else int(z_default)]
        df_model = df_model.copy()
        df_model["z_ed"] = z_values[0]

    tp_values = sorted(df_model["tp"].unique().tolist())

    model_dir = out_dir / model
    model_dir.mkdir(parents=True, exist_ok=True)

    for tp in tp_values:
        for z in z_values:
            subset = df_model[(df_model["tp"] == tp) & (df_model["z_ed"] == z)]
            if subset.empty:
                continue

            table = create_sf_distance_table(subset)
            summary = create_summary_statistics(table)

            # Filenames (same as FLoRa), placed under per-model folder
            heatmap_file = model_dir / f"sf_distance_heatmap_tp{tp}_z{z}m.png"
            lineplot_file = model_dir / f"sf_distance_lineplot_tp{tp}_z{z}m.png"
            table_csv    = model_dir / f"sf_distance_table_z{z}m.csv"
            summary_csv  = model_dir / f"summary_statistics_z{z}m.csv"
            md_file      = model_dir / f"results_table_z{z}m.md"

            heatmap_packets_flora(subset, f"SF vs Distance — {model} — z={z} m", heatmap_file)
            lineplot_packets_flora(subset, f"Packets vs Distance by SF — {model} — z={z} m", lineplot_file)
            table.to_csv(table_csv)
            summary.to_csv(summary_csv, index=False)
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(create_markdown_table(table))

            print_formatted_table(table, z=z, model=model)

        # 2-heights comparison (only within this model)
        if len(z_values) == 2:
            z1, z2 = z_values
            comp_png = model_dir / f"comparison_heatmap_tp{tp}_z{z1}m_vs_z{z2}m.png"
            comparison_heatmap_two_heights_flora(df_model[df_model["tp"] == tp], tp, z1, z2, comp_png)
            comp_df = comparison_table_two_heights(df_model[df_model["tp"] == tp], tp, z1, z2)
            comp_csv = model_dir / f"comparison_table_tp{tp}_z{z1}m_vs_z{z2}m.csv"
            comp_df.to_csv(comp_csv, index=False)

# -------------------------
# CLI
# -------------------------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="NS-3 LoRaWAN CSV analyzer (strict per-model, FLoRa colors)")
    grp = ap.add_mutually_exclusive_group(required=False)
    grp.add_argument("--input", type=str, help="Directory to scan recursively for CSVs.")
    grp.add_argument("--files", nargs="+", help="Explicit CSV files or glob patterns.")
    ap.add_argument("--out", type=str, default="plots", help="Output directory.")
    ap.add_argument("--z", type=int, default=None, help="Constant z_ed if CSVs lack it (e.g., 0).")
    return ap.parse_args()

def main():
    args = parse_args()
    inputs = [args.input] if args.input else (args.files if args.files else ["." ])
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_files = discover_csvs(inputs)
    grouped = group_files_by_model(all_files)
    if not grouped:
        print("No CSVs matched the expected filename pattern (sim_model_<Model>_sf*_tp*_dist*.csv).", file=sys.stderr)
        sys.exit(1)

    for model, files in sorted(grouped.items()):
        df_model = load_group(files)
        if df_model.empty:
            print(f"[warn] No valid rows for model {model}", file=sys.stderr)
            continue
        analyze_model_group(df_model, model, out_dir, z_default=args.z)

    print(f"\nDone. Outputs in: {out_dir.resolve()} (per-model subfolders)")

if __name__ == "__main__":
    main()
