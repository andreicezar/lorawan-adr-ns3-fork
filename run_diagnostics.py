"""
Quick test script for your NS3 LoRaWAN simulation results.
Place this in: ns3-comparison-clean/ns-3-dev/
"""

import sys
import os
from pathlib import Path

# Add the current directory to Python path so we can import our analyzer
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ns3_lorawan_parser import NS3LoRaWANAnalyzer

def quick_test():
    """
    Quick test with your specific file structure.
    """
    print("🔍 NS3 LoRaWAN Analysis - Quick Test")
    print("=" * 50)
    
    # Initialize analyzer pointing to your output directory
    analyzer = NS3LoRaWANAnalyzer(csv_directory="./output")
    
    # First, let's see what files we can find
    print("📁 Looking for CSV files...")
    
    # Check if output directory exists
    if not os.path.exists("./output"):
        print("❌ Error: ./output directory not found!")
        print("   Make sure you're running this from: ns3-comparison-clean/ns-3-dev/")
        return
    
    # Search for CSV files recursively
    import glob
    csv_files = glob.glob("./output/**/*.csv", recursive=True)
    print(f"   Found {len(csv_files)} CSV files:")
    
    for file_path in csv_files[:10]:  # Show first 10
        print(f"   - {file_path}")
    
    if len(csv_files) > 10:
        print(f"   ... and {len(csv_files) - 10} more files")
    
    if not csv_files:
        print("❌ No CSV files found in ./output directory")
        return
    
    print(f"\n📊 Analyzing files...")
    
    # Analyze all CSV files
    scenarios = analyzer.analyze_all_csv_files_recursive("*results*.csv")
    
    if not scenarios:
        print("❌ No valid scenario data found")
        return
    
    print(f"✅ Successfully analyzed {len(scenarios)} scenarios!")
    
    # Print summary
    analyzer.print_summary()
    
    # Test with your specific file if it exists
    specific_file = "./output/scenario-05-traffic-patterns/interval-600s/result_interval600s_results.csv"
    if os.path.exists(specific_file):
        print(f"\n🎯 Testing with your specific file:")
        print(f"   {specific_file}")
        
        # Parse just this file
        test_data = analyzer.parse_single_csv(specific_file)
        
        print(f"✅ File parsed successfully!")
        print(f"   Scenario: {test_data['scenario_info'].get('title', 'Unknown')}")
        print(f"   Columns: {test_data['columns']}")
        print(f"   Nodes: {len(test_data['per_node_data']) if test_data['per_node_data'] is not None else 'N/A'}")
        
        # Show some sample data
        if test_data['per_node_data'] is not None:
            df = test_data['per_node_data']
            print(f"\n📋 Sample data (first 5 rows):")
            print(df.head(5).to_string(index=False))
            
            if 'PDR_Percent' in df.columns:
                print(f"\n📈 PDR Statistics:")
                print(f"   Mean PDR: {df['PDR_Percent'].mean():.2f}%")
                print(f"   Min PDR:  {df['PDR_Percent'].min():.2f}%")
                print(f"   Max PDR:  {df['PDR_Percent'].max():.2f}%")
    else:
        print(f"\n⚠️  Specific file not found: {specific_file}")
    
    # Export results
    try:
        print(f"\n💾 Exporting results...")
        analyzer.export_combined_data("ns3_quick_test_results.xlsx")
        print(f"✅ Results exported to: ns3_quick_test_results.xlsx")
    except Exception as e:
        print(f"❌ Export failed: {e}")
    
    print(f"\n🎉 Quick test completed successfully!")
    print(f"   - Analyzed {len(scenarios)} scenarios")
    print(f"   - Results saved to ns3_quick_test_results.xlsx")

def check_requirements():
    """
    Check if required packages are installed.
    """
    required_packages = ['pandas', 'openpyxl']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print(f"   Install with: pip install {' '.join(missing_packages)}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting NS3 LoRaWAN Analysis Quick Test...")
    
    # Check requirements
    if not check_requirements():
        exit(1)
    
    try:
        quick_test()
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()