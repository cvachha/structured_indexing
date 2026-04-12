#! /usr/bin/env bash

echo "Building benchmark..."

mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j 8 

cd ..

BENCHMARK=build/benchmark
if [ ! -f $BENCHMARK ]; then
    echo "benchmark binary does not exist"
    exit 1
fi

echo "Generating mixed workloads for Facebook dataset..."
cd build
./generate ../data/fb_100M_public_uint64 2000000 --insert-ratio 0.1 --negative-lookup-ratio 0.5 --mix  # 90% lookup, 10% insert
./generate ../data/fb_100M_public_uint64 2000000 --insert-ratio 0.9 --negative-lookup-ratio 0.5 --mix  # 10% lookup, 90% insert
cd ..

echo "Running benchmarks for mixed workloads..."

mkdir -p ./results

function run_mixed_benchmark() {
    local data=$1
    local ops=$2
    local index=$3
    echo "Executing $index on $data with operations $ops"
    $BENCHMARK ./data/$data ./data/$ops --through --csv --only $index -r 3
}

DATA=fb_100M_public_uint64

# Mixed workload: 90% Lookup, 10% Insertion
OPS_10I=${DATA}_ops_2M_0.000000rq_0.500000nl_0.100000i_0m_mix

# Mixed workload: 10% Lookup, 90% Insertion  
OPS_90I=${DATA}_ops_2M_0.000000rq_0.500000nl_0.900000i_0m_mix

echo "========================================="
echo "Running 90% Lookup, 10% Insertion workload"
echo "========================================="

for INDEX in DynamicPGM LIPP HybridPGMLIPP
do
    run_mixed_benchmark $DATA $OPS_10I $INDEX
done

echo "========================================="
echo "Running 10% Lookup, 90% Insertion workload"
echo "========================================="

for INDEX in DynamicPGM LIPP HybridPGMLIPP
do
    run_mixed_benchmark $DATA $OPS_90I $INDEX
done

echo "===================Benchmarking complete!===================="

# Add headers to CSV files
for FILE in ./results/*.csv
do
    if [[ $FILE == *mix* ]]; then
        # For mixed workload
        if head -n 1 $FILE | grep -q "index_name"; then
            sed -i '1d' $FILE  # Delete the first line if header exists
        fi
        # Add the header
        sed -i '1s/^/index_name,build_time_ns1,build_time_ns2,build_time_ns3,index_size_bytes,mixed_throughput_mops1,mixed_throughput_mops2,mixed_throughput_mops3,search_method,value\n/' $FILE
        echo "Header set for $FILE"
    fi
done

echo "Results saved in ./results/"
echo "You can analyze the results using analysis scripts or manually inspect the CSV files."
