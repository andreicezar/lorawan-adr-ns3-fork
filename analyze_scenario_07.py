"""
Scenario 07 analyzer: Propagation Model Comparison (FreeSpace vs LogDistance)

Outputs:
  - scenario_07_summary.csv   (one row per model)
  - scenario_07_per_node.csv  (all nodes across models, with model & exponent)
  - scenario_07_analysis.png  (2x2 figure)
"""

import os
import re
import warnings
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore", message="Unable to import Axes3D", category=UserWarning)

try:
    from ns3_lorawan_parser import NS3LoRaWANAnalyzer
except ImportError:
    print("❌ Missing dependency: ns3_lorawan_parser (NS3LoRaWANAnalyzer). Put it on PYTHONPATH.")
    raise

# --- CONFIG ---
SCENARIO_07_OUTPUT_DIR = "./output/scenario-07-propagation-models"
GLOB_PATTERN = "*results.csv"
SUMMARY_CSV = "scenario_07_summary.csv"
PER_NODE_CSV = "scenario_07_per_node.csv"
FIG_PNG = "scenario_07_analysis.png"


# ---------- helpers ----------
def _to_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def _to_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def _first_present(d: dict, names: list, cast=float, default=0.0):
    """Return the first present key from names in dict d, cast to type; else default."""
    for n in names:
        if n in d and d[n] not in (None, "", "N/A"):
            try:
                return cast(d[n])
            except Exception:
                pass
    return default

def extract_model_info(key_or_path: str):
    """
    Extract a friendly model label and (optional) exponent from a scenario key/path.
    - '.../logdist-376/...' -> ('LogDistance (n=3.76)', 'LogDistance', 3.76)
    - '.../freespace/...'   -> ('FreeSpace', 'FreeSpace', None)
    - fallback to OVERALL 'PropagationModel' string if folder name is undecidable (handled elsewhere)
    """
    s = key_or_path.lower()
    if "freespace" in s:
        return "FreeSpace", "FreeSpace", None
    m = re.search(r"logdist-(\d+)", s)
    if m:
        digits = m.group(1)
        # map '376' -> '3.76', '35' -> '3.5', etc
        n = float(digits[0] + "." + digits[1:]) if len(digits) > 1 else float(digits)
        return f"LogDistance (n={n:.2f})", "LogDistance", n
    # fallback
    return "Unknown", "Unknown", None


# ---------- aggregation ----------
def create_summary_dataframe(analyzer: NS3LoRaWANAnalyzer):
    """
    Aggregates key metrics from all sub-scenarios into a single DataFrame.
    Returns the summary DataFrame (indexed by Model label).
    """
    rows = []

    for key, data in sorted(analyzer.scenarios_data.items()):
        stats = data.get("overall_stats", {}) or {}
        file_path = data.get("file_path", "") or key

        # Prefer folder-derived label; if Unknown, use CSV field as fallback
        label, family, n = extract_model_info(file_path)
        if label == "Unknown":
            fam = str(stats.get("PropagationModel", "Unknown"))
            label = fam

        pdr_pct = _first_present(stats, ["PDR_Percent", "PDR(%)", "PDR"], cast=float, default=0.0)
        max_ok  = _first_present(stats, ["MaxSuccessfulDistance_m"], cast=float, default=0.0)
        min_fail= _first_present(stats, ["MinFailureDistance_m"], cast=float, default=0.0)
        avg_rssi= _first_present(stats, ["OverallAvgRSSI_dBm"], cast=float, default=0.0)

        rows.append({
            "Model": label,
            "Family": family,
            "Exponent_n": n,
            "Overall PDR (%)": pdr_pct,
            "Max Successful Distance (m)": max_ok,
            "Min Failure Distance (m)": min_fail,
            "Overall Avg RSSI (dBm)": avg_rssi,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        # stable, human-pleasant ordering: FreeSpace first, then LogDistance sorted by n
        frees = df[df["Family"] == "FreeSpace"]
        logs  = df[df["Family"] == "LogDistance"].sort_values(by=["Exponent_n"])
        others= df[(df["Family"] != "FreeSpace") & (df["Family"] != "LogDistance")]
        df = pd.concat([frees, logs, others], ignore_index=True)
        df = df.set_index("Model")

    return df


def create_combined_per_node_dataframe(analyzer: NS3LoRaWANAnalyzer):
    """
    Combines per-node data from all sub-scenarios into a single DataFrame
    and attaches the model label, family, and exponent.
    """
    all_node = []
    for key, data in analyzer.scenarios_data.items():
        df = data.get("per_node_data")
        if isinstance(df, pd.DataFrame) and not df.empty:
            file_path = data.get("file_path", "") or key
            label, family, n = extract_model_info(file_path)

            pn = df.copy()
            pn["Model"] = label
            pn["Family"] = family
            pn["Exponent_n"] = n
            # normalize expected columns (the exporter provides these in Scenario 07)
            for col in ["Distance_m", "AvgRSSI_dBm", "AvgSNR_dB", "PDR_Percent", "Sent", "Received"]:
                if col in pn.columns:
                    pn[col] = pd.to_numeric(pn[col], errors="coerce")
            all_node.append(pn)

    return pd.concat(all_node, ignore_index=True) if all_node else pd.DataFrame()


# ---------- plots ----------
def plot_scenario_comparison(summary_df: pd.DataFrame, combined_node_df: pd.DataFrame) -> None:
    """
    2x2 figure:
      (0,0) RSSI vs Distance (scatter, colored by model)
      (0,1) SNR  vs Distance (scatter, colored by model)
      (1,0) Overall PDR by model (bar)
      (1,1) Max successful distance by model (bar)
    """
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle("Scenario 07: Propagation Model Comparison", fontsize=20, weight="bold")

    # --- (0,0) RSSI vs Distance ---
    ax = axes[0, 0]
    if not combined_node_df.empty and {"Distance_m", "AvgRSSI_dBm", "Model"}.issubset(combined_node_df.columns):
        sns.scatterplot(
            data=combined_node_df, x="Distance_m", y="AvgRSSI_dBm",
            hue="Model", s=50, alpha=0.7, ax=ax
        )
        ax.set_title("Signal Strength (RSSI) vs. Distance", fontsize=14, weight="bold")
        ax.set_xlabel("Distance from Gateway (m)")
        ax.set_ylabel("Average RSSI (dBm)")
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
    else:
        ax.text(0.5, 0.5, "Per-node RSSI not available", ha="center", va="center")
        ax.set_axis_off()

    # --- (0,1) SNR vs Distance ---
    ax = axes[0, 1]
    if not combined_node_df.empty and {"Distance_m", "AvgSNR_dB", "Model"}.issubset(combined_node_df.columns):
        sns.scatterplot(
            data=combined_node_df, x="Distance_m", y="AvgSNR_dB",
            hue="Model", s=50, alpha=0.7, ax=ax
        )
        ax.set_title("Signal Quality (SNR) vs. Distance", fontsize=14, weight="bold")
        ax.set_xlabel("Distance from Gateway (m)")
        ax.set_ylabel("Average SNR (dB)")
        ax.grid(True, which="both", linestyle="--", alpha=0.5)
    else:
        ax.text(0.5, 0.5, "Per-node SNR not available", ha="center", va="center")
        ax.set_axis_off()

    # --- (1,0) Overall PDR ---
    ax = axes[1, 0]
    df_pdr = summary_df.reset_index()
    sns.barplot(
        data=df_pdr, x="Model", y="Overall PDR (%)",
        hue="Model", legend=False, palette="viridis", ax=ax
    )
    ax.set_title("Overall Network Reliability (PDR)", fontsize=14, weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("PDR (%)")
    ax.tick_params(axis="x", rotation=25)
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{h:.2f}", (p.get_x() + p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 5),
                        textcoords="offset points", weight="bold")

    # --- (1,1) Max Successful Distance ---
    ax = axes[1, 1]
    sns.barplot(
        data=df_pdr, x="Model", y="Max Successful Distance (m)",
        hue="Model", legend=False, palette="plasma", ax=ax
    )
    ax.set_title("Maximum Communication Range", fontsize=14, weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Distance (m)")
    ax.tick_params(axis="x", rotation=25)
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{int(h)} m", (p.get_x() + p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 5),
                        textcoords="offset points", weight="bold")

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(FIG_PNG, dpi=300)
    print(f"✅ Visualizations saved: {FIG_PNG}")


# ---------- main ----------
def main():
    print("🔬 Scenario 07: Propagation Model Testing — Analysis")
    if not os.path.isdir(SCENARIO_07_OUTPUT_DIR):
        print(f"❌ Directory not found: {SCENARIO_07_OUTPUT_DIR}")
        print("   Run './run-07.sh' first to generate results.")
        return

    analyzer = NS3LoRaWANAnalyzer(csv_directory=SCENARIO_07_OUTPUT_DIR)
    analyzer.analyze_all_csv_files_recursive(GLOB_PATTERN)

    if not analyzer.scenarios_data:
        print("❌ No CSVs found. Check the output path and naming (*results.csv).")
        return

    summary_df = create_summary_dataframe(analyzer)
    combined_node_df = create_combined_per_node_dataframe(analyzer)

    # Pretty print
    print("\n📊 Scenario 07 Summary:")
    print("-" * 100)
    with pd.option_context("display.float_format", lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)):
        print(summary_df.to_string())
    print("-" * 100)

    # Save CSVs
    summary_df.to_csv(SUMMARY_CSV, index=True)
    print(f"💾 Summary saved: {SUMMARY_CSV}")
    if not combined_node_df.empty:
        combined_node_df.to_csv(PER_NODE_CSV, index=False)
        print(f"💾 Per-node data saved: {PER_NODE_CSV}")

    # Plots
    try:
        plot_scenario_comparison(summary_df, combined_node_df)
    except Exception as e:
        print(f"⚠️ Plotting skipped due to error: {e}")

    print("🎉 Analysis complete.")

if __name__ == "__main__":
    main()
