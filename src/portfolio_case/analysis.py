from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def write_cohort_summary(features: pd.DataFrame, output_path: Path) -> pd.DataFrame:
    summary = (
        features.groupby("cohort", as_index=False)
        .agg(
            episode_count=("episode_id", "count"),
            mean_final_response=("outcome_final_response", "mean"),
            mean_rebound_strength=("outcome_rebound_strength", "mean"),
            share_high_response=("target_high_response", "mean"),
        )
        .sort_values("cohort")
    )
    summary.to_csv(output_path, index=False)
    return summary


def plot_pre_post_tape(pre_entry: pd.DataFrame, post_entry: pd.DataFrame, output_path: Path) -> None:
    episode_id = pre_entry["episode_id"].iloc[0]
    pre = pre_entry.loc[pre_entry["episode_id"] == episode_id].copy()
    post = post_entry.loc[post_entry["episode_id"] == episode_id].copy()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.scatter(pre["relative_ms"] / 1000.0, pre["value_gap"], s=12, label="pre-entry rows", color=(0.30, 0.47, 0.66, 0.8))
    ax.scatter(post["elapsed_ms"] / 1000.0, post["value_gap"], s=12, label="post-entry rows", color=(0.96, 0.52, 0.11, 0.8))
    ax.axvline(0, color="black", linewidth=1, linestyle="--")
    ax.set_title("Pre/Post Event Tape Split")
    ax.set_xlabel("Seconds relative to event")
    ax.set_ylabel("Cross-feed value gap")
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def plot_cohort_outcomes(summary: pd.DataFrame, output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(summary["cohort"], summary["mean_rebound_strength"], color=["#4C78A8", "#F58518", "#54A24B"])
    ax.set_title("Synthetic Cohort Outcomes")
    ax.set_xlabel("Mechanism-based cohort")
    ax.set_ylabel("Mean rebound strength")
    fig.tight_layout()
    fig.savefig(output_path, dpi=140)
    plt.close(fig)


def plot_rebound_pattern(post_entry: pd.DataFrame, output_path: Path) -> None:
    rebound = post_entry.loc[post_entry["cohort"] == "rebound"].copy()
    rebound["elapsed_bucket_s"] = (rebound["elapsed_ms"] / 1000.0 // 30 * 30).astype(int)
    curve = rebound.groupby("elapsed_bucket_s", as_index=False)["outcome_response"].mean()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(curve["elapsed_bucket_s"], curve["outcome_response"], marker="o", linewidth=1.8)
    ax.axhline(0, color="black", linewidth=1, linestyle="--")
    ax.set_title("Synthetic V-Shaped Rebound Cohort")
    ax.set_xlabel("Seconds after event")
    ax.set_ylabel("Mean downstream response")
    fig.tight_layout()
    fig.savefig(output_path, dpi=140)
    plt.close(fig)
