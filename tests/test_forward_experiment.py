from __future__ import annotations

import csv
import math
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pandas import DataFrame
from sklearn.datasets import make_classification

from smarttrading.models.artifacts import ModelArtifact
from smarttrading.models.freeze import freeze_real_artifact
from smarttrading.models.splitting import SealedFinalHoldout
from smarttrading.models.training import make_model
from smarttrading.paper.forward import (
    ExperimentHealth,
    ExperimentLock,
    FrozenExperimentConfig,
    daily_snapshot,
    export_experiment,
    health_from_signals,
    mature_predictions,
    prediction_id,
    reconcile_accounting,
)
from smarttrading.paper.persistence import PaperStore


def config(frozen_at: datetime | None = None) -> FrozenExperimentConfig:
    return FrozenExperimentConfig(
        artifact_versions=("a", "b", "c", "d"),
        feature_version="features-v1",
        target={"prediction_horizon": 6, "return_threshold": 0.001},
        thresholds={
            "buy_threshold": 0.60,
            "exit_threshold": 0.45,
            "abstain_confidence": 0.20,
            "disagreement_penalty": 1.0,
        },
        ensemble_weights={"a": 0.5, "b": 0.5},
        costs={"taker_fee_bps": 5, "spread_bps": 2, "slippage_bps": 1},
        sizing={"max_asset_allocation": 0.25},
        risk_limits={"max_portfolio_exposure": 0.60},
        shadow_strategies=("logistic-btc", "gradient-btc", "momentum"),
        drift_thresholds={"psi": 0.2, "ks": 0.1},
        evaluation_metrics=("roc_auc", "brier_score"),
        configuration_frozen_at=frozen_at or datetime(2026, 9, 22, tzinfo=UTC),
    )


def test_experiment_id_determinism_and_immutability(tmp_path: Path) -> None:
    first = config()
    assert first.experiment_id == config().experiment_id
    store = PaperStore(tmp_path / "forward.db")
    started = datetime(2026, 9, 22, 1, tzinfo=UTC)
    metadata = ExperimentLock.start_or_resume(store, first, started)
    assert ExperimentLock.start_or_resume(store, first).experiment_id == metadata.experiment_id
    changed = first.model_copy(update={"starting_capital": Decimal("90000")})
    try:
        ExperimentLock.start_or_resume(store, changed)
    except ValueError as error:
        assert "immutable" in str(error)
    else:
        raise AssertionError("modified frozen experiment was accepted")
    store.close()


def test_real_estimators_round_trip_without_prediction_change(tmp_path: Path) -> None:
    X, y = make_classification(n_samples=120, n_features=4, random_state=17)
    values = {f"f{index}": float(value) for index, value in enumerate(X[0])}
    frame = DataFrame(X, columns=tuple(values))
    for name in ("logistic", "gradient_boosting"):
        estimator = make_model(name, 17)
        estimator.fit(frame, y)
        encoded, digest = ModelArtifact.serialize_estimator(estimator)
        artifact = ModelArtifact.create(
            model_name=name,
            feature_version="features-v1",
            dataset_hash="dataset",
            training_start="start",
            training_end="end",
            validation_metrics={"roc_auc": 0.5},
            feature_names=tuple(values),
            estimator_b64=encoded,
            estimator_sha256=digest,
        )
        path = tmp_path / f"{name}.json"
        path.write_text(artifact.model_dump_json(), encoding="utf-8")
        loaded = ModelArtifact.load(path, "features-v1")
        assert loaded.predict_probability(values) == artifact.predict_probability(values)


def test_prediction_ids_health_and_accounting_are_deterministic() -> None:
    timestamp = datetime(2026, 9, 22, tzinfo=UTC)
    assert prediction_id("exp", "BTC/USDT", timestamp) == prediction_id(
        "exp", "BTC/USDT", timestamp
    )
    assert health_from_signals()[0] is ExperimentHealth.HEALTHY
    assert health_from_signals(reconnects=3)[0] is ExperimentHealth.DEGRADED
    assert health_from_signals(artifact_match=False)[0] is ExperimentHealth.UNSAFE
    state = {
        "cash": "90",
        "equity": "110",
        "positions": {"BTC/USDT": {"quantity": "2", "average_entry_price": "10"}},
    }
    assert reconcile_accounting(state, {"BTC/USDT": Decimal("10")})[0] is ExperimentHealth.HEALTHY
    state["equity"] = "111"
    assert reconcile_accounting(state, {"BTC/USDT": Decimal("10")})[0] is ExperimentHealth.UNSAFE


def test_report_and_export_are_reproducible(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "forward.db")
    frozen = config(datetime(2026, 9, 21, tzinfo=UTC))
    ExperimentLock.start_or_resume(store, frozen, datetime(2026, 9, 22, tzinfo=UTC))
    now = datetime(2026, 9, 22, 12, tzinfo=UTC)
    first, _ = daily_snapshot(store, tmp_path / "reports", now)
    before = first.read_bytes()
    second, _ = daily_snapshot(store, tmp_path / "reports", now)
    assert before == second.read_bytes()
    bundle = export_experiment(store, tmp_path / "bundle")
    assert (bundle / "frozen_config.json").exists()
    store.close()


def test_configuration_must_be_frozen_before_start(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "forward.db")
    try:
        ExperimentLock.start_or_resume(
            store,
            config(datetime(2026, 9, 23, tzinfo=UTC)),
            datetime(2026, 9, 22, tzinfo=UTC),
        )
    except ValueError as error:
        assert "frozen before" in str(error)
    else:
        raise AssertionError("post-start freeze was accepted")
    store.close()


def test_prediction_maturity_is_idempotent_and_evaluation_only(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "forward.db")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    pid = prediction_id("exp", "BTC/USDT", start)
    store.append(
        f"prediction:{pid}",
        "forward_prediction",
        start.isoformat(),
        {
            "prediction_id": pid,
            "experiment_id": "exp",
            "prediction_timestamp": start.isoformat(),
            "asset": "BTC/USDT",
            "probability_up": 0.7,
        },
    )
    for index, close in enumerate((100, 101, 103)):
        timestamp = start + timedelta(hours=index)
        store.append(
            f"bar:{index}",
            "closed_bar",
            timestamp.isoformat(),
            {
                "timestamp": timestamp.isoformat(),
                "asset": "BTC/USDT",
                "close": str(close),
            },
        )
    outcomes = mature_predictions(
        store,
        experiment_id="exp",
        horizon_bars=2,
        return_threshold=0.01,
        round_trip_cost=0.002,
    )
    assert len(outcomes) == 1
    assert outcomes[0].realized_class == 1
    assert outcomes[0].transaction_cost_adjusted_outcome == pytest.approx(0.028)
    assert (
        mature_predictions(
            store,
            experiment_id="exp",
            horizon_bars=2,
            return_threshold=0.01,
            round_trip_cost=0.002,
        )
        == []
    )
    assert store.events("training_event") == []
    store.close()


def test_artifact_freeze_never_opens_final_holdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dataset = tmp_path / "bars.csv"
    start = datetime(2025, 1, 1, tzinfo=UTC)
    with dataset.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["timestamp", "asset", "timeframe", "open", "high", "low", "close", "volume"]
        )
        for index in range(500):
            close = 100 + index * 0.01 + math.sin(index / 3) * 2
            writer.writerow(
                [
                    (start + timedelta(hours=index)).isoformat(),
                    "BTC/USDT",
                    "1h",
                    close,
                    close + 1,
                    close - 1,
                    close,
                    1000 + index,
                ]
            )

    def forbidden_open(
        self: SealedFinalHoldout, *, explicit_final_evaluation: bool = False
    ) -> tuple[int, ...]:
        del self, explicit_final_evaluation
        raise AssertionError("final holdout was opened")

    monkeypatch.setattr(SealedFinalHoldout, "open", forbidden_open)
    artifact = freeze_real_artifact(
        dataset,
        model_name="logistic",
        asset="BTC/USDT",
        output=tmp_path / "artifact.json",
    )
    assert artifact.preprocessing_configuration["final_holdout"] == "SEALED"
