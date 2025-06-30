import pandas as pd
import matplotlib.pyplot as plt
import re
import sys
import os
import argparse

# --- File Parsing Functions ---
def parse_global_performance(filepath):
    """Parses globalPerformance.txt"""
    data = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                match = re.match(r'\+(\d+\.?\d*)s\s+(\d+\.?\d*)\s+(\d+\.?\d*)', line.strip())
                if match:
                    time_s, sent, received = [float(g) for g in match.groups()]
                    pdr = received / sent if sent > 0 else 0
                    data.append({'Time_s': time_s, 'PDR': pdr, 'PacketsSent': sent, 'PacketsReceived': received})
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
    return pd.DataFrame(data)

def parse_node_data(filepath):
    """Parses nodeData.txt"""
    data = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                match = re.match(r'\+(\d+\.?\d*)s\s+(\d+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(\d+)\s+(\d+)', line.strip())
                if match:
                    data.append({'Time_s': float(match.group(1)), 'DeviceId': int(match.group(2)), 'DR': int(match.group(5)), 'TX_Power': int(match.group(6))})
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
    return pd.DataFrame(data)

def parse_phy_performance(filepath):
    """Parses phyPerformance.txt"""
    data = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                match = re.match(r'\+(\d+\.?\d*)s\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', line.strip())
                if match:
                    data.append({'Time_s': float(match.group(1)), 'GatewayId': int(match.group(2)), 'TotalSentInInterval': int(match.group(3)), 'Received': int(match.group(4)), 'Interfered': int(match.group(5)), 'NoMoreReceivers': int(match.group(6)), 'UnderSensitivity': int(match.group(7)), 'LostBecauseTx': int(match.group(8))})
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
    return pd.DataFrame(data)

def parse_tx_info(filepath):
    """
    Parses txInfo.txt and calculates total transmissions from AvgTxPerPkt.
    """
    data = []
    try:
        with open(filepath, 'r') as f:
            next(f, None)  # Skip header
            for line in f:
                # This regex now ignores the histogram, as it's not needed.
                match = re.search(r'(\d+)\s+ConfirmedPkts:(\d+)\s+SuccessfulPkts:(\d+)\s+FailedPkts:(\d+)\s+AvgTxPerPkt:([\d\.]+)', line)
                if match:
                    confirmed_pkts = int(match.group(2))
                    avg_tx = float(match.group(5))
                    
                    # Calculate total transmissions directly. It's more robust.
                    # Since ConfirmedPkts is 1, TotalTx is just the rounded AvgTx.
                    total_tx_in_interval = round(avg_tx * confirmed_pkts)
                    
                    data.append({
                        'Time_s': int(match.group(1)),
                        'ConfirmedPkts': confirmed_pkts,
                        'SuccessfulPkts': int(match.group(3)),
                        'FailedPkts': int(match.group(4)),
                        'AvgTxPerPkt': avg_tx,
                        'TotalTxInInterval': total_tx_in_interval
                    })
    except FileNotFoundError:
        print(f"Warning: File not found: {filepath}")
    return pd.DataFrame(data)

def calculate_and_print_kpis(df_tx, df_node, payload_size):
    """
    Calculates and prints key performance indicators (KPIs) for the ADR performance.
    """
    if df_tx.empty:
        print("\nKPI Report could not be generated: No transmission data available.")
        return

    # --- Reliability Metrics ---
    total_confirmed = df_tx['ConfirmedPkts'].sum()
    total_successful = df_tx['SuccessfulPkts'].sum()
    total_failed = df_tx['FailedPkts'].sum()
    
    packet_success_rate = (total_successful / total_confirmed) * 100 if total_confirmed > 0 else 0
    packet_error_rate = (total_failed / total_confirmed) * 100 if total_confirmed > 0 else 0

    # --- Efficiency Metrics ---
    total_transmissions = df_tx['TotalTxInInterval'].sum()
    avg_transmissions = total_transmissions / total_confirmed if total_confirmed > 0 else 0

    # --- Throughput Metrics ---
    total_simulation_time = df_node['Time_s'].max() if not df_node.empty else df_tx['Time_s'].max()
    total_bits_extracted = total_successful * payload_size * 8
    data_extraction_rate = total_bits_extracted / total_simulation_time if total_simulation_time > 0 else 0

    # --- Final ADR State ---
    final_dr = "N/A"
    final_power = "N/A"
    if not df_node.empty:
        final_state = df_node.iloc[-1]
        final_dr = final_state['DR']
        final_power = final_state['TX_Power']

    # --- Print Report ---
    print("\n" + "="*50)
    print(" ADR Performance Analysis Report")
    print("="*50)
    print(f"\n[Simulation Overview]")
    print(f"  Total Simulation Time:      {total_simulation_time:.2f} s")
    print(f"  Final Device State:         DR{final_dr}, {final_power} dBm")
    
    print(f"\n[Reliability Metrics]")
    print(f"  Total Confirmed Packets:    {total_confirmed}")
    print(f"  - Successful Packets:       {total_successful}")
    print(f"  - Failed Packets:           {total_failed}")
    print(f"  Packet Success Rate (PSR):  {packet_success_rate:.2f}%")
    print(f"  Packet Error Rate (PER):    {packet_error_rate:.2f}%")

    print(f"\n[Efficiency & Throughput]")
    print(f"  Total Transmissions:        {total_transmissions}")
    print(f"  Avg. Transmissions/Packet:  {avg_transmissions:.3f}")
    print(f"  Data Extraction Rate (DER): {data_extraction_rate:.2f} bps")
    print("="*50)


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Analyze NS-3 LoRaWAN simulation output.")
    parser.add_argument("main_log", help="Path to the main simulation log (e.g., complete_simulation.log)")
    parser.add_argument("global_perf", help="Path to globalPerformance.txt")
    parser.add_argument("node_data", help="Path to nodeData.txt")
    parser.add_argument("phy_perf", help="Path to phyPerformance.txt")
    parser.add_argument("tx_info", help="Path to txInfo.txt")
    parser.add_argument("--payload-size", type=int, default=20, help="Payload size in bytes used in the simulation.")
    parser.add_argument("--no-plots", action="store_true", help="Suppress plot generation.")

    args = parser.parse_args()
    
    print("Starting analysis on files...")

    # Parse all log files
    df_global = parse_global_performance(args.global_perf)
    df_node = parse_node_data(args.node_data)
    df_phy = parse_phy_performance(args.phy_perf)
    df_tx = parse_tx_info(args.tx_info)
    
    # Calculate and Print KPIs
    calculate_and_print_kpis(df_tx, df_node, args.payload_size)

    if not args.no_plots:
        print("\nPlot generation is enabled. You can add plotting function calls here if needed.")
    else:
        print("\nPlot generation suppressed by --no-plots flag.")

    print("\nAnalysis complete.")

if __name__ == "__main__":
    main()