#include "benchmarks/benchmark_hybrid_pgm_lipp.h"

#include "benchmark.h"
#include "benchmarks/common.h"
#include "competitors/hybrid_pgm_lipp.h"

template <typename Searcher>
void benchmark_64_hybrid_pgm_lipp(tli::Benchmark<uint64_t>& benchmark, 
                                  bool pareto, const std::vector<int>& params) {
  if (!pareto) {
    // Run with specific parameters
    if (params.size() > 0) {
      // params[0] should be flush threshold percentage (e.g., 5 for 5%)
      benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 64>>(params);
    } else {
      // Default configuration
      benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 64>>();
    }
  } else {
    // Pareto frontier: sweep different configurations
    // Try different PGM errors
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 16>>();
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 32>>();
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 64>>();
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 128>>();
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 256>>();
  }
}

template <int record>
void benchmark_64_hybrid_pgm_lipp(tli::Benchmark<uint64_t>& benchmark, const std::string& filename) {
  // Simple configuration for mixed workloads
  // Use reasonable defaults: PGM error of 64 and 5% flush threshold
  std::vector<int> params = {5};  // 5% flush threshold
  
  if (filename.find("mix") != std::string::npos) {
    // For mixed workloads
    if (filename.find("0.100000i") != std::string::npos) {
      // 90% lookup, 10% insertion - lookup heavy
      benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 64>>(params);
      benchmark.template Run<HybridPGMLIPP<uint64_t, InterpolationSearch<record>, 64>>(params);
    } else if (filename.find("0.500000i") != std::string::npos) {
      // 50% lookup, 50% insertion - balanced
      benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 64>>(params);
      benchmark.template Run<HybridPGMLIPP<uint64_t, InterpolationSearch<record>, 64>>(params);
    } else if (filename.find("0.900000i") != std::string::npos) {
      // 10% lookup, 90% insertion - insertion heavy
      benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 64>>(params);
      benchmark.template Run<HybridPGMLIPP<uint64_t, InterpolationSearch<record>, 64>>(params);
    }
  } else {
    // Default for non-mixed workloads
    benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 64>>(params);
  }
}

// Explicit instantiations
template void benchmark_64_hybrid_pgm_lipp<BranchingBinarySearch<1024>>(
    tli::Benchmark<uint64_t>&, bool, const std::vector<int>&);
template void benchmark_64_hybrid_pgm_lipp<BranchingBinarySearch<2048>>(
    tli::Benchmark<uint64_t>&, bool, const std::vector<int>&);
template void benchmark_64_hybrid_pgm_lipp<LinearSearch<1024>>(
    tli::Benchmark<uint64_t>&, bool, const std::vector<int>&);
template void benchmark_64_hybrid_pgm_lipp<InterpolationSearch<1024>>(
    tli::Benchmark<uint64_t>&, bool, const std::vector<int>&);
template void benchmark_64_hybrid_pgm_lipp<ExponentialSearch<1024>>(
    tli::Benchmark<uint64_t>&, bool, const std::vector<int>&);

template void benchmark_64_hybrid_pgm_lipp<1024>(
    tli::Benchmark<uint64_t>&, const std::string&);
template void benchmark_64_hybrid_pgm_lipp<2048>(
    tli::Benchmark<uint64_t>&, const std::string&);
