from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _safe_auc(y_true: np.ndarray, scores: np.ndarray) -> float | None:
    try:
        from sklearn.metrics import roc_auc_score

        if len(set(y_true.tolist())) < 2:
            return None
        return float(roc_auc_score(y_true, scores))
    except Exception:
        return None


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

    model_name = "lightgbm"
    fallback_reason = None
    try:
        from lightgbm import LGBMClassifier

        model = LGBMClassifier(
            n_estimators=35,
            learning_rate=0.08,
            max_depth=3,
            random_state=int(config["random_seed"]),
            verbose=-1,
        )
        model.fit(x_train, y_train)
        scores = model.predict_proba(x_test)[:, 1]
        predictions = (scores >= 0.5).astype(int)
    except Exception as exc:
        model_name = "sklearn_logistic_regression"
        fallback_reason = f"LightGBM unavailable or unsuitable; used scikit-learn fallback ({exc.__class__.__name__})."
        try:
            from sklearn.linear_model import LogisticRegression

            model = LogisticRegression(max_iter=500, random_state=int(config["random_seed"]))
            model.fit(x_train, y_train)
            scores = model.predict_proba(x_test)[:, 1]
            predictions = (scores >= 0.5).astype(int)
        except Exception as second_exc:
            model_name = "constant_rate_baseline"
            fallback_reason = (
                "LightGBM and scikit-learn model fitting were unavailable; "
                f"used constant-rate baseline ({second_exc.__class__.__name__})."
            )
            train_rate = float(np.mean(y_train)) if len(y_train) else 0.0
            scores = np.full(len(y_test), train_rate)
            predictions = (scores >= 0.5).astype(int)

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
