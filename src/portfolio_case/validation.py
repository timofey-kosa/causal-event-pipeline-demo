from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


class ValidationError(ValueError):
    """Raised when a pipeline validation contract fails."""


@dataclass(frozen=True)
class ValidationResult:
    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


REQUIRED_FEED_COLUMNS = {
    "timestamp",
    "event_id",
    "source",
    "observed_value",
    "noise",
    "synthetic_marker",
}


def require_columns(df: pd.DataFrame, columns: Iterable[str], name: str) -> ValidationResult:
    missing = sorted(set(columns) - set(df.columns))
    if missing:
        raise ValidationError(f"{name} missing required columns: {missing}")
    return ValidationResult(name=f"{name}:required_columns", passed=True, detail="all required columns present")


def validate_feed_contract(df: pd.DataFrame, name: str) -> list[ValidationResult]:
    results = [require_columns(df, REQUIRED_FEED_COLUMNS, name)]
    if df["timestamp"].isna().any():
        raise ValidationError(f"{name} contains null timestamps")
    results.append(ValidationResult(f"{name}:no_null_timestamps", True, "timestamps are non-null"))

    duplicate_count = int(df["event_id"].duplicated().sum())
    if duplicate_count:
        raise ValidationError(f"{name} contains duplicate event_id values: {duplicate_count}")
    results.append(ValidationResult(f"{name}:unique_event_ids", True, "event identifiers are unique"))

    monotonic_by_source = df.groupby("source", sort=False)["timestamp"].apply(lambda s: bool(s.is_monotonic_increasing))
    bad_sources = monotonic_by_source[~monotonic_by_source].index.tolist()
    if bad_sources:
        raise ValidationError(f"{name} has non-monotonic timestamps for sources: {bad_sources}")
    results.append(ValidationResult(f"{name}:timestamp_monotonicity", True, "timestamps are monotonic by source"))
    return results


def validate_event_tape(df: pd.DataFrame) -> list[ValidationResult]:
    require_columns(df, REQUIRED_FEED_COLUMNS | {"sequence_id"}, "event_tape")
    if not df["timestamp"].is_monotonic_increasing:
        raise ValidationError("event_tape is not globally time ordered")
    return [ValidationResult("event_tape:global_order", True, "event tape is globally ordered")]


def validate_asof_no_lookahead(df: pd.DataFrame) -> list[ValidationResult]:
    require_columns(df, {"timestamp", "other_timestamp"}, "asof_aligned")
    usable = df["other_timestamp"].notna()
    violations = df.loc[usable & (df["other_timestamp"] > df["timestamp"])]
    if len(violations):
        raise ValidationError(f"ASOF alignment used future rows: {len(violations)}")
    return [ValidationResult("asof:no_lookahead", True, "other-feed timestamps are past or current")]


def validate_pre_entry_tape(df: pd.DataFrame) -> list[ValidationResult]:
    require_columns(df, {"timestamp", "event_timestamp", "episode_id"}, "pre_entry_tape")
    violations = df.loc[df["timestamp"] >= df["event_timestamp"]]
    if len(violations):
        raise ValidationError(f"pre-entry tape contains rows at or after event time: {len(violations)}")
    outcome_columns = [col for col in df.columns if col.startswith("outcome_")]
    if outcome_columns:
        raise ValidationError(f"pre-entry tape contains outcome columns: {outcome_columns}")
    return [ValidationResult("pre_entry:strictly_before_event", True, "all pre-entry rows precede event time")]


def validate_post_entry_tape(df: pd.DataFrame) -> list[ValidationResult]:
    require_columns(df, {"timestamp", "event_timestamp", "episode_id", "elapsed_ms"}, "post_entry_tape")
    before_event = df.loc[df["timestamp"] < df["event_timestamp"]]
    if len(before_event):
        raise ValidationError(f"post-entry tape contains rows before event time: {len(before_event)}")
    negative_elapsed = df.loc[df["elapsed_ms"] < 0]
    if len(negative_elapsed):
        raise ValidationError(f"post-entry tape contains negative elapsed time: {len(negative_elapsed)}")
    return [ValidationResult("post_entry:starts_at_event", True, "all post-entry rows are at or after event time")]


def validate_no_outcome_feature_leakage(df: pd.DataFrame) -> list[ValidationResult]:
    feature_columns = [col for col in df.columns if col.startswith("feature_")]
    leaked = [col for col in feature_columns if col.startswith("feature_outcome_") or "outcome" in col]
    if leaked:
        raise ValidationError(f"outcome-like columns appear in feature set: {leaked}")
    return [ValidationResult("features:no_outcome_leakage", True, "feature columns do not include outcomes")]
