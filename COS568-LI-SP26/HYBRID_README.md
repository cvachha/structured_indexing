# Hybrid DPGM + LIPP Implementation

## Overview

This implementation combines DynamicPGM (DPGM) and LIPP into a hybrid index structure designed to optimize performance for mixed workloads containing both insertions and lookups.

### Key Design Decisions

1. **Initial Bulk Loading**: Data is initially bulk-loaded into LIPP for efficient initial indexing
2. **Insertion Strategy**: New insertions go to DPGM (optimized for fast amortized insertions)
3. **Lookup Strategy**: Lookups check DPGM first (smaller, newer data), then fall back to LIPP
4. **Flushing Mechanism**: When DPGM reaches a threshold (default 5% of total keys), data is flushed from DPGM to LIPP

### Implementation Details

**Milestone Version - Simplified Hybrid Approach:**

The current implementation uses a **no-flush** strategy for simplicity:
- Initial data is bulk-loaded into LIPP
- All new insertions go to DPGM (which handles dynamic updates efficiently)
- Lookups check DPGM first (smaller, newer data), then LIPP
- **No flushing occurs** - DPGM grows indefinitely

This is still a valid hybrid approach that combines:
- LIPP's excellent bulk-load and lookup performance
- DPGM's efficient dynamic insertion handling

**Future Enhancement:**
A production version would implement periodic flushing from DPGM to LIPP when DPGM reaches a threshold size.

## Running Benchmarks

### Prerequisites
1. **Linux Environment**: This project is designed for Linux (Adroit/Della cluster recommended)
2. Ensure you have the Facebook dataset downloaded in `./data/`
3. C++17 compatible compiler (GCC/Clang)
4. CMake >= 3.10
5. Build tools (make)

### Quick Start

```bash
# Make the script executable
chmod +x scripts/run_hybrid_benchmark.sh

# Run the benchmarks
./scripts/run_hybrid_benchmark.sh
```

This script will:
1. Build the benchmark binary
2. Generate mixed workload operations for Facebook dataset
3. Run benchmarks for three indexes: DynamicPGM, LIPP, and HybridPGMLIPP
4. Test two workload scenarios:
   - 90% Lookup, 10% Insertion (lookup-heavy)
   - 10% Lookup, 90% Insertion (insertion-heavy)

### Analyzing Results

After running benchmarks, analyze the results:

```bash
# Install required Python packages (if needed)
pip install pandas matplotlib numpy

# Run analysis script
python3 scripts/analyze_hybrid_results.py
```

This will:
1. Parse CSV results from `./results/` directory
2. Print a summary showing throughput for each index
3. Generate a bar plot comparison (`hybrid_comparison.png`)

### Manual Execution

You can also run benchmarks manually:

```bash
# Build first
mkdir -p build && cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j 8
cd ..

# Generate workloads
./build/generate ./data/fb_100M_public_uint64 2000000 --insert-ratio 0.1 --negative-lookup-ratio 0.5 --mix
./build/generate ./data/fb_100M_public_uint64 2000000 --insert-ratio 0.9 --negative-lookup-ratio 0.5 --mix

# Run benchmarks
./build/benchmark ./data/fb_100M_public_uint64 ./data/fb_100M_public_uint64_ops_2M_0.000000rq_0.500000nl_0.100000i_0m_mix --through --csv --only HybridPGMLIPP -r 3
./build/benchmark ./data/fb_100M_public_uint64 ./data/fb_100M_public_uint64_ops_2M_0.000000rq_0.500000nl_0.900000i_0m_mix --through --csv --only HybridPGMLIPP -r 3
```

## Architecture

### Hybrid Architecture

```
┌─────────────────────────────────────┐
│      Hybrid DPGM + LIPP Index       │
│         (No-Flush Version)          │
├─────────────────────────────────────┤
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │   DPGM       │  │    LIPP     │ │
│  │  (Dynamic)   │  │   (Bulk)    │ │
│  │              │  │             │ │
│  │ - New keys   │  │ - Initial   │ │
│  │ - Grows      │  │   100M keys │ │
│  │   indefin.   │  │ - Fast      │ │
│  │              │  │   lookup    │ │
│  └──────────────┘  └─────────────┘ │
│         ↑                 ↑         │
│         └────Lookup───────┘         │
│      (check DPGM first, then LIPP)  │
└─────────────────────────────────────┘
```

### Operation Flow

**Insertion:**
1. Insert key-value pair into DPGM
2. DPGM grows to accommodate new data (no size limit)

**Lookup:**
1. Search for key in DPGM
2. If found, return value
3. If not found, search in LIPP
4. Return result

**No Flushing:**
- For milestone simplicity, DPGM never flushes to LIPP
- This avoids complexity while still demonstrating hybrid approach
- Trade-off: DPGM memory grows with insertions

## Performance Characteristics

### Expected Behavior

**90% Lookup, 10% Insertion (Lookup-Heavy):**
- Should favor LIPP-like performance
- Few flushes occur
- Lookup performance is critical

**10% Lookup, 90% Insertion (Insertion-Heavy):**
- Should favor DPGM-like performance
- More frequent flushes
- Insertion performance is critical

### Limitations (Milestone No-Flush Implementation)

1. **Growing DPGM Size**: DPGM memory increases with every insertion (no flushing)
2. **Lookup Performance**: May degrade as DPGM grows larger
3. **No Memory Recycling**: Old data stays in DPGM indefinitely
4. **Simplified Approach**: Trade-off between implementation complexity and performance

These limitations are **intentional for the milestone** to provide a working baseline.

## Future Improvements

Potential optimizations beyond the milestone no-flush version:

1. **Implement Flushing**: Add periodic flush from DPGM to LIPP when threshold reached
2. **Batch Insertion**: Collect multiple items before inserting into LIPP (reduces overhead)
3. **Asynchronous Flushing**: Background thread for flushing to avoid blocking operations
4. **Adaptive Threshold**: Dynamically adjust flush threshold based on workload patterns
5. **LIPP Bulk Load Support**: Modify LIPP to support efficient bulk loading with existing data
6. **Smart Flushing**: Flush only frequently accessed or relevant keys
7. **Multi-level DPGM**: Use multiple DPGM instances before flushing to LIPP

## Dataset Information

The Facebook dataset (`fb_100M_public_uint64`) contains 100 million 64-bit integer keys representing social network user IDs.

## Troubleshooting

### Build Errors
- Ensure all submodules are initialized: `git submodule update --init --recursive`
- Check that you have a C++17 compatible compiler
- Verify CMake version >= 3.10

### Missing Results
- Check that benchmarks completed successfully
- Verify CSV files exist in `./results/` directory
- Ensure enough disk space for results

### Performance Issues
- Try different flush thresholds by modifying the params in the benchmark
- Verify no other processes are competing for resources
- Run with fewer repeats if time-limited

## Citation

If you use this implementation in your research, please cite the original LIPP and PGM papers:

- LIPP: http://www.vldb.org/pvldb/vol13/p175-wu.pdf
- PGM: http://www.vldb.org/pvldb/vol13/p1162-ferragina.pdf
