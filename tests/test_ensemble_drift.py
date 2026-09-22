from datetime import UTC, datetime

import pytest

from smarttrading.domain import DecisionAction
from smarttrading.models.ensemble import EnsembleConfig, WeightedEnsemble
from smarttrading.monitoring.drift import (
    calibration_degradation,
    class_balance_change,
    ks_statistic,
    population_stability_index,
)


def test_ensemble_determinism_disagreement_and_abstention() -> None:
    ensemble = WeightedEnsemble(
        EnsembleConfig(weights={"logistic": 0.5, "gradient": 0.5}, abstain_confidence=0.3)
    )
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    agreed = ensemble.combine(timestamp, "BTC/USDT", {"logistic": 0.8, "gradient": 0.8})
    assert agreed == ensemble.combine(timestamp, "BTC/USDT", {"logistic": 0.8, "gradient": 0.8})
    assert agreed.action is DecisionAction.BUY
    disagree = ensemble.combine(timestamp, "BTC/USDT", {"logistic": 0.8, "gradient": 0.2})
    assert disagree.action is DecisionAction.ABSTAIN
    assert disagree.confidence < agreed.confidence


def test_drift_is_reproducible() -> None:
    reference = [float(index) for index in range(100)]
    shifted = [float(index + 20) for index in range(100)]
    assert population_stability_index(reference, shifted) == population_stability_index(
        reference, shifted
    )
    assert ks_statistic(reference, shifted) == pytest.approx(0.2)
    assert calibration_degradation(0.2, [0, 1], [0.1, 0.9]) is None
    labels = [0, 1] * 20
    assert calibration_degradation(0.1, labels, [0.5] * 40) == pytest.approx(0.15)
    assert class_balance_change([0, 0, 1, 1], [1, 1, 1, 0]) == 0.25
