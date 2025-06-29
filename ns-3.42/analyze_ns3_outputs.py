import pandas as pd
import matplotlib.pyplot as plt
import re
import sys
from collections import defaultdict

# --- File Parsing Functions ---

def parse_global_performance(filepath):
    """
    Parses the globalPerformance.txt file into a pandas DataFrame.
    Expected format: "+<time>s <PDR> <EnergyEfficiency>"
    Example: "+0s 0.000000 0.000000"
    """
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line: # Skip empty lines
                continue
            # Regex to match time (e.g., +123s or +123.45s) and two float values
            match = re.match(r'\+(\d+\.?\d*)s (\d+\.?\d*) (\d+\.?\d*)', line)
            if match:
                time_s = float(match.group(1))
                pdr = float(match.group(2))
                energy_efficiency = float(match.group(3))
                data.append({'Time_s': time_s, 'PDR': pdr, 'EnergyEfficiency': energy_efficiency})
    return pd.DataFrame(data)

def parse_node_data(filepath):
    """
    Parses the nodeData.txt file into a pandas DataFrame.
    Expected format: "+<time>s <DeviceId> <X-coord> <Y-coord> <DR> <TXPower>"
    Example: "+0s 8 866.401 -558.515 5 14"
    """
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line: # Skip empty lines
                continue
            # Regex to match time, device ID, x, y coordinates, DR, and TX Power
            # Device ID can be any integer, coords floats, DR/TXPower integers
            match = re.match(r'\+(\d+\.?\d*)s (\d+) (\-?\d+\.?\d*) (\-?\d+\.?\d*) (\d+) (\d+)', line)
            if match:
                time_s = float(match.group(1))
                device_id = int(match.group(2))
                x_coord = float(match.group(3))
                y_coord = float(match.group(4))
                dr = int(match.group(5))
                tx_power = int(match.group(6))
                data.append({
                    'Time_s': time_s,
                    'DeviceId': device_id,
                    'X_Coord': x_coord,
                    'Y_Coord': y_coord,
                    'DR': dr,
                    'TX_Power': tx_power
                })
    return pd.DataFrame(data)

def parse_phy_performance(filepath):
    """
    Parses the phyPerformance.txt file into a pandas DataFrame.
    Expected format: "+<time>s <DeviceId> <PacketSent> <PacketReceived> <Collisions> <ChannelBusy> <RxWindowTooSoon> <RxWindowTooLate>"
    Example: "+0s 0 0 0 0 0 0 0"
    """
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line: # Skip empty lines
                continue
            # Regex to match time, device ID, and several integer performance counters
            match = re.match(r'\+(\d+\.?\d*)s (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)', line)
            if match:
                time_s = float(match.group(1))
                device_id = int(match.group(2))
                packet_sent = int(match.group(3))
                packet_received = int(match.group(4))
                collisions = int(match.group(5))
                channel_busy = int(match.group(6))
                rx_window_too_soon = int(match.group(7))
                rx_window_too_late = int(match.group(8))
                data.append({
                    'Time_s': time_s,
                    'DeviceId': device_id,
                    'PacketsSent': packet_sent,
                    'PacketsReceived': packet_received,
                    'Collisions': collisions,
                    'ChannelBusy': channel_busy,
                    'RxWindowTooSoon': rx_window_too_soon,
                    'RxWindowTooLate': rx_window_too_late
                })
    return pd.DataFrame(data)

# --- Analysis and Plotting Functions ---

def plot_global_performance(df_global):
    """
    Plots global PDR (Packet Delivery Ratio) and Energy Efficiency over time.
    """
    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Packet Delivery Ratio', color='tab:blue')
    ax1.plot(df_global['Time_s'], df_global['PDR'], color='tab:blue', label='Global PDR')
    ax1.tick_params(axis='y', labelcolor='tab:blue')
    ax1.set_title('Global Network Performance Over Time')
    ax1.grid(True, linestyle='--', alpha=0.6)

    ax2 = ax1.twinx()  # Create a second y-axis that shares the same x-axis
    ax2.set_ylabel('Energy Efficiency', color='tab:red')
    ax2.plot(df_global['Time_s'], df_global['EnergyEfficiency'], color='tab:red', label='Global Energy Efficiency')
    ax2.tick_params(axis='y', labelcolor='tab:red')

    # Combine legends from both axes
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper left', bbox_to_anchor=(0.1, 0.9))
    
    fig.tight_layout() # Adjust layout to prevent labels from overlapping
    plt.show()

