"""
Scenario 02 analyzer: Fixed SF12 vs ADR Enabled

Reads the two CSVs produced by scenario-02-adr-comparison, aggregates key stats,
and produces a summary table + a comparison figure.
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

try:
    from ns3_lorawan_parser import NS3LoRaWANAnalyzer
except ImportError:
    print("❌ Missing dependency: ns3_lorawan_parser (NS3LoRaWANAnalyzer). Make sure it's on PYTHONPATH.")
    sys.exit(1)

# --- CONFIG ---
SCENARIO_02_OUTPUT_DIR = "./output/scenario-02-adr-comparison"
GLOB_PATTERN = "*results.csv"
SUMMARY_CSV = "scenario_02_summary.csv"
FIG_PNG = "scenario_02_analysis.png"

# optional pretty name mapping
NAME_MAP = {
    "fixed-sf12": "Fixed SF12",
    "adr-enabled": "ADR Enabled",
}

def _pretty_name(folder_name: str) -> str:
    return NAME_MAP.get(folder_name, folder_name)

def create_summary_dataframe(analyzer: NS3LoRaWANAnalyzer) -> pd.DataFrame:
    rows = []

    # sort to keep output stable
    for key, data in sorted(analyzer.scenarios_data.items()):
        file_path = data.get("file_path", "")
        folder = os.path.basename(os.path.dirname(file_path))  # e.g., "fixed-sf12" or "adr-enabled"
        label = _pretty_name(folder)

        overall = data.get("overall_stats", {}) or {}
        per_node = data.get("per_node_data", None)

        # Robust per-node metrics
        avg_final_tp = None
        avg_final_sf = None
        avg_rssi = None
        avg_snr = None

        if isinstance(per_node, pd.DataFrame) and not per_node.empty:
            if "FinalTP_dBm" in per_node.columns:
                avg_final_tp = pd.to_numeric(per_node["FinalTP_dBm"], errors="coerce").mean()
            # Prefer FinalSF; if future CSVs ever include FinalSF_DR, convert DR -> SF
            if "FinalSF" in per_node.columns:
                avg_final_sf = pd.to_numeric(per_node["FinalSF"], errors="coerce").mean()
            elif "FinalSF_DR" in per_node.columns:
                avg_final_sf = (12 - pd.to_numeric(per_node["FinalSF_DR"], errors="coerce")).mean()
            # Optional columns, present only if your analyzer enriches them
            if "AvgRSSI_dBm" in per_node.columns:
                avg_rssi = pd.to_numeric(per_node["AvgRSSI_dBm"], errors="coerce").mean()
            if "AvgSNR_dB" in per_node.columns:
                avg_snr = pd.to_numeric(per_node["AvgSNR_dB"], errors="coerce").mean()

        # Pull exporter’s fields (names match your C++)
        total_sent = int(overall.get("TotalSent", 0) or 0)
        total_recv = int(overall.get("TotalReceived", 0) or 0)
        pdr_pct = float(overall.get("PDR_Percent", 0.0) or 0.0)
        total_airtime_s = float(overall.get("TotalAirTime_ms", 0.0) or 0.0) / 1000.0
        airtime_reduction_pct = float(overall.get("AirtimeReduction_vs_SF12_Percent", 0.0) or 0.0)
        adr_enabled_flag = str(overall.get("ADR_Enabled", "")).upper() in ("TRUE", "1", "YES")

        rows.append({
            "Configuration": label,
            "ADR Enabled": adr_enabled_flag,
            "Total Sent": total_sent,
            "Total Received": total_recv,
            "Overall PDR (%)": pdr_pct,
            "Total Airtime (s)": total_airtime_s,
            "Airtime Reduction vs SF12 (%)": airtime_reduction_pct,
            "Avg Final SF": avg_final_sf,
            "Avg Final TP (dBm)": avg_final_tp,
            "Avg RSSI (dBm)": avg_rssi,
            "Avg SNR (dB)": avg_snr,
        })

    df = pd.DataFrame(rows)
    df.set_index("Configuration", inplace=True)
    return df

def plot_scenario_comparison(summary_df: pd.DataFrame, analyzer: NS3LoRaWANAnalyzer) -> None:
    import warnings
    warnings.filterwarnings("ignore", message="Unable to import Axes3D", category=UserWarning)

    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle("Scenario 02: Fixed SF12 vs ADR Performance", fontsize=20, weight="bold")

    # Work with columns instead of index for seaborn hue
    df = summary_df.reset_index()  # keeps "Configuration" as a column

    # --- Bar 1: PDR ---
    ax = axes[0, 0]
    sns.barplot(
        data=df, x="Configuration", y="Overall PDR (%)",
        hue="Configuration", legend=False, palette="coolwarm", ax=ax
    )
    ax.set_title("Packet Delivery Ratio (PDR)", fontsize=14, weight="bold")
    # annotate
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f'{h:.2f}', (p.get_x() + p.get_width()/2., h),
                        ha='center', va='center', xytext=(0, 5),
                        textcoords='offset points', weight='bold')

    # --- Bar 2: Total Airtime ---
    ax = axes[0, 1]
    sns.barplot(
        data=df, x="Configuration", y="Total Airtime (s)",
        hue="Configuration", legend=False, palette="magma", ax=ax
    )
    ax.set_title("Total Network Airtime", fontsize=14, weight="bold")
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f'{h:.1f}', (p.get_x() + p.get_width()/2., h),
                        ha='center', va='center', xytext=(0, 5),
                        textcoords='offset points', weight='bold')

    # --- Pie: Final SF distribution for ADR ---
    ax = axes[1, 0]
    adr_key = None
    for key, data in analyzer.scenarios_data.items():
        folder = os.path.basename(os.path.dirname(data.get("file_path", "")))
        if folder in ("adr-enabled", "ADR Enabled"):
            adr_key = key
            break

    if adr_key:
        adr_df = analyzer.scenarios_data[adr_key].get("per_node_data")
        if isinstance(adr_df, pd.DataFrame) and "FinalSF" in adr_df.columns:
            sf_counts = adr_df["FinalSF"].value_counts().sort_index()
            if not sf_counts.empty:
                labels = [f"SF{int(sf)}" for sf in sf_counts.index]
                ax.pie(
                    sf_counts.values, labels=labels, autopct="%1.1f%%", startangle=90,
                    colors=sns.color_palette("viridis", len(sf_counts))
                )
                ax.set_title("Final Spreading Factor Distribution (ADR Enabled)", fontsize=14, weight="bold")
            else:
                ax.text(0.5, 0.5, "No data", ha="center", va="center")
        else:
            ax.text(0.5, 0.5, "FinalSF not available", ha="center", va="center")
    else:
        ax.text(0.5, 0.5, "ADR scenario not found", ha="center", va="center")

    # --- Bar 4: Avg Final TP ---
    ax = axes[1, 1]
    sns.barplot(
        data=df, x="Configuration", y="Avg Final TP (dBm)",
        hue="Configuration", legend=False, palette="crest", ax=ax
    )
    ax.set_title("Average Final Transmit Power", fontsize=14, weight="bold")
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f'{h:.1f}', (p.get_x() + p.get_width()/2., h),
                        ha='center', va='center', xytext=(0, 5),
                        textcoords='offset points', weight='bold')

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(FIG_PNG, dpi=300)
    print(f"✅ Visualizations saved: {FIG_PNG}")


def main():
    print("🔬 Scenario 02: ADR Comparison — Analysis")
    if not os.path.isdir(SCENARIO_02_OUTPUT_DIR):
        print(f"❌ Directory not found: {SCENARIO_02_OUTPUT_DIR}")
        return

    analyzer = NS3LoRaWANAnalyzer(csv_directory=SCENARIO_02_OUTPUT_DIR)
    analyzer.analyze_all_csv_files_recursive(GLOB_PATTERN)

    if not analyzer.scenarios_data:
        print("❌ No CSVs found. Check the path and naming (*results.csv).")
        return

    summary_df = create_summary_dataframe(analyzer)

    # Pretty print
    print("\n📊 Summary:")
    print("-" * 100)
    print(summary_df.to_string(float_format=lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)))
    print("-" * 100)

    # Save summary CSV
    summary_df.to_csv(SUMMARY_CSV, index=True)
    print(f"💾 Summary saved: {SUMMARY_CSV}")

    # Plots
    try:
        plot_scenario_comparison(summary_df, analyzer)
    except Exception as e:
        print(f"⚠️ Plotting skipped due to error: {e}")

    print("🎉 Analysis complete.")

if __name__ == "__main__":
    main()
