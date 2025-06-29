# #!/usr/bin/env python3
# """
# ADR Command Flow Analyzer
# Parses NS-3 simulation logs to extract and analyze actual ADR command sequences
# """

# import re
# import sys
# from dataclasses import dataclass
# from typing import List, Dict, Optional
# from collections import defaultdict

# @dataclass
# class ADRCommand:
#     """ADR command sent by network server"""
#     time: float
#     device_id: str
#     dr: int
#     tx_power: float
#     nb_trans: int
#     per_estimate: float
#     toa: float
#     algorithm_result: str

# @dataclass
# class PacketEvent:
#     """Packet reception event"""
#     time: float
#     device_id: str
#     packet_count: int

# @dataclass
# class SNRReading:
#     """SNR measurement from gateway"""
#     gateway_id: str
#     snr: float

# @dataclass
# class ADRDecision:
#     """Complete ADR decision context"""
#     time: float
#     device_id: str
#     packet_history: int
#     active_gateways: int
#     snr_readings: List[SNRReading]
#     command: Optional[ADRCommand]
#     current_dr: int
#     current_power: float

# class ADRLogAnalyzer:
#     def __init__(self):
#         self.adr_decisions: List[ADRDecision] = []
#         self.packet_events: List[PacketEvent] = []
#         self.device_stats: Dict[str, int] = defaultdict(int)
    
#     def parse_simulation_log(self, log_content: str) -> None:
#         """Parse the complete simulation log for ADR events"""
#         lines = log_content.split('\n')
        
#         current_decision = None
#         snr_readings = []
        
#         for line in lines:
#             line = line.strip()
            
#             # Track packet events
#             packet_match = re.search(r'OnReceivedPacket - Device (\d+) at time ([\d.]+)s', line)
#             if packet_match:
#                 device_id = packet_match.group(1)
#                 time = float(packet_match.group(2))
#                 self.device_stats[device_id] += 1
#                 self.packet_events.append(PacketEvent(time, device_id, self.device_stats[device_id]))
            
#             # Track ADR decision start
#             decision_start = re.search(r'BeforeSendingReply START - Device (\d+) at time ([\d.]+)s', line)
#             if decision_start:
#                 device_id = decision_start.group(1)
#                 time = float(decision_start.group(2))
#                 current_decision = ADRDecision(
#                     time=time,
#                     device_id=device_id,
#                     packet_history=0,
#                     active_gateways=0,
#                     snr_readings=[],
#                     command=None,
#                     current_dr=0,
#                     current_power=0.0
#                 )
#                 snr_readings = []
            
#             if current_decision:
#                 # Extract packet history
#                 history_match = re.search(r'Packet history: (\d+) packets', line)
#                 if history_match:
#                     current_decision.packet_history = int(history_match.group(1))
                
#                 # Extract current parameters
#                 current_match = re.search(r'Current: SF(\d+) DR(\d+) TxPower:([\d.]+)dBm', line)
#                 if current_match:
#                     current_decision.current_dr = int(current_match.group(2))
#                     current_decision.current_power = float(current_match.group(3))
                
#                 # Extract active gateways count
#                 gw_count_match = re.search(r'Active gateways: (\d+)', line)
#                 if gw_count_match:
#                     current_decision.active_gateways = int(gw_count_match.group(1))
                
#                 # Extract SNR readings
#                 snr_match = re.search(r'Gateway ([a-fA-F0-9:]+) mean SNR: ([-\d.]+) dB', line)
#                 if snr_match:
#                     snr_readings.append(SNRReading(snr_match.group(1), float(snr_match.group(2))))
                
#                 # Extract ADR selection
#                 selection_match = re.search(r'ADRopt selected: DR(\d+) TP:([\d.]+) NbTrans:(\d+) PER:([\d.e-]+) ToA:([\d.]+)', line)
#                 if selection_match:
#                     current_decision.command = ADRCommand(
#                         time=current_decision.time,
#                         device_id=current_decision.device_id,
#                         dr=int(selection_match.group(1)),
#                         tx_power=float(selection_match.group(2)),
#                         nb_trans=int(selection_match.group(3)),
#                         per_estimate=float(selection_match.group(4)),
#                         toa=float(selection_match.group(5)),
#                         algorithm_result="SELECTED"
#                     )
                
#                 # Check if ADR decision ends
#                 if "BeforeSendingReply END" in line:
#                     current_decision.snr_readings = snr_readings.copy()
#                     self.adr_decisions.append(current_decision)
#                     current_decision = None
#                     snr_readings = []
    
#     def analyze_adr_performance(self) -> None:
#         """Analyze ADR algorithm performance"""
#         print("=" * 80)
#         print("ADR COMMAND FLOW ANALYSIS")
#         print("=" * 80)
        
#         if not self.adr_decisions:
#             print("❌ No ADR decisions found in log")
#             return
        
#         print(f"✅ Found {len(self.adr_decisions)} ADR decisions")
#         print(f"✅ Total packet events: {len(self.packet_events)}")
        
#         # Analyze per device
#         devices = defaultdict(list)
#         for decision in self.adr_decisions:
#             devices[decision.device_id].append(decision)
        
#         for device_id, decisions in devices.items():
#             print(f"\n📱 DEVICE {device_id} ADR TIMELINE:")
#             print("-" * 50)
            
#             decisions.sort(key=lambda x: x.time)
            
#             # Track parameter evolution
#             dr_changes = []
#             power_changes = []
            
#             for i, decision in enumerate(decisions):
#                 time_min = decision.time / 60
                
#                 # Show summary
#                 if i == 0:
#                     print(f"📊 Initial State:")
#                     print(f"   Time: {time_min:.1f}min")
#                     print(f"   Current: DR{decision.current_dr}, {decision.current_power:.1f}dBm")
#                     print(f"   Packet History: {decision.packet_history}")
#                     print(f"   Active Gateways: {decision.active_gateways}")
                
#                 # Show ADR command if present
#                 if decision.command:
#                     cmd = decision.command
#                     print(f"\n🚀 ADR Command #{i+1} at {time_min:.1f}min:")
#                     print(f"   Selected: DR{cmd.dr}, {cmd.tx_power:.1f}dBm, NbTrans:{cmd.nb_trans}")
#                     print(f"   Predicted PER: {cmd.per_estimate:.2e}")
#                     print(f"   Time on Air: {cmd.toa:.1f}ms")
                    
#                     # Track changes
#                     if cmd.dr != decision.current_dr:
#                         dr_changes.append((time_min, decision.current_dr, cmd.dr))
#                     if abs(cmd.tx_power - decision.current_power) > 0.1:
#                         power_changes.append((time_min, decision.current_power, cmd.tx_power))
                
#                 # Show gateway diversity (first few decisions)
#                 if i < 3 and decision.snr_readings:
#                     print(f"   📡 Gateway SNRs:")
#                     for snr in decision.snr_readings[:4]:  # Show first 4
#                         print(f"      {snr.gateway_id}: {snr.snr:.1f}dB")
#                     if len(decision.snr_readings) > 4:
#                         print(f"      ... and {len(decision.snr_readings)-4} more")
            
#             # Summary of changes
#             print(f"\n📈 OPTIMIZATION SUMMARY:")
#             if dr_changes:
#                 print(f"   🔄 DR Changes: {len(dr_changes)}")
#                 for time_min, old_dr, new_dr in dr_changes[:5]:  # Show first 5
#                     sf_old, sf_new = 12-old_dr, 12-new_dr
#                     print(f"      {time_min:.1f}min: DR{old_dr}(SF{sf_old}) → DR{new_dr}(SF{sf_new})")
#                 if len(dr_changes) > 5:
#                     print(f"      ... and {len(dr_changes)-5} more changes")
            
#             if power_changes:
#                 print(f"   ⚡ Power Changes: {len(power_changes)}")
#                 for time_min, old_power, new_power in power_changes[:5]:
#                     savings = old_power - new_power
#                     print(f"      {time_min:.1f}min: {old_power:.1f}dBm → {new_power:.1f}dBm (saved {savings:.1f}dB)")
#                 if len(power_changes) > 5:
#                     print(f"      ... and {len(power_changes)-5} more changes")
            
#             # Calculate optimization effectiveness
#             if decisions:
#                 first_decision = decisions[0]
#                 last_command = None
#                 for decision in reversed(decisions):
#                     if decision.command:
#                         last_command = decision.command
#                         break
                
#                 if last_command:
#                     dr_improvement = last_command.dr - first_decision.current_dr
#                     power_savings = first_decision.current_power - last_command.tx_power
                    
#                     print(f"\n🎯 FINAL OPTIMIZATION RESULTS:")
#                     print(f"   📶 Data Rate: DR{first_decision.current_dr} → DR{last_command.dr} ({dr_improvement:+d})")
#                     print(f"   🔋 Power Savings: {power_savings:.1f}dB ({power_savings/first_decision.current_power*100:.1f}%)")
#                     print(f"   ⏱️  Final ToA: {last_command.toa:.1f}ms")
#                     print(f"   📊 Final PER: {last_command.per_estimate:.2e}")
    
#     def generate_performance_report(self) -> None:
#         """Generate comprehensive performance report"""
#         print(f"\n{'='*80}")
#         print("ADR ALGORITHM PERFORMANCE REPORT")
#         print(f"{'='*80}")
        
#         if not self.adr_decisions:
#             print("❌ No ADR data to analyze")
#             return
        
#         # Overall statistics
#         total_commands = sum(1 for d in self.adr_decisions if d.command)
#         avg_packet_history = sum(d.packet_history for d in self.adr_decisions) / len(self.adr_decisions)
#         avg_gw_count = sum(d.active_gateways for d in self.adr_decisions) / len(self.adr_decisions)
        
#         print(f"📋 ALGORITHM STATISTICS:")
#         print(f"   Total ADR Decisions: {len(self.adr_decisions)}")
#         print(f"   Commands Sent: {total_commands}")
#         print(f"   Average Packet History: {avg_packet_history:.1f}")
#         print(f"   Average Gateway Count: {avg_gw_count:.1f}")
        
#         # Analyze command effectiveness
#         dr_selections = defaultdict(int)
#         power_selections = defaultdict(int)
        
#         for decision in self.adr_decisions:
#             if decision.command:
#                 dr_selections[decision.command.dr] += 1
#                 power_selections[decision.command.tx_power] += 1
        
#         print(f"\n📊 PARAMETER SELECTION PATTERNS:")
#         print(f"   Data Rate Preferences:")
#         for dr in sorted(dr_selections.keys()):
#             sf = 12 - dr
#             count = dr_selections[dr]
#             percent = count / total_commands * 100
#             print(f"      DR{dr} (SF{sf}): {count} times ({percent:.1f}%)")
        
#         print(f"   Power Level Preferences:")
#         for power in sorted(power_selections.keys()):
#             count = power_selections[power]
#             percent = count / total_commands * 100
#             print(f"      {power:.1f}dBm: {count} times ({percent:.1f}%)")
        
#         # Check for convergence
#         if len(self.adr_decisions) > 10:
#             recent_decisions = self.adr_decisions[-10:]
#             recent_drs = [d.command.dr for d in recent_decisions if d.command]
#             recent_powers = [d.command.tx_power for d in recent_decisions if d.command]
            
#             if recent_drs and recent_powers:
#                 dr_stable = len(set(recent_drs)) == 1
#                 power_stable = len(set(recent_powers)) == 1
                
#                 print(f"\n🎯 CONVERGENCE ANALYSIS (last 10 decisions):")
#                 print(f"   DR Stability: {'✅ Converged' if dr_stable else '🔄 Still adapting'}")
#                 print(f"   Power Stability: {'✅ Converged' if power_stable else '🔄 Still adapting'}")
                
#                 if dr_stable and power_stable:
#                     print(f"   🏆 OPTIMAL CONFIGURATION FOUND:")
#                     print(f"      DR{recent_drs[0]} (SF{12-recent_drs[0]}), {recent_powers[0]:.1f}dBm")

# def main():
#     """Main execution function"""
#     if len(sys.argv) != 2:
#         print("Usage: python3 adr_analyzer.py <simulation_log_file>")
#         print("Example: python3 adr_analyzer.py simulation_output.log")
#         sys.exit(1)
    
#     log_file = sys.argv[1]
    
#     try:
#         with open(log_file, 'r') as f:
#             log_content = f.read()
#     except FileNotFoundError:
#         print(f"Error: Log file '{log_file}' not found")
#         sys.exit(1)
    
#     analyzer = ADRLogAnalyzer()
#     analyzer.parse_simulation_log(log_content)
#     analyzer.analyze_adr_performance()
#     analyzer.generate_performance_report()

# if __name__ == "__main__":
#     main()


import re
import pandas as pd
import argparse
from dataclasses import dataclass, field
from typing import List, Dict, Optional

# --- Data-classes for storing structured log data ---

@dataclass
class SnrReading:
    """Represents a single SNR reading from a gateway."""
    gateway_id: str
    snr: float

@dataclass
class AdrDecisionContext:
    """Stores the context before an ADR decision is made."""
    time: float
    device_id: int
    packet_history: int
    active_gateways: int
    current_dr: int
    current_power: float
    snr_readings: List[SnrReading] = field(default_factory=list)

@dataclass
class AdrCommand:
    """Represents a sent ADR command."""
    time: float
    device_id: int
    dr: int
    tx_power: float
    nb_trans: int
    per: float
    toa: float
    result: str

@dataclass
class PacketEvent:
    """Represents a received packet event."""
    time: float
    device_id: int

# --- Regular expressions for parsing log lines ---

# Matches: *** ADRopt: OnReceivedPacket - Device 1811941192 at time 397.4s ***
PACKET_EVENT_RE = re.compile(
    r"\*\*\* ADRopt: OnReceivedPacket - Device (?P<device_id>\d+) at time (?P<time>[\d.]+)s \*\*\*"
)

# Matches the detailed ADR_DECISION_CONTEXT line
ADR_DECISION_CONTEXT_RE = re.compile(
    r"ADR_DECISION_CONTEXT: Time:(?P<time>[\d.]+)\s"
    r"DeviceId:(?P<device_id>\d+)\s"
    r"PktHistory:(?P<pkt_history>\d+)\s"
    r"ActiveGWs:(?P<active_gws>\d+)\s"
    r"CurrentDR:(?P<dr>\d+)\s"
    r"CurrentPower:(?P<power>[\d.-]+)\s"
    r"SNRReadings:\[(?P<snr_readings>.*)\]"
)

# Matches the ADR_COMMAND_SENT line
ADR_COMMAND_SENT_RE = re.compile(
    r"ADR_COMMAND_SENT: Time:(?P<time>[\d.]+)\s"
    r"DeviceId:(?P<device_id>\d+)\s"
    r"DR:(?P<dr>\d+)\s"
    r"TxPower:(?P<tx_power>[\d.-]+)\s"
    r"NbTrans:(?P<nb_trans>\d+)\s"
    r"PER:(?P<per>[\d.e-]+)\s"
    r"ToA:(?P<toa>[\d.e-]+)\s"
    r"Result:(?P<result>\w+)"
)


def parse_log_file(log_file_path: str):
    """Parses the ns-3 log file and extracts structured data."""
    adr_decisions = []
    adr_commands = []
    packet_events = []

    with open(log_file_path, 'r') as f:
        for line in f:
            # Try to match an ADR decision context
            match = ADR_DECISION_CONTEXT_RE.search(line)
            if match:
                data = match.groupdict()
                snr_list_str = data['snr_readings']
                snr_readings = []
                if snr_list_str:
                    for snr_pair in snr_list_str.split('|'):
                        parts = snr_pair.split(':')
                        if len(parts) == 2:
                            snr_readings.append(SnrReading(gateway_id=parts[0], snr=float(parts[1])))

                decision = AdrDecisionContext(
                    time=float(data['time']) / 60,  # Convert to minutes
                    device_id=int(data['device_id']),
                    packet_history=int(data['pkt_history']),
                    active_gateways=int(data['active_gws']),
                    current_dr=int(data['dr']),
                    current_power=float(data['power']),
                    snr_readings=snr_readings
                )
                adr_decisions.append(decision)
                continue

            # Try to match a sent ADR command
            match = ADR_COMMAND_SENT_RE.search(line)
            if match:
                data = match.groupdict()
                command = AdrCommand(
                    time=float(data['time']) / 60,  # Convert to minutes
                    device_id=int(data['device_id']),
                    dr=int(data['dr']),
                    tx_power=float(data['tx_power']),
                    nb_trans=int(data['nb_trans']),
                    per=float(data['per']),
                    toa=float(data['toa']),
                    result=data['result']
                )
                adr_commands.append(command)
                continue
            
            # Try to match a packet reception event
            match = PACKET_EVENT_RE.search(line)
            if match:
                data = match.groupdict()
                event = PacketEvent(
                    time=float(data['time']) / 60, # Convert to minutes
                    device_id=int(data['device_id'])
                )
                packet_events.append(event)


    return adr_decisions, adr_commands, packet_events


def analyze_adr_performance(adr_decisions: List[AdrDecisionContext], adr_commands: List[AdrCommand], packet_events: List[PacketEvent]):
    """Analyzes the parsed data and prints a performance report."""

    print("================================================================================")
    print("ADR COMMAND FLOW ANALYSIS")
    print("================================================================================")
    
    if not adr_decisions:
        print("❌ No ADR decision contexts found in the log.")
        return

    print(f"✅ Found {len(adr_decisions)} ADR decisions")
    print(f"✅ Total packet events: {len(packet_events)}")

    # Group data by device
    decisions_by_device = {}
    for d in adr_decisions:
        decisions_by_device.setdefault(d.device_id, []).append(d)

    commands_by_device = {}
    for c in adr_commands:
        commands_by_device.setdefault(c.device_id, []).append(c)

    for device_id, decisions in decisions_by_device.items():
        print(f"\n📱 DEVICE {device_id} ADR TIMELINE:")
        print("--------------------------------------------------")
        
        # Initial State (from first decision context)
        first_decision = decisions[0]
        print("📊 Initial State:")
        print(f"    Time: {first_decision.time:.1f}min")
        print(f"    Current: DR{first_decision.current_dr}, {first_decision.current_power:.1f}dBm")
        print(f"    Packet History: {first_decision.packet_history}")
        print(f"    Active Gateways: {first_decision.active_gateways}")

        device_commands = commands_by_device.get(device_id, [])
        if device_commands:
            print("\n📈 OPTIMIZATION SUMMARY:")
            for cmd in device_commands:
                print(f"    - At {cmd.time:.1f}min: Sent command to set DR{cmd.dr}, {cmd.tx_power:.1f}dBm, {cmd.nb_trans} Tx")
                print(f"      (Predicted PER: {cmd.per:.3f}, ToA: {cmd.toa:.2f}ms)")
        else:
            print("\n📉 No ADR optimization commands were sent for this device.")
    
    print("\n================================================================================")
    print("ADR ALGORITHM PERFORMANCE REPORT")
    print("================================================================================")

    if not adr_decisions:
        return

    # --- Overall Algorithm Statistics ---
    print("📋 ALGORITHM STATISTICS:")
    print(f"    Total ADR Decisions: {len(adr_decisions)}")
    print(f"    Commands Sent: {len(adr_commands)}")

    if adr_decisions:
        avg_pkt_history = sum(d.packet_history for d in adr_decisions) / len(adr_decisions)
        avg_gw_count = sum(d.active_gateways for d in adr_decisions) / len(adr_decisions)
        print(f"    Average Packet History: {avg_pkt_history:.1f}")
        print(f"    Average Gateway Count: {avg_gw_count:.1f}")

    # --- Parameter Selection Patterns ---
    if adr_commands:
        print("\n📊 PARAMETER SELECTION PATTERNS:")
        df_cmds = pd.DataFrame([vars(c) for c in adr_commands])
        
        # Data Rate Preferences
        print("    Data Rate Preferences:")
        dr_counts = df_cmds['dr'].value_counts(normalize=True).mul(100).sort_index()
        for dr, perc in dr_counts.items():
            print(f"        DR{dr}: {perc:.1f}%")
            
        # Power Level Preferences
        print("    Power Level Preferences:")
        power_counts = df_cmds['tx_power'].value_counts(normalize=True).mul(100).sort_index()
        for power, perc in power_counts.items():
            print(f"        {power:.1f} dBm: {perc:.1f}%")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse and analyze ns-3 ADR logs.")
    parser.add_argument("log_file", help="Path to the ns-3 log file.")
    args = parser.parse_args()

    adr_decisions, adr_commands, packet_events = parse_log_file(args.log_file)
    analyze_adr_performance(adr_decisions, adr_commands, packet_events)