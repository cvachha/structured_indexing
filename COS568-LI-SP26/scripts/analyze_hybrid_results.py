#!/usr/bin/env python3
"""
Script to analyze and visualize hybrid benchmark results.
Creates bar plots comparing throughput for DPGM, LIPP, and Hybrid approaches.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import glob

def load_results(result_dir='./results'):
    """Load all CSV results from the results directory."""
    csv_files = glob.glob(os.path.join(result_dir, '*mix*.csv'))
    
    results = {}
    for csv_file in csv_files:
        basename = os.path.basename(csv_file)
        
        # Parse the workload type from filename
        if '0.100000i_0m_mix' in basename:
            workload_type = '90% Lookup, 10% Insertion'
        elif '0.900000i_0m_mix' in basename:
            workload_type = '10% Lookup, 90% Insertion'
        else:
            continue
            
        try:
            df = pd.read_csv(csv_file)
            results[workload_type] = df
        except Exception as e:
            print(f"Error loading {csv_file}: {e}")
    
    return results

def aggregate_throughput(df):
    """Aggregate throughput measurements for each index."""
    # Group by index name and calculate mean throughput
    throughput_cols = [col for col in df.columns if 'throughput' in col.lower()]
    
    aggregated = {}
    for index_name in df['index_name'].unique():
        index_df = df[df['index_name'] == index_name]
        
        # Calculate mean throughput across all runs
        throughput_values = []
        for col in throughput_cols:
            if col in index_df.columns:
                throughput_values.extend(index_df[col].dropna().values)
        
        if throughput_values:
            aggregated[index_name] = np.mean(throughput_values)
    
    return aggregated

def create_bar_plot(results, output_file='hybrid_comparison.png'):
    """Create bar plots comparing throughput for different workloads."""
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    
    workloads = ['90% Lookup, 10% Insertion', '10% Lookup, 90% Insertion']
    colors = {'DynamicPGM': '#1f77b4', 'LIPP': '#ff7f0e', 'HybridPGMLIPP': '#2ca02c'}
    
    for idx, workload in enumerate(workloads):
        ax = axes[idx]
        
        if workload not in results:
            print(f"Warning: No results found for {workload}")
            continue
        
        df = results[workload]
        throughput_data = aggregate_throughput(df)
        
        # Sort by a specific order: DPGM, LIPP, Hybrid
        index_order = ['DynamicPGM', 'LIPP', 'HybridPGMLIPP']
        indices = [idx_name for idx_name in index_order if idx_name in throughput_data]
        throughputs = [throughput_data[idx_name] for idx_name in indices]
        
        # Create bar plot
        bars = ax.bar(range(len(indices)), throughputs, 
                      color=[colors.get(idx, '#888888') for idx in indices])
        
        # Customize plot
        ax.set_xlabel('Index Type', fontsize=12)
        ax.set_ylabel('Throughput (M ops/sec)', fontsize=12)
        ax.set_title(workload, fontsize=14, fontweight='bold')
        ax.set_xticks(range(len(indices)))
        ax.set_xticklabels(indices, rotation=15, ha='right')
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, throughputs)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{value:.2f}',
                   ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to {output_file}")
    plt.close()

def print_summary(results):
    """Print a summary of the results."""
    print("\n" + "="*60)
    print("HYBRID BENCHMARK RESULTS SUMMARY")
    print("="*60 + "\n")
    
    for workload, df in results.items():
        print(f"\n{workload}:")
        print("-" * 60)
        
        throughput_data = aggregate_throughput(df)
        
        for index_name, throughput in sorted(throughput_data.items()):
            print(f"  {index_name:20s}: {throughput:8.2f} M ops/sec")
        
        # Calculate improvement
        if 'HybridPGMLIPP' in throughput_data:
            hybrid_throughput = throughput_data['HybridPGMLIPP']
            
            if 'DynamicPGM' in throughput_data:
                dpgm_throughput = throughput_data['DynamicPGM']
                improvement_dpgm = ((hybrid_throughput - dpgm_throughput) / dpgm_throughput) * 100
                print(f"\n  Hybrid vs DynamicPGM: {improvement_dpgm:+.2f}%")
            
            if 'LIPP' in throughput_data:
                lipp_throughput = throughput_data['LIPP']
                improvement_lipp = ((hybrid_throughput - lipp_throughput) / lipp_throughput) * 100
                print(f"  Hybrid vs LIPP:       {improvement_lipp:+.2f}%")
    
    print("\n" + "="*60 + "\n")

def main():
    # Load results
    results = load_results()
    
    if not results:
        print("Error: No results found. Please run benchmarks first.")
        return
    
    # Print summary
    print_summary(results)
    
    # Create visualization
    create_bar_plot(results, 'hybrid_comparison.png')
    
    print("\nAnalysis complete!")

if __name__ == '__main__':
    main()
