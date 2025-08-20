import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
import os

def plot_scenario_positions_2d(csv_file_path, output_dir="plots"):
    """
    Plot 2D positions for each scenario from the CSV file.
    Uses different colors/markers for different types and heights.
    
    Args:
        csv_file_path: Path to the CSV file
        output_dir: Directory to save the plots (default: "plots")
    """
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read the CSV file
    try:
        df = pd.read_csv(csv_file_path)
        print(f"Loaded data with {len(df)} rows and {len(df.columns)} columns")
        print(f"Scenarios found: {df['scenario'].unique()}")
        print(f"Types found: {df['type'].unique()}")
        print(f"Height levels (Z): {sorted(df['z'].unique())}")
    except FileNotFoundError:
        print(f"Error: Could not find file {csv_file_path}")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Get unique scenarios, types, and height levels
    scenarios = df['scenario'].unique()
    types = df['type'].unique()
    z_levels = sorted(df['z'].unique())
    
    # Create markers and colors for different types and heights
    type_markers = {'gateway': 's', 'endnode': 'o'}  # square for gateway, circle for endnode
    type_colors = {'gateway': 'red', 'endnode': 'blue'}
    
    # If there are other types, assign default markers/colors
    available_markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h', 'H', '+', 'x']
    available_colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan']
    
    for i, type_name in enumerate(types):
        if type_name not in type_markers:
            type_markers[type_name] = available_markers[i % len(available_markers)]
        if type_name not in type_colors:
            type_colors[type_name] = available_colors[i % len(available_colors)]
    
    # Create subplots - adjust layout based on number of scenarios
    n_scenarios = len(scenarios)
    if n_scenarios <= 4:
        cols = min(2, n_scenarios)
        rows = (n_scenarios + 1) // 2
    else:
        cols = 3
        rows = (n_scenarios + 2) // 3
    
    fig, axes = plt.subplots(rows, cols, figsize=(8*cols, 6*rows))
    fig.suptitle('2D Node Positions by Scenario\n(Colors/Markers indicate Type, Size indicates Height)', 
                 fontsize=16, fontweight='bold')
    
    # Handle case where there's only one subplot
    if n_scenarios == 1:
        axes = [axes]
    elif rows == 1:
        axes = axes if isinstance(axes, list) else [axes]
    else:
        axes = axes.flatten()
    
    # Plot each scenario
    for i, scenario in enumerate(scenarios):
        ax = axes[i] if i < len(axes) else None
        if ax is None:
            continue
            
        # Filter data for current scenario
        scenario_data = df[df['scenario'] == scenario]
        
        # Plot each type with different colors and markers
        for type_name in types:
            type_data = scenario_data[scenario_data['type'] == type_name]
            if not type_data.empty:
                # Use size to represent height (Z coordinate)
                # Normalize Z to reasonable marker sizes (30-150)
                z_min, z_max = scenario_data['z'].min(), scenario_data['z'].max()
                if z_max > z_min:
                    sizes = 50 + (type_data['z'] - z_min) / (z_max - z_min) * 100
                else:
                    sizes = 75  # Default size if all same height
                
                scatter = ax.scatter(type_data['x'], type_data['y'], 
                                   c=type_colors[type_name],
                                   marker=type_markers[type_name],
                                   s=sizes,
                                   alpha=0.7,
                                   label=f'{type_name} (z={type_data["z"].iloc[0]}m)',
                                   edgecolors='black',
                                   linewidth=0.5)
        
        # Customize the plot
        ax.set_xlabel('X Position (m)', fontsize=12)
        ax.set_ylabel('Y Position (m)', fontsize=12)
        ax.set_title(f'{scenario}', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')
        
        # Add legend
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        # Add statistics text
        stats_text = f"Nodes: {len(scenario_data)}\n"
        for type_name in types:
            count = len(scenario_data[scenario_data['type'] == type_name])
            if count > 0:
                stats_text += f"{type_name}: {count}\n"
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Hide unused subplots
    for i in range(n_scenarios, len(axes)):
        axes[i].set_visible(False)
    
    # Adjust layout to prevent overlap
    plt.tight_layout()
    
    # Save the plot instead of trying to display it
    filename = os.path.join(output_dir, 'all_scenarios_combined.png')
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()  # Close to free memory
    print(f"✓ Saved combined plot as: {filename}")
    
    return fig

def plot_individual_scenarios_2d(csv_file_path, output_dir="plots"):
    """
    Create individual detailed 2D plots for each scenario.
    Saves each plot as a PNG file in the specified directory.
    
    Args:
        csv_file_path: Path to the CSV file
        output_dir: Directory to save the plots (default: "plots")
    """
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    df = pd.read_csv(csv_file_path)
    scenarios = df['scenario'].unique()
    types = df['type'].unique()
    
    # Colors and markers
    type_markers = {'gateway': 's', 'endnode': 'o'}
    type_colors = {'gateway': 'red', 'endnode': 'blue'}
    
    for scenario in scenarios:
        scenario_data = df[df['scenario'] == scenario]
        
        fig, ax = plt.subplots(figsize=(12, 10))
        
        # Plot each type
        for type_name in types:
            type_data = scenario_data[scenario_data['type'] == type_name]
            if not type_data.empty:
                # Use size to represent height
                z_min, z_max = scenario_data['z'].min(), scenario_data['z'].max()
                if z_max > z_min:
                    sizes = 60 + (type_data['z'] - z_min) / (z_max - z_min) * 120
                else:
                    sizes = 100
                
                scatter = ax.scatter(type_data['x'], type_data['y'], 
                                   c=type_colors.get(type_name, 'gray'),
                                   marker=type_markers.get(type_name, 'o'),
                                   s=sizes,
                                   alpha=0.7,
                                   label=f'{type_name} (z={type_data["z"].iloc[0]}m)',
                                   edgecolors='black',
                                   linewidth=0.8)
                
                # Add node IDs as text annotations
                for _, row in type_data.iterrows():
                    ax.annotate(f'ID:{row["id"]}', 
                               (row['x'], row['y']), 
                               xytext=(5, 5), 
                               textcoords='offset points',
                               fontsize=8, 
                               alpha=0.8)
        
        # Customize
        ax.set_xlabel('X Position (m)', fontsize=14)
        ax.set_ylabel('Y Position (m)', fontsize=14)
        ax.set_title(f'Node Layout - {scenario}\n(Marker size indicates height, IDs shown)', 
                     fontsize=16, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.set_aspect('equal', adjustable='box')
        ax.legend(fontsize=12)
        
        # Add detailed statistics
        stats_text = f"Total Nodes: {len(scenario_data)}\n"
        stats_text += f"Area: {scenario_data['x'].max() - scenario_data['x'].min():.0f}m × {scenario_data['y'].max() - scenario_data['y'].min():.0f}m\n"
        for type_name in types:
            type_count = len(scenario_data[scenario_data['type'] == type_name])
            if type_count > 0:
                stats_text += f"{type_name.title()}s: {type_count}\n"
        
        ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, 
                verticalalignment='top', fontsize=11,
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
        
        # Save individual plot
        filename = os.path.join(output_dir, f'scenario_{scenario.replace(" ", "_")}_detailed.png')
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()  # Close to free memory
        print(f"✓ Saved detailed plot: {filename}")

def generate_summary_statistics(csv_file_path):
    """
    Generate summary statistics for the position data.
    """
    
    df = pd.read_csv(csv_file_path)
    
    print("=== SUMMARY STATISTICS ===")
    print(f"Total number of data points: {len(df)}")
    print(f"Number of scenarios: {len(df['scenario'].unique())}")
    print(f"Number of types: {len(df['type'].unique())}")
    print(f"Number of unique IDs: {len(df['id'].unique())}")
    
    print("\n=== SCENARIOS ===")
    scenario_counts = df['scenario'].value_counts()
    for scenario, count in scenario_counts.items():
        print(f"  {scenario}: {count} points")
    
    print("\n=== TYPES ===")
    type_counts = df['type'].value_counts()
    for type_name, count in type_counts.items():
        print(f"  {type_name}: {count} points")
    
    print("\n=== HEIGHT LEVELS (Z) ===")
    z_counts = df['z'].value_counts().sort_index()
    for z_val, count in z_counts.items():
        print(f"  {z_val}m: {count} nodes")
    
    print("\n=== POSITION RANGES ===")
    print(f"X range: {df['x'].min():.1f}m to {df['x'].max():.1f}m (span: {df['x'].max() - df['x'].min():.1f}m)")
    print(f"Y range: {df['y'].min():.1f}m to {df['y'].max():.1f}m (span: {df['y'].max() - df['y'].min():.1f}m)")
    print(f"Z range: {df['z'].min():.1f}m to {df['z'].max():.1f}m")
    
    print("\n=== BY SCENARIO BREAKDOWN ===")
    for scenario in df['scenario'].unique():
        scenario_data = df[df['scenario'] == scenario]
        print(f"\n{scenario}:")
        print(f"  Total nodes: {len(scenario_data)}")
        for type_name in df['type'].unique():
            type_count = len(scenario_data[scenario_data['type'] == type_name])
            if type_count > 0:
                print(f"    {type_name}: {type_count}")

# Example usage
if __name__ == "__main__":
    # Configuration
    csv_file = "scenario_positions.csv"
    plots_dir = "plots"
    
    print("🗺️  LoRaWAN Network Scenario Plotter")
    print(f"📁 Plots will be saved in: {plots_dir}/")
    print("=" * 60)
    
    # Create plots directory
    os.makedirs(plots_dir, exist_ok=True)
    
    # Generate summary statistics
    print("Analyzing data...")
    generate_summary_statistics(csv_file)
    
    # Create combined 2D plot with all scenarios
    print(f"\nCreating combined 2D plot in {plots_dir}/...")
    plot_scenario_positions_2d(csv_file, plots_dir)
    
    # Create individual detailed plots for each scenario
    print(f"\nCreating individual detailed plots in {plots_dir}/...")
    plot_individual_scenarios_2d(csv_file, plots_dir)
    
    print(f"\n🎉 All plots have been saved in {plots_dir}/")
    print(f"   📊 {plots_dir}/all_scenarios_combined.png - Overview of all scenarios")
    print(f"   📈 {plots_dir}/scenario_*_detailed.png - Individual detailed plots")
    print(f"\n🔍 Open the {plots_dir}/ directory to view your network topology visualizations!")