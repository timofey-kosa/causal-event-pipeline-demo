from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SyntheticBundle:
    feed_a: pd.DataFrame
    feed_b: pd.DataFrame
    episodes: pd.DataFrame


def _make_offsets(rng: np.random.Generator, count: int, duration_seconds: int) -> np.ndarray:
    grid = np.arange(0, duration_seconds * 1000, 250, dtype=np.int64)
    offsets = np.sort(rng.choice(grid, size=count, replace=False))
    return offsets


def _episode_schedule(config: dict, rng: np.random.Generator) -> pd.DataFrame:
    duration_ms = int(config["duration_seconds"]) * 1000
    pre_ms = int(config["pre_window_seconds"]) * 1000
    post_ms = int(config["post_window_seconds"]) * 1000
    count = int(config["episode_count"])
    start = pre_ms * 2
    stop = duration_ms - int(post_ms * 1.2)
    base_offsets = np.linspace(start, stop, count, dtype=np.int64)
    jitter = rng.integers(-20_000, 20_000, size=count)
    offsets = np.clip(base_offsets + jitter, start, stop)
    cohorts = np.resize(np.array(["rebound", "drift", "steady"], dtype=object), count)
    return pd.DataFrame(
        {
            "episode_id": [f"episode_{idx:03d}" for idx in range(count)],
            "event_offset_ms": offsets,
            "cohort": cohorts,
            "episode_order": np.arange(count),
        }
    )


def _effect_for_offsets(
    offsets_ms: np.ndarray,
    schedule: pd.DataFrame,
    pre_window_ms: int,
    post_window_ms: int,
    amplitude: float,
    delay_ms: int,
) -> np.ndarray:
    effect = np.zeros(len(offsets_ms), dtype=float)
    for row in schedule.itertuples(index=False):
        elapsed = offsets_ms - int(row.event_offset_ms) - delay_ms
        pre_mask = (elapsed >= -pre_window_ms) & (elapsed < 0)
        post_mask = (elapsed >= 0) & (elapsed <= post_window_ms)

        if row.cohort == "rebound":
            effect[pre_mask] += -0.12 * amplitude * ((elapsed[pre_mask] + pre_window_ms) / pre_window_ms)
            trough_ms = max(int(post_window_ms * 0.35), 1)
            early = post_mask & (elapsed <= trough_ms)
            late = post_mask & (elapsed > trough_ms)
            effect[early] += -amplitude * (elapsed[early] / trough_ms)
            effect[late] += -amplitude + 1.55 * amplitude * ((elapsed[late] - trough_ms) / (post_window_ms - trough_ms))
        elif row.cohort == "drift":
            effect[pre_mask] += 0.10 * amplitude * ((elapsed[pre_mask] + pre_window_ms) / pre_window_ms)
            effect[post_mask] += 0.55 * amplitude * (elapsed[post_mask] / post_window_ms)
        else:
            effect[pre_mask] += 0.04 * amplitude * np.sin((elapsed[pre_mask] + pre_window_ms) / pre_window_ms * np.pi)
            effect[post_mask] += 0.12 * amplitude * np.sin(elapsed[post_mask] / post_window_ms * 2 * np.pi)
    return effect


def _make_feed(
    source: str,
    offsets_ms: np.ndarray,
    start_time: pd.Timestamp,
    schedule: pd.DataFrame,
    config: dict,
    rng: np.random.Generator,
    delay_ms: int = 0,
) -> pd.DataFrame:
    seconds = offsets_ms / 1000.0
    base = 100.0 + 0.35 * np.sin(seconds / 420.0) + 0.18 * np.cos(seconds / 155.0) + 0.00003 * seconds
    noise = rng.normal(0.0, 0.045 if source == "feed_a" else 0.055, size=len(offsets_ms))
    effect = _effect_for_offsets(
        offsets_ms,
        schedule,
        int(config["pre_window_seconds"]) * 1000,
        int(config["post_window_seconds"]) * 1000,
        float(config["response_amplitude"]),
        delay_ms=delay_ms,
    )
    observed = base + noise + effect
    timestamps = start_time + pd.to_timedelta(offsets_ms, unit="ms")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "event_id": [f"{source}_{idx:06d}" for idx in range(len(offsets_ms))],
            "source": source,
            "observed_value": observed.round(6),
            "noise": noise.round(6),
            "synthetic_marker": "none",
            "offset_ms": offsets_ms,
        }
    )

    for row in schedule.itertuples(index=False):
        marker_offset = int(row.event_offset_ms) + delay_ms
        idx = int(np.argmin(np.abs(offsets_ms - marker_offset)))
        df.loc[idx, "synthetic_marker"] = row.cohort
    return df.sort_values(["timestamp", "event_id"]).reset_index(drop=True)


def generate_synthetic_feeds(config: dict) -> SyntheticBundle:
    rng = np.random.default_rng(int(config["random_seed"]))
    start_time = pd.Timestamp(config["start_time"])
    if start_time.tzinfo is None:
        start_time = start_time.tz_localize("UTC")
    else:
        start_time = start_time.tz_convert("UTC")

    schedule = _episode_schedule(config, rng)
    feed_a_offsets = _make_offsets(rng, int(config["feed_a_events"]), int(config["duration_seconds"]))
    feed_b_offsets = _make_offsets(rng, int(config["feed_b_events"]), int(config["duration_seconds"]))
    delay_ms = int(config["feed_b_delay_seconds"]) * 1000

    feed_a = _make_feed("feed_a", feed_a_offsets, start_time, schedule, config, rng, delay_ms=0)
    feed_b = _make_feed("feed_b", feed_b_offsets, start_time, schedule, config, rng, delay_ms=delay_ms)

    schedule = schedule.copy()
    schedule["event_timestamp"] = start_time + pd.to_timedelta(schedule["event_offset_ms"], unit="ms")
    return SyntheticBundle(feed_a=feed_a, feed_b=feed_b, episodes=schedule)
