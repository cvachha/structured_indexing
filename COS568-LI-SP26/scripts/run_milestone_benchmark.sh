#!/bin/bash
# Milestone Benchmark: Compare Hybrid vs DPGM vs LIPP on Facebook dataset
# Tests mixed workloads with different insert ratios

set -e  # Exit on error

echo "========================================="
echo "Building benchmark..."
echo "========================================="

mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j 8 
cd ..

BENCHMARK=build/benchmark
if [ ! -f $BENCHMARK ]; then
    echo "Error: benchmark binary does not exist"
    exit 1
fi

echo ""
echo "========================================="
echo "Generating mixed workloads for Facebook dataset..."
echo "========================================="

cd build
# 90% lookup, 10% insert (lookup-heavy)
./generate ../data/fb_100M_public_uint64 2000000 --insert-ratio 0.1 --negative-lookup-ratio 0.5 --mix

# 10% lookup, 90% insert (insertion-heavy)
./generate ../data/fb_100M_public_uint64 2000000 --insert-ratio 0.9 --negative-lookup-ratio 0.5 --mix
cd ..

mkdir -p ./results

DATA=fb_100M_public_uint64

# Workload files
OPS_10I=${DATA}_ops_2M_0.000000rq_0.500000nl_0.100000i_0m_mix  # 90% lookup, 10% insert
OPS_90I=${DATA}_ops_2M_0.000000rq_0.500000nl_0.900000i_0m_mix  # 10% lookup, 90% insert

function run_benchmark() {
    local ops=$1
    local index=$2
    local label=$3
    echo ""
    echo "Running $index on $label..."
    $BENCHMARK ./data/$DATA ./data/$ops --through --csv --only $index -r 3
}

echo ""
echo "========================================="
echo "Workload 1: 90% Lookup, 10% Insert"
echo "========================================="

# LIPP baseline
run_benchmark $OPS_10I LIPP "90% Lookup, 10% Insert"

# DynamicPGM with multiple error parameters to find best
echo ""
echo "Testing DynamicPGM with different error bounds..."
for ERROR in 16 32 64 128 256 512
do
    echo "  - DynamicPGM (error=$ERROR)"
    # Note: DynamicPGM requires --pareto flag to test different errors
done

# For now, run with default (which tests multiple errors in pareto mode)
$BENCHMARK ./data/$DATA ./data/$OPS_10I --through --csv --only DynamicPGM --pareto -r 3

# HybridPGMLIPP
run_benchmark $OPS_10I HybridPGMLIPP "90% Lookup, 10% Insert"

echo ""
echo "========================================="
echo "Workload 2: 10% Lookup, 90% Insert"
echo "========================================="

# LIPP baseline
run_benchmark $OPS_90I LIPP "10% Lookup, 90% Insert"

# DynamicPGM with pareto mode
echo ""
echo "Testing DynamicPGM with different error bounds..."
$BENCHMARK ./data/$DATA ./data/$OPS_90I --through --csv --only DynamicPGM --pareto -r 3

# HybridPGMLIPP
run_benchmark $OPS_90I HybridPGMLIPP "10% Lookup, 90% Insert"

echo ""
echo "========================================="
echo "Benchmarking complete!"
echo "========================================="

# Add headers to CSV files
echo ""
echo "Adding headers to CSV files..."
for FILE in ./results/*mix*.csv
do
    if [ -f "$FILE" ]; then
        # Check if header already exists
        if head -n 1 "$FILE" | grep -q "index_name"; then
            sed -i '1d' "$FILE"  # Remove existing header
        fi
        # Add proper header for mixed workload. Non-hybrid rows simply leave later variant columns empty.
        sed -i '1s/^/index_name,build_time_ns1,build_time_ns2,build_time_ns3,index_size_bytes,mixed_throughput_mops1,mixed_throughput_mops2,mixed_throughput_mops3,search_method,pgm_error,flush_threshold,flush_batch,max_flush_threshold,min_flush_threshold\n/' "$FILE"
        echo "  - Header set for $(basename $FILE)"
    fi
done

echo ""
echo "========================================="
echo "Results saved in ./results/"
echo "Run: python3 scripts/generate_milestone_report.py"
echo "========================================="
