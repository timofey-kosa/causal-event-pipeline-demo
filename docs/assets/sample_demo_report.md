# Demo Report

## Run

- run id: `demo_20260708T022230Z_e6512daf`
- random seed: `41`
- all data: synthetic

## Data Volume

- asof_aligned: 8000
- cohort_summary: 3
- event_tape: 8000
- features: 220
- feed_a: 3600
- feed_b: 4400
- post_entry_tape: 36847
- pre_entry_tape: 18220

## Pipeline Stages Completed

- generate synthetic feeds
- normalise feeds
- build unified event tape
- ASOF alignment
- build pre-entry tape
- build post-entry tape
- feature generation
- mechanism-based cohort analysis
- V-shaped rebound demonstration
- baseline model scaffold
- artefact freezing

## Validation Checks

- feed_a:required_columns: passed (all required columns present)
- feed_a:no_null_timestamps: passed (timestamps are non-null)
- feed_a:unique_event_ids: passed (event identifiers are unique)
- feed_a:timestamp_monotonicity: passed (timestamps are monotonic by source)
- feed_b:required_columns: passed (all required columns present)
- feed_b:no_null_timestamps: passed (timestamps are non-null)
- feed_b:unique_event_ids: passed (event identifiers are unique)
- feed_b:timestamp_monotonicity: passed (timestamps are monotonic by source)
- event_tape:global_order: passed (event tape is globally ordered)
- asof:no_lookahead: passed (other-feed timestamps are past or current)
- pre_entry:strictly_before_event: passed (all pre-entry rows precede event time)
- post_entry:starts_at_event: passed (all post-entry rows are at or after event time)
- features:no_outcome_leakage: passed (feature columns do not include outcomes)

## Pre/Post Separation

Pre-entry rows are strictly before each synthetic event timestamp. Post-entry rows start at or after that timestamp and carry non-negative elapsed time. Outcome columns are generated from post-entry trajectories and are not used as model features.

## Cohort Analysis

- drift: episodes=73, mean_rebound_strength=1.0628, share_high_response=0.808
- rebound: episodes=74, mean_rebound_strength=1.8226, share_high_response=0.932
- steady: episodes=73, mean_rebound_strength=0.8228, share_high_response=0.630

## Rebound Demonstration

The `rebound` cohort is synthetic by construction and is included to make the trajectory analysis visible in `figures/rebound_pattern.png`.

## Baseline Model Scaffold

- model: `lightgbm`
- train rows: `154`
- test rows: `66`
- accuracy: `0.7727272727272727`
- roc_auc: `0.5103021978021978`
- fallback: No fallback was needed.

The modelling stage is included as an evaluation scaffold, not as a performance claim. In the public synthetic demo, the baseline is intentionally simple and illustrative. Metric values are run artefacts rather than selling points.

## Embargoed Temporal Cross-Validation

Each fold trains only on rows strictly earlier than its test block, with an embargo gap of rows withheld immediately before the test window so no time-adjacent row leaks into training. Fold AUCs are summarised with a percentile bootstrap confidence interval.

- fold 0: train_rows=42, test_rows=44, embargo_rows=2, auc=0.48382352941176465
- fold 1: train_rows=86, test_rows=44, embargo_rows=2, auc=0.49806949806949813
- fold 2: train_rows=130, test_rows=44, embargo_rows=2, auc=0.5482625482625483
- fold 3: train_rows=174, test_rows=44, embargo_rows=2, auc=0.6523809523809524

Fold AUC bootstrap 95% CI: mean=0.5456341320311908, lower=0.4945080059050647, upper=0.6138030888030888 (n_folds=4).

## Limitations

- Synthetic data only.
- Simplified public demo.
- No real thresholds.
- No real operational rules.
- No real venues.
- Not deployable.
- Methodology demonstration only.
