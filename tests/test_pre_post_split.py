from causal_pipeline.pipeline import (
    build_asof_alignment,
    build_episodes,
    build_post_entry_tape,
    build_pre_entry_tape,
    generate_features,
    normalise_feeds,
)
from causal_pipeline.synthetic_data import generate_synthetic_feeds
from causal_pipeline.validation import (
    validate_no_outcome_feature_leakage,
    validate_post_entry_tape,
    validate_pre_entry_tape,
)


def _config() -> dict:
    return {
        "random_seed": 11,
        "start_time": "2026-01-01T00:00:00Z",
        "duration_seconds": 1800,
        "feed_a_events": 240,
        "feed_b_events": 300,
        "episode_count": 6,
        "pre_window_seconds": 90,
        "post_window_seconds": 180,
        "feed_b_delay_seconds": 5,
        "response_amplitude": 1.1,
    }


def test_pre_and_post_tapes_are_separated() -> None:
    config = _config()
    bundle = generate_synthetic_feeds(config)
    feeds = normalise_feeds(bundle)
    aligned = build_asof_alignment(feeds)
    episodes = build_episodes(feeds, bundle.episodes)

    pre_entry = build_pre_entry_tape(aligned, episodes, config["pre_window_seconds"])
    post_entry = build_post_entry_tape(aligned, episodes, pre_entry, config["post_window_seconds"])

    validate_pre_entry_tape(pre_entry)
    validate_post_entry_tape(post_entry)
    assert (pre_entry["timestamp"] < pre_entry["event_timestamp"]).all()
    assert (post_entry["timestamp"] >= post_entry["event_timestamp"]).all()
    assert (post_entry["elapsed_ms"] >= 0).all()


def test_post_outcomes_do_not_leak_into_pre_features() -> None:
    config = _config()
    bundle = generate_synthetic_feeds(config)
    feeds = normalise_feeds(bundle)
    aligned = build_asof_alignment(feeds)
    episodes = build_episodes(feeds, bundle.episodes)
    pre_entry = build_pre_entry_tape(aligned, episodes, config["pre_window_seconds"])
    post_entry = build_post_entry_tape(aligned, episodes, pre_entry, config["post_window_seconds"])
    features = generate_features(pre_entry, post_entry, episodes, target_response_threshold=0.2)

    validate_no_outcome_feature_leakage(features)
    feature_columns = [col for col in features.columns if col.startswith("feature_")]
    assert feature_columns
    assert all("outcome" not in col for col in feature_columns)
