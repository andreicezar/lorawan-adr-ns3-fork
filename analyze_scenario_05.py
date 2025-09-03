"""
Scenario 05 analyzer: Traffic Pattern Variation (intervals 600s / 300s / 60s)

Outputs:
  - scenario_05_summary.csv   (one row per packet-interval sub-scenario)
  - scenario_05_per_node.csv  (all nodes, with interval column)
  - scenario_05_analysis.png  (2x2 figure)

Robust to small naming changes in CSV headers (tries multiple aliases).
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
SCENARIO_05_OUTPUT_DIR = "./output/scenario-05-traffic-patterns"
GLOB_PATTERN = "*results.csv"
SUMMARY_CSV = "scenario_05_summary.csv"
PER_NODE_CSV = "scenario_05_per_node.csv"
FIG_PNG = "scenario_05_analysis.png"


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


# ---------- aggregation ----------
def create_summary_dataframe(analyzer: NS3LoRaWANAnalyzer):
    """
    Aggregates key metrics from all traffic-load sub-scenarios into a single DataFrame.
    Also returns a concatenated per-node DataFrame if available.
    """
    rows = []
    per_node_all = []

    for key, data in sorted(analyzer.scenarios_data.items()):
        stats = data.get("overall_stats", {}) or {}
        per_node = data.get("per_node_data", None)

        pkt_interval = _first_present(stats, ["PacketInterval_s", "PacketIntervalSec"], cast=int, default=0)
        total_sent   = _first_present(stats, ["TotalSent"], cast=int, default=0)
        total_recv   = _first_present(stats, ["TotalReceived"], cast=int, default=0)
        pdr_pct      = _first_present(stats, ["PDR_Percent", "PDR(%)", "PDR"], cast=float,
                                      default=(100.0 * total_recv / total_sent if total_sent else 0.0))
        drop_rate    = _first_present(stats, ["DropRate_Percent", "DropRate(%)"], cast=float,
                                      default=(100.0 * max(0, total_sent - total_recv) / total_sent if total_sent else 0.0))

        offered_erlangs = _first_present(stats, ["OfferedLoad_Erlangs", "Offered_Load_Erlangs"], cast=float, default=0.0)
        chan_util_pct   = _first_present(stats, ["ChannelUtilization_Percent", "ChannelUtil(%)"], cast=float, default=0.0)

        avg_dc_use_pct  = _first_present(stats, ["AvgDutyCycleUsage_Percent"], cast=float, default=0.0)
        avg_dc_head_pct = _first_present(stats, ["AvgDutyCycleHeadroom_Percent"], cast=float, default=max(0.0, 1.0 - avg_dc_use_pct) * 100.0)
        saturation_pct  = _first_present(stats, ["SaturationLevel_Percent"], cast=float, default=chan_util_pct)

        total_air_ms    = _first_present(stats, ["TotalChannelAirTime_ms", "TotalAirTime_ms"], cast=float, default=0.0)
        total_air_s     = total_air_ms / 1000.0

        # Optional header values (for throughput etc.) – your header may include this
        sim_minutes     = _first_present(stats, ["SimulationTime_minutes", "SimulationTime_min"], cast=float, default=0.0)
        throughput_ps   = (total_recv / (sim_minutes * 60.0)) if sim_minutes > 0 else None

        rows.append({
            "Packet Interval (s)": pkt_interval,
            "Total Sent": total_sent,
            "Total Received": total_recv,
            "Overall PDR (%)": pdr_pct,
            "Drop Rate (%)": drop_rate,
            "Offered Load (Erlangs)": offered_erlangs,
            "Channel Utilization (%)": chan_util_pct,
            "Avg Duty Cycle Usage (%)": avg_dc_use_pct,
            "Avg Duty Cycle Headroom (%)": avg_dc_head_pct,
            "Saturation Level (%)": saturation_pct,
            "Total Channel Airtime (s)": total_air_s,
            "Throughput (pkts/s)": throughput_ps,
        })

        # Keep a concatenated per-node table for deeper analysis
        if isinstance(per_node, pd.DataFrame) and not per_node.empty:
            pn = per_node.copy()
            pn["Packet Interval (s)"] = pkt_interval
            per_node_all.append(pn)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by="Packet Interval (s)").set_index("Packet Interval (s)")

    per_node_concat = pd.concat(per_node_all, ignore_index=True) if per_node_all else pd.DataFrame()
    return df, per_node_concat


# ---------- plots ----------
def plot_scenario_comparison(summary_df: pd.DataFrame) -> None:
    """
    2x2 figure:
      (0,0) PDR vs interval
      (0,1) Channel Utilization vs interval
      (1,0) Drop Rate vs interval
      (1,1) Offered Load vs interval
    """
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle("Scenario 05: Traffic Load Impact Analysis", fontsize=20, weight="bold")

    xvals = summary_df.index.values

    # (0,0) PDR
    ax = axes[0, 0]
    sns.lineplot(x=xvals, y=summary_df["Overall PDR (%)"], marker="o", linewidth=2.5, ax=ax)
    ax.set_title("Network Reliability vs Traffic Load", fontsize=14, weight="bold")
    ax.set_xlabel("Packet Interval (seconds) — Lower = More Traffic")
    ax.set_ylabel("Overall PDR (%)")
    ax.invert_xaxis()
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    for x, y in zip(xvals, summary_df["Overall PDR (%)"]):
        if pd.notna(y):
            ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")

    # (0,1) Channel Utilization
    ax = axes[0, 1]
    sns.lineplot(x=xvals, y=summary_df["Channel Utilization (%)"], marker="s", linewidth=2.5, ax=ax)
    ax.set_title("Channel Congestion vs Traffic Load", fontsize=14, weight="bold")
    ax.set_xlabel("Packet Interval (seconds) — Lower = More Traffic")
    ax.set_ylabel("Channel Utilization (%)")
    ax.invert_xaxis()
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    for x, y in zip(xvals, summary_df["Channel Utilization (%)"]):
        if pd.notna(y):
            ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")

    # (1,0) Drop Rate
    ax = axes[1, 0]
    sns.lineplot(x=xvals, y=summary_df["Drop Rate (%)"], marker="^", linewidth=2.5, ax=ax)
    ax.set_title("Packet Drop Rate vs Traffic Load", fontsize=14, weight="bold")
    ax.set_xlabel("Packet Interval (seconds) — Lower = More Traffic")
    ax.set_ylabel("Drop Rate (%)")
    ax.invert_xaxis()
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    for x, y in zip(xvals, summary_df["Drop Rate (%)"]):
        if pd.notna(y):
            ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")

    # (1,1) Offered Load (Erlangs)
    ax = axes[1, 1]
    sns.lineplot(x=xvals, y=summary_df["Offered Load (Erlangs)"], marker="d", linewidth=2.5, ax=ax)
    ax.set_title("Formal Traffic Intensity (Offered Load)", fontsize=14, weight="bold")
    ax.set_xlabel("Packet Interval (seconds) — Lower = More Traffic")
    ax.set_ylabel("Offered Load (Erlangs)")
    ax.invert_xaxis()
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    for x, y in zip(xvals, summary_df["Offered Load (Erlangs)"]):
        if pd.notna(y):
            ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", weight="bold")

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(FIG_PNG, dpi=300)
    print(f"✅ Visualizations saved: {FIG_PNG}")


# ---------- main ----------
def main():
    print("🔬 Scenario 05: Traffic Pattern Variation — Analysis")
    if not os.path.isdir(SCENARIO_05_OUTPUT_DIR):
        print(f"❌ Directory not found: {SCENARIO_05_OUTPUT_DIR}")
        print("   Run './run-05.sh' first to generate results.")
        return

    analyzer = NS3LoRaWANAnalyzer(csv_directory=SCENARIO_05_OUTPUT_DIR)
    analyzer.analyze_all_csv_files_recursive(GLOB_PATTERN)

    if not analyzer.scenarios_data:
        print("❌ No CSVs found. Check the output path and naming (*results.csv).")
        return

    summary_df, per_node_concat = create_summary_dataframe(analyzer)

    print("\n📊 Scenario 05 Summary (by Packet Interval):")
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
