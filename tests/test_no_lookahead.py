from portfolio_case.pipeline import build_asof_alignment, normalise_feeds
from portfolio_case.synthetic_data import generate_synthetic_feeds
from portfolio_case.validation import validate_asof_no_lookahead


def _config() -> dict:
    return {
        "random_seed": 7,
        "start_time": "2026-01-01T00:00:00Z",
        "duration_seconds": 1200,
        "feed_a_events": 180,
        "feed_b_events": 220,
        "episode_count": 6,
        "pre_window_seconds": 60,
        "post_window_seconds": 120,
        "feed_b_delay_seconds": 4,
        "response_amplitude": 1.0,
    }


def test_asof_alignment_never_uses_future_rows() -> None:
    bundle = generate_synthetic_feeds(_config())
    feeds = normalise_feeds(bundle)
    aligned = build_asof_alignment(feeds)
    validate_asof_no_lookahead(aligned)
    usable = aligned["other_timestamp"].notna()
    assert (aligned.loc[usable, "other_timestamp"] <= aligned.loc[usable, "timestamp"]).all()
