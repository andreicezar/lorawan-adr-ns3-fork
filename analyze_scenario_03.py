"""
Scenario 03 analyzer: Spreading Factor (SF7..SF12) impact

Outputs:
  - scenario_03_summary.csv  (one row per SF)
  - scenario_03_per_node.csv (all nodes, with SF column)
  - scenario_03_analysis.png (2x2 figure)
"""

import os
import warnings
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings(
    "ignore",
    message="Unable to import Axes3D",
    category=UserWarning,
)

try:
    from ns3_lorawan_parser import NS3LoRaWANAnalyzer
except ImportError:
    print("❌ Missing dependency: ns3_lorawan_parser (NS3LoRaWANAnalyzer). Make sure it's on PYTHONPATH.")
    raise

# --- CONFIG ---
SCENARIO_03_OUTPUT_DIR = "./output/scenario-03-sf-impact"
GLOB_PATTERN = "*results.csv"
SUMMARY_CSV = "scenario_03_summary.csv"
PER_NODE_CSV = "scenario_03_per_node.csv"
FIG_PNG = "scenario_03_analysis.png"


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


def create_summary_dataframe(analyzer: NS3LoRaWANAnalyzer):
    """
    Aggregates key metrics from all SF sub-scenarios into a single DataFrame,
    and returns (summary_df, per_node_concat_df).
    """
    rows = []
    per_node_all = []

    # Sort keys for deterministic output
    for key, data in sorted(analyzer.scenarios_data.items()):
        overall = data.get("overall_stats", {}) or {}
        per_node = data.get("per_node_data", None)

        sf = _to_int(overall.get("SpreadingFactor", 0))
        total_sent = _to_int(overall.get("TotalSent", 0))
        total_recv = _to_int(overall.get("TotalReceived", 0))
        pdr_pct = _to_float(overall.get("PDR_Percent", 0.0))
        drop_count = _to_int(overall.get("PacketsDropped_SentMinusReceived", total_sent - total_recv))
        drop_rate_pct = _to_float(overall.get("DropRate_Percent", 0.0))
        total_airtime_s = _to_float(overall.get("TotalAirTime_ms", 0.0)) / 1000.0
        theo_airtime_ms = _to_float(overall.get("TheoreticalAirTimePerPacket_ms", 0.0))
        ch_util_pct = _to_float(overall.get("ChannelUtilization_Percent", 0.0))
        airtime_scale_vs_sf7 = _to_float(overall.get("AirtimeScale_vs_SF7", 0.0))

        # Per-node averages (if present)
        avg_rssi = avg_snr = avg_tp = None
        if isinstance(per_node, pd.DataFrame) and not per_node.empty:
            if "AvgRSSI_dBm" in per_node.columns:
                avg_rssi = pd.to_numeric(per_node["AvgRSSI_dBm"], errors="coerce").mean()
            if "AvgSNR_dB" in per_node.columns:
                avg_snr = pd.to_numeric(per_node["AvgSNR_dB"], errors="coerce").mean()
            # Your exporter doesn’t write per-node TP in Scenario 03; keep placeholder if added later.
            if "AvgTP_dBm" in per_node.columns:
                avg_tp = pd.to_numeric(per_node["AvgTP_dBm"], errors="coerce").mean()

            # Keep a concatenated per-node table for deeper analysis
            pn = per_node.copy()
            pn["SpreadingFactor"] = sf
            per_node_all.append(pn)

        rows.append({
            "Spreading Factor": sf,
            "Total Sent": total_sent,
            "Total Received": total_recv,
            "Overall PDR (%)": pdr_pct,
            "Packets Dropped": drop_count,
            "Drop Rate (%)": drop_rate_pct,
            "Total Airtime (s)": total_airtime_s,
            "Theoretical Airtime/packet (ms)": theo_airtime_ms,
            "Airtime Scale vs SF7 (×)": airtime_scale_vs_sf7,
            "Channel Utilization (%)": ch_util_pct,
            "Average RSSI (dBm)": avg_rssi,
            "Average SNR (dB)": avg_snr,
            "Average TP (dBm)": avg_tp,
        })

    summary_df = pd.DataFrame(rows)
    summary_df = summary_df.sort_values(by="Spreading Factor").set_index("Spreading Factor")

    per_node_concat = pd.concat(per_node_all, ignore_index=True) if per_node_all else pd.DataFrame()
    return summary_df, per_node_concat