def plot_device_adr_parameters(df_node):
    """
    Plots Data Rate (DR) and Transmit Power (TX_Power) for each unique device over time.
    Uses 'step' plot to show discrete changes.
    """
    unique_devices = df_node['DeviceId'].unique()
    for device_id in unique_devices:
        # Filter data for the current device and sort by time
        df_device = df_node[df_node['DeviceId'] == device_id].sort_values('Time_s')

        fig, ax1 = plt.subplots(figsize=(12, 6))
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Data Rate (DR)', color='tab:green')
        # Use 'step' plot to show changes as discrete steps, typical for DR/TX power
        ax1.step(df_device['Time_s'], df_device['DR'], where='post', color='tab:green', label='Data Rate')
        ax1.tick_params(axis='y', labelcolor='tab:green')
        ax1.set_title(f'Device {device_id} - ADR Parameters Over Time')
        ax1.grid(True, linestyle='--', alpha=0.6)

        ax2 = ax1.twinx() # Create a second y-axis for TX Power
        ax2.set_ylabel('TX Power (dBm)', color='tab:purple')
        ax2.step(df_device['Time_s'], df_device['TX_Power'], where='post', color='tab:purple', label='TX Power')
        ax2.tick_params(axis='y', labelcolor='tab:purple')

        # Combine legends
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines + lines2, labels + labels2, loc='upper left', bbox_to_anchor=(0.1, 0.9))

        fig.tight_layout()
        plt.show()

def plot_device_phy_performance(df_phy):
    """
    Plots physical layer performance metrics (Packets Sent, Received, Collisions)
    for each unique device over time.
    """
    unique_devices = df_phy['DeviceId'].unique()
    for device_id in unique_devices:
        # Filter data for the current device and sort by time
        df_device = df_phy[df_phy['DeviceId'] == device_id].sort_values('Time_s')

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.set_xlabel('Time (seconds)')
        ax.set_ylabel('Count')
        ax.plot(df_device['Time_s'], df_device['PacketsSent'], label='Packets Sent', marker='o', markersize=4, linestyle='-')
        ax.plot(df_device['Time_s'], df_device['PacketsReceived'], label='Packets Received', marker='x', markersize=4, linestyle='-')
        ax.plot(df_device['Time_s'], df_device['Collisions'], label='Collisions', marker='^', markersize=4, linestyle='-')
        
        ax.set_title(f'Device {device_id} - Physical Layer Performance Over Time')
        ax.grid(True, linestyle='--', alpha=0.6)
        ax.legend()
        plt.show()

# --- Main Execution ---

def main(global_perf_file, node_data_file, phy_perf_file):
    """
    Main function to orchestrate parsing of files and generation of plots.
    """
    print(f"Starting analysis of:\n  - {global_perf_file}\n  - {node_data_file}\n  - {phy_perf_file}")

    # Parse each file
    df_global = parse_global_performance(global_perf_file)
    df_node = parse_node_data(node_data_file)
    df_phy = parse_phy_performance(phy_perf_file)

    # Generate plots if data is available
    if not df_global.empty:
        print("\n--- Global Performance Data Head ---")
        print(df_global.head())
        plot_global_performance(df_global)
    else:
        print(f"Warning: No data parsed from {global_perf_file}. Skipping global performance plot.")

    if not df_node.empty:
        print("\n--- Node Data Head ---")
        print(df_node.head())
        plot_device_adr_parameters(df_node)
    else:
        print(f"Warning: No data parsed from {node_data_file}. Skipping device ADR parameters plot.")

    if not df_phy.empty:
        print("\n--- Physical Layer Performance Data Head ---")
        print(df_phy.head())
        plot_device_phy_performance(df_phy)
    else:
        print(f"Warning: No data parsed from {phy_perf_file}. Skipping physical layer performance plot.")

    print("\nAnalysis complete. Check generated plots.")

if __name__ == "__main__":
    # Check if the correct number of command-line arguments are provided
    if len(sys.argv) != 4:
        print("Usage: python3 analyze_ns3_outputs.py <global_performance_file> <node_data_file> <phy_performance_file>")
        print("Example: python3 analyze_ns3_outputs.py globalPerformance.txt nodeData.txt phyPerformance.txt")
        sys.exit(1) # Exit with an error code

    # Assign command-line arguments to variables
    global_perf_file = sys.argv[1]
    node_data_file = sys.argv[2]
    phy_perf_file = sys.argv[3]

    # Call the main analysis function
    main(global_perf_file, node_data_file, phy_perf_file)
