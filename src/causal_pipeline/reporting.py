from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def write_demo_report(
    report_path: Path,
    run_id: str,
    config: dict,
    row_counts: dict[str, int],
    validations: list[dict[str, object]],
    cohort_summary: pd.DataFrame,
    model_metrics: dict[str, Any],
) -> None:
    validation_lines = "\n".join(
        f"- {item['name']}: {'passed' if item['passed'] else 'failed'} ({item['detail']})" for item in validations
    )
    cohort_lines = "\n".join(
        f"- {row.cohort}: episodes={int(row.episode_count)}, "
        f"mean_rebound_strength={row.mean_rebound_strength:.4f}, "
        f"share_high_response={row.share_high_response:.3f}"
        for row in cohort_summary.itertuples(index=False)
    )
    row_count_lines = "\n".join(f"- {name}: {count}" for name, count in sorted(row_counts.items()))
    fallback = model_metrics.get("fallback_reason") or "No fallback was needed."

    cv = model_metrics.get("embargoed_cv") or {}
    if cv.get("status") == "ok":
        fold_lines = "\n".join(
            f"- fold {r['fold']}: train_rows={r['train_rows']}, test_rows={r['test_rows']}, "
            f"embargo_rows={r['embargo_rows']}, auc={r['auc']}"
            for r in cv.get("folds", [])
        )
        ci = cv.get("auc_ci") or {}
        cv_block = (
            f"{fold_lines}\n\n"
            f"Fold AUC bootstrap 95% CI: mean={ci.get('mean')}, "
            f"lower={ci.get('lower')}, upper={ci.get('upper')} (n_folds={ci.get('n')})."
        )
    else:
        cv_block = f"Embargoed CV was skipped ({cv.get('reason', 'unavailable')})."

    text = f"""# Demo Report

## Run

- run id: `{run_id}`
- random seed: `{config['synthetic']['random_seed']}`
- all data: synthetic

## Data Volume

{row_count_lines}

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

{validation_lines}

## Pre/Post Separation

Pre-entry rows are strictly before each synthetic event timestamp. Post-entry rows start at or after that timestamp and carry non-negative elapsed time. Outcome columns are generated from post-entry trajectories and are not used as model features.

## Cohort Analysis

{cohort_lines}

## Rebound Demonstration

The `rebound` cohort is synthetic by construction and is included to make the trajectory analysis visible in `figures/rebound_pattern.png`.

## Baseline Model Scaffold

- model: `{model_metrics['model_name']}`
- train rows: `{model_metrics['train_rows']}`
- test rows: `{model_metrics['test_rows']}`
- accuracy: `{model_metrics['accuracy']}`
- roc_auc: `{model_metrics['roc_auc']}`
- fallback: {fallback}

The modelling stage is included as an evaluation scaffold, not as a performance claim. In the public synthetic demo, the baseline is intentionally simple and illustrative. Metric values are run artefacts rather than selling points.

## Embargoed Temporal Cross-Validation

Each fold trains only on rows strictly earlier than its test block, with an embargo gap of rows withheld immediately before the test window so no time-adjacent row leaks into training. Fold AUCs are summarised with a percentile bootstrap confidence interval.

{cv_block}

## Limitations

- Synthetic data only.
- Simplified public demo.
- No real thresholds.
- No real operational rules.
- No real venues.
- Not deployable.
- Methodology demonstration only.
"""
    report_path.write_text(text, encoding="utf-8")
