import os
import pandas as pd
import re
from pathlib import Path
from typing import Dict, List, Tuple, Any
import glob

class NS3LoRaWANAnalyzer:
    """
    A class to analyze NS3 LoRaWAN simulation CSV files with custom structure.
    """
    
    def __init__(self, csv_directory: str = "."):
        """
        Initialize the analyzer with the directory containing CSV files.
        
        Args:
            csv_directory (str): Path to directory containing CSV files
        """
        self.csv_directory = csv_directory
        self.scenarios_data = {}
        self.all_column_sets = set()
        
    def parse_single_csv(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a single CSV file and extract all relevant information.
        
        Args:
            file_path (str): Path to the CSV file
            
        Returns:
            Dict containing parsed data: scenario_info, config, overall_stats, per_node_data, columns
        """
        
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        
        # Initialize data structure
        parsed_data = {
            'file_path': file_path,
            'scenario_info': {},
            'config': {},
            'overall_stats': {},
            'per_node_data': None,
            'columns': [],
            'metadata': {}
        }
        
        current_section = None
        per_node_stats_found = False
        per_node_start_line = -1
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Parse scenario header
            if line.startswith('# Scenario'):
                parsed_data['scenario_info']['title'] = line
                # Extract scenario number if possible
                match = re.search(r'Scenario (\d+)', line)
                if match:
                    parsed_data['scenario_info']['number'] = int(match.group(1))
                continue
                
            # Parse other metadata comments
            if line.startswith('#') and 'Scenario' not in line:
                if 'Generated:' in line:
                    parsed_data['metadata']['generated'] = line.replace('# Generated:', '').strip()
                elif 'Devices:' in line or 'Gateways:' in line:
                    parsed_data['metadata']['simulation_params'] = line.replace('#', '').strip()
                continue
            
            # Identify sections
            if line in ['CONFIGURATION', 'OVERALL_STATS', 'PER_NODE_STATS']:
                current_section = line
                if line == 'PER_NODE_STATS':
                    per_node_stats_found = True
                    per_node_start_line = i + 1  # Next line should be headers
                continue
            
            # Parse configuration section
            if current_section == 'CONFIGURATION' and ',' in line:
                key, value = line.split(',', 1)
                parsed_data['config'][key] = self._convert_value(value)
                
            # Parse overall stats section
            elif current_section == 'OVERALL_STATS' and ',' in line:
                key, value = line.split(',', 1)
                parsed_data['overall_stats'][key] = self._convert_value(value)
                
            # Parse PER_NODE_STATS headers
            elif current_section == 'PER_NODE_STATS' and i == per_node_start_line:
                parsed_data['columns'] = [col.strip() for col in line.split(',')]
                self.all_column_sets.add(tuple(parsed_data['columns']))
                break
        
        # Read the PER_NODE_STATS data using pandas
        if per_node_stats_found and per_node_start_line != -1:
            try:
                # Read from the line after PER_NODE_STATS
                parsed_data['per_node_data'] = pd.read_csv(
                    file_path, 
                    skiprows=per_node_start_line,
                    header=0
                )
                # Clean column names
                parsed_data['per_node_data'].columns = parsed_data['per_node_data'].columns.str.strip()
                
            except Exception as e:
                print(f"Error reading PER_NODE_STATS data from {file_path}: {e}")
                parsed_data['per_node_data'] = None
        
        return parsed_data
    
    def _convert_value(self, value: str) -> Any:
        """
        Convert string values to appropriate Python types.
        """
        value = value.strip()
        
        # Try to convert to boolean
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        
        # Try to convert to number
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            return value
    
    def analyze_all_csv_files(self, file_pattern: str = "*.csv") -> Dict[str, Any]:
        """
        Analyze all CSV files in the specified directory.
        
        Args:
            file_pattern (str): File pattern to match (default: "*.csv")
            
        Returns:
            Dictionary containing all parsed scenarios
        """
        
        csv_files = glob.glob(os.path.join(self.csv_directory, file_pattern))
        
        if not csv_files:
            print(f"No CSV files found in {self.csv_directory}")
            return {}
        
        print(f"Found {len(csv_files)} CSV files to analyze...")
        
        for file_path in csv_files:
            print(f"Processing: {os.path.basename(file_path)}")
            
            try:
                parsed_data = self.parse_single_csv(file_path)
                
                # Use filename as key if no scenario number is found
                scenario_key = (parsed_data['scenario_info'].get('number', 
                               os.path.splitext(os.path.basename(file_path))[0]))
                
                self.scenarios_data[scenario_key] = parsed_data
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        return self.scenarios_data
    
    def analyze_all_csv_files_recursive(self, file_pattern: str = "*.csv") -> Dict[str, Any]:
        """
        Analyze all CSV files recursively in the specified directory and subdirectories.
        
        Args:
            file_pattern (str): File pattern to match (default: "*.csv")
            
        Returns:
            Dictionary containing all parsed scenarios
        """
        
        # Use recursive glob to find files in subdirectories
        search_pattern = os.path.join(self.csv_directory, "**", file_pattern)
        csv_files = glob.glob(search_pattern, recursive=True)
        
        if not csv_files:
            print(f"No CSV files found recursively in {self.csv_directory}")
            return {}
        
        print(f"Found {len(csv_files)} CSV files to analyze recursively...")
        
        for file_path in csv_files:
            # Create a more meaningful key from the directory structure
            rel_path = os.path.relpath(file_path, self.csv_directory)
            print(f"Processing: {rel_path}")
            
            try:
                parsed_data = self.parse_single_csv(file_path)
                
                # Create a better scenario key from directory structure
                path_parts = Path(rel_path).parts
                if len(path_parts) >= 2:
                    # Use directory names as part of the key (e.g., "scenario-05-traffic-patterns_interval-600s")
                    scenario_key = "_".join(path_parts[:-1]) + "_" + Path(file_path).stem
                else:
                    # Fallback to filename
                    scenario_key = (parsed_data['scenario_info'].get('number', 
                                   os.path.splitext(os.path.basename(file_path))[0]))
                
                # Store relative path for reference
                parsed_data['relative_path'] = rel_path
                self.scenarios_data[scenario_key] = parsed_data
                
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                continue
        
        return self.scenarios_data
    
    def get_column_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all different column sets found across scenarios.
        """
        column_summary = {
            'unique_column_sets': len(self.all_column_sets),
            'column_sets': list(self.all_column_sets),
            'common_columns': None
        }
        
        if self.all_column_sets:
            # Find common columns across all scenarios
            column_sets_list = list(self.all_column_sets)
            common_columns = set(column_sets_list[0])
            for column_set in column_sets_list:
                common_columns &= set(column_set)
            column_summary['common_columns'] = list(common_columns)
            
        return column_summary
    
    def print_summary(self):
        """
        Print a summary of all analyzed scenarios.
        """
        if not self.scenarios_data:
            print("No data to summarize. Run analyze_all_csv_files() first.")
            return
            
        print(f"\n{'='*60}")
        print(f"NS3 LoRaWAN SIMULATION ANALYSIS SUMMARY")
        print(f"{'='*60}")
        
        print(f"Total scenarios analyzed: {len(self.scenarios_data)}")
        
        column_summary = self.get_column_summary()
        print(f"Unique column sets found: {column_summary['unique_column_sets']}")
        
        if column_summary['common_columns']:
            print(f"Common columns across all scenarios: {column_summary['common_columns']}")
        
        print(f"\n{'Scenario Details:'}")
        print(f"{'-'*40}")
        
        for scenario_key, data in self.scenarios_data.items():
            print(f"\nScenario: {scenario_key}")
            if 'relative_path' in data:
                print(f"  File: {data['relative_path']}")
            else:
                print(f"  File: {os.path.basename(data['file_path'])}")
            print(f"  Title: {data['scenario_info'].get('title', 'N/A')}")
            print(f"  Columns: {data['columns']}")
            print(f"  Nodes: {len(data['per_node_data']) if data['per_node_data'] is not None else 'N/A'}")
            
            # Show key overall stats
            if data['overall_stats']:
                key_stats = ['TotalSent', 'TotalReceived', 'PDR_Percent']
                stats_str = []
                for stat in key_stats:
                    if stat in data['overall_stats']:
                        stats_str.append(f"{stat}: {data['overall_stats'][stat]}")
                if stats_str:
                    print(f"  Key Stats: {', '.join(stats_str)}")
    
    def export_combined_data(self, output_file: str = "combined_scenarios.xlsx"):
        """
        Export all scenario data to an Excel file with multiple sheets.
        
        Args:
            output_file (str): Output Excel filename
        """
        if not self.scenarios_data:
            print("No data to export. Run analyze_all_csv_files() first.")
            return
            
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            
            # Create summary sheet
            summary_data = []
            for scenario_key, data in self.scenarios_data.items():
                summary_row = {
                    'Scenario': scenario_key,
                    'Title': data['scenario_info'].get('title', ''),
                    'File': os.path.basename(data['file_path']),
                    'Columns': ', '.join(data['columns']),
                    'Node_Count': len(data['per_node_data']) if data['per_node_data'] is not None else 0
                }
                
                # Add key overall stats
                for key, value in data['overall_stats'].items():
                    summary_row[f"Overall_{key}"] = value
                    
                summary_data.append(summary_row)
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Create individual sheets for each scenario's per-node data
            for scenario_key, data in self.scenarios_data.items():
                if data['per_node_data'] is not None:
                    sheet_name = f"Scenario_{scenario_key}"[:31]  # Excel sheet name limit
                    data['per_node_data'].to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"Data exported to {output_file}")

def main():
    """
    Example usage of the NS3LoRaWANAnalyzer
    """
    # Initialize analyzer (change path to your CSV directory)
    analyzer = NS3LoRaWANAnalyzer(csv_directory=".")
    
    # Analyze all CSV files
    scenarios = analyzer.analyze_all_csv_files()
    
    # Print summary
    analyzer.print_summary()
    
    # Export to Excel
    analyzer.export_combined_data("ns3_lorawan_analysis.xlsx")
    
    # Example: Access specific scenario data
    if scenarios:
        first_scenario_key = list(scenarios.keys())[0]
        first_scenario = scenarios[first_scenario_key]
        
        print(f"\nExample - Accessing data from scenario {first_scenario_key}:")
        print(f"Configuration: {first_scenario['config']}")
        print(f"Overall Stats: {first_scenario['overall_stats']}")
        print(f"Per-node data shape: {first_scenario['per_node_data'].shape if first_scenario['per_node_data'] is not None else 'N/A'}")

if __name__ == "__main__":
    main()