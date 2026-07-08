import pandas as pd
import pytest

from causal_pipeline.validation import ValidationError, validate_feed_contract


def _valid_feed() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z"],
                utc=True,
            ),
            "event_id": ["feed_a_000001", "feed_a_000002", "feed_a_000003"],
            "source": ["feed_a", "feed_a", "feed_a"],
            "observed_value": [100.0, 100.1, 100.2],
            "noise": [0.0, 0.01, -0.01],
            "synthetic_marker": ["none", "rebound", "none"],
        }
    )


def test_required_columns_and_valid_contract_pass() -> None:
    results = validate_feed_contract(_valid_feed(), "feed_a")
    assert {item.name for item in results} >= {
        "feed_a:required_columns",
        "feed_a:no_null_timestamps",
        "feed_a:unique_event_ids",
        "feed_a:timestamp_monotonicity",
    }


def test_duplicate_event_id_detection() -> None:
    df = _valid_feed()
    df.loc[2, "event_id"] = df.loc[1, "event_id"]
    with pytest.raises(ValidationError, match="duplicate"):
        validate_feed_contract(df, "feed_a")


def test_timestamp_monotonicity_detection() -> None:
    df = _valid_feed()
    df.loc[2, "timestamp"] = pd.Timestamp("2025-12-31T23:59:59Z")
    with pytest.raises(ValidationError, match="non-monotonic"):
        validate_feed_contract(df, "feed_a")
