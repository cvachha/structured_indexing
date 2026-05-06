# Milestone 3 Progress Report (Run 3)

## 1. Goal and Scope

This report summarizes the current HybridPGMLIPP implementation, how it was integrated into the benchmark pipeline, and the experimental results from Run 3.

The Milestone 3 target is to improve mixed-workload throughput versus vanilla DynamicPGM and LIPP while preserving correctness (no dropped keys).

All quantitative results and charts in this report come from:

- milestone3_run3/results
- milestone3_run3/milestone3/milestone3_summary.csv
- milestone3_run3/milestone3/*.png
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

- state_mu_ (mutex): protects active/pending/flushing metadata and PGM buffers.
- lipp_mu_ (mutex): protects LIPP updates and reads.

The current implementation intentionally uses plain mutexes rather than shared_mutex because the benchmark workload is single-threaded; this reduces lock overhead on the hot path.

### 2.3 Tunable Parameters

Hybrid tuning parameters exposed through benchmark variants:

1. flush_threshold_ratio (% of total keys)
2. flush_batch_size
3. max_flush_threshold
4. min_flush_threshold
5. pgm_error (template parameter)

These are surfaced in the variant metadata and recorded in result CSVs.

### 2.4 Differences vs Milestone 2 Implementation

Previous file:

- milestone2_implementation/hybrid_pgm_lipp.h

Current file:

- competitors/hybrid_pgm_lipp.h

The Milestone 2 version was a minimal hybrid wrapper, while the current implementation is a substantially more complete asynchronous design.

Key implementation differences:

1. Milestone 2 used a single `pgm_` write buffer with no flushing; inserts simply accumulated in DynamicPGM indefinitely.
2. The current implementation replaces that with a three-stage pipeline: `active_pgm_`, `pending_pgm_`, and `flushing_snapshot_`, with data eventually merged into `lipp_`.
3. Milestone 2 had no background worker. The current version starts a dedicated flush worker thread in `Build()` and stops it in the destructor.
4. Milestone 2 lookup checked only `pgm_` and then `lipp_`. The current version checks all in-flight states so keys remain visible during migration from buffer to LIPP.
5. The current version adds an atomic `keys_in_buffers_` counter so lookups can skip buffer checks entirely once all buffered keys have drained into LIPP.
6. Milestone 2 exposed only a flush-threshold ratio parameter. The current version adds `flush_batch_size`, `min_flush_threshold`, and `max_flush_threshold`, which makes the flush policy much more tunable.
7. Milestone 2 range query covered only one PGM buffer plus LIPP. The current version merges results from active, pending, snapshot, and LIPP states.
8. Milestone 2 size accounting was just `pgm_.size_in_bytes() + lipp_.index_size()`. The current version also accounts for pending buffers and snapshot capacity.

Why these changes matter:

1. The Milestone 2 design was functionally closer to "LIPP plus a growing insert buffer" than a true staged hybrid index.
2. The current design actually implements the intended architecture for Milestone 3: buffered writes, asynchronous migration, and correctness-preserving visibility during flush.
3. The fast-path lookup optimization and lower-overhead mutex choice specifically target the benchmark bottlenecks seen in earlier runs.
4. The additional flush controls make it possible to retune the design for different lookup/insert mixes instead of relying on a single fixed threshold.

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

## 4. Experimental Setup (Run 3)

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

## 5. Quantitative Results from milestone3_run3/milestone3/milestone3_summary.csv

### 5.1 Throughput (M ops/sec)

| Dataset | Workload | DynamicPGM | LIPP | HybridPGMLIPP | Winner |
|---|---|---:|---:|---:|---|
| Facebook | 90% Lookup / 10% Insert | 1.075 | 17.995 | 1.452 | LIPP |
| Facebook | 10% Lookup / 90% Insert | 3.192 | 2.370 | 3.331 | Hybrid |
| Books | 90% Lookup / 10% Insert | 1.152 | 22.893 | 1.549 | LIPP |
| Books | 10% Lookup / 90% Insert | 3.385 | 3.032 | 1.524 | DynamicPGM |
| OSMC | 90% Lookup / 10% Insert | 1.165 | 14.789 | 1.438 | LIPP |
| OSMC | 10% Lookup / 90% Insert | 3.082 | 1.949 | 1.310 | DynamicPGM |

Observations:

1. Hybrid wins 1 out of 6 workload/dataset combinations (Facebook insertion-heavy), unchanged from Run 1.
2. LIPP dominates lookup-heavy workloads (all 3 datasets), with larger margins than Run 1.
3. DynamicPGM still dominates insertion-heavy workloads for Books and OSMC.

### 5.2 Index Size (MiB)

- DynamicPGM remains much smaller (about 1.6 GiB class).
- LIPP and Hybrid remain close in size (about 11-19 GiB depending on dataset).
- Hybrid still does not deliver a size advantage over LIPP.

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

From milestone3_run3/milestone3/milestone3_summary.csv (Facebook rows):

- Facebook, 90% Lookup / 10% Insert:
  - DynamicPGM: 1.075 M ops/sec
  - LIPP: 17.995 M ops/sec
  - Hybrid: 1.452 M ops/sec
- Facebook, 10% Lookup / 90% Insert:
  - DynamicPGM: 3.192 M ops/sec
  - LIPP: 2.170 M ops/sec
  - Hybrid: 3.331 M ops/sec

Interpretation:

1. Milestone 3 Run 3 continues to exceed the Milestone 2 Facebook Hybrid values.
2. Winner identity by workload is unchanged versus Milestone 2 and Run 1.
3. The major Milestone 3 gain remains expanded evaluation coverage (Facebook + Books + OSMC), not a clear cross-dataset throughput leap over both baselines.

Milestone 2 chart references:

![M2 Throughput 90/10](../milestone2_run/plots_1/throughput_90_lookup_10_insert.png)

![M2 Throughput 10/90](../milestone2_run/plots_1/throughput_10_lookup_90_insert.png)

## 6. Chart References (Run 3)

The following figures were generated in milestone3_run3/milestone3:

### Facebook

![Facebook Throughput 90/10](milestone3_run3/milestone3/tp_fb_90pct_Lookup___10pct_Insert.png)

![Facebook Throughput 10/90](milestone3_run3/milestone3/tp_fb_10pct_Lookup___90pct_Insert.png)

### Books

![Books Throughput 90/10](milestone3_run3/milestone3/tp_books_90pct_Lookup___10pct_Insert.png)

![Books Throughput 10/90](milestone3_run3/milestone3/tp_books_10pct_Lookup___90pct_Insert.png)

### OSMC

![OSMC Throughput 90/10](milestone3_run3/milestone3/tp_osmc_90pct_Lookup___10pct_Insert.png)

![OSMC Throughput 10/90](milestone3_run3/milestone3/tp_osmc_10pct_Lookup___90pct_Insert.png)

### Size Charts

![Facebook Size 90/10](milestone3_run3/milestone3/size_fb_90pct_Lookup___10pct_Insert.png)

![Facebook Size 10/90](milestone3_run3/milestone3/size_fb_10pct_Lookup___90pct_Insert.png)

![Books Size 90/10](milestone3_run3/milestone3/size_books_90pct_Lookup___10pct_Insert.png)

![Books Size 10/90](milestone3_run3/milestone3/size_books_10pct_Lookup___90pct_Insert.png)

![OSMC Size 90/10](milestone3_run3/milestone3/size_osmc_90pct_Lookup___10pct_Insert.png)

![OSMC Size 10/90](milestone3_run3/milestone3/size_osmc_10pct_Lookup___90pct_Insert.png)

## 7. Run 3 vs Run 1 Comparison

Using Run 1 values from the previous report and Run 3 values from milestone3_run3/milestone3/milestone3_summary.csv:

| Dataset | Workload | Hybrid Run 1 | Hybrid Run 3 | Delta (Run 3 - Run 1) |
|---|---|---:|---:|---:|
| Facebook | 90% Lookup / 10% Insert | 1.320 | 1.452 | +0.132 |
| Facebook | 10% Lookup / 90% Insert | 3.331 | 3.331 | ~0.000 |
| Books | 90% Lookup / 10% Insert | 1.168 | 1.549 | +0.381 |
| Books | 10% Lookup / 90% Insert | 1.257 | 1.524 | +0.267 |
| OSMC | 90% Lookup / 10% Insert | 0.964 | 1.438 | +0.474 |
| OSMC | 10% Lookup / 90% Insert | 1.161 | 1.310 | +0.149 |

Assessment:

1. Hybrid throughput improved in all 6 scenarios (one effectively unchanged within rounding).
2. Absolute performance improved, but relative ranking did not improve: Hybrid still wins only Facebook 10/90.
3. Baselines also improved substantially in several scenarios, especially LIPP on lookup-heavy workloads, so the Hybrid competitiveness gap remains.

## 8. Current Status vs Milestone 3 Objective

What is complete:

1. Hybrid index implemented and benchmark-integrated.
2. Full 3-dataset x 2-workload run completed.
3. Required 12 plots and summary CSV generated.

What remains to improve:

1. Throughput superiority is still not consistent versus both baselines.
2. Relative to Run 1, Hybrid improved absolutely but not enough to change winner identity in 5 of 6 settings.
3. Flush policy likely needs stronger workload adaptivity.
4. Additional tuning is needed to reduce Hybrid lookup-path overhead on lookup-heavy workloads.

## 9. Next Steps

1. Introduce adaptive flush triggers based on observed lookup/insert mix, not just key-count thresholds.
2. Reduce LIPP insertion contention during flush by coarser micro-batches or staged apply windows.
3. Expand pareto search around the Facebook-winning configuration and retune separately for Books and OSMC.
4. Add instrumentation for time split: insert path, lookup path, flush worker, and lock wait time.
5. Run ablations on flush threshold, batch size, and buffer lookup checks to identify the dominant bottleneck.

---

Data source note: Run 3 Milestone 3 numbers were taken from milestone3_run3/milestone3/milestone3_summary.csv. Run 1 comparison values were taken from the prior Run 1 report table. Milestone 2 comparison values were taken from milestone2_run/milestone_report_1.txt and milestone2_run/plots_1 outputs.
