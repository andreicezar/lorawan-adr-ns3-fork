"""
Scenario 06 analyzer: Collision & Capture Effect (SF7..SF12)

Outputs:
  - scenario_06_summary.csv   (one row per SF)
  - scenario_06_per_node.csv  (all nodes with SF & cohort)
  - scenario_06_analysis.png  (2x2 figure)
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
    print("❌ Missing dependency: ns3_lorawan_parser (NS3LoRaWANAnalyzer). Put it on PYTHONPATH.")
    raise

# --- CONFIG ---
SCENARIO_06_OUTPUT_DIR = "./output/scenario-06-collision-capture"
GLOB_PATTERN = "*results.csv"
SUMMARY_CSV = "scenario_06_summary.csv"
PER_NODE_CSV = "scenario_06_per_node.csv"
FIG_PNG = "scenario_06_analysis.png"


# ---------- helpers ----------
def _first_present(d: dict, names: list, cast=float, default=0.0):
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
    Aggregates key metrics from all SF sub-scenarios into a single DataFrame.
    Also returns a concatenated per-node DataFrame (if available).
    """
    rows, per_node_all = [], []

    for key, data in sorted(analyzer.scenarios_data.items()):
        stats = data.get("overall_stats", {}) or {}
        per_node = data.get("per_node_data", None)

        sf = int(_first_present(stats, ["SpreadingFactor", "SF"], int, 0))

        total_sent = int(_first_present(stats, ["TotalSent", "UL_Sent"], int, 0))
        total_recv = int(_first_present(stats, ["TotalReceived", "UL_Received"], int, 0))
        pdr_pct = float(_first_present(stats, ["PDR_Percent", "PDR(%)", "PDR"], float,
                                       (100.0 * total_recv / total_sent if total_sent else 0.0)))
        drops = int(_first_present(stats, ["PacketsDropped_SentMinusReceived", "Drops"], int,
                                   max(0, total_sent - total_recv)))
        drop_rate = float(_first_present(stats, ["DropRate_Percent", "DropRate(%)"], float,
                                         (100.0 * drops / total_sent if total_sent else 0.0)))

        # Capture section (overall)
        near_sent = int(_first_present(stats, ["NearCohortSent"], int, 0))
        near_recv = int(_first_present(stats, ["NearCohortReceived"], int, 0))
        near_pdr = float(_first_present(stats, ["NearCohortPDR_Percent"], float,
                                        (100.0 * near_recv / near_sent if near_sent else 0.0)))
        far_sent = int(_first_present(stats, ["FarCohortSent"], int, 0))
        far_recv = int(_first_present(stats, ["FarCohortReceived"], int, 0))
        far_pdr = float(_first_present(stats, ["FarCohortPDR_Percent"], float,
                                       (100.0 * far_recv / far_sent if far_sent else 0.0)))
        capture_delta = float(_first_present(stats, ["CaptureEffectStrength_PDR_Delta"], float,
                                             (near_pdr - far_pdr)))

        # From per-node (if available)
        total_collisions = None
        mean_dist_near = mean_dist_far = None
        mean_rssi_near = mean_rssi_far = None

        if isinstance(per_node, pd.DataFrame) and not per_node.empty:
            pn = per_node.copy()
            pn["Spreading Factor"] = sf
            per_node_all.append(pn)

            if "Collisions" in pn.columns:
                total_collisions = pd.to_numeric(pn["Collisions"], errors="coerce").fillna(0).sum()

            # Cohort stats from per-node (nice-to-have, doesn’t affect plots if absent)
            if "Cohort" in pn.columns:
                if "Distance_m" in pn.columns:
                    near_mask = pn["Cohort"].str.upper() == "NEAR"
                    far_mask = pn["Cohort"].str.upper() == "FAR"
                    mean_dist_near = pd.to_numeric(pn.loc[near_mask, "Distance_m"], errors="coerce").mean()
                    mean_dist_far = pd.to_numeric(pn.loc[far_mask, "Distance_m"], errors="coerce").mean()
                if "EstimatedRSSI_dBm" in pn.columns:
                    near_mask = pn["Cohort"].str.upper() == "NEAR"
                    far_mask = pn["Cohort"].str.upper() == "FAR"
                    mean_rssi_near = pd.to_numeric(pn.loc[near_mask, "EstimatedRSSI_dBm"], errors="coerce").mean()
                    mean_rssi_far = pd.to_numeric(pn.loc[far_mask, "EstimatedRSSI_dBm"], errors="coerce").mean()

        # Fallback: if no per-node collisions, use drops
        if total_collisions is None:
            total_collisions = drops
        collision_rate = (100.0 * total_collisions / total_sent) if total_sent else 0.0

        rows.append({
            "Spreading Factor": sf,
            "Total Sent": total_sent,
            "Total Received": total_recv,
            "Overall PDR (%)": pdr_pct,
            "Packets Dropped": drops,
            "Drop Rate (%)": drop_rate,
            "Total Collisions": int(total_collisions),
            "Collision Rate (%)": collision_rate,
            "Near Cohort Sent": near_sent,
            "Near Cohort Received": near_recv,
            "Near Cohort PDR (%)": near_pdr,
            "Far Cohort Sent": far_sent,
            "Far Cohort Received": far_recv,
            "Far Cohort PDR (%)": far_pdr,
            "Capture Effect Strength (%)": capture_delta,
            "Mean Distance NEAR (m)": mean_dist_near,
            "Mean Distance FAR (m)": mean_dist_far,
            "Mean Est RSSI NEAR (dBm)": mean_rssi_near,
            "Mean Est RSSI FAR (dBm)": mean_rssi_far,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by="Spreading Factor").set_index("Spreading Factor")

    per_node_concat = pd.concat(per_node_all, ignore_index=True) if per_node_all else pd.DataFrame()
    return df, per_node_concat


# ---------- plots ----------
def plot_scenario_comparison(summary_df: pd.DataFrame) -> None:
    """
    2x2 figure:
      (0,0) Cohort PDR (near vs far)
      (0,1) Capture effect (near - far) as bar
      (1,0) Total collisions (annotated with rate %)
      (1,1) Overall PDR
    """
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle("Scenario 06: Collision & Capture Effect Analysis", fontsize=20, weight="bold")

    sf = summary_df.index.values

    # --- (0,0) Cohort PDR ---
    ax = axes[0, 0]
    sns.lineplot(x=sf, y=summary_df["Near Cohort PDR (%)"], marker="o", linewidth=2.5, ax=ax, label="Near")
    sns.lineplot(x=sf, y=summary_df["Far Cohort PDR (%)"], marker="s", linewidth=2.5, ax=ax, label="Far")
    ax.set_title("PDR by Cohort", fontsize=14, weight="bold")
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("PDR (%)")
    ax.legend(title="Cohort")
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    for x, y in zip(sf, summary_df["Near Cohort PDR (%)"]):
        if pd.notna(y): ax.annotate(f"{y:.1f}", (x, y), xytext=(0, 6), textcoords="offset points", ha="center", weight="bold")
    for x, y in zip(sf, summary_df["Far Cohort PDR (%)"]):
        if pd.notna(y): ax.annotate(f"{y:.1f}", (x, y), xytext=(0, 6), textcoords="offset points", ha="center", weight="bold")

    # --- (0,1) Capture effect strength ---
    ax = axes[0, 1]
    df_cap = summary_df.reset_index()
    sns.barplot(data=df_cap, x="Spreading Factor", y="Capture Effect Strength (%)",
                hue="Spreading Factor", legend=False, palette="viridis", ax=ax)
    ax.set_title("Capture Effect Strength (Near − Far PDR)", fontsize=14, weight="bold")
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("PDR Δ (pp)")
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{h:.2f}", (p.get_x() + p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 5), textcoords="offset points", weight="bold")

    # --- (1,0) Total collisions ---
    ax = axes[1, 0]
    sns.barplot(data=df_cap, x="Spreading Factor", y="Total Collisions",
                hue="Spreading Factor", legend=False, palette="plasma", ax=ax)
    ax.set_title("Total Packet Collisions", fontsize=14, weight="bold")
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("Collisions (count)")
    # annotate with count + collision rate
    for i, p in enumerate(ax.patches):
        h = p.get_height()
        if pd.notna(h):
            sf_val = int(df_cap.loc[i, "Spreading Factor"])
            rate = summary_df.loc[sf_val, "Collision Rate (%)"]
            ax.annotate(f"{int(h)} ({rate:.1f}%)", (p.get_x()+p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 6), textcoords="offset points", weight="bold")

    # --- (1,1) Overall PDR ---
    ax = axes[1, 1]
    sns.lineplot(x=sf, y=summary_df["Overall PDR (%)"], marker="d", linewidth=2.5, ax=ax, color="crimson")
    ax.set_title("Overall Network PDR", fontsize=14, weight="bold")
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("PDR (%)")
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    for x, y in zip(sf, summary_df["Overall PDR (%)"]):
        if pd.notna(y): ax.annotate(f"{y:.1f}", (x, y), xytext=(0, 6), textcoords="offset points", ha="center", weight="bold")

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(FIG_PNG, dpi=300)
    print(f"✅ Visualizations saved: {FIG_PNG}")


# ---------- main ----------
def main():
    print("🔬 Scenario 06: Collision & Capture Effect — Analysis")
    if not os.path.isdir(SCENARIO_06_OUTPUT_DIR):
        print(f"❌ Directory not found: {SCENARIO_06_OUTPUT_DIR}")
        print("   Run './run-06.sh' first to generate results.")
        return

    analyzer = NS3LoRaWANAnalyzer(csv_directory=SCENARIO_06_OUTPUT_DIR)
    analyzer.analyze_all_csv_files_recursive(GLOB_PATTERN)

    if not analyzer.scenarios_data:
        print("❌ No CSVs found. Check the path and naming (*results.csv).")
        return

    summary_df, per_node_concat = create_summary_dataframe(analyzer)

    print("\n📊 Scenario 06 Summary (by Spreading Factor):")
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
