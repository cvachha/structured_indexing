#include "benchmarks/benchmark_hybrid_pgm_lipp.h"

#include "benchmark.h"
#include "benchmarks/common.h"
#include "competitors/hybrid_pgm_lipp.h"

// params: { flush_threshold_pct, flush_batch_size, max_flush_threshold, min_flush_threshold }
//
// Pareto sweep covers four (pgm_error, tuning) points.  Larger batch sizes
// are now cheap because the flush worker copies from a sorted vector rather
// than walking a PGM tree, so we push batches up relative to Milestone 2.

template <typename Searcher>
void benchmark_64_hybrid_pgm_lipp(tli::Benchmark<uint64_t>& benchmark,
                                   bool pareto,
                                   const std::vector<int>& params) {
  if (!pareto) {
    if (!params.empty())
      benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 64>>(params);
    else
      benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 64>>();
  } else {
    // Pareto frontier: vary error bound and flush aggressiveness.
    // Smaller min_flush_threshold keeps keys_in_buffers_ near 0, enabling the
    // atomic fast-path in EqualityLookup for lookup-heavy workloads.
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 32>>({1, 128, 8192,  128});
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 64>>({1, 256, 32768, 256});
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 128>>({2, 512, 65536, 512});
    benchmark.template Run<HybridPGMLIPP<uint64_t, Searcher, 256>>({4, 1024, 131072, 1024});
  }
}

template <int record>
void benchmark_64_hybrid_pgm_lipp(tli::Benchmark<uint64_t>& benchmark,
                                   const std::string& filename) {
  if (filename.find("mix") != std::string::npos) {
    if (filename.find("0.100000i") != std::string::npos) {
      // 90% lookup, 10% insert: flush aggressively so most keys live in LIPP.
      const std::vector<int> p = {1, 512, 32768, 512};
      benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 64>>(p);
      benchmark.template Run<HybridPGMLIPP<uint64_t, InterpolationSearch<record>, 64>>(p);
    } else if (filename.find("0.500000i") != std::string::npos) {
      // 50/50: balanced threshold and batch.
      const std::vector<int> p = {2, 512, 65536, 1024};
      benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 64>>(p);
      benchmark.template Run<HybridPGMLIPP<uint64_t, InterpolationSearch<record>, 64>>(p);
    } else if (filename.find("0.900000i") != std::string::npos) {
      // 10% lookup, 90% insert: large threshold to amortise flush cost.
      const std::vector<int> p = {5, 2048, 262144, 4096};
      benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 128>>(p);
      benchmark.template Run<HybridPGMLIPP<uint64_t, InterpolationSearch<record>, 128>>(p);
    }
  } else {
    const std::vector<int> p = {2, 512, 65536, 1024};
    benchmark.template Run<HybridPGMLIPP<uint64_t, BranchingBinarySearch<record>, 64>>(p);
  }
}

INSTANTIATE_TEMPLATES_MULTITHREAD(benchmark_64_hybrid_pgm_lipp, uint64_t);
