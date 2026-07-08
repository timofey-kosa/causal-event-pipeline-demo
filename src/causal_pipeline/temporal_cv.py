"""Embargoed temporal cross-validation and bootstrap confidence intervals.

These are deliberately small, dependency-light implementations of two protocol
pieces that matter for honest evaluation of event-response models:

* time-ordered folds with an embargo gap between train and test, so that rows
  adjacent in time to the test window cannot leak into training;
* a percentile bootstrap confidence interval, so that a reported metric carries
  an uncertainty band rather than a single point value.

Everything here operates on chronologically ordered inputs. No row is ever used
for training if it lies at or after the start of its test fold (minus the
embargo). The functions are pure and deterministic given a seed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class TimeFold:
    fold: int
    train_index: np.ndarray
    test_index: np.ndarray


def embargoed_time_folds(n_rows: int, n_folds: int, embargo: int = 0) -> list[TimeFold]:
    """Expanding-window folds over chronologically ordered rows.

    Fold ``k`` trains on the earliest rows and tests on the next contiguous
    block. An ``embargo`` gap of that many rows immediately before each test
    block is withheld from training, so no row bordering the test window in time
    is used to fit the model. Assumes the caller has already sorted rows by time.
    """
    if n_rows <= 0:
        raise ValueError("n_rows must be positive")
    if n_folds < 2:
        raise ValueError("n_folds must be at least 2")
    if embargo < 0:
        raise ValueError("embargo must be non-negative")

    # First segment seeds the initial training window; the remaining segments
    # are each used once as a test block in chronological order.
    segment = max(1, n_rows // (n_folds + 1))
    folds: list[TimeFold] = []
    for k in range(1, n_folds + 1):
        test_start = k * segment
        test_end = n_rows if k == n_folds else (k + 1) * segment
        if test_start >= n_rows:
            break
        train_end = max(0, test_start - embargo)
        if train_end <= 0:
            continue
        train_index = np.arange(0, train_end)
        test_index = np.arange(test_start, test_end)
        if len(test_index) == 0:
            continue
        folds.append(TimeFold(fold=len(folds), train_index=train_index, test_index=test_index))
    if not folds:
        raise ValueError("no valid folds could be built; reduce n_folds or embargo")
    return folds


def bootstrap_ci(
    values: np.ndarray,
    n_samples: int = 1000,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, float | int]:
    """Percentile bootstrap confidence interval for the mean of ``values``."""
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    if n == 0:
        return {"mean": float("nan"), "lower": float("nan"), "upper": float("nan"), "n": 0}
    if n == 1:
        v = float(values[0])
        return {"mean": v, "lower": v, "upper": v, "n": 1}

    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, n, size=(n_samples, n))].mean(axis=1)
    lower = float(np.quantile(means, alpha / 2.0))
    upper = float(np.quantile(means, 1.0 - alpha / 2.0))
    return {"mean": float(values.mean()), "lower": lower, "upper": upper, "n": n}
