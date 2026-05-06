# Milestone 3 Progress Report (Run 1)

## 1. Goal and Scope

This report summarizes the current HybridPGMLIPP implementation, how it was integrated into the benchmark pipeline, and the experimental results from Run 1.

The Milestone 3 target is to improve mixed-workload throughput versus vanilla DynamicPGM and LIPP while preserving correctness (no dropped keys).

All quantitative results and charts in this report come from:

- run1/results
- run1/plots/milestone3/milestone3_summary.csv
- run1/plots/milestone3/*.png
- milestone2_run/milestone_report_1.txt
- milestone2_run/plots_1/*.png

## 2. Implementation Summary

### 2.1 Core Hybrid Design

Implemented file:

- competitors/hybrid_pgm_lipp.h

The hybrid index combines DynamicPGM for write buffering and LIPP as the main resident structure:

1. LIPP is bulk-loaded at Build time using the initial dataset.
2. New inserts go to an active DynamicPGM buffer.
3. When the active buffer reaches a threshold, it is sealed and prepared for flush.
4. A background worker incrementally flushes buffered keys into LIPP in batches.
5. Lookups check buffers first, then LIPP.

Key mechanisms implemented:

- Double-buffered PGM state:
  - active_pgm_: receives current inserts
  - pending_pgm_: sealed buffer while another flush is in progress
  - flushing_snapshot_: sorted vector drained by worker
- Asynchronous flush worker with condition variable and bounded batch size.
- Buffer-first lookup path to avoid key loss during migration windows.
- Range query support across active, pending, flushing snapshot, and LIPP.
- Size accounting that includes all components.

### 2.2 Thread Safety and Concurrency

The implementation uses separate synchronization domains:

- state_mu_ (shared_mutex): protects active/pending/flushing metadata and PGM buffers.
- lipp_mu_ (shared_mutex): protects LIPP updates and reads.

Read-heavy operations use shared locks where possible; inserts and buffer rotations use exclusive locks.

### 2.3 Tunable Parameters

Hybrid tuning parameters exposed through benchmark variants:

1. flush_threshold_ratio (% of total keys)
2. flush_batch_size
3. max_flush_threshold
4. min_flush_threshold
5. pgm_error (template parameter)

These are surfaced in the variant metadata and recorded in result CSVs.

## 3. Benchmark Integration

Implemented/updated files:

- benchmarks/benchmark_hybrid_pgm_lipp.h
- benchmarks/benchmark_hybrid_pgm_lipp.cc

Integration details:

1. Added benchmark entry points for HybridPGMLIPP.
2. Added pareto-style sweeps over multiple (pgm_error, flush policy) configurations.
3. Added workload-aware presets:
   - 90% lookup / 10% insert: more aggressive flushing
   - 10% lookup / 90% insert: larger thresholds and batches to amortize flush cost

## 4. Experimental Setup (Run 1)

Dataset/workload matrix:

- Datasets: Facebook, Books, OSMC (100M keys)
- Mixed workloads:
  - 90% lookup / 10% insert
  - 10% lookup / 90% insert
- Repetitions: 3 runs per point

Compared indexes:

- DynamicPGM
- LIPP
- HybridPGMLIPP

## 5. Quantitative Results from run1/plots/milestone3/milestone3_summary.csv

### 5.1 Throughput (M ops/sec)

| Dataset | Workload | DynamicPGM | LIPP | HybridPGMLIPP | Winner |
|---|---|---:|---:|---:|---|
| Facebook | 90% Lookup / 10% Insert | 1.075 | 13.818 | 1.320 | LIPP |
| Facebook | 10% Lookup / 90% Insert | 3.192 | 2.170 | 3.331 | Hybrid |
| Books | 90% Lookup / 10% Insert | 1.047 | 15.835 | 1.168 | LIPP |
| Books | 10% Lookup / 90% Insert | 3.385 | 2.966 | 1.257 | DynamicPGM |
| OSMC | 90% Lookup / 10% Insert | 1.111 | 10.133 | 0.964 | LIPP |
| OSMC | 10% Lookup / 90% Insert | 3.058 | 0.914 | 1.161 | DynamicPGM |

Observations:

1. Hybrid wins 1 out of 6 workload/dataset combinations (Facebook insertion-heavy).
2. LIPP dominates lookup-heavy workloads (all 3 datasets).
3. DynamicPGM dominates insertion-heavy workloads for Books and OSMC.

### 5.2 Index Size (MiB)

- DynamicPGM remains much smaller (about 1.6 GiB class).
- LIPP and Hybrid are close in size (about 11-19 GiB depending on dataset).
- Hybrid currently does not deliver a size advantage over LIPP.

### 5.3 Comparison with Milestone 2 (Naive Baseline)

Milestone 2 artifacts are in milestone2_run. That run reports Facebook-only mixed workloads.

From milestone2_run/milestone_report_1.txt:

- Facebook, 90% Lookup / 10% Insert:
  - DynamicPGM: 1.07 M ops/sec
  - LIPP: 13.82 M ops/sec
  - Hybrid: 1.30 M ops/sec
- Facebook, 10% Lookup / 90% Insert:
  - DynamicPGM: 3.19 M ops/sec
  - LIPP: 2.17 M ops/sec
  - Hybrid: 3.33 M ops/sec

From run1/plots/milestone3/milestone3_summary.csv (Facebook rows):

- Facebook, 90% Lookup / 10% Insert:
  - DynamicPGM: 1.075 M ops/sec
  - LIPP: 13.818 M ops/sec
  - Hybrid: 1.320 M ops/sec
- Facebook, 10% Lookup / 90% Insert:
  - DynamicPGM: 3.192 M ops/sec
  - LIPP: 2.170 M ops/sec
  - Hybrid: 3.331 M ops/sec

Interpretation:

1. Milestone 3 Run 1 reproduces and slightly improves the Milestone 2 Facebook Hybrid numbers.
2. The improvement is small, and does not change winner identity by workload.
3. The major Milestone 3 gain is expanded evaluation coverage (Facebook + Books + OSMC), not a clear cross-dataset throughput leap over baselines.

Milestone 2 chart references:

![M2 Throughput 90/10](../milestone2_run/plots_1/throughput_90_lookup_10_insert.png)

![M2 Throughput 10/90](../milestone2_run/plots_1/throughput_10_lookup_90_insert.png)

## 6. Chart References (Run 1)

The following figures were generated in run1/plots/milestone3:

### Facebook

![Facebook Throughput 90/10](plots/milestone3/tp_fb_90pct_Lookup___10pct_Insert.png)

![Facebook Throughput 10/90](plots/milestone3/tp_fb_10pct_Lookup___90pct_Insert.png)

### Books

![Books Throughput 90/10](plots/milestone3/tp_books_90pct_Lookup___10pct_Insert.png)

![Books Throughput 10/90](plots/milestone3/tp_books_10pct_Lookup___90pct_Insert.png)

### OSMC

![OSMC Throughput 90/10](plots/milestone3/tp_osmc_90pct_Lookup___10pct_Insert.png)

![OSMC Throughput 10/90](plots/milestone3/tp_osmc_10pct_Lookup___90pct_Insert.png)

### Size Charts

![Facebook Size 90/10](plots/milestone3/size_fb_90pct_Lookup___10pct_Insert.png)

![Facebook Size 10/90](plots/milestone3/size_fb_10pct_Lookup___90pct_Insert.png)

![Books Size 90/10](plots/milestone3/size_books_90pct_Lookup___10pct_Insert.png)

![Books Size 10/90](plots/milestone3/size_books_10pct_Lookup___90pct_Insert.png)

![OSMC Size 90/10](plots/milestone3/size_osmc_90pct_Lookup___10pct_Insert.png)

![OSMC Size 10/90](plots/milestone3/size_osmc_10pct_Lookup___90pct_Insert.png)

## 7. Current Status vs Milestone 3 Objective

What is complete:

1. Hybrid index implemented and benchmark-integrated.
2. Full 3-dataset x 2-workload run completed.
3. Required 12 plots and summary CSV generated.

What remains to improve:

1. Throughput superiority is not consistent versus both baselines.
2. Relative to Milestone 2, Facebook gains are incremental rather than step-change.
3. Flush policy likely needs stronger workload adaptivity.
4. Additional tuning needed to reduce Hybrid write-path and lookup-path overheads.

## 8. Next Steps

1. Introduce adaptive flush triggers based on observed lookup/insert mix, not just key-count thresholds.
2. Reduce LIPP insertion contention during flush by coarser micro-batches or staged apply windows.
3. Expand pareto search around the Facebook-winning configuration to see if it transfers to Books/OSMC.
4. Add instrumentation for time split: insert path, lookup path, flush worker, and lock wait time.
5. Re-run Facebook-only with the exact Milestone 2 harness to isolate algorithmic improvement from script/pipeline differences.

---

Data source note: Milestone 3 numbers were taken from run1/plots/milestone3/milestone3_summary.csv. Milestone 2 comparison values were taken from milestone2_run/milestone_report_1.txt and milestone2_run/plots_1 outputs.
