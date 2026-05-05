#!/usr/bin/env python3
"""Task 3 analysis for hybrid learned indexing benchmarks.

Generates 12 bar plots:
- 3 datasets x 2 mixed workloads x 2 metrics (throughput, index size)

For each workload file, the best configuration per index is selected by maximum
average mixed throughput across the 3 repeated runs.
"""

import glob
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DATASET_LABELS = {
    "fb_100M_public_uint64": "Facebook",
    "books_100M_public_uint64": "Books",
    "osmc_100M_public_uint64": "OSMC",
}

WORKLOAD_LABELS = {
    "0.100000i": "90% Lookup, 10% Insertion",
    "0.900000i": "10% Lookup, 90% Insertion",
}

INDEX_ORDER = ["DynamicPGM", "LIPP", "HybridPGMLIPP"]
INDEX_COLORS = {
    "DynamicPGM": "#1f77b4",
    "LIPP": "#ff7f0e",
    "HybridPGMLIPP": "#2ca02c",
}


@dataclass
class BestRow:
    index_name: str
    throughput_mops: float
    size_bytes: float


def parse_dataset_and_workload(filename: str) -> Optional[Tuple[str, str]]:
    dataset = None
    for ds in DATASET_LABELS:
        if filename.startswith(ds):
            dataset = ds
            break

    if dataset is None:
        return None

    workload = None
    for token, label in WORKLOAD_LABELS.items():
        if token in filename:
            workload = label
            break

    if workload is None:
        return None

    return dataset, workload


def throughput_columns(df: pd.DataFrame) -> List[str]:
    return [
        c
        for c in [
            "mixed_throughput_mops1",
            "mixed_throughput_mops2",
            "mixed_throughput_mops3",
        ]
        if c in df.columns
    ]


def add_mean_throughput(df: pd.DataFrame) -> pd.DataFrame:
    cols = throughput_columns(df)
    if not cols:
        raise ValueError("No mixed throughput columns found")

    out = df.copy()
    out["mean_mixed_throughput"] = out[cols].mean(axis=1, skipna=True)
    return out


def choose_best_rows(df: pd.DataFrame) -> Dict[str, BestRow]:
    if "index_name" not in df.columns:
        raise ValueError("Missing index_name column")
    if "index_size_bytes" not in df.columns:
        raise ValueError("Missing index_size_bytes column")

    scored = add_mean_throughput(df)

    best: Dict[str, BestRow] = {}
    for index_name in INDEX_ORDER:
        subset = scored[scored["index_name"] == index_name]
        if subset.empty:
            continue

        idx = subset["mean_mixed_throughput"].idxmax()
        row = subset.loc[idx]
        best[index_name] = BestRow(
            index_name=index_name,
            throughput_mops=float(row["mean_mixed_throughput"]),
            size_bytes=float(row["index_size_bytes"]),
        )

    return best


def plot_metric(
    dataset_label: str,
    workload_label: str,
    metric_name: str,
    best_rows: Dict[str, BestRow],
    output_path: str,
) -> None:
    indexes = [idx for idx in INDEX_ORDER if idx in best_rows]
    if not indexes:
        return

    if metric_name == "throughput":
        values = [best_rows[idx].throughput_mops for idx in indexes]
        ylabel = "Throughput (M ops/sec)"
        title_metric = "Throughput"
    else:
        values = [best_rows[idx].size_bytes / (1024 * 1024) for idx in indexes]
        ylabel = "Index Size (MiB)"
        title_metric = "Index Size"

    plt.figure(figsize=(8, 5))
    bars = plt.bar(
        range(len(indexes)),
        values,
        color=[INDEX_COLORS.get(idx, "#888888") for idx in indexes],
    )

    plt.xticks(range(len(indexes)), indexes)
    plt.ylabel(ylabel)
    plt.title(f"{dataset_label} | {workload_label} | {title_metric}")
    plt.grid(axis="y", alpha=0.25)

    for bar, value in zip(bars, values):
        label = f"{value:.2f}"
        plt.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            label,
            ha="center",
            va="bottom",
            fontsize=9,
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=250)
    plt.close()


def analyze_results(results_dir: str = "./results", output_dir: str = "./results/task3_plots") -> None:
    os.makedirs(output_dir, exist_ok=True)

    paths = sorted(glob.glob(os.path.join(results_dir, "*mix*_results_table.csv")))
    if not paths:
        print("No mixed workload result files found.")
        return

    summaries = []
    produced_plots = 0

    for path in paths:
        filename = os.path.basename(path)
        parsed = parse_dataset_and_workload(filename)
        if parsed is None:
            continue

        dataset_key, workload_label = parsed
        dataset_label = DATASET_LABELS[dataset_key]

        try:
            df = pd.read_csv(path)
            best_rows = choose_best_rows(df)
        except Exception as exc:
            print(f"Skipping {filename}: {exc}")
            continue

        throughput_plot = os.path.join(
            output_dir,
            f"{dataset_key}_{workload_label.replace('%', 'pct').replace(', ', '_').replace(' ', '_')}_throughput.png",
        )
        size_plot = os.path.join(
            output_dir,
            f"{dataset_key}_{workload_label.replace('%', 'pct').replace(', ', '_').replace(' ', '_')}_size.png",
        )

        plot_metric(dataset_label, workload_label, "throughput", best_rows, throughput_plot)
        plot_metric(dataset_label, workload_label, "size", best_rows, size_plot)
        produced_plots += 2

        for idx in INDEX_ORDER:
            if idx not in best_rows:
                continue
            row = best_rows[idx]
            summaries.append(
                {
                    "dataset": dataset_label,
                    "workload": workload_label,
                    "index": idx,
                    "best_mean_mixed_throughput_mops": row.throughput_mops,
                    "best_index_size_bytes": row.size_bytes,
                    "best_index_size_mib": row.size_bytes / (1024 * 1024),
                }
            )

    if summaries:
        summary_df = pd.DataFrame(summaries)
        summary_path = os.path.join(output_dir, "task3_best_config_summary.csv")
        summary_df.to_csv(summary_path, index=False)
        print(f"Summary written: {summary_path}")

    print(f"Generated {produced_plots} plots in {output_dir}")


if __name__ == "__main__":
    analyze_results()
