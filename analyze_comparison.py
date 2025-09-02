#!/usr/bin/env python3
"""
Simple LoRaWAN Analysis for ns3-lorawan comparison
"""

import pandas as pd
import sys
import os

def dr_to_sf(dr):
    """Convert Data Rate to Spreading Factor"""
    dr_map = {0: 12, 1: 11, 2: 10, 3: 9, 4: 8, 5: 7}
    return dr_map.get(int(dr), 12)

def parse_time(time_str):
    """Parse time format '+600s' to seconds"""
    return float(str(time_str).replace('+', '').replace('s', ''))

def main():
    prefix = sys.argv[1] if len(sys.argv) > 1 else "comparison_avg"
    
    print(f"🔬 LoRaWAN Analysis: {prefix}")
    print("="*40)
    
    # Load device status file
    device_file = f"{prefix}_deviceStatus.txt"
    if os.path.exists(device_file):
        df = pd.read_csv(device_file, sep=' ', 
                         names=['time', 'device_id', 'x', 'y', 'dr', 'tx_power'])
        df['time'] = df['time'].apply(parse_time)
        df['dr'] = pd.to_numeric(df['dr'])
        df['sf'] = df['dr'].apply(dr_to_sf)
        
        # Basic info
        n_devices = len(df[df['time'] == 0])
        max_time = df['time'].max()
        print(f"Devices: {n_devices}")
        print(f"Time: {max_time/60:.0f} minutes")
        
        # Initial SF distribution
        initial = df[df['time'] == 0]
        print(f"\n📊 Initial SF Distribution:")
        for sf in range(7, 13):
            count = len(initial[initial['sf'] == sf])
            pct = count/n_devices*100
            if count > 0:
                print(f"  SF{sf}: {count:2d} devices ({pct:4.1f}%)")
        
        # Final SF distribution
        final = df[df['time'] == max_time]
        print(f"\n🎯 Final SF Distribution:")
        for sf in range(7, 13):
            count = len(final[final['sf'] == sf])
            pct = count/n_devices*100
            if count > 0:
                print(f"  SF{sf}: {count:2d} devices ({pct:4.1f}%)")
                
        # TX Power distribution
        print(f"\n⚡ Final TX Power Distribution:")
        power_counts = final['tx_power'].value_counts().sort_index()
        for power, count in power_counts.items():
            pct = count/n_devices*100
            print(f"  {power:2.0f}dBm: {count:2d} devices ({pct:4.1f}%)")
    else:
        print(f"❌ {device_file} not found")
        return
    
    # Load global performance file
    global_file = f"{prefix}_globalPerformance.txt"
    if os.path.exists(global_file):
        perf = pd.read_csv(global_file, sep=' ', 
                          names=['time', 'sent', 'received'])
        perf['time'] = perf['time'].apply(parse_time)
        perf['sent'] = pd.to_numeric(perf['sent'])
        perf['received'] = pd.to_numeric(perf['received'])
        
        total_sent = perf['sent'].sum()
        total_received = perf['received'].sum()
        pdr = total_received/total_sent*100 if total_sent > 0 else 0
        
        print(f"\n📦 Global Performance:")
        print(f"  Packets sent: {total_sent:.0f}")
        print(f"  Packets received: {total_received:.0f}")
        print(f"  PDR: {pdr:.1f}%")
        
        # Show time evolution
        print(f"\n📈 Packet Flow:")
        for _, row in perf.iterrows():
            time_min = row['time']/60
            instant_pdr = row['received']/row['sent']*100 if row['sent'] > 0 else 0
            print(f"  {time_min:3.0f}min: {row['sent']:.0f} sent, {row['received']:.0f} recv ({instant_pdr:.0f}%)")
    else:
        print(f"⚠️  {global_file} not found")
    
    # Load PHY performance file
    phy_file = f"{prefix}_phyPerformance.txt"
    if os.path.exists(phy_file):
        # PHY file format: time col1 sent received col4 col5 col6 col7
        phy = pd.read_csv(phy_file, sep='\s+',  # Use \s+ to handle multiple spaces
                         names=['time', 'col1', 'sent', 'received', 'col4', 'col5', 'col6', 'col7'])
        phy['time'] = phy['time'].apply(parse_time)
        phy['sent'] = pd.to_numeric(phy['sent'], errors='coerce')
        phy['received'] = pd.to_numeric(phy['received'], errors='coerce')
        
        # Remove any rows with NaN values
        phy = phy.dropna(subset=['sent', 'received'])
        
        total_phy_sent = phy['sent'].sum()
        total_phy_received = phy['received'].sum()
        
        print(f"\n📡 PHY Performance:")
        print(f"  PHY sent: {total_phy_sent:.0f}")
        print(f"  PHY received: {total_phy_received:.0f}")
        
        # Show any notable PHY metrics
        if total_phy_sent > 0:
            phy_success = total_phy_received/total_phy_sent*100
            print(f"  PHY success: {phy_success:.1f}%")
            
        # Show lost packets (col6 might be interference/lost)
        if 'col6' in phy.columns:
            total_lost = phy['col6'].sum()
            if total_lost > 0:
                print(f"  PHY lost: {total_lost:.0f}")
    else:
        print(f"⚠️  {phy_file} not found")
    
    print(f"\n✅ Analysis complete - Ready for OMNeT++ comparison")

if __name__ == "__main__":
    main()