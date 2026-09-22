import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from smarttrading.config import load_settings
from smarttrading.data.realtime import CandleEvent
from smarttrading.domain import Bar
from smarttrading.features.pipeline import CausalFeaturePipeline
from smarttrading.models.artifacts import ModelArtifact, ModelRegistry, ModelStatus
from smarttrading.models.ensemble import EnsembleConfig, WeightedEnsemble
from smarttrading.paper.engine import PaperTradingEngine
from smarttrading.paper.journal import DecisionRecord, explain
from smarttrading.paper.persistence import PaperStore


def artifact(probability: float = 0.9) -> ModelArtifact:
    pipeline = CausalFeaturePipeline()
    names = tuple(sorted(pipeline.transform(make_bars(50))[-1].values))
    return ModelArtifact.create(
        model_name="constant",
        feature_version=pipeline.config.version,
        dataset_hash="synthetic",
        training_start="2024-01-01",
        training_end="2024-12-31",
        validation_metrics={"brier": 0.25},
        feature_names=names,
        constant_probability=probability,
    )


def make_bars(count: int) -> list[Bar]:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    return [
        Bar(
            timestamp=start + timedelta(minutes=5 * index),
            asset="BTC/USDT",
            timeframe="5m",
            open=Decimal(100 + index),
            high=Decimal(102 + index),
            low=Decimal(99 + index),
            close=Decimal(101 + index),
            volume=Decimal(1000 + index * 3),
        )
        for index in range(count)
    ]


def candle(value: Bar) -> CandleEvent:
    return CandleEvent(
        event_id=f"{value.asset}:{value.timestamp.isoformat()}",
        bar=value,
        closed=True,
        received_at=value.timestamp + timedelta(minutes=5),
    )


def test_artifact_validation_promotion_and_feature_mismatch(tmp_path: Path) -> None:
    value = artifact()
    path = tmp_path / "model.json"
    path.write_text(value.model_dump_json(), encoding="utf-8")
    assert ModelArtifact.load(path, value.feature_version) == value
    with pytest.raises(ValueError, match="feature version"):
        ModelArtifact.load(path, "wrong")
    tampered = json.loads(path.read_text())
    tampered["model_version"] = "invalid"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        ModelArtifact.load(path, value.feature_version)
    registry = ModelRegistry(tmp_path / "registry.db")
    registry.register(value)
    assert registry.status(value.model_version) is ModelStatus.CANDIDATE
    registry.promote_to_paper(value.model_version)
    assert registry.status(value.model_version) is ModelStatus.PAPER


def test_chaos_restart_idempotency_and_persistent_risk(tmp_path: Path) -> None:
    database = tmp_path / "paper.db"
    settings = load_settings()
    value = artifact()
    ensemble = WeightedEnsemble(EnsembleConfig(weights={"constant": 1.0}))
    store = PaperStore(database)
    engine = PaperTradingEngine(settings, store, (value,), ensemble, shadow_names=("shadow",))
    bars = make_bars(45)
    for item in bars[:42]:
        engine.process(candle(item))
    engine.risk.activate_kill_switch()
    engine.risk.record_execution_error()
    engine.risk.record_execution_error()
    engine.risk.record_execution_error()
    engine.process(candle(bars[42]))
    cash_before = engine.account.cash
    orders_before = len(store.events("order"))
    decisions_before = len(store.events("decision"))
    store.close()  # abrupt process boundary after committed event/state transactions

    recovered_store = PaperStore(database)
    recovered = PaperTradingEngine(
        settings, recovered_store, (value,), ensemble, shadow_names=("shadow",)
    )
    assert recovered.account.cash == cash_before
    assert recovered.risk.kill_switch
    assert recovered.risk.circuit_state.value == "open"
    assert recovered.process(candle(bars[42])) is None
    assert len(recovered_store.events("order")) == orders_before
    assert len(recovered_store.events("decision")) == decisions_before
    recovered.process(candle(bars[44]))  # missing candle simulates REST-reconciled gap
    assert recovered.buffer.missing
    assert recovered.shadows.accounts["shadow"].cash == settings.initial_cash

    payload = recovered_store.events("decision")[-1]["payload"]
    record = DecisionRecord.model_validate(payload)
    assert explain(record) == explain(record)
    assert record.decision.value in {"buy", "exit", "abstain"}


def test_unsafe_stale_feed_blocks_new_exposure(tmp_path: Path) -> None:
    store = PaperStore(tmp_path / "unsafe.db")
    settings = load_settings()
    value = artifact(0.95)
    engine = PaperTradingEngine(
        settings,
        store,
        (value,),
        WeightedEnsemble(EnsembleConfig(weights={"constant": 1.0})),
    )
    record = None
    for bar in make_bars(45):
        record = engine.process(
            CandleEvent(
                event_id=f"stale:{bar.timestamp.isoformat()}",
                bar=bar,
                closed=True,
                received_at=bar.timestamp + timedelta(hours=1),
            )
        )
    assert record is not None
    assert record.decision.value == "abstain"
    assert record.ensemble_prediction["health_override"] == "unsafe_blocks_new_exposure"
    assert store.events("order") == []
    assert engine.status()["health"] == "UNSAFE"
    store.close()
