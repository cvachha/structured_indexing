#!/usr/bin/env python3
"""Generate Milestone 3 bar plots for mixed workloads.

The script groups result CSVs by dataset and produces throughput and index-size
plots for both mixed workloads:

- 90% lookup, 10% insert (`0.100000i`)
- 10% lookup, 90% insert (`0.900000i`)
"""

import glob
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


WORKLOADS = {
    "90_lookup_10_insert": ("0.100000i_0m_mix", "90% Lookup, 10% Insert"),
    "10_lookup_90_insert": ("0.900000i_0m_mix", "10% Lookup, 90% Insert"),
}
INDEX_ORDER = ["DynamicPGM", "LIPP", "HybridPGMLIPP"]
COLORS = {
    "DynamicPGM": "#3498db",
    "LIPP": "#e74c3c",
    "HybridPGMLIPP": "#2ecc71",
}


def dataset_from_result_path(path):
    return os.path.basename(path).split("_ops_")[0]


def load_results(result_dir="./results"):
    results = {}
    for workload_key, (needle, _) in WORKLOADS.items():
        for csv_file in glob.glob(os.path.join(result_dir, f"*{needle}*.csv")):
            dataset = dataset_from_result_path(csv_file)
            try:
                df = pd.read_csv(csv_file, skipinitialspace=True)
            except Exception as exc:
                print(f"Warning: failed to load {csv_file}: {exc}")
                continue

            results.setdefault(dataset, {}).setdefault(workload_key, []).append(df)

    for dataset, workloads in results.items():
        for workload_key, frames in workloads.items():
            workloads[workload_key] = pd.concat(frames, ignore_index=True)
    return results


def throughput_columns(df):
    return [col for col in df.columns if "throughput" in col.lower()]


def mean_row_throughput(df):
    cols = throughput_columns(df)
    if not cols:
        return pd.Series(np.zeros(len(df)), index=df.index)
    return df[cols].mean(axis=1)


def select_best_variant(df, index_name):
    index_df = df[df["index_name"] == index_name].copy()
    if index_df.empty:
        return None
    index_df["mean_throughput"] = mean_row_throughput(index_df)
    return index_df.loc[index_df["mean_throughput"].idxmax()].copy()


def aggregate_metrics(df):
    metrics = {}
    for index_name in INDEX_ORDER:
        best = select_best_variant(df, index_name)
        if best is None:
            continue
        metrics[index_name] = {
            "throughput": float(best["mean_throughput"]),
            "size_mb": float(best.get("index_size_bytes", 0)) / (1024 * 1024),
        }
    return metrics


def plot_metric(dataset, workload_key, workload_label, metrics, metric, ylabel, output_dir):
    values = [metrics[idx][metric] for idx in INDEX_ORDER if idx in metrics]
    labels = [idx for idx in INDEX_ORDER if idx in metrics]
    if not values:
        return

    fig, ax = plt.subplots(figsize=(8, 5.5))
    bars = ax.bar(
        range(len(labels)),
        values,
        color=[COLORS[idx] for idx in labels],
        edgecolor="black",
        linewidth=1.2,
        width=0.62,
    )
    ax.set_ylabel(ylabel, fontsize=12, fontweight="bold")
    ax.set_title(f"{dataset}\n{workload_label}", fontsize=14, fontweight="bold", pad=12)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=11)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.set_axisbelow(True)

    for bar, value in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.2f}" if metric == "throughput" else f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

    plt.tight_layout()
    safe_dataset = dataset.replace("_100M_public_uint64", "")
    filename = f"{metric}_{safe_dataset}_{workload_key}.png"
    plt.savefig(os.path.join(output_dir, filename), dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Saved {filename}")


def create_plots(results, output_dir="./plots"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    for dataset in sorted(results):
        for workload_key, (_, workload_label) in WORKLOADS.items():
            df = results[dataset].get(workload_key)
            if df is None:
                print(f"Warning: no {workload_label} results for {dataset}")
                continue

            metrics = aggregate_metrics(df)
            print(f"\n{dataset} - {workload_label}")
            for index_name in INDEX_ORDER:
                if index_name in metrics:
                    print(
                        f"  {index_name:14s} "
                        f"throughput={metrics[index_name]['throughput']:.2f} Mops/s, "
                        f"size={metrics[index_name]['size_mb']:.1f} MB"
                    )

            plot_metric(
                dataset,
                workload_key,
                workload_label,
                metrics,
                "throughput",
                "Throughput (M ops/sec)",
                output_dir,
            )
            plot_metric(
                dataset,
                workload_key,
                workload_label,
                metrics,
                "size_mb",
                "Index Size (MB)",
                output_dir,
            )


def main():
    print("Loading benchmark results from ./results")
    results = load_results()
    if not results:
        print("No mixed-workload CSVs found. Run scripts/run_benchmarks.sh or scripts/run_milestone_benchmark.sh first.")
        return
    create_plots(results)
    print("\nDone. Plots are in ./plots.")


if __name__ == "__main__":
    main()
