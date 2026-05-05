#!/usr/bin/env python3
"""Generate Milestone 3 bar plots (12 total).

Layout: 3 datasets × 2 workloads × 2 metrics (throughput, index size).

Usage:
    python3 scripts/milestone3_plot.py [--results ./results] [--out ./plots/milestone3]

The script:
  1. Scans results/ for *mix*_results_table.csv files.
  2. Groups them by dataset and workload (10% insert vs 90% insert).
  3. For each index picks the variant with the highest mean mixed throughput.
  4. Emits one bar chart per (dataset, workload, metric) combination.
"""

import argparse
import glob
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ── Configuration ─────────────────────────────────────────────────────────────

DATASET_PRETTY = {
    "fb_100M_public_uint64":    "Facebook",
    "books_100M_public_uint64": "Books",
    "osmc_100M_public_uint64":  "OSMC",
}

# (token present in filename) → human-readable label
WORKLOAD_TOKENS = {
    "0.100000i": "90% Lookup / 10% Insert",
    "0.900000i": "10% Lookup / 90% Insert",
}

INDEX_ORDER  = ["DynamicPGM", "LIPP", "HybridPGMLIPP"]
INDEX_COLORS = {
    "DynamicPGM":    "#1f77b4",   # steel blue
    "LIPP":          "#ff7f0e",   # orange
    "HybridPGMLIPP": "#2ca02c",   # green
}

THROUGHPUT_COLS = [
    "mixed_throughput_mops1",
    "mixed_throughput_mops2",
    "mixed_throughput_mops3",
]


# ── Data loading ──────────────────────────────────────────────────────────────

@dataclass
class BestEntry:
    index_name: str
    throughput_mops: float   # mean over 3 runs
    size_bytes: float


def _parse_filename(name: str) -> Optional[Tuple[str, str]]:
    """Return (dataset_key, workload_label) or None if not recognised."""
    dataset = next((k for k in DATASET_PRETTY if name.startswith(k)), None)
    if dataset is None:
        return None
    workload = next((v for k, v in WORKLOAD_TOKENS.items() if k in name), None)
    if workload is None:
        return None
    return dataset, workload


def _throughput_cols(df: pd.DataFrame) -> List[str]:
    return [c for c in THROUGHPUT_COLS if c in df.columns]


def _best_per_index(df: pd.DataFrame) -> Dict[str, BestEntry]:
    cols = _throughput_cols(df)
    if not cols:
        raise ValueError("No mixed throughput columns found in CSV.")
    if "index_name" not in df.columns:
        raise ValueError("Missing 'index_name' column.")
    if "index_size_bytes" not in df.columns:
        raise ValueError("Missing 'index_size_bytes' column.")

    df = df.copy()
    df["_mean_tp"] = df[cols].apply(pd.to_numeric, errors="coerce").mean(axis=1)

    best: Dict[str, BestEntry] = {}
    for name in INDEX_ORDER:
        sub = df[df["index_name"] == name]
        if sub.empty:
            continue
        row = sub.loc[sub["_mean_tp"].idxmax()]
        best[name] = BestEntry(
            index_name=name,
            throughput_mops=float(row["_mean_tp"]),
            size_bytes=float(pd.to_numeric(row["index_size_bytes"], errors="coerce")),
        )
    return best


def load_all_results(results_dir: str) -> Dict[Tuple[str, str], pd.DataFrame]:
    """Return dict keyed by (dataset_key, workload_label) → concatenated DataFrame."""
    buckets: Dict[Tuple[str, str], List[pd.DataFrame]] = {}

    for path in sorted(glob.glob(os.path.join(results_dir, "*mix*_results_table.csv"))):
        key = _parse_filename(os.path.basename(path))
        if key is None:
            print(f"  Skipping (unrecognised name): {os.path.basename(path)}")
            continue
        try:
            df = pd.read_csv(path, skipinitialspace=True)
        except Exception as exc:
            print(f"  Warning — could not read {path}: {exc}")
            continue
        buckets.setdefault(key, []).append(df)

    return {k: pd.concat(v, ignore_index=True) for k, v in buckets.items()}


# ── Plotting ──────────────────────────────────────────────────────────────────

def _bar_chart(
    ax: plt.Axes,
    labels: List[str],
    values: List[float],
    ylabel: str,
    title: str,
    fmt: str = ".2f",
) -> None:
    colors = [INDEX_COLORS.get(lbl, "#888888") for lbl in labels]
    bars = ax.bar(range(len(labels)), values, color=colors,
                  edgecolor="black", linewidth=0.8, width=0.55)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=11, fontweight="bold")
    ax.set_title(title, fontsize=12, fontweight="bold", pad=8)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{val:{fmt}}",
            ha="center", va="bottom", fontsize=9, fontweight="bold",
        )


def make_plots(
    results: Dict[Tuple[str, str], pd.DataFrame],
    output_dir: str,
) -> int:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    produced = 0

    for (dataset_key, workload_label), df in sorted(results.items()):
        dataset_pretty = DATASET_PRETTY.get(dataset_key, dataset_key)

        try:
            best = _best_per_index(df)
        except Exception as exc:
            print(f"  Error processing {dataset_key} / {workload_label}: {exc}")
            continue

        if not best:
            print(f"  No recognised indexes in {dataset_key} / {workload_label}")
            continue

        present = [idx for idx in INDEX_ORDER if idx in best]
        tp_vals   = [best[idx].throughput_mops for idx in present]
        size_vals = [best[idx].size_bytes / (1024 ** 2) for idx in present]

        # Summary to stdout
        print(f"\n{dataset_pretty} | {workload_label}")
        for idx in present:
            print(f"  {idx:16s}  tp={best[idx].throughput_mops:6.2f} M ops/s  "
                  f"size={best[idx].size_bytes/(1024**2):6.1f} MiB")

        safe_ds = dataset_key.replace("_100M_public_uint64", "")
        safe_wl = (workload_label
                   .replace("%", "pct")
                   .replace("/", "_")
                   .replace(" ", "_"))

        # Throughput plot
        fig, ax = plt.subplots(figsize=(7, 4.5))
        _bar_chart(ax, present, tp_vals,
                   "Throughput (M ops/sec)",
                   f"{dataset_pretty}\n{workload_label}")
        plt.tight_layout()
        tp_path = os.path.join(output_dir, f"tp_{safe_ds}_{safe_wl}.png")
        plt.savefig(tp_path, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  Saved {os.path.basename(tp_path)}")
        produced += 1

        # Index-size plot
        fig, ax = plt.subplots(figsize=(7, 4.5))
        _bar_chart(ax, present, size_vals,
                   "Index Size (MiB)",
                   f"{dataset_pretty}\n{workload_label}",
                   fmt=".1f")
        plt.tight_layout()
        sz_path = os.path.join(output_dir, f"size_{safe_ds}_{safe_wl}.png")
        plt.savefig(sz_path, dpi=300, bbox_inches="tight")
        plt.close()
        print(f"  Saved {os.path.basename(sz_path)}")
        produced += 1

    return produced


# ── Summary CSV ───────────────────────────────────────────────────────────────

def write_summary(
    results: Dict[Tuple[str, str], pd.DataFrame],
    output_dir: str,
) -> None:
    rows = []
    for (dataset_key, workload_label), df in sorted(results.items()):
        try:
            best = _best_per_index(df)
        except Exception:
            continue
        for idx, entry in best.items():
            rows.append({
                "dataset":            DATASET_PRETTY.get(dataset_key, dataset_key),
                "workload":           workload_label,
                "index":              idx,
                "mean_throughput_mops": entry.throughput_mops,
                "index_size_mib":     entry.size_bytes / (1024 ** 2),
            })
    if rows:
        summary_path = os.path.join(output_dir, "milestone3_summary.csv")
        pd.DataFrame(rows).to_csv(summary_path, index=False)
        print(f"\nSummary written to {summary_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="./results",
                        help="Directory containing *mix*_results_table.csv files")
    parser.add_argument("--out", default="./plots/milestone3",
                        help="Output directory for plots")
    args = parser.parse_args()

    print(f"Loading results from: {os.path.abspath(args.results)}")
    results = load_all_results(args.results)

    if not results:
        print(
            "No mixed-workload CSVs found.\n"
            "Run scripts/run_task3_benchmarks.sh first, then re-run this script."
        )
        sys.exit(1)

    n = make_plots(results, args.out)
    write_summary(results, args.out)

    expected = 12  # 3 datasets × 2 workloads × 2 metrics
    status = "OK" if n == expected else f"WARNING: expected {expected}"
    print(f"\nProduced {n} plots in {os.path.abspath(args.out)} [{status}]")


if __name__ == "__main__":
    main()
