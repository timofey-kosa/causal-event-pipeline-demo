from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from causal_pipeline.temporal_cv import bootstrap_ci, embargoed_time_folds


def _safe_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    try:
        from sklearn.metrics import roc_auc_score

        if len(set(y_true.tolist())) < 2:
            return None
        return float(roc_auc_score(y_true, scores))
    except Exception:
        return None


def _fit_predict(
    x_train: pd.DataFrame,
    y_train: np.ndarray,
    x_test: pd.DataFrame,
    seed: int,
) -> tuple[np.ndarray, str, str | None]:
    """Fit the best available model and score the test rows.

    Falls back from LightGBM to scikit-learn logistic regression to a constant
    positive-rate baseline so the demo runs in any environment. Returns the
    positive-class scores, the model name, and a fallback reason if one applied.
    """
    try:
        from lightgbm import LGBMClassifier

        model = LGBMClassifier(
            n_estimators=35,
            learning_rate=0.08,
            max_depth=3,
            random_state=seed,
            verbose=-1,
        )
        model.fit(x_train, y_train)
        return model.predict_proba(x_test)[:, 1], "lightgbm", None
    except Exception as exc:
        try:
            from sklearn.linear_model import LogisticRegression

            model = LogisticRegression(max_iter=500, random_state=seed)
            model.fit(x_train, y_train)
            reason = f"LightGBM unavailable or unsuitable; used scikit-learn fallback ({exc.__class__.__name__})."
            return model.predict_proba(x_test)[:, 1], "sklearn_logistic_regression", reason
        except Exception as second_exc:
            train_rate = float(np.mean(y_train)) if len(y_train) else 0.0
            reason = (
                "LightGBM and scikit-learn model fitting were unavailable; "
                f"used constant-rate baseline ({second_exc.__class__.__name__})."
            )
            return np.full(len(x_test), train_rate), "constant_rate_baseline", reason


def evaluate_embargoed_cv(
    ordered: pd.DataFrame,
    feature_columns: list[str],
    config: dict,
) -> dict[str, Any]:
    """Embargoed temporal cross-validation with a bootstrap CI on fold AUC.

    Rows are already time-ordered. Each fold trains only on rows strictly before
    its test block, with an embargo gap withheld so no row bordering the test
    window in time leaks into training. The per-fold AUCs are summarised with a
    percentile bootstrap confidence interval.
    """
    n_folds = int(config.get("cv_folds", 4))
    embargo = int(config.get("cv_embargo_rows", 2))
    seed = int(config["random_seed"])

    x_all = ordered[feature_columns].fillna(0.0)
    y_all = ordered["target_high_response"].astype(int).to_numpy()

    fold_records: list[dict[str, Any]] = []
    try:
        folds = embargoed_time_folds(len(ordered), n_folds, embargo)
    except ValueError as exc:
        return {"status": "skipped", "reason": str(exc), "folds": [], "auc_ci": None}

    for tf in folds:
        scores, _, _ = _fit_predict(
            x_all.iloc[tf.train_index], y_all[tf.train_index], x_all.iloc[tf.test_index], seed
        )
        y_test = y_all[tf.test_index]
        fold_records.append(
            {
                "fold": tf.fold,
                "train_rows": int(len(tf.train_index)),
                "test_rows": int(len(tf.test_index)),
                "embargo_rows": embargo,
                "auc": _safe_auc(y_test, scores),
            }
        )

    aucs = np.array([r["auc"] for r in fold_records if r["auc"] is not None], dtype=float)
    auc_ci = bootstrap_ci(aucs, n_samples=int(config.get("bootstrap_samples", 1000)), seed=seed)
    return {"status": "ok", "folds": fold_records, "auc_ci": auc_ci}


def train_baseline_model(features: pd.DataFrame, config: dict, model_dir: Path, report_dir: Path) -> dict[str, Any]:
    model_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    feature_columns = [col for col in features.columns if col.startswith("feature_")]
    ordered = features.sort_values("event_timestamp").reset_index(drop=True)
    split_idx = max(1, int(len(ordered) * (1.0 - float(config["test_fraction"]))))
    split_idx = min(split_idx, len(ordered) - 1)
    train = ordered.iloc[:split_idx]
    test = ordered.iloc[split_idx:]

    x_train = train[feature_columns].fillna(0.0)
    x_test = test[feature_columns].fillna(0.0)
    y_train = train["target_high_response"].astype(int).to_numpy()
    y_test = test["target_high_response"].astype(int).to_numpy()

    seed = int(config["random_seed"])
    scores, model_name, fallback_reason = _fit_predict(x_train, y_train, x_test, seed)
    predictions = (scores >= 0.5).astype(int)

    cv = evaluate_embargoed_cv(ordered, feature_columns, config)

    accuracy = float(np.mean(predictions == y_test)) if len(y_test) else None
    metrics: dict[str, Any] = {
        "model_name": model_name,
        "fallback_reason": fallback_reason,
        "feature_columns": feature_columns,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "temporal_split_event_timestamp": str(test["event_timestamp"].iloc[0]) if len(test) else None,
        "accuracy": accuracy,
        "roc_auc": _safe_auc(y_test, scores) if len(y_test) else None,
        "positive_rate_train": float(np.mean(y_train)) if len(y_train) else None,
        "positive_rate_test": float(np.mean(y_test)) if len(y_test) else None,
        "embargoed_cv": cv,
    }

    metrics_path = report_dir / "model_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")

    model_text = [
        "Baseline model",
        f"model_name: {model_name}",
        f"train_rows: {metrics['train_rows']}",
        f"test_rows: {metrics['test_rows']}",
        "purpose: illustrative temporal evaluation only",
    ]
    if fallback_reason:
        model_text.append(f"fallback_reason: {fallback_reason}")
    (model_dir / "baseline_model.txt").write_text("\n".join(model_text) + "\n", encoding="utf-8")
    return metrics
