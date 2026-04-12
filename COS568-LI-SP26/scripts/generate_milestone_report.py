#!/usr/bin/env python3
"""
Generate milestone report with bar plots comparing DPGM, LIPP, and Hybrid.
Creates 4 plots:
  1. Throughput - 90% Lookup, 10% Insert
  2. Throughput - 10% Lookup, 90% Insert  
  3. Index Size - 90% Lookup, 10% Insert
  4. Index Size - 10% Lookup, 90% Insert
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import glob
from pathlib import Path

def load_and_parse_results(result_dir='./results'):
    """Load CSV results and organize by workload type."""
    
    results = {
        '90_lookup_10_insert': {'file_pattern': '*0.100000i_0m_mix*.csv', 'data': None},
        '10_lookup_90_insert': {'file_pattern': '*0.900000i_0m_mix*.csv', 'data': None}
    }
    
    for workload_key, workload_info in results.items():
        pattern = os.path.join(result_dir, workload_info['file_pattern'])
        csv_files = glob.glob(pattern)
        
        if not csv_files:
            print(f"Warning: No results found for {workload_key}")
            continue
        
        # Load all matching CSV files
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                dfs.append(df)
            except Exception as e:
                print(f"Error loading {csv_file}: {e}")
        
        if dfs:
            workload_info['data'] = pd.concat(dfs, ignore_index=True)
    
    return results

def select_best_dpgm(df):
    """
    Select the best-performing DPGM configuration based on throughput.
    Returns a single row representing the best DPGM variant.
    """
    # Filter for DynamicPGM entries
    dpgm_df = df[df['index_name'] == 'DynamicPGM'].copy()
    
    if dpgm_df.empty:
        return None
    
    # Calculate mean throughput for each configuration
    throughput_cols = [col for col in dpgm_df.columns if 'throughput' in col.lower()]
    dpgm_df['mean_throughput'] = dpgm_df[throughput_cols].mean(axis=1)
    
    # Find the best configuration
    best_idx = dpgm_df['mean_throughput'].idxmax()
    best_config = dpgm_df.loc[best_idx].copy()
    
    # Add identifier for the best config
    error_value = best_config.get('pgm_error', 'unknown')
    search_method = best_config.get('search_method', 'unknown')
    
    print(f"  Best DynamicPGM: error={error_value}, search={search_method}, "
          f"throughput={best_config['mean_throughput']:.2f} M ops/sec")
    
    return best_config

def aggregate_metrics(df, select_best_dpgm_config=True):
    """
    Aggregate throughput and size metrics for each index type.
    For DPGM, select only the best-performing configuration.
    """
    metrics = {}
    
    # Process each index type
    for index_name in df['index_name'].unique():
        index_df = df[df['index_name'] == index_name].copy()
        
        # For DynamicPGM, select only the best configuration
        if index_name == 'DynamicPGM' and select_best_dpgm_config:
            best_config = select_best_dpgm(df)
            if best_config is None:
                continue
            index_df = pd.DataFrame([best_config])
        
        # Calculate mean throughput
        throughput_cols = [col for col in index_df.columns if 'throughput' in col.lower()]
        throughput_values = []
        for col in throughput_cols:
            if col in index_df.columns:
                throughput_values.extend(index_df[col].dropna().values)
        
        mean_throughput = np.mean(throughput_values) if throughput_values else 0
        
        # Get index size (should be the same across runs)
        size_bytes = index_df['index_size_bytes'].iloc[0] if 'index_size_bytes' in index_df.columns else 0
        size_mb = size_bytes / (1024 * 1024)  # Convert to MB
        
        metrics[index_name] = {
            'throughput': mean_throughput,
            'size_mb': size_mb,
            'size_bytes': size_bytes
        }
    
    return metrics

def create_bar_plots(results, output_dir='./plots'):
    """
    Create 4 bar plots comparing DPGM, LIPP, and Hybrid.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Define workloads
    workloads = [
        ('90_lookup_10_insert', '90% Lookup, 10% Insert'),
        ('10_lookup_90_insert', '10% Lookup, 90% Insert')
    ]
    
    # Index order and colors
    index_order = ['DynamicPGM', 'LIPP', 'HybridPGMLIPP']
    colors = {
        'DynamicPGM': '#3498db',    # Blue
        'LIPP': '#e74c3c',           # Red
        'HybridPGMLIPP': '#2ecc71'  # Green
    }
    
    # Create 2x2 subplot layout
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Hybrid Index Performance Comparison (Facebook Dataset)', 
                 fontsize=18, fontweight='bold', y=0.995)
    
    for row_idx, (workload_key, workload_label) in enumerate(workloads):
        if results[workload_key]['data'] is None:
            print(f"Skipping {workload_label} - no data available")
            continue
        
        df = results[workload_key]['data']
        print(f"\n{workload_label}:")
        metrics = aggregate_metrics(df)
        
        # Throughput plot (left column)
        ax_throughput = axes[row_idx, 0]
        throughput_data = {idx: metrics[idx]['throughput'] 
                          for idx in index_order if idx in metrics}
        
        indices = list(throughput_data.keys())
        throughputs = list(throughput_data.values())
        
        bars = ax_throughput.bar(range(len(indices)), throughputs,
                                 color=[colors[idx] for idx in indices],
                                 edgecolor='black', linewidth=1.5)
        
        ax_throughput.set_ylabel('Throughput (M ops/sec)', fontsize=13, fontweight='bold')
        ax_throughput.set_title(f'{workload_label}\nThroughput', 
                               fontsize=14, fontweight='bold', pad=10)
        ax_throughput.set_xticks(range(len(indices)))
        ax_throughput.set_xticklabels(indices, fontsize=11)
        ax_throughput.grid(axis='y', alpha=0.3, linestyle='--')
        ax_throughput.set_axisbelow(True)
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, throughputs)):
            height = bar.get_height()
            ax_throughput.text(bar.get_x() + bar.get_width()/2., height,
                             f'{value:.2f}',
                             ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        # Index size plot (right column)
        ax_size = axes[row_idx, 1]
        size_data = {idx: metrics[idx]['size_mb'] 
                    for idx in index_order if idx in metrics}
        
        indices_size = list(size_data.keys())
        sizes = list(size_data.values())
        
        bars = ax_size.bar(range(len(indices_size)), sizes,
                          color=[colors[idx] for idx in indices_size],
                          edgecolor='black', linewidth=1.5)
        
        ax_size.set_ylabel('Index Size (MB)', fontsize=13, fontweight='bold')
        ax_size.set_title(f'{workload_label}\nIndex Size', 
                         fontsize=14, fontweight='bold', pad=10)
        ax_size.set_xticks(range(len(indices_size)))
        ax_size.set_xticklabels(indices_size, fontsize=11)
        ax_size.grid(axis='y', alpha=0.3, linestyle='--')
        ax_size.set_axisbelow(True)
        
        # Add value labels on bars
        for i, (bar, value) in enumerate(zip(bars, sizes)):
            height = bar.get_height()
            ax_size.text(bar.get_x() + bar.get_width()/2., height,
                       f'{value:.1f}',
                       ha='center', va='bottom', fontsize=11, fontweight='bold')
        
        # Print summary
        print(f"  Throughput (M ops/sec):")
        for idx in index_order:
            if idx in metrics:
                print(f"    {idx:20s}: {metrics[idx]['throughput']:8.2f}")
        
        print(f"  Index Size (MB):")
        for idx in index_order:
            if idx in metrics:
                print(f"    {idx:20s}: {metrics[idx]['size_mb']:8.1f}")
        
        # Calculate improvements
        if 'HybridPGMLIPP' in metrics:
            hybrid_throughput = metrics['HybridPGMLIPP']['throughput']
            
            if 'DynamicPGM' in metrics:
                dpgm_throughput = metrics['DynamicPGM']['throughput']
                improvement = ((hybrid_throughput - dpgm_throughput) / dpgm_throughput) * 100
                print(f"  Hybrid vs DynamicPGM throughput: {improvement:+.2f}%")
            
            if 'LIPP' in metrics:
                lipp_throughput = metrics['LIPP']['throughput']
                improvement = ((hybrid_throughput - lipp_throughput) / lipp_throughput) * 100
                print(f"  Hybrid vs LIPP throughput:       {improvement:+.2f}%")
    
    plt.tight_layout()
    output_file = os.path.join(output_dir, 'milestone_comparison.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n✓ Plots saved to {output_file}")
    plt.close()
    
    # Also create individual plots for easier inclusion in report
    create_individual_plots(results, index_order, colors, output_dir)

def create_individual_plots(results, index_order, colors, output_dir):
    """Create individual plots for each metric and workload."""
    
    workloads = [
        ('90_lookup_10_insert', '90% Lookup, 10% Insert'),
        ('10_lookup_90_insert', '10% Lookup, 90% Insert')
    ]
    
    for workload_key, workload_label in workloads:
        if results[workload_key]['data'] is None:
            continue
        
        df = results[workload_key]['data']
        metrics = aggregate_metrics(df)
        
        # Throughput plot
        fig, ax = plt.subplots(figsize=(8, 6))
        throughput_data = {idx: metrics[idx]['throughput'] 
                          for idx in index_order if idx in metrics}
        
        indices = list(throughput_data.keys())
        throughputs = list(throughput_data.values())
        
        bars = ax.bar(range(len(indices)), throughputs,
                     color=[colors[idx] for idx in indices],
                     edgecolor='black', linewidth=1.5, width=0.6)
        
        ax.set_ylabel('Throughput (M ops/sec)', fontsize=14, fontweight='bold')
        ax.set_title(f'{workload_label}\nThroughput Comparison', 
                    fontsize=16, fontweight='bold', pad=15)
        ax.set_xticks(range(len(indices)))
        ax.set_xticklabels(indices, fontsize=12)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        for bar, value in zip(bars, throughputs):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{value:.2f}',
                   ha='center', va='bottom', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        filename = f'throughput_{workload_key}.png'
        plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
        print(f"✓ Saved {filename}")
        plt.close()
        
        # Size plot
        fig, ax = plt.subplots(figsize=(8, 6))
        size_data = {idx: metrics[idx]['size_mb'] 
                    for idx in index_order if idx in metrics}
        
        indices = list(size_data.keys())
        sizes = list(size_data.values())
        
        bars = ax.bar(range(len(indices)), sizes,
                     color=[colors[idx] for idx in indices],
                     edgecolor='black', linewidth=1.5, width=0.6)
        
        ax.set_ylabel('Index Size (MB)', fontsize=14, fontweight='bold')
        ax.set_title(f'{workload_label}\nIndex Size Comparison', 
                    fontsize=16, fontweight='bold', pad=15)
        ax.set_xticks(range(len(indices)))
        ax.set_xticklabels(indices, fontsize=12)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.set_axisbelow(True)
        
        for bar, value in zip(bars, sizes):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{value:.1f}',
                   ha='center', va='bottom', fontsize=12, fontweight='bold')
        
        plt.tight_layout()
        filename = f'size_{workload_key}.png'
        plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches='tight')
        print(f"✓ Saved {filename}")
        plt.close()

