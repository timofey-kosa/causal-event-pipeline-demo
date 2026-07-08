from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from causal_pipeline.analysis import (
    plot_cohort_outcomes,
    plot_pre_post_tape,
    plot_rebound_pattern,
    write_cohort_summary,
)
from causal_pipeline.freeze import freeze_run
from causal_pipeline.logging_utils import RunLogger
from causal_pipeline.modelling import train_baseline_model
from causal_pipeline.reporting import write_demo_report
from causal_pipeline.synthetic_data import SyntheticBundle, generate_synthetic_feeds
from causal_pipeline.validation import (
    ValidationResult,
    validate_asof_no_lookahead,
    validate_event_tape,
    validate_feed_contract,
    validate_no_outcome_feature_leakage,
    validate_post_entry_tape,
    validate_pre_entry_tape,
)

PIPELINE_STAGES = [
    "generate_synthetic_feeds",
    "normalise_feeds",
    "build_unified_event_tape",
    "asof_alignment",
    "build_pre_entry_tape",
    "build_post_entry_tape",
    "feature_generation",
    "cohort_analysis",
    "rebound_demonstration",
    "baseline_model",
    "final_report",
    "freeze_artefacts",
]


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def make_run_id(prefix: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}_{stamp}_{uuid.uuid4().hex[:8]}"


