# Milestone 3 Flushing Strategy

The advanced `HybridPGMLIPP` implementation now uses a true asynchronous flushing pipeline with a background migration worker and double-buffer handoff.

## Design

- Initial bulk-loaded keys are stored in LIPP.
- Foreground insertions go to an active Dynamic PGM buffer.
- Once the active buffer reaches an adaptive threshold, it is sealed and handed off for background migration.
- If a flush is already running, one extra sealed buffer is retained as a pending buffer (double buffering).
- A dedicated background thread migrates sealed-buffer keys into LIPP in configurable batches.
- Lookups check active buffer, pending buffer, flushing buffer, and finally LIPP.

This avoids stop-the-world flushes: insertion throughput is not forced to pay full migration cost on the hot path.

## Thread Safety

- LIPP accesses are protected with a shared mutex:
	- foreground lookups take shared locks,
	- background migration inserts take unique locks.
- Flush-buffer state transitions are protected by a state mutex and condition variable.
- The worker drains all remaining buffered keys before shutdown, ensuring no key is lost.

## Parameters

`HybridPGMLIPP` accepts:

1. `flush_threshold`: percentage of current total keys.
2. `flush_batch`: number of entries migrated per worker batch.
3. `max_flush_threshold`: upper cap on active-buffer size before sealing.
4. `min_flush_threshold`: lower cap to avoid tiny, inefficient flushes.

The hybrid benchmark driver applies workload-aware presets and a pareto sweep for Task 3.

## Task 3 Execution

- Benchmark script: `scripts/run_task3_benchmarks.sh`
- Analysis script: `scripts/analyze_task3_results.py`

The Task 3 analysis script selects the best configuration per index by mean mixed throughput and emits 12 plots:

- 3 datasets (Facebook, Books, OSMC)
- 2 workloads (10% insert and 90% insert)
- 2 metrics (throughput and index size)