def print_summary_table(results):
    """Print a formatted summary table of all results."""
    
    print("\n" + "="*80)
    print("MILESTONE REPORT SUMMARY - Facebook Dataset")
    print("="*80)
    
    workloads = [
        ('90_lookup_10_insert', '90% Lookup, 10% Insert'),
        ('10_lookup_90_insert', '10% Lookup, 90% Insert')
    ]
    
    for workload_key, workload_label in workloads:
        if results[workload_key]['data'] is None:
            continue
        
        print(f"\n{workload_label}")
        print("-" * 80)
        
        df = results[workload_key]['data']
        metrics = aggregate_metrics(df)
        
        print(f"{'Index':<20} {'Throughput (M ops/s)':<25} {'Size (MB)':<15}")
        print("-" * 80)
        
        for idx in ['DynamicPGM', 'LIPP', 'HybridPGMLIPP']:
            if idx in metrics:
                throughput = metrics[idx]['throughput']
                size = metrics[idx]['size_mb']
                print(f"{idx:<20} {throughput:>10.2f}{'':<15} {size:>10.1f}")
    
    print("\n" + "="*80 + "\n")

def main():
    print("="*80)
    print("GENERATING MILESTONE REPORT")
    print("="*80)
    
    # Load results
    print("\nLoading results from ./results/...")
    results = load_and_parse_results()
    
    # Check if we have data
    has_data = any(r['data'] is not None for r in results.values())
    if not has_data:
        print("\nError: No benchmark results found!")
        print("Please run: ./scripts/run_milestone_benchmark.sh")
        return
    
    # Generate plots
    print("\nGenerating bar plots...")
    create_bar_plots(results)
    
    # Print summary
    print_summary_table(results)
    
    print("="*80)
    print("REPORT GENERATION COMPLETE")
    print("="*80)
    print("\nPlots saved in ./plots/:")
    print("  - milestone_comparison.png (all 4 plots)")
    print("  - throughput_90_lookup_10_insert.png")
    print("  - size_90_lookup_10_insert.png")
    print("  - throughput_10_lookup_90_insert.png")
    print("  - size_10_lookup_90_insert.png")
    print("\nUse these plots in your milestone report!")
    print("="*80)

if __name__ == '__main__':
    main()