def make_run_dirs(output_root: Path, run_id: str) -> dict[str, Path]:
    run_dir = output_root / run_id
    if run_dir.exists():
        raise FileExistsError(f"run directory already exists: {run_dir}")
    dirs = {
        "run": run_dir,
        "raw": run_dir / "data" / "raw",
        "interim": run_dir / "data" / "interim",
        "features": run_dir / "data" / "features",
        "reports": run_dir / "reports",
        "figures": run_dir / "figures",
        "models": run_dir / "models",
        "frozen": run_dir / "frozen",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def _result_dicts(results: list[ValidationResult]) -> list[dict[str, object]]:
    return [result.as_dict() for result in results]


def normalise_feeds(bundle: SyntheticBundle) -> dict[str, pd.DataFrame]:
    feeds = {}
    for name, df in {"feed_a": bundle.feed_a, "feed_b": bundle.feed_b}.items():
        out = df.copy()
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
        out["event_id"] = out["event_id"].astype(str)
        out["source"] = out["source"].astype(str)
        out["synthetic_marker"] = out["synthetic_marker"].astype(str)
        out = out.sort_values(["timestamp", "event_id"]).reset_index(drop=True)
        feeds[name] = out
    return feeds


def build_event_tape(feeds: dict[str, pd.DataFrame]) -> pd.DataFrame:
    tape = pd.concat(feeds.values(), ignore_index=True)
    tape = tape.sort_values(["timestamp", "source", "event_id"]).reset_index(drop=True)
    tape.insert(0, "sequence_id", range(len(tape)))
    return tape


def _align_one_side(left: pd.DataFrame, right: pd.DataFrame, other_source: str) -> pd.DataFrame:
    left_sorted = left.sort_values("timestamp").reset_index(drop=True)
    right_sorted = (
        right[["timestamp", "event_id", "observed_value"]]
        .rename(
            columns={
                "timestamp": "other_timestamp",
                "event_id": "other_event_id",
                "observed_value": "other_observed_value",
            }
        )
        .sort_values("other_timestamp")
        .reset_index(drop=True)
    )
    aligned = pd.merge_asof(
        left_sorted,
        right_sorted,
        left_on="timestamp",
        right_on="other_timestamp",
        direction="backward",
        allow_exact_matches=True,
    )
    aligned["other_source"] = other_source
    aligned["freshness_ms"] = (aligned["timestamp"] - aligned["other_timestamp"]).dt.total_seconds() * 1000.0
    aligned["value_gap"] = aligned["observed_value"] - aligned["other_observed_value"]
    return aligned


def build_asof_alignment(feeds: dict[str, pd.DataFrame]) -> pd.DataFrame:
    a = _align_one_side(feeds["feed_a"], feeds["feed_b"], "feed_b")
    b = _align_one_side(feeds["feed_b"], feeds["feed_a"], "feed_a")
    aligned = pd.concat([a, b], ignore_index=True)
    aligned = aligned.sort_values(["timestamp", "source", "event_id"]).reset_index(drop=True)
    aligned.insert(0, "aligned_sequence_id", range(len(aligned)))
    return aligned


def build_episodes(feeds: dict[str, pd.DataFrame], schedule: pd.DataFrame) -> pd.DataFrame:
    marked = feeds["feed_a"].loc[feeds["feed_a"]["synthetic_marker"] != "none"].copy()
    marked = marked.sort_values("timestamp").reset_index(drop=True)
    episodes = schedule[["episode_id", "cohort", "episode_order"]].copy()
    episodes["event_timestamp"] = marked["timestamp"].to_numpy()
    episodes["event_event_id"] = marked["event_id"].to_numpy()
    return episodes


def build_pre_entry_tape(aligned: pd.DataFrame, episodes: pd.DataFrame, pre_window_seconds: int) -> pd.DataFrame:
    rows = []
    window = pd.Timedelta(seconds=int(pre_window_seconds))
    for episode in episodes.itertuples(index=False):
        event_ts = pd.Timestamp(episode.event_timestamp)
        mask = (aligned["timestamp"] >= event_ts - window) & (aligned["timestamp"] < event_ts)
        piece = aligned.loc[mask].copy()
        piece["episode_id"] = episode.episode_id
        piece["event_timestamp"] = event_ts
        piece["cohort"] = episode.cohort
        piece["relative_ms"] = (piece["timestamp"] - event_ts).dt.total_seconds() * 1000.0
        rows.append(piece)
    return pd.concat(rows, ignore_index=True).sort_values(["episode_id", "timestamp", "source"]).reset_index(drop=True)


def build_post_entry_tape(
    aligned: pd.DataFrame,
    episodes: pd.DataFrame,
    pre_entry: pd.DataFrame,
    post_window_seconds: int,
) -> pd.DataFrame:
    rows = []
    window = pd.Timedelta(seconds=int(post_window_seconds))
    for episode in episodes.itertuples(index=False):
        event_ts = pd.Timestamp(episode.event_timestamp)
        pre_piece = pre_entry.loc[pre_entry["episode_id"] == episode.episode_id].sort_values("timestamp")
        own_anchor = float(pre_piece["observed_value"].dropna().iloc[-1]) if len(pre_piece) else 0.0
        other_anchor = float(pre_piece["other_observed_value"].dropna().iloc[-1]) if len(pre_piece) else 0.0
        mask = (aligned["timestamp"] >= event_ts) & (aligned["timestamp"] <= event_ts + window)
        piece = aligned.loc[mask].copy()
        piece["episode_id"] = episode.episode_id
        piece["event_timestamp"] = event_ts
        piece["cohort"] = episode.cohort
        piece["elapsed_ms"] = (piece["timestamp"] - event_ts).dt.total_seconds() * 1000.0
        piece["outcome_response"] = piece["observed_value"] - own_anchor
        piece["outcome_other_response"] = piece["other_observed_value"] - other_anchor
        rows.append(piece)
    return pd.concat(rows, ignore_index=True).sort_values(["episode_id", "timestamp", "source"]).reset_index(drop=True)


def generate_features(
    pre_entry: pd.DataFrame,
    post_entry: pd.DataFrame,
    episodes: pd.DataFrame,
    target_response_threshold: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for episode in episodes.sort_values("episode_order").itertuples(index=False):
        pre = pre_entry.loc[pre_entry["episode_id"] == episode.episode_id].sort_values("timestamp")
        post = post_entry.loc[post_entry["episode_id"] == episode.episode_id].sort_values("timestamp")
        gap = pre["value_gap"].dropna()
        observed_diff = pre["observed_value"].diff().dropna()
        post_response = post["outcome_response"].dropna()
        final_response = float(post_response.iloc[-1]) if len(post_response) else 0.0
        min_response = float(post_response.min()) if len(post_response) else 0.0
        rebound_strength = final_response - min_response
        freshness = pre["freshness_ms"].dropna()
        rows.append(
            {
                "episode_id": episode.episode_id,
                "event_timestamp": pd.Timestamp(episode.event_timestamp),
                "cohort": episode.cohort,
                "episode_order": int(episode.episode_order),
                "feature_pre_gap_mean": float(gap.mean()) if len(gap) else 0.0,
                "feature_pre_gap_last": float(gap.iloc[-1]) if len(gap) else 0.0,
                "feature_pre_gap_volatility": float(gap.std(ddof=0)) if len(gap) > 1 else 0.0,
                "feature_observed_diff_volatility": float(observed_diff.std(ddof=0)) if len(observed_diff) else 0.0,
                "feature_event_count_pre": int(len(pre)),
                "feature_feed_freshness_ms_mean": float(freshness.mean()) if len(freshness) else 0.0,
                "outcome_final_response": final_response,
                "outcome_min_response": min_response,
                "outcome_rebound_strength": rebound_strength,
                "target_high_response": int(rebound_strength >= target_response_threshold),
            }
        )
    return pd.DataFrame(rows)


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def log_validations(logger: RunLogger, validations: list[dict[str, object]]) -> None:
    for result in validations:
        logger.info(
            "validation_passed",
            str(result["name"]),
            validation=result["name"],
            detail=result["detail"],
        )


def run_pipeline(config_path: Path, project_root: Path | None = None) -> Path:
    project_root = project_root or Path.cwd()
    config = load_config(config_path)
    run_id = make_run_id(config["run"].get("run_id_prefix", "demo"))
    dirs = make_run_dirs(project_root / config["run"].get("output_root", "runs"), run_id)
    logger = RunLogger(dirs["run"], run_id)
    validations: list[dict[str, object]] = []
    row_counts: dict[str, int] = {}

    logger.info("run_start", "Run started", config_path=config_path, run_dir=dirs["run"])
    logger.info("config_loaded", "Config loaded", random_seed=config["synthetic"]["random_seed"])

    with logger.stage("generate_synthetic_feeds"):
        bundle = generate_synthetic_feeds(config["synthetic"])
        write_parquet(bundle.feed_a.drop(columns=["offset_ms"]), dirs["raw"] / "feed_a.parquet")
        write_parquet(bundle.feed_b.drop(columns=["offset_ms"]), dirs["raw"] / "feed_b.parquet")
        row_counts["feed_a"] = int(len(bundle.feed_a))
        row_counts["feed_b"] = int(len(bundle.feed_b))
        logger.info("file_out", "Wrote synthetic feed A", path=dirs["raw"] / "feed_a.parquet", rows=len(bundle.feed_a))
        logger.info("file_out", "Wrote synthetic feed B", path=dirs["raw"] / "feed_b.parquet", rows=len(bundle.feed_b))

    with logger.stage("normalise_feeds"):
        feeds = normalise_feeds(bundle)
        for name, df in feeds.items():
            results = _result_dicts(validate_feed_contract(df, name))
            validations.extend(results)
            log_validations(logger, results)

    with logger.stage("build_unified_event_tape"):
        event_tape = build_event_tape(feeds)
        results = _result_dicts(validate_event_tape(event_tape))
        validations.extend(results)
        log_validations(logger, results)
        write_parquet(event_tape, dirs["interim"] / "event_tape.parquet")
        row_counts["event_tape"] = int(len(event_tape))
        logger.info("file_out", "Wrote unified event tape", path=dirs["interim"] / "event_tape.parquet", rows=len(event_tape))

    with logger.stage("asof_alignment"):
        aligned = build_asof_alignment(feeds)
        results = _result_dicts(validate_asof_no_lookahead(aligned))
        validations.extend(results)
        log_validations(logger, results)
        write_parquet(aligned, dirs["interim"] / "asof_aligned.parquet")
        row_counts["asof_aligned"] = int(len(aligned))
        logger.info("file_out", "Wrote ASOF aligned table", path=dirs["interim"] / "asof_aligned.parquet", rows=len(aligned))

    with logger.stage("build_pre_entry_tape"):
        episodes = build_episodes(feeds, bundle.episodes)
        pre_entry = build_pre_entry_tape(aligned, episodes, config["synthetic"]["pre_window_seconds"])
        results = _result_dicts(validate_pre_entry_tape(pre_entry))
        validations.extend(results)
        log_validations(logger, results)
        write_parquet(pre_entry, dirs["interim"] / "pre_entry_tape.parquet")
        row_counts["pre_entry_tape"] = int(len(pre_entry))
        logger.info("file_out", "Wrote pre-entry tape", path=dirs["interim"] / "pre_entry_tape.parquet", rows=len(pre_entry))

    with logger.stage("build_post_entry_tape"):
        post_entry = build_post_entry_tape(aligned, episodes, pre_entry, config["synthetic"]["post_window_seconds"])
        results = _result_dicts(validate_post_entry_tape(post_entry))
        validations.extend(results)
        log_validations(logger, results)
        write_parquet(post_entry, dirs["interim"] / "post_entry_tape.parquet")
        row_counts["post_entry_tape"] = int(len(post_entry))
        logger.info("file_out", "Wrote post-entry tape", path=dirs["interim"] / "post_entry_tape.parquet", rows=len(post_entry))

    with logger.stage("feature_generation"):
        features = generate_features(
            pre_entry,
            post_entry,
            episodes,
            float(config["model"]["target_response_threshold"]),
        )
        results = _result_dicts(validate_no_outcome_feature_leakage(features))
        validations.extend(results)
        log_validations(logger, results)
        write_parquet(features, dirs["features"] / "features.parquet")
        row_counts["features"] = int(len(features))
        logger.info("file_out", "Wrote feature table", path=dirs["features"] / "features.parquet", rows=len(features))

    with logger.stage("cohort_analysis"):
        cohort_summary = write_cohort_summary(features, dirs["reports"] / "cohort_summary.csv")
        plot_cohort_outcomes(cohort_summary, dirs["figures"] / "cohort_outcomes.png")
        row_counts["cohort_summary"] = int(len(cohort_summary))
        logger.info("file_out", "Wrote cohort summary", path=dirs["reports"] / "cohort_summary.csv", rows=len(cohort_summary))
        logger.info("file_out", "Wrote cohort figure", path=dirs["figures"] / "cohort_outcomes.png")

    with logger.stage("rebound_demonstration"):
        plot_pre_post_tape(pre_entry, post_entry, dirs["figures"] / "pre_post_tape.png")
        plot_rebound_pattern(post_entry, dirs["figures"] / "rebound_pattern.png")
        logger.info("file_out", "Wrote pre/post figure", path=dirs["figures"] / "pre_post_tape.png")
        logger.info("file_out", "Wrote rebound figure", path=dirs["figures"] / "rebound_pattern.png")

    with logger.stage("baseline_model"):
        model_metrics = train_baseline_model(features, config["model"], dirs["models"], dirs["reports"])
        logger.info("model_metrics", "Baseline model evaluated", **model_metrics)

    with logger.stage("final_report"):
        write_demo_report(
            dirs["reports"] / "demo_report.md",
            run_id,
            config,
            row_counts,
            validations,
            cohort_summary,
            model_metrics,
        )
        logger.info("file_out", "Wrote demo report", path=dirs["reports"] / "demo_report.md")

    with logger.stage("freeze_artefacts"):
        manifest = freeze_run(
            dirs["run"],
            project_root,
            run_id,
            config,
            PIPELINE_STAGES,
            row_counts,
            validations,
        )
        logger.info(
            "artefact_freeze",
            "Run artefacts frozen",
            validation_status=manifest["validation_status"],
            artefact_count=len(manifest["produced_artefacts"]),
        )

    logger.info("run_complete", "Run completed", run_dir=dirs["run"])
    return dirs["run"]
