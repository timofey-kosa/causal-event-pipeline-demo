import numpy as np
import pytest

from causal_pipeline.temporal_cv import bootstrap_ci, embargoed_time_folds


def test_folds_never_train_on_test_or_embargo_rows() -> None:
    embargo = 3
    folds = embargoed_time_folds(n_rows=100, n_folds=4, embargo=embargo)
    assert len(folds) >= 2
    for tf in folds:
        # training rows are strictly earlier than the test block ...
        assert tf.train_index.max() < tf.test_index.min()
        # ... and the embargo gap immediately before the test block is withheld.
        assert tf.train_index.max() < tf.test_index.min() - embargo
        assert set(tf.train_index).isdisjoint(set(tf.test_index))


def test_folds_are_time_ordered_and_expanding() -> None:
    folds = embargoed_time_folds(n_rows=120, n_folds=5, embargo=0)
    test_starts = [tf.test_index.min() for tf in folds]
    train_sizes = [len(tf.train_index) for tf in folds]
    assert test_starts == sorted(test_starts)
    assert train_sizes == sorted(train_sizes)


def test_embargoed_folds_reject_bad_arguments() -> None:
    with pytest.raises(ValueError):
        embargoed_time_folds(n_rows=100, n_folds=1, embargo=0)
    with pytest.raises(ValueError):
        embargoed_time_folds(n_rows=0, n_folds=4, embargo=0)


def test_bootstrap_ci_brackets_the_mean_and_is_deterministic() -> None:
    values = np.array([0.6, 0.62, 0.58, 0.65, 0.55])
    a = bootstrap_ci(values, n_samples=500, seed=1)
    b = bootstrap_ci(values, n_samples=500, seed=1)
    assert a == b  # deterministic given the seed
    assert a["lower"] <= a["mean"] <= a["upper"]
    assert a["n"] == 5


def test_bootstrap_ci_handles_empty_and_singleton() -> None:
    empty = bootstrap_ci(np.array([]), seed=0)
    assert empty["n"] == 0 and np.isnan(empty["mean"])
    one = bootstrap_ci(np.array([0.7]), seed=0)
    assert one == {"mean": 0.7, "lower": 0.7, "upper": 0.7, "n": 1}
