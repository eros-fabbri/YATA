import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from smarttrading.config import load_settings
from smarttrading.features.dataset import MLDatasetBuilder
from smarttrading.features.pipeline import CausalFeaturePipeline
from smarttrading.features.target import TargetConfig
from smarttrading.models.experiment import economic_evaluation
from smarttrading.models.splitting import expanding_walk_forward, seal_final_holdout
from smarttrading.models.training import walk_forward_train
from tests.helpers import bars_from_prices


def dataset() -> object:
    rng = np.random.default_rng(7)
    changes = rng.normal(0.001, 0.01, 320)
    prices = 100 * np.exp(np.cumsum(changes))
    return MLDatasetBuilder(
        CausalFeaturePipeline(), TargetConfig(prediction_horizon=3, return_threshold=0.001)
    ).build(bars_from_prices([str(value) for value in prices]))


def test_purging_embargo_and_sealed_holdout() -> None:
    folds = expanding_walk_forward(
        200,
        minimum_train_size=80,
        validation_size=20,
        step_size=20,
        horizon=5,
        embargo=3,
    )
    for fold in folds:
        assert max(fold.train) + 5 < min(fold.validation)
        assert min(fold.validation) - (max(fold.train) + 5) >= 3
    sealed = seal_final_holdout(200)
    assert "SEALED" in repr(sealed)
    with pytest.raises(PermissionError):
        sealed.open()


def test_walk_forward_is_reproducible() -> None:
    data = dataset()
    folds = expanding_walk_forward(
        len(data.X),
        minimum_train_size=100,
        validation_size=30,
        step_size=30,
        horizon=3,
        embargo=2,
        max_folds=3,
    )
    first = walk_forward_train(data, folds, "logistic", seed=11)
    second = walk_forward_train(data, folds, "logistic", seed=11)
    assert first.predictions == second.predictions
    assert first.metrics == second.metrics


def test_random_labels_collapse_and_deliberate_future_leak_is_suspicious() -> None:
    rng = np.random.default_rng(42)
    y = np.tile([0, 1], 200)
    legitimate = y + rng.normal(0, 0.2, len(y))
    original = roc_auc_score(
        y,
        LogisticRegression()
        .fit(legitimate.reshape(-1, 1), y)
        .predict_proba(legitimate.reshape(-1, 1))[:, 1],
    )
    shuffled = rng.permutation(y)
    shuffled_auc = roc_auc_score(
        shuffled,
        LogisticRegression()
        .fit(legitimate.reshape(-1, 1), shuffled)
        .predict_proba(legitimate.reshape(-1, 1))[:, 1],
    )
    leaked = pd.DataFrame({"future_target": y})
    leak_auc = roc_auc_score(y, LogisticRegression().fit(leaked, y).predict_proba(leaked)[:, 1])
    assert original > 0.9 and abs(shuffled_auc - 0.5) < 0.15
    assert leak_auc > 0.99


def test_constant_price_has_no_magical_edge_or_pnl() -> None:
    bars = bars_from_prices(["100"] * 260)
    data = MLDatasetBuilder(
        CausalFeaturePipeline(), TargetConfig(prediction_horizon=3, return_threshold=0.001)
    ).build(bars)
    folds = expanding_walk_forward(
        len(data.X),
        minimum_train_size=100,
        validation_size=30,
        step_size=30,
        horizon=3,
        embargo=1,
        max_folds=2,
    )
    predictive = walk_forward_train(data, folds, "dummy", seed=5)
    economic = economic_evaluation(bars, predictive, load_settings(), seed=5)
    assert predictive.metrics.roc_auc is None
    assert economic.ml.metrics.total_return == 0
    assert economic.ml.metrics.total_fees == 0