def plot_scenario_comparison(summary_df: pd.DataFrame) -> None:
    """
    2x2 figure:
      (0,0) PDR vs SF
      (0,1) Total Airtime (log) vs SF
      (1,0) RSSI vs SF
      (1,1) SNR vs SF
    """
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle("Scenario 03: Spreading Factor Impact Analysis", fontsize=20, weight="bold")

    # Work with column access (index is SF)
    sf = summary_df.index.values

    # --- (0,0) PDR ---
    ax = axes[0, 0]
    sns.lineplot(
        x=sf, y=summary_df["Overall PDR (%)"],
        marker="o", linewidth=2.5, ax=ax
    )
    ax.set_title("Reliability (PDR) vs Spreading Factor", fontsize=14, weight="bold")
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("PDR (%)")
    for x, y in zip(sf, summary_df["Overall PDR (%)"]):
        if pd.notna(y):
            ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")

    # --- (0,1) Airtime (log) ---
    ax = axes[0, 1]
    sns.lineplot(
        x=sf, y=summary_df["Total Airtime (s)"],
        marker="s", linewidth=2.5, ax=ax
    )
    ax.set_yscale("log")
    ax.set_title("Network Airtime vs Spreading Factor (log scale)", fontsize=14, weight="bold")
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("Total Airtime (s)")
    for x, y in zip(sf, summary_df["Total Airtime (s)"]):
        if pd.notna(y):
            ax.annotate(f"{y:.1f}s", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")

    # --- (1,0) RSSI ---
    ax = axes[1, 0]
    if "Average RSSI (dBm)" in summary_df.columns and summary_df["Average RSSI (dBm)"].notna().any():
        sns.lineplot(
            x=sf, y=summary_df["Average RSSI (dBm)"],
            marker="^", linewidth=2.5, ax=ax
        )
        ax.set_title("Signal Strength (RSSI) vs Spreading Factor", fontsize=14, weight="bold")
        ax.set_xlabel("Spreading Factor")
        ax.set_ylabel("Average RSSI (dBm)")
        for x, y in zip(sf, summary_df["Average RSSI (dBm)"]):
            if pd.notna(y):
                ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")
    else:
        ax.text(0.5, 0.5, "RSSI not available", ha="center", va="center")
        ax.set_axis_off()

    # --- (1,1) SNR ---
    ax = axes[1, 1]
    if "Average SNR (dB)" in summary_df.columns and summary_df["Average SNR (dB)"].notna().any():
        sns.lineplot(
            x=sf, y=summary_df["Average SNR (dB)"],
            marker="d", linewidth=2.5, ax=ax
        )
        ax.set_title("Signal Quality (SNR) vs Spreading Factor", fontsize=14, weight="bold")
        ax.set_xlabel("Spreading Factor")
        ax.set_ylabel("Average SNR (dB)")
        for x, y in zip(sf, summary_df["Average SNR (dB)"]):
            if pd.notna(y):
                ax.annotate(f"{y:.1f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")
    else:
        ax.text(0.5, 0.5, "SNR not available", ha="center", va="center")
        ax.set_axis_off()

    for ax in axes.flat:
        if ax.has_data():
            ax.grid(True, which="both", linestyle="--", alpha=0.5)

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(FIG_PNG, dpi=300)
    print(f"✅ Visualizations saved: {FIG_PNG}")


def main():
    print("🔬 Scenario 03: Spreading Factor Impact — Analysis")

    if not os.path.isdir(SCENARIO_03_OUTPUT_DIR):
        print(f"❌ Directory not found: {SCENARIO_03_OUTPUT_DIR}")
        return

    analyzer = NS3LoRaWANAnalyzer(csv_directory=SCENARIO_03_OUTPUT_DIR)
    analyzer.analyze_all_csv_files_recursive(GLOB_PATTERN)

    if not analyzer.scenarios_data:
        print("❌ No CSVs found. Check the output path and naming (*results.csv).")
        return

    summary_df, per_node_concat = create_summary_dataframe(analyzer)

    # Pretty print
    print("\n📊 Summary (by Spreading Factor):")
    print("-" * 120)
    with pd.option_context("display.float_format", lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)):
        print(summary_df.to_string())
    print("-" * 120)

    # Save CSVs
    summary_df.to_csv(SUMMARY_CSV, index=True)
    print(f"💾 Summary saved: {SUMMARY_CSV}")
    if not per_node_concat.empty:
        per_node_concat.to_csv(PER_NODE_CSV, index=False)
        print(f"💾 Per-node data saved: {PER_NODE_CSV}")

    # Plots
    try:
        plot_scenario_comparison(summary_df)
    except Exception as e:
        print(f"⚠️ Plotting skipped due to error: {e}")

    print("🎉 Analysis complete.")


if __name__ == "__main__":
    main()
