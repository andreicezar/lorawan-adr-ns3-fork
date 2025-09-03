#!/usr/bin/env python3
"""
Simple Analysis Script for NS3 LoRaWAN Scenario 01
Extracts raw performance data from simulation results without fancy formatting.
"""

import os
import glob
import pandas as pd
import re

class SimpleScenario01Analyzer:
    def __init__(self, results_dir="./output/scenario-01-enhanced"):
        self.results_dir = results_dir
        self.results = {}
        
    def read_csv_file(self, filepath):
        """Read a single CSV result file and extract key metrics."""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            # Extract scenario name from filepath - better extraction
            scenario_name = os.path.basename(filepath)
            scenario_name = scenario_name.replace('_results.csv', '').replace('result_results.csv', 'result')
            
            # Try to get parent folder name if filename is generic
            if scenario_name in ['result', 'results']:
                parent_folder = os.path.basename(os.path.dirname(filepath))
                if parent_folder and parent_folder != '.':
                    scenario_name = parent_folder
            
            print(f"DEBUG: Processing file {filepath} -> scenario '{scenario_name}'")
            
            result = {
                'scenario': scenario_name,
                'filepath': filepath,
                'config': {},
                'overall': {},
                'per_node_stats': None
            }
            
            # Parse line by line
            current_section = None
            per_node_lines = []
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Skip comment lines and empty lines
                if line.startswith('#') or not line:
                    continue
                
                # Identify sections
                if line == 'CONFIGURATION':
                    current_section = 'config'
                    print(f"DEBUG: Found CONFIGURATION section at line {i+1}")
                    continue
                elif line == 'OVERALL_STATS':
                    current_section = 'overall'
                    print(f"DEBUG: Found OVERALL_STATS section at line {i+1}")
                    continue
                elif line == 'PER_NODE_STATS':
                    current_section = 'per_node'
                    print(f"DEBUG: Found PER_NODE_STATS section at line {i+1}")
                    continue
                
                # Parse data based on current section
                if current_section == 'config' and ',' in line:
                    key, value = line.split(',', 1)
                    # Convert boolean strings
                    if value.lower() == 'true':
                        result['config'][key] = True
                    elif value.lower() == 'false':
                        result['config'][key] = False
                    else:
                        try:
                            # Try numeric conversion
                            if '.' in value:
                                result['config'][key] = float(value)
                            else:
                                result['config'][key] = int(value)
                        except ValueError:
                            result['config'][key] = value
                            
                elif current_section == 'overall' and ',' in line:
                    key, value = line.split(',', 1)
                    try:
                        # Try to convert to number
                        if '.' in value:
                            result['overall'][key] = float(value)
                        else:
                            result['overall'][key] = int(value)
                    except ValueError:
                        result['overall'][key] = value
                        
                elif current_section == 'per_node' and line:
                    per_node_lines.append(line)
                    
                elif ',' in line and any(keyword in line for keyword in ['TotalADRChanges', 'ChannelUtilization']):
                    # Handle lines that appear between sections
                    key, value = line.split(',', 1)
                    try:
                        if '.' in value:
                            result['overall'][key] = float(value)
                        else:
                            result['overall'][key] = int(value)
                    except ValueError:
                        result['overall'][key] = value
            
            print(f"DEBUG: Config keys found: {list(result['config'].keys())}")
            print(f"DEBUG: Overall keys found: {list(result['overall'].keys())}")
            print(f"DEBUG: Per-node lines count: {len(per_node_lines)}")
            
            # Parse per-node data if available
            if per_node_lines:
                from io import StringIO
                try:
                    per_node_content = '\n'.join(per_node_lines)
                    result['per_node_stats'] = pd.read_csv(StringIO(per_node_content))
                    print(f"DEBUG: Successfully parsed {len(result['per_node_stats'])} per-node records")
                except Exception as e:
                    print(f"Warning: Could not parse per-node data for {scenario_name}: {e}")
                    print(f"Per-node content sample: {per_node_lines[:2] if per_node_lines else 'None'}")
            
            return result
            
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def debug_file(self, filepath):
        """Debug a specific CSV file to see its structure."""
        print(f"\nDEBUG: Examining file structure of {filepath}")
        print("="*60)
        
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
            
            print(f"Total lines: {len(lines)}")
            print("\nFirst 20 lines:")
            for i, line in enumerate(lines[:20]):
                line_clean = line.strip()
                print(f"{i+1:2d}: {repr(line_clean)}")
            
            print("\nSection markers found:")
            for i, line in enumerate(lines):
                line_clean = line.strip()
                if line_clean in ['CONFIGURATION', 'OVERALL_STATS', 'PER_NODE_STATS']:
                    print(f"  Line {i+1}: {line_clean}")
            
        except Exception as e:
            print(f"Error reading file: {e}")

    def analyze_directory(self):
        """Analyze all CSV result files in the directory."""
        if not os.path.exists(self.results_dir):
            print(f"Directory not found: {self.results_dir}")
            return
        
        # Find all result CSV files
        pattern = os.path.join(self.results_dir, "**", "*results.csv")
        csv_files = glob.glob(pattern, recursive=True)
        
        if not csv_files:
            print(f"No result CSV files found in {self.results_dir}")
            print("Looking for any CSV files...")
            pattern = os.path.join(self.results_dir, "**", "*.csv")
            all_csv_files = glob.glob(pattern, recursive=True)
            print(f"Found {len(all_csv_files)} CSV files total:")
            for f in all_csv_files:
                print(f"  {f}")
            return
        
        print(f"Found {len(csv_files)} result files:")
        for f in csv_files:
            print(f"  {f}")
        
        for csv_file in sorted(csv_files):
            result = self.read_csv_file(csv_file)
            if result:
                self.results[result['scenario']] = result
            else:
                print(f"Failed to parse: {csv_file}")
        
        print(f"Successfully parsed {len(self.results)} scenarios")
    
    def print_compact_comparison(self):
        """Print a compact comparison focusing on key differences."""
        if not self.results:
            print("No results to analyze")
            return
        
        print("\n" + "="*80)
        print("COMPACT PERFORMANCE COMPARISON")
        print("="*80)
        
        # Group by configuration type
        fixed_configs = []
        adr_configs = []
        
        for scenario_name in sorted(self.results.keys()):
            result = self.results[scenario_name]
            config = result['config']
            
            if config.get('EnableADR', False):
                adr_configs.append((scenario_name, result))
            else:
                fixed_configs.append((scenario_name, result))
        
        # Print fixed configurations
        if fixed_configs:
            print("\nFIXED PARAMETER CONFIGURATIONS (ADR OFF):")
            print(f"{'Config':<25} {'PDR%':<8} {'Sent':<8} {'Recv':<8} {'ChUtil%':<8}")
            print("-" * 65)
            for scenario_name, result in fixed_configs:
                overall = result['overall']
                pdr = overall.get('PDR_Percent', 0)
                sent = overall.get('TotalSent', 0)
                received = overall.get('TotalReceived', 0)
                ch_util = overall.get('ChannelUtilization_Percent', 0)
                print(f"{scenario_name:<25} {pdr:<8.2f} {sent:<8} {received:<8} {ch_util:<8.4f}")
        
        # Print ADR configurations
        if adr_configs:
            print("\nADAPTIVE CONFIGURATIONS (ADR ON):")
            print(f"{'Config':<25} {'PDR%':<8} {'Sent':<8} {'Recv':<8} {'ADRChg':<8} {'ChUtil%':<8}")
            print("-" * 75)
            for scenario_name, result in adr_configs:
                overall = result['overall']
                pdr = overall.get('PDR_Percent', 0)
                sent = overall.get('TotalSent', 0)
                received = overall.get('TotalReceived', 0)
                adr_changes = overall.get('TotalADRChanges', 0)
                ch_util = overall.get('ChannelUtilization_Percent', 0)
                print(f"{scenario_name:<25} {pdr:<8.2f} {sent:<8} {received:<8} {adr_changes:<8} {ch_util:<8.4f}")
        
        # Best and worst performers
        all_results = [(name, result) for name, result in self.results.items()]
        if all_results:
            best_pdr = max(all_results, key=lambda x: x[1]['overall'].get('PDR_Percent', 0))
            worst_pdr = min(all_results, key=lambda x: x[1]['overall'].get('PDR_Percent', 0))
            
            print(f"\nBEST PDR: {best_pdr[0]} ({best_pdr[1]['overall'].get('PDR_Percent', 0):.2f}%)")
            print(f"WORST PDR: {worst_pdr[0]} ({worst_pdr[1]['overall'].get('PDR_Percent', 0):.2f}%)")

    def print_summary_table(self):
        """Print a summary table of all scenarios."""
        if not self.results:
            print("No results to analyze")
            return
        
        print("\n" + "="*120)
        print("SCENARIO 01 SUMMARY - RAW DATA")
        print("="*120)
        
        # Header
        print(f"{'Scenario':<25} {'InitSF':<8} {'InitTP':<8} {'ADR':<8} {'Sent':<8} {'Received':<8} {'PDR%':<8} {'Drops':<8} {'ADRChg':<8}")
        print("-"*120)
        
        # Data rows
        for scenario_name in sorted(self.results.keys()):
            result = self.results[scenario_name]
            config = result['config']
            overall = result['overall']
            
            init_sf = "YES" if config.get('InitSF', False) else "NO"
            init_tp = "YES" if config.get('InitTP', False) else "NO"
            enable_adr = "YES" if config.get('EnableADR', False) else "NO"
            
            sent = overall.get('TotalSent', 0)
            received = overall.get('TotalReceived', 0)
            pdr = overall.get('PDR_Percent', 0)
            drops = overall.get('Drops_SentMinusReceived', 0)
            adr_changes = overall.get('TotalADRChanges', 0)
            
            print(f"{scenario_name:<25} {init_sf:<8} {init_tp:<8} {enable_adr:<8} {sent:<8} {received:<8} {pdr:<8.2f} {drops:<8} {adr_changes:<8}")
        
        print("\nKey:")
        print("InitSF = Initialize Spreading Factor, InitTP = Initialize Transmit Power")
        print("ADR = Adaptive Data Rate, PDR% = Packet Delivery Rate")
        print("ADRChg = Total ADR parameter changes during simulation")
    
    def print_detailed_metrics(self):
        """Print detailed metrics for each scenario."""
        if not self.results:
            print("No results to analyze")
            return
            
        print("\n" + "="*80)
        print("DETAILED METRICS BY SCENARIO")
        print("="*80)
        
        for scenario_name in sorted(self.results.keys()):
            result = self.results[scenario_name]
            print(f"\nScenario: {scenario_name}")
            print("-" * 40)
            
            # Configuration
            print("Configuration:")
            for key, value in result['config'].items():
                print(f"  {key}: {value}")
            
            # Overall stats
            print("\nOverall Performance:")
            for key, value in result['overall'].items():
                if isinstance(value, float):
                    print(f"  {key}: {value:.4f}")
                else:
                    print(f"  {key}: {value}")
            
            # Per-node summary if available
            if result['per_node_stats'] is not None:
                df = result['per_node_stats']
                print(f"\nPer-Node Summary ({len(df)} nodes):")
                
                if 'PDR_Percent' in df.columns:
                    print(f"  PDR - Min: {df['PDR_Percent'].min():.2f}%, Max: {df['PDR_Percent'].max():.2f}%, Avg: {df['PDR_Percent'].mean():.2f}%")
                
                if 'Sent' in df.columns:
                    print(f"  Packets Sent - Min: {df['Sent'].min()}, Max: {df['Sent'].max()}, Avg: {df['Sent'].mean():.1f}")
                
                if 'ADR_Changes' in df.columns:
                    nodes_with_adr = len(df[df['ADR_Changes'] > 0])
                    print(f"  ADR Changes - Nodes affected: {nodes_with_adr}, Total changes: {df['ADR_Changes'].sum()}")
                
                if 'FinalSF_DR' in df.columns:
                    # Convert DR to SF for readability
                    final_sf = 12 - df['FinalSF_DR']
                    print(f"  Final SF - Min: SF{final_sf.max():.0f}, Max: SF{final_sf.min():.0f}, Avg: SF{final_sf.mean():.1f}")
                
                if 'FinalTP_dBm' in df.columns:
                    print(f"  Final TP - Min: {df['FinalTP_dBm'].min():.0f}dBm, Max: {df['FinalTP_dBm'].max():.0f}dBm, Avg: {df['FinalTP_dBm'].mean():.1f}dBm")
    
    def export_comparison_csv(self, output_file="scenario_01_comparison.csv"):
        """Export a comparison table to CSV."""
        if not self.results:
            print("No results to export")
            return
        
        comparison_data = []
        
        for scenario_name in sorted(self.results.keys()):
            result = self.results[scenario_name]
            config = result['config']
            overall = result['overall']
            
            row = {
                'Scenario': scenario_name,
                'InitSF': config.get('InitSF', False),
                'InitTP': config.get('InitTP', False),
                'EnableADR': config.get('EnableADR', False),
                'DefaultSF': config.get('DefaultSF', 'N/A'),
                'DefaultTP_dBm': config.get('DefaultTP_dBm', 'N/A'),
                'TotalSent': overall.get('TotalSent', 0),
                'TotalReceived': overall.get('TotalReceived', 0),
                'PDR_Percent': overall.get('PDR_Percent', 0),
                'Drops': overall.get('Drops_SentMinusReceived', 0),
                'DropRate_Percent': overall.get('DropRate_Percent', 0),
                'TotalADRChanges': overall.get('TotalADRChanges', 0),
                'ChannelUtilization_Percent': overall.get('ChannelUtilization_Percent', 0),
                'TheoreticalToA_ms': overall.get('TheoreticalToA_ms', 0),
                'AvgSF': overall.get('AvgSF', 0)
            }
            
            # Add per-node averages if available
            if result['per_node_stats'] is not None:
                df = result['per_node_stats']
                if 'FinalSF_DR' in df.columns:
                    row['AvgFinalSF'] = (12 - df['FinalSF_DR']).mean()
                if 'FinalTP_dBm' in df.columns:
                    row['AvgFinalTP_dBm'] = df['FinalTP_dBm'].mean()
                if 'PDR_Percent' in df.columns:
                    row['AvgNodePDR_Percent'] = df['PDR_Percent'].mean()
                if 'ADR_Changes' in df.columns:
                    row['NodesWithADRChanges'] = len(df[df['ADR_Changes'] > 0])
                    row['MaxADRChangesPerNode'] = df['ADR_Changes'].max()
            
            comparison_data.append(row)
        
        df = pd.DataFrame(comparison_data)
        df.to_csv(output_file, index=False)
        print(f"\nComparison data exported to: {output_file}")
        return df

def main():
    # Configuration
    results_directory = "./output/scenario-01-enhanced"
    
    print("NS3 LoRaWAN Scenario 01 - Raw Data Analyzer")
    print("=" * 50)
    
    analyzer = SimpleScenario01Analyzer(results_directory)
    analyzer.analyze_directory()
    
    if analyzer.results:
        analyzer.print_compact_comparison()
        analyzer.print_summary_table()
        analyzer.print_detailed_metrics()
        
        # Export comparison CSV
        comparison_df = analyzer.export_comparison_csv()
        
        print(f"\nAnalysis complete. Processed {len(analyzer.results)} scenarios.")
        print(f"Results directory: {results_directory}")
        
    else:
        print("No valid results found.")
        print("\nTrying to debug first available CSV file...")
        
        # Find any CSV file to debug
        pattern = os.path.join(results_directory, "**", "*.csv")
        all_csv_files = glob.glob(pattern, recursive=True)
        if all_csv_files:
            analyzer.debug_file(all_csv_files[0])
        else:
            print("No CSV files found at all.")

if __name__ == "__main__":
    main()