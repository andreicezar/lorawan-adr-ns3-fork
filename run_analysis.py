"""
Example script showing how to use the NS3LoRaWANAnalyzer
for analyzing multiple simulation scenarios.
"""

from ns3_lorawan_parser  import NS3LoRaWANAnalyzer
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

def compare_scenarios(analyzer):
    """
    Compare key metrics across all scenarios.
    """
    if not analyzer.scenarios_data:
        print("No data available for comparison")
        return
    
    # Create comparison dataframe
    comparison_data = []
    
    for scenario_key, data in analyzer.scenarios_data.items():
        row = {
            'Scenario': scenario_key,
            'Title': data['scenario_info'].get('title', 'Unknown'),
        }
        
        # Add overall statistics
        for key, value in data['overall_stats'].items():
            row[key] = value
            
        # Add configuration parameters
        for key, value in data['config'].items():
            row[f'Config_{key}'] = value
            
        # Add per-node statistics summary
        if data['per_node_data'] is not None:
            df = data['per_node_data']
            if 'PDR_Percent' in df.columns:
                row['Avg_Node_PDR'] = df['PDR_Percent'].mean()
                row['Min_Node_PDR'] = df['PDR_Percent'].min()
                row['Max_Node_PDR'] = df['PDR_Percent'].max()
            if 'Drops' in df.columns:
                row['Total_Node_Drops'] = df['Drops'].sum()
                row['Avg_Node_Drops'] = df['Drops'].mean()
        
        comparison_data.append(row)
    
    comparison_df = pd.DataFrame(comparison_data)
    return comparison_df

def plot_pdr_comparison(analyzer):
    """
    Create visualizations comparing PDR across scenarios.
    """
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('NS3 LoRaWAN Simulation - PDR Analysis', fontsize=16)
    
    scenario_names = []
    overall_pdrs = []
    node_pdr_data = []
    
    for scenario_key, data in analyzer.scenarios_data.items():
        scenario_name = f"Scenario {scenario_key}"
        scenario_names.append(scenario_name)
        
        # Overall PDR
        if 'PDR_Percent' in data['overall_stats']:
            overall_pdrs.append(data['overall_stats']['PDR_Percent'])
        else:
            overall_pdrs.append(0)
        
        # Per-node PDR data
        if data['per_node_data'] is not None and 'PDR_Percent' in data['per_node_data'].columns:
            node_pdrs = data['per_node_data']['PDR_Percent'].tolist()
            for pdr in node_pdrs:
                node_pdr_data.append({'Scenario': scenario_name, 'PDR': pdr})
    
    # Plot 1: Overall PDR comparison
    axes[0, 0].bar(scenario_names, overall_pdrs)
    axes[0, 0].set_title('Overall PDR by Scenario')
    axes[0, 0].set_ylabel('PDR (%)')
    axes[0, 0].tick_params(axis='x', rotation=45)
    
    # Plot 2: Per-node PDR distribution
    if node_pdr_data:
        node_df = pd.DataFrame(node_pdr_data)
        sns.boxplot(data=node_df, x='Scenario', y='PDR', ax=axes[0, 1])
        axes[0, 1].set_title('Per-Node PDR Distribution')
        axes[0, 1].tick_params(axis='x', rotation=45)
    
    # Plot 3: Channel utilization (if available)
    channel_utils = []
    for scenario_key, data in analyzer.scenarios_data.items():
        if 'ChannelUtilization_Percent' in data['overall_stats']:
            channel_utils.append(data['overall_stats']['ChannelUtilization_Percent'])
        else:
            channel_utils.append(0)
    
    axes[1, 0].bar(scenario_names, channel_utils)
    axes[1, 0].set_title('Channel Utilization by Scenario')
    axes[1, 0].set_ylabel('Utilization (%)')
    axes[1, 0].tick_params(axis='x', rotation=45)
    
    # Plot 4: Drop rate comparison
    drop_rates = []
    for scenario_key, data in analyzer.scenarios_data.items():
        if 'DropRate_Percent' in data['overall_stats']:
            drop_rates.append(data['overall_stats']['DropRate_Percent'])
        else:
            drop_rates.append(0)
    
    axes[1, 1].bar(scenario_names, drop_rates)
    axes[1, 1].set_title('Drop Rate by Scenario')
    axes[1, 1].set_ylabel('Drop Rate (%)')
    axes[1, 1].tick_params(axis='x', rotation=45)
    
    plt.tight_layout()
    plt.savefig('ns3_lorawan_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def analyze_node_performance(analyzer, scenario_key):
    """
    Detailed analysis of individual node performance for a specific scenario.
    """
    if scenario_key not in analyzer.scenarios_data:
        print(f"Scenario {scenario_key} not found")
        return
    
    data = analyzer.scenarios_data[scenario_key]
    if data['per_node_data'] is None:
        print(f"No per-node data available for scenario {scenario_key}")
        return
    
    df = data['per_node_data']
    
    print(f"\nDetailed Node Analysis for Scenario {scenario_key}")
    print(f"{'='*50}")
    
    # Basic statistics
    print(f"Total Nodes: {len(df)}")
    
    if 'PDR_Percent' in df.columns:
        print(f"PDR Statistics:")
        print(f"  Mean: {df['PDR_Percent'].mean():.2f}%")
        print(f"  Std:  {df['PDR_Percent'].std():.2f}%")
        print(f"  Min:  {df['PDR_Percent'].min():.2f}%")
        print(f"  Max:  {df['PDR_Percent'].max():.2f}%")
        
        # Nodes with poor performance
        poor_nodes = df[df['PDR_Percent'] < 80]
        print(f"  Nodes with PDR < 80%: {len(poor_nodes)}")
        if len(poor_nodes) > 0:
            print(f"  Worst performing nodes: {poor_nodes['NodeID'].tolist()[:5]}")
    
    if 'Drops' in df.columns:
        total_drops = df['Drops'].sum()
        print(f"Total Packet Drops: {total_drops}")
        print(f"Average Drops per Node: {df['Drops'].mean():.2f}")
        
    # Show first few rows
    print(f"\nFirst 10 nodes data:")
    print(df.head(10).to_string(index=False))

def main():
    """
    Main function demonstrating the analyzer usage.
    """
    print("Starting NS3 LoRaWAN Simulation Analysis...")
    
    # Initialize analyzer with your specific directory structure
    analyzer = NS3LoRaWANAnalyzer(csv_directory="./output")
    
    # Analyze all CSV files recursively in the output directory
    scenarios = analyzer.analyze_all_csv_files_recursive("*results*.csv")
    
    if not scenarios:
        print("No scenarios found. Check your file path and pattern.")
        return
    
    # Print overall summary
    analyzer.print_summary()
    
    # Create comparison dataframe
    comparison_df = compare_scenarios(analyzer)
    print(f"\nScenario Comparison Summary:")
    print(comparison_df.to_string(index=False))
    
    # Export everything to Excel
    analyzer.export_combined_data("detailed_ns3_analysis.xlsx")
    
    # Save comparison data
    comparison_df.to_csv("scenario_comparison.csv", index=False)
    print(f"\nComparison data saved to scenario_comparison.csv")
    
    # Create visualizations (requires matplotlib and seaborn)
    try:
        plot_pdr_comparison(analyzer)
        print("Visualization saved as ns3_lorawan_analysis.png")
    except ImportError:
        print("Matplotlib/Seaborn not available. Install them for visualizations:")
        print("pip install matplotlib seaborn")
    
    # Detailed analysis of first scenario
    if scenarios:
        first_scenario = list(scenarios.keys())[0]
        analyze_node_performance(analyzer, first_scenario)
    
    print(f"\nAnalysis complete! Files created:")
    print(f"- detailed_ns3_analysis.xlsx (Excel with all data)")
    print(f"- scenario_comparison.csv (Summary comparison)")
    print(f"- ns3_lorawan_analysis.png (Visualizations)")

if __name__ == "__main__":
    main()