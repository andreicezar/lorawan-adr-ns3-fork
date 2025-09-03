"""
Scenario 08 analyzer: Multi-Gateway Coordination (1 / 2 / 4 GWs)

Outputs:
  - scenario_08_summary.csv        (one row per number of gateways)
  - scenario_08_per_gateway.csv    (all gateway rows across runs)
  - scenario_08_per_node.csv       (all node rows across runs)
  - scenario_08_analysis.png       (2x2 figure: Unique PDR, Hearings/UL, Dedup %, Load variance)
  - scenario_08_load_balance.png   (per-gateway load% distributions; if gateway table present)
  - scenario_08_ownership.png      (owner-GW distribution; if per-node table present)
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
    print("❌ Missing dependency: ns3_lorawan_parser (NS3LoRaWANAnalyzer). Make sure it's on PYTHONPATH.")
    raise

# --- CONFIG ---
SCENARIO_08_OUTPUT_DIR = "./output/scenario-08-multi-gateway"
GLOB_PATTERN = "*results.csv"

SUMMARY_CSV = "scenario_08_summary.csv"
PER_GATEWAY_CSV = "scenario_08_per_gateway.csv"
PER_NODE_CSV = "scenario_08_per_node.csv"

MAIN_FIG = "scenario_08_analysis.png"
LOAD_BALANCE_FIG = "scenario_08_load_balance.png"
OWNERSHIP_FIG = "scenario_08_ownership.png"


# ---------- helpers ----------
def _first_present(d: dict, names: list, cast=float, default=0.0):
    """Return first present key from names in dict d, cast to type; else default."""
    for n in names:
        if n in d and d[n] not in (None, "", "N/A"):
            try:
                return cast(d[n])
            except Exception:
                pass
    return default


# ---------- aggregation ----------
def create_summary_dataframe(analyzer: NS3LoRaWANAnalyzer) -> pd.DataFrame:
    """
    Aggregates key metrics from all sub-scenarios into a single DataFrame,
    indexed by number of gateways.
    """
    rows = []
    for key, data in sorted(analyzer.scenarios_data.items()):
        stats = data.get("overall_stats", {}) or {}

        n_gw      = int(_first_present(stats, ["NumberOfGateways"], int, 0))
        total_tx  = int(_first_present(stats, ["TotalSent"], int, 0))
        total_raw = int(_first_present(stats, ["TotalRawHearings"], int, 0))
        unique    = int(_first_present(stats, ["UniquePackets"], int, 0))
        dups      = int(_first_present(stats, ["DuplicatePackets"], int, 0))

        unique_pdr = float(_first_present(stats, ["UniquePDR_Percent"], float,
                                          (100.0 * unique / total_tx if total_tx else 0.0)))
        raw_rate   = float(_first_present(stats, ["RawHearingsRate_Percent"], float,
                                          (100.0 * total_raw / total_tx if total_tx else 0.0)))
        dedup_pct  = float(_first_present(stats, ["DeduplicationRate_Percent"], float,
                                          (100.0 * dups / total_raw if total_raw else 0.0)))
        hearings_ul= float(_first_present(stats, ["AvgHearingsPerUplink"], float,
                                          (float(total_raw) / total_tx if total_tx else 0.0)))
        load_var   = float(_first_present(stats, ["GatewayLoadVariance"], float, 0.0))

        rows.append({
            "Gateways": n_gw,
            "Total Sent": total_tx,
            "Total Raw Hearings": total_raw,
            "Unique Packets": unique,
            "Duplicate Packets": dups,
            "Unique PDR (%)": unique_pdr,
            "Raw Hearings Rate (%)": raw_rate,
            "Avg Hearings Per Uplink": hearings_ul,
            "Deduplication Rate (%)": dedup_pct,
            "Gateway Load Variance": load_var,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by="Gateways").set_index("Gateways")
    return df


def collect_per_gateway(analyzer: NS3LoRaWANAnalyzer) -> pd.DataFrame:
    """
    Collects per-gateway table across runs, if present.
    Expects columns like: GatewayID, RawHearings, LoadPercentage, Position_X, Position_Y.
    Adds a 'Gateways' column from OVERALL stats for grouping.
    """
    all_rows = []
    for key, data in analyzer.scenarios_data.items():
        stats = data.get("overall_stats", {}) or {}
        n_gw = int(_first_present(stats, ["NumberOfGateways"], int, 0))

        # Try multiple keys for the per-gateway DataFrame
        pg = (data.get("per_gateway_data") or
              data.get("per_gateway_stats") or
              data.get("gateway_stats") or
              None)

        if isinstance(pg, pd.DataFrame) and not pg.empty:
            df = pg.copy()
            df["Gateways"] = n_gw

            # Normalize expected columns
            rename_map = {
                "LoadPercentage": "Load_Percentage",
                "Position_X": "PosX",
                "Position_Y": "PosY",
            }
            df = df.rename(columns=rename_map)

            # Coerce numeric
            for c in ["GatewayID", "RawHearings", "Load_Percentage", "PosX", "PosY", "Gateways"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            all_rows.append(df)

    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


def collect_per_node(analyzer: NS3LoRaWANAnalyzer) -> pd.DataFrame:
    """
    Collects per-node table across runs, if present.
    Expects columns like: NodeID, Sent, RawHearings, UniqueReceived, UniquePDR_Percent,
                          OwnerGatewayIdx, GatewayDistributionUnique.
    Adds a 'Gateways' column from OVERALL stats for grouping.
    """
    all_rows = []
    for key, data in analyzer.scenarios_data.items():
        stats = data.get("overall_stats", {}) or {}
        n_gw = int(_first_present(stats, ["NumberOfGateways"], int, 0))

        pn = data.get("per_node_data", None)
        if isinstance(pn, pd.DataFrame) and not pn.empty:
            df = pn.copy()
            df["Gateways"] = n_gw

            # Normalize expected columns
            rename_map = {
                "UniquePDR_Percent": "Unique_PDR_Percent",
                "OwnerGatewayIdx": "OwnerGW_Idx",
                "GatewayDistributionUnique": "GW_Distribution_Unique",
            }
            df = df.rename(columns=rename_map)

            # Coerce numeric for common columns
            for c in ["NodeID", "Sent", "RawHearings", "UniqueReceived", "Unique_PDR_Percent", "OwnerGW_Idx", "Gateways"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            all_rows.append(df)

    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


# ---------- plots ----------
def plot_main(summary_df: pd.DataFrame) -> None:
    """Main 2x2 figure: Unique PDR / Hearings per UL / Dedup % / Load variance."""
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(18, 14))
    fig.suptitle("Scenario 08: Multi-Gateway Performance Analysis", fontsize=20, weight="bold")

    df = summary_df.reset_index()  # exposes "Gateways" as a column

    # (0,0) Unique PDR
    ax = axes[0, 0]
    sns.barplot(
        data=df, x="Gateways", y="Unique PDR (%)",
        hue="Gateways", legend=False, palette="viridis", ax=ax
    )
    ax.set_title("Network Reliability (Unique PDR)", fontsize=14, weight="bold")
    ax.set_xlabel("Number of Gateways")
    ax.set_ylabel("Unique PDR (%)")
    low = max(0, float(df["Unique PDR (%)"].min()) - 5.0)
    ax.set_ylim(low, 100)
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{h:.2f}", (p.get_x() + p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 5),
                        textcoords="offset points", weight="bold")

    # (0,1) Avg hearings per UL
    ax = axes[0, 1]
    sns.barplot(
        data=df, x="Gateways", y="Avg Hearings Per Uplink",
        hue="Gateways", legend=False, palette="plasma", ax=ax
    )
    ax.set_title("Spatial Diversity (Avg Hearings per Uplink)", fontsize=14, weight="bold")
    ax.set_xlabel("Number of Gateways")
    ax.set_ylabel("Avg Hearings per Uplink")
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{h:.2f}", (p.get_x() + p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 5),
                        textcoords="offset points", weight="bold")

    # (1,0) Deduplication rate
    ax = axes[1, 0]
    sns.barplot(
        data=df, x="Gateways", y="Deduplication Rate (%)",
        hue="Gateways", legend=False, palette="magma", ax=ax
    )
    ax.set_title("Duplicate Message Rate (Deduplicated)", fontsize=14, weight="bold")
    ax.set_xlabel("Number of Gateways")
    ax.set_ylabel("Deduplication Rate (%)")
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{h:.2f}", (p.get_x() + p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 5),
                        textcoords="offset points", weight="bold")

    # (1,1) Gateway load variance
    ax = axes[1, 1]
    sns.barplot(
        data=df, x="Gateways", y="Gateway Load Variance",
        hue="Gateways", legend=False, palette="cividis", ax=ax
    )
    ax.set_title("Gateway Load Balancing (Lower is Better)", fontsize=14, weight="bold")
    ax.set_xlabel("Number of Gateways")
    ax.set_ylabel("Variance of Raw Hearings")
    for p in ax.patches:
        h = p.get_height()
        if pd.notna(h):
            ax.annotate(f"{h:.2f}", (p.get_x() + p.get_width()/2., h),
                        ha="center", va="center", xytext=(0, 5),
                        textcoords="offset points", weight="bold")

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])
    plt.savefig(MAIN_FIG, dpi=300)
    print(f"✅ Visualizations saved: {MAIN_FIG}")


def plot_load_balance(per_gateway_df: pd.DataFrame) -> None:
    """Optional figure: per-gateway load share distributions (box/strip) by # gateways."""
    if per_gateway_df.empty or "Load_Percentage" not in per_gateway_df.columns:
        return

    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.boxplot(
        data=per_gateway_df, x="Gateways", y="Load_Percentage",
        palette="Blues", ax=ax
    )
    sns.stripplot(
        data=per_gateway_df, x="Gateways", y="Load_Percentage",
        color="black", alpha=0.5, jitter=True, ax=ax
    )
    ax.set_title("Gateway Load Share Distribution by Run", fontsize=16, weight="bold")
    ax.set_xlabel("Number of Gateways")
    ax.set_ylabel("Load Percentage (%)")
    plt.tight_layout()
    plt.savefig(LOAD_BALANCE_FIG, dpi=300)
    print(f"✅ Load balance visualization saved: {LOAD_BALANCE_FIG}")


def plot_ownership(per_node_df: pd.DataFrame) -> None:
    """Optional figure: owner-gateway share per # gateways (stacked bar of counts by OwnerGW_Idx)."""
    if per_node_df.empty or "OwnerGW_Idx" not in per_node_df.columns:
        return

    # Count nodes by owner index per number of gateways
    counts = (per_node_df
              .dropna(subset=["OwnerGW_Idx", "Gateways"])
              .assign(OwnerGW_Idx=lambda d: d["OwnerGW_Idx"].astype(int))
              .groupby(["Gateways", "OwnerGW_Idx"])
              .size()
              .reset_index(name="Count"))

    if counts.empty:
        return

    # Pivot to stacked bar format
    pivot = counts.pivot(index="Gateways", columns="OwnerGW_Idx", values="Count").fillna(0).astype(int)
    pivot = pivot.sort_index()

    sns.set_theme(style="whitegrid")
    ax = pivot.plot(
        kind="bar",
        stacked=True,
        figsize=(14, 7),
        colormap="tab20"
    )
    ax.set_title("Owner Gateway Distribution (per run)", fontsize=16, weight="bold")
    ax.set_xlabel("Number of Gateways")
    ax.set_ylabel("Node Count")
    plt.legend(title="OwnerGW_Idx", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.savefig(OWNERSHIP_FIG, dpi=300)
    print(f"✅ Ownership visualization saved: {OWNERSHIP_FIG}")


# ---------- main ----------
def main():
    print("🔬 Scenario 08: Multi-Gateway Coordination — Analysis")
    if not os.path.isdir(SCENARIO_08_OUTPUT_DIR):
        print(f"❌ Directory not found: {SCENARIO_08_OUTPUT_DIR}")
        print("   Run './run-08.sh' first to generate results.")
        return

    analyzer = NS3LoRaWANAnalyzer(csv_directory=SCENARIO_08_OUTPUT_DIR)
    analyzer.analyze_all_csv_files_recursive(GLOB_PATTERN)

    if not analyzer.scenarios_data:
        print("❌ No CSVs found. Check the path and naming (*results.csv).")
        return

    # Summary & tables
    summary_df = create_summary_dataframe(analyzer)
    per_gateway_df = collect_per_gateway(analyzer)
    per_node_df = collect_per_node(analyzer)

    # Console preview
    print("\n📊 Scenario 08 Summary:")
    print("-" * 110)
    with pd.option_context("display.float_format", lambda x: f"{x:.2f}" if isinstance(x, float) else str(x)):
        print(summary_df.to_string())
    print("-" * 110)

    # Save CSVs
    summary_df.to_csv(SUMMARY_CSV, index=True)
    print(f"💾 Summary saved: {SUMMARY_CSV}")
    if not per_gateway_df.empty:
        per_gateway_df.to_csv(PER_GATEWAY_CSV, index=False)
        print(f"💾 Per-gateway data saved: {PER_GATEWAY_CSV}")
    if not per_node_df.empty:
        per_node_df.to_csv(PER_NODE_CSV, index=False)
        print(f"💾 Per-node data saved: {PER_NODE_CSV}")

    # Plots
    try:
        plot_main(summary_df)
        plot_load_balance(per_gateway_df)
        plot_ownership(per_node_df)
    except Exception as e:
        print(f"⚠️ Plotting skipped due to error: {e}")

    print("🎉 Analysis complete.")


if __name__ == "__main__":
    main()
