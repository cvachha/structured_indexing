# Milestone Report: Hybrid Index Benchmark Guide

## Quick Start (Recommended for Milestone)

Run the focused milestone benchmark script that tests only the Facebook dataset:

```bash
# Make executable
chmod +x scripts/run_milestone_benchmark.sh

# Run benchmarks (takes ~15-30 minutes depending on system)
./scripts/run_milestone_benchmark.sh

# Generate the 4 bar plots for your report
python3 scripts/generate_milestone_report.py
```

## What This Does

### Benchmark Script (`run_milestone_benchmark.sh`)

1. **Builds** the benchmark binary
2. **Generates** two mixed workloads:
   - 90% Lookup, 10% Insert (lookup-heavy)
   - 10% Lookup, 90% Insert (insertion-heavy)
3. **Runs** three indexes:
   - **LIPP**: Optimized for lookups
   - **DynamicPGM**: Multiple error configurations (16, 32, 64, 128, 256, 512)
   - **HybridPGMLIPP**: Your hybrid implementation
4. **Saves** results to `./results/` as CSV files

### Analysis Script (`generate_milestone_report.py`)

Generates **4 bar plots** as required:

1. **Throughput - 90% Lookup, 10% Insert**
2. **Throughput - 10% Lookup, 90% Insert**
3. **Index Size - 90% Lookup, 10% Insert**
4. **Index Size - 10% Lookup, 90% Insert**

Each plot compares:
- **DynamicPGM** (best-performing configuration selected automatically)
- **LIPP**
- **HybridPGMLIPP**

## Output Files

After running both scripts, you'll find:

```
plots/
├── milestone_comparison.png          # All 4 plots in one figure (2x2 grid)
├── throughput_90_lookup_10_insert.png  # Individual plot
├── size_90_lookup_10_insert.png        # Individual plot
├── throughput_10_lookup_90_insert.png  # Individual plot
└── size_10_lookup_90_insert.png        # Individual plot
```

## Alternative: Run All Benchmarks

If you want to run benchmarks on all datasets (FB, Books, OSMC):

```bash
# This will take much longer
./scripts/run_all.sh
```

Note: `run_all.sh` now includes HybridPGMLIPP thanks to the updated `run_benchmarks.sh`.

## Understanding the Results

### Expected Performance Patterns

**90% Lookup, 10% Insert (Lookup-Heavy):**
- **LIPP**: Excellent lookup performance, few insertions
- **DynamicPGM**: Good balanced performance
- **Hybrid**: Uses LIPP for bulk data (fast lookups) + DPGM for new inserts (efficient)
  - DPGM grows slowly (only 10% insertions)
  - Should perform close to LIPP for lookups

**10% Lookup, 90% Insert (Insertion-Heavy):**
- **LIPP**: Struggles with heavy insertions
- **DynamicPGM**: Best insertion performance
- **Hybrid**: DPGM handles insertions well
  - DPGM grows quickly (90% insertions)
  - Memory usage increases but maintains good insert throughput
  - No flush overhead (milestone simplification)

### DynamicPGM Hyperparameter Selection

The script automatically:
1. Tests DynamicPGM with multiple error bounds (16, 32, 64, 128, 256, 512)
2. Selects the **best-performing** configuration based on throughput
3. Reports which configuration was chosen

You'll see output like:
```
Best DynamicPGM: error=128, search=BranchingBinarySearch, throughput=4.52 M ops/sec
```

## Interpreting the Plots

### Throughput Plots
- **Higher is better**
- Shows operations per second (millions)
- Indicates how fast each index handles the workload

### Index Size Plots
- **Lower is better** (more space-efficient)
- Shows memory footprint in MB
- Trade-off: smaller indexes may sacrifice performance

## Console Output

The analysis script prints a detailed summary:

```
90% Lookup, 10% Insert:
  Throughput (M ops/sec):
    DynamicPGM          :     4.52
    LIPP                :     5.23
    HybridPGMLIPP       :     4.87
  
  Index Size (MB):
    DynamicPGM          :   1234.5
    LIPP                :    987.3
    HybridPGMLIPP       :   1156.8
  
  Hybrid vs DynamicPGM throughput: +7.74%
  Hybrid vs LIPP throughput:       -6.88%
```

## Including in Your Report

For your one-page report, you can:

1. **Use the combined plot**: `milestone_comparison.png` (shows all 4 plots)
2. **Use individual plots**: One plot per metric/workload for larger visibility
3. **Quote the summary table** from console output

## Troubleshooting

### No results found
```bash
# Check if CSV files exist
ls -lh results/*mix*.csv

# If empty, re-run the benchmark
./scripts/run_milestone_benchmark.sh
```

### Python dependencies missing
```bash
# Install required packages
pip install pandas matplotlib numpy

# Or with conda
conda install pandas matplotlib numpy
```

### Benchmark takes too long
- The `-r 3` flag runs 3 repetitions per configuration
- You can edit the script to use `-r 1` for faster testing

## Performance Notes

- **Benchmark time**: ~15-30 minutes for Facebook dataset only
- **Dataset size**: 100M keys (uint64)
- **Operations**: 2M operations per workload
- **Memory usage**: ~2-4 GB RAM required

## Next Steps After Milestone

Consider these optimizations for the hybrid approach:
1. **Implement flushing**: Add threshold-based flush from DPGM to LIPP
2. **Batch insertion into LIPP**: Reduce per-item overhead
3. **Asynchronous flushing**: Background thread to avoid blocking
4. **Adaptive flush thresholds**: Workload-aware tuning
5. **Smart selective flushing**: Flush hot/cold data differently

## Implementation Notes

**Current Hybrid Strategy (Milestone):**
- Initial 100M keys → Bulk loaded into LIPP
- New insertions → Go to DPGM indefinitely
- No flushing implemented (avoids iterator complexity)
- DPGM memory grows with insertions

This is a valid baseline hybrid approach that demonstrates:
- Combining static (LIPP) and dynamic (DPGM) structures
- Query routing (check DPGM first, then LIPP)
- Trade-offs between implementation complexity and performance
