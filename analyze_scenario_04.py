"""
Scenario 04 analyzer: Confirmed vs Unconfirmed Messages

Outputs:
  - scenario_04_summary.csv   (one row per configuration)
  - scenario_04_per_node.csv  (all nodes, if per-node tables exist)
  - scenario_04_analysis.png  (2x2 figure)

Robust to different CSV column names (tries several aliases).
"""

import os
import warnings
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

warnings.filterwarnings("ignore", message="Unable to import Axes3D", category=UserWarning)

try:
    from ns3_lorawan_parser import NS3LoRaWANAnalyzer
except ImportError:
    print("❌ Missing dependency: ns3_lorawan_parser (NS3LoRaWANAnalyzer). Add it to PYTHONPATH.")
    raise

# --- CONFIG ---
SCENARIO_04_OUTPUT_DIR = "./output/scenario-04-confirmed-messages"
GLOB_PATTERN = "*results.csv"
SUMMARY_CSV = "scenario_04_summary.csv"
PER_NODE_CSV = "scenario_04_per_node.csv"
FIG_PNG = "scenario_04_analysis.png"


def _to_float(x, default=0.0):
    try: return float(x)
    except Exception: return default

def _to_int(x, default=0):
    try: return int(x)
    except Exception: return default

def _first_present(d: dict, names: list, cast=float, default=0.0):
    """Return the first present key from names in dict d, cast to type; else default."""
    for n in names:
        if n in d and d[n] not in (None, "", "N/A"):
            try:
                return cast(d[n])
            except Exception:
                pass
    return default

def _label_from_source(stats: dict, file_path: str) -> str:
    # Prefer explicit field
    mt = str(stats.get("MessageType", "")).upper()
    if mt.startswith("CONFIRMED"):
        return "Confirmed"
    if mt.startswith("UNCONFIRMED"):
        return "Unconfirmed"
    # Fallback to filename
    base = os.path.basename(file_path).lower()
    if "confirmed" in base:
        return "Confirmed"
    if "unconfirmed" in base:
        return "Unconfirmed"
    # Folder name as last resort
    folder = os.path.basename(os.path.dirname(file_path)).lower()
    if "confirmed" in folder:
        return "Confirmed"
    if "unconfirmed" in folder:
        return "Unconfirmed"
    return "Unconfirmed"  # sensible default (keeps ordering stable)

def create_summary_dataframe(analyzer: NS3LoRaWANAnalyzer):
    """
    Aggregates key metrics and returns (summary_df, per_node_concat_df).
    Tries multiple aliases for each metric to handle exporter naming diffs.
    """
    rows, per_node_all = [], []

    for key, data in sorted(analyzer.scenarios_data.items()):
        stats = data.get("overall_stats", {}) or {}
        per_node = data.get("per_node_data", None)
        path = data.get("file_path", "")

        label = _label_from_source(stats, path)

        total_sent = _first_present(stats, ["TotalSent", "UL_Sent", "UplinkSent"], cast=int, default=0)
        total_recv = _first_present(stats, ["TotalReceived", "UL_Received", "UplinkReceived"], cast=int, default=0)
        pdr_pct    = _first_present(stats, ["PDR_Percent", "PDR(%)", "PDR"], cast=float, default=(100.0 * total_recv / total_sent if total_sent else 0.0))

        total_retx = _first_present(stats, ["TotalRetransmissions", "Retransmissions", "UL_Retransmissions"], cast=int, default=0)
        retx_rate  = _first_present(stats, ["RetransmissionRate_Percent", "RetxRate(%)"], cast=float, default=(100.0 * total_retx / total_sent if total_sent else 0.0))

        # Airtime components (ms), try several names
        ul_air_ms  = _first_present(stats, ["TotalAirTime_ms", "UplinkAirTime_ms", "UL_Airtime_ms"], cast=float, default=0.0)
        retx_ms    = _first_present(stats, ["ExtraAirtime_ms_Retransmissions", "RetransmissionAirTime_ms", "Retx_Airtime_ms"], cast=float, default=0.0)

        dl_sent    = _first_present(stats, ["TotalDownlinksSent", "DownlinksSent", "DL_Sent"], cast=int, default=0)
        dl_recv    = _first_present(stats, ["TotalDownlinksReceived", "DownlinksReceived", "DL_Received"], cast=int, default=0)
        acks       = _first_present(stats, ["TotalACKs", "ACKsReceived", "DL_ACKs"], cast=int, default=0)
        ack_to     = _first_present(stats, ["TotalACKTimeouts", "ACKTimeouts", "ACK_Miss"], cast=int, default=0)

        # Per-node concat (if available)
        if isinstance(per_node, pd.DataFrame) and not per_node.empty:
            pn = per_node.copy()
            pn["Configuration"] = label
            per_node_all.append(pn)

        rows.append({
            "Configuration": label,
            "Total Sent": total_sent,
            "Total Received": total_recv,
            "Overall PDR (%)": pdr_pct,
            "Total Retransmissions": total_retx,
            "Retransmission Rate (%)": retx_rate,
            "Uplink Airtime (s)": ul_air_ms / 1000.0,
            "Retransmission Airtime (s)": retx_ms / 1000.0,
            "Total Airtime (s)": (ul_air_ms + retx_ms) / 1000.0,
            "Downlinks Sent": dl_sent,
            "Downlinks Received": dl_recv,
            "ACKs": acks,
            "ACK Timeouts": ack_to,
            # Handy flags showing if fields were missing
            "_has_airtime": (ul_air_ms > 0 or retx_ms > 0),
            "_has_downlinks": (dl_sent > 0 or dl_recv > 0 or acks > 0 or ack_to > 0),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        order = ["Unconfirmed", "Confirmed"]
        df["Configuration"] = pd.Categorical(df["Configuration"], categories=order, ordered=True)
        df = df.sort_values("Configuration").set_index("Configuration")

    per_node_concat = pd.concat(per_node_all, ignore_index=True) if per_node_all else pd.DataFrame()
    return df, per_node_concat

def plot_scenario_comparison(summary_df: pd.DataFrame) -> None:
    """2x2 figure: PDR, Airtime components, Retransmissions, Downlinks."""
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle("Scenario 04: Confirmed vs Unconfirmed Message Analysis", fontsize=20, weight="bold")

    df = summary_df.reset_index()

    # (0,0) PDR
    ax = axes[0, 0]
    sns.barplot(data=df, x="Configuration", y="Overall PDR (%)",
                hue="Configuration", legend=False, palette="viridis", ax=ax)
    ax.set_title("Message Reliability (PDR)", fontsize=14, weight="bold")
    ax.set_xlabel("")
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{h:.2f}", (p.get_x()+p.get_width()/2., h), ha="center", va="center",
                        xytext=(0,5), textcoords="offset points", weight="bold")

    # (0,1) Airtime components
    ax = axes[0, 1]
    airtime_long = df.melt(id_vars=["Configuration"],
                           value_vars=["Uplink Airtime (s)", "Retransmission Airtime (s)"],
                           var_name="Component", value_name="Seconds")
    sns.barplot(data=airtime_long, x="Configuration", y="Seconds",
                hue="Component", palette="plasma", ax=ax)
    ax.set_title("Network Efficiency (Airtime Components)", fontsize=14, weight="bold")
    ax.set_xlabel("")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.1f", padding=3, weight="bold")

    # (1,0) Retransmissions
    ax = axes[1, 0]
    sns.barplot(data=df, x="Configuration", y="Total Retransmissions",
                hue="Configuration", legend=False, palette="magma", ax=ax)
    ax.set_title("Retransmission Overhead", fontsize=14, weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Retransmitted Uplinks (count)")
    for i, p in enumerate(ax.patches):
        h = p.get_height()
        if pd.notna(h):
            cfg = df.loc[i, "Configuration"]
            rate = df.loc[df["Configuration"] == cfg, "Retransmission Rate (%)"].values[0]
            ax.annotate(f"{int(h)} ({rate:.2f}%)", (p.get_x()+p.get_width()/2., h),
                        ha="center", va="center", xytext=(0,6),
                        textcoords="offset points", weight="bold")

    # (1,1) Downlinks
    ax = axes[1, 1]
    dl_long = df.melt(id_vars=["Configuration"],
                      value_vars=["Downlinks Sent", "Downlinks Received"],
                      var_name="Downlink Metric", value_name="Count")
    sns.barplot(data=dl_long, x="Configuration", y="Count",
                hue="Downlink Metric", palette="cividis", ax=ax)
    ax.set_title("Downlink Traffic Overhead (ACKs)", fontsize=14, weight="bold")
    ax.set_xlabel("")
    ax.set_ylabel("Packets")
    for container in ax.containers:
        ax.bar_label(container, fmt="%.0f", padding=3, weight="bold")

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(FIG_PNG, dpi=300)
    print(f"✅ Visualizations saved: {FIG_PNG}")

def main():
    print("🔬 Scenario 04: Confirmed vs Unconfirmed — Analysis")
    if not os.path.isdir(SCENARIO_04_OUTPUT_DIR):
        print(f"❌ Directory not found: {SCENARIO_04_OUTPUT_DIR}")
        print("   Run './run-04.sh' first to generate results.")
        return

    analyzer = NS3LoRaWANAnalyzer(csv_directory=SCENARIO_04_OUTPUT_DIR)
    analyzer.analyze_all_csv_files_recursive(GLOB_PATTERN)

    if not analyzer.scenarios_data:
        print("❌ No CSVs found. Check the path and naming (*results.csv).")
        return

    summary_df, per_node_concat = create_summary_dataframe(analyzer)

    # Show if fields were missing
    if "_has_airtime" in summary_df.columns and not summary_df["_has_airtime"].any():
        print("⚠️  No airtime fields found in CSVs. Fields expected like: "
              "'TotalAirTime_ms' and 'ExtraAirtime_ms_Retransmissions'.")
    if "_has_downlinks" in summary_df.columns and not summary_df["_has_downlinks"].any():
        print("⚠️  No downlink/ACK fields found in CSVs. Fields expected like: "
              "'TotalDownlinksSent', 'TotalDownlinksReceived', 'TotalACKs', 'TotalACKTimeouts'.")

    # Pretty print
    print("\n📊 Summary:")
    print("-" * 110)
    with pd.option_context("display.float_format", lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)):
        print(summary_df.drop(columns=[c for c in summary_df.columns if c.startswith("_")]).to_string())
    print("-" * 110)

    # Save CSVs
    summary_df.drop(columns=[c for c in summary_df.columns if c.startswith("_")], errors="ignore").to_csv(SUMMARY_CSV, index=True)
    print(f"💾 Summary saved: {SUMMARY_CSV}")
    if not per_node_concat.empty:
        per_node_concat.to_csv(PER_NODE_CSV, index=False)
        print(f"💾 Per-node data saved: {PER_NODE_CSV}")

    # Plots
    try:
        plot_scenario_comparison(summary_df.drop(columns=[c for c in summary_df.columns if c.startswith("_")], errors="ignore"))
    except Exception as e:
        print(f"⚠️ Plotting skipped due to error: {e}")

    print("🎉 Analysis complete.")

if __name__ == "__main__":
    main()
