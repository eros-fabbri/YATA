from __future__ import annotations

import logging
import os
from collections import deque
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from smarttrading.data.market_store import MarketDataStore, inspect_storage
from smarttrading.data.market_v2 import (
    AggregateTradeEvent,
    BBOEvent,
    DepthUpdate,
    DerivativesEvent,
    LocalOrderBook,
    MarketContextSynchronizer,
)
from smarttrading.domain import OrderBookLevel, OrderBookSnapshot, Side
from smarttrading.features.dataset_v2 import DatasetV2Builder
from smarttrading.features.microstructure_v2 import (
    FEATURE_VERSION_V2,
    derivatives_features,
    microstructure_features,
)
from smarttrading.models.artifacts import ModelArtifact, ModelRegistry, ModelStatus
from smarttrading.monitoring.runtime import InstanceGuard, log_event, runtime_logger
from smarttrading.paper.shadow_v2 import (
    health_assessment,
    latency_percentiles,
    operational_health,
    readiness_assessment,
    run_shadow_v2,
    storage_guardrail,
    storage_measurement,
)

T = datetime(2025, 1, 1, tzinfo=UTC)


def level(price: str, quantity: str) -> OrderBookLevel:
    return OrderBookLevel(price=Decimal(price), quantity=Decimal(quantity))


def book(sequence: int = 10) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        timestamp=T,
        asset="BTC/USDT",
        sequence=sequence,
        bids=(level("99", "3"), level("98", "2")),
        asks=(level("101", "1"), level("102", "2")),
    )


def update(first: int, last: int, event_id: str = "u") -> DepthUpdate:
    return DepthUpdate(
        event_id=event_id,
        asset="BTC/USDT",
        event_timestamp=T + timedelta(seconds=1),
        received_at=T + timedelta(seconds=1),
        first_sequence=first,
        last_sequence=last,
        bids=(level("99", "4"),),
        asks=(level("102", "0"),),
    )


def test_order_book_update_duplicate_out_of_order_gap_and_resync() -> None:
    local = LocalOrderBook("BTC/USDT")
    local.apply_snapshot(book())
    assert local.apply_update(update(11, 11))
    assert not local.apply_update(update(11, 11))
    assert local.duplicates == 1
    assert not local.apply_update(update(9, 10, "old"))
    assert local.out_of_order == 1
    assert not local.apply_update(update(13, 13, "gap"))
    assert not local.valid and local.sequence_gaps == 1
    local.apply_snapshot(book(20))
    assert local.valid and local.resyncs == 2


def test_pre_snapshot_queued_updates_are_discarded_not_out_of_order() -> None:
    local = LocalOrderBook("BTC/USDT")
    local.apply_snapshot(book(20))
    assert not local.apply_update(update(18, 19, "queued-old"))
    assert local.pre_snapshot_discards == 1 and local.out_of_order == 0
    assert local.apply_update(update(20, 21, "bridge"))
    assert not local.awaiting_bridge


def test_causal_snapshot_future_mutation_and_stale_policy() -> None:
    sync = MarketContextSynchronizer("BTC/USDT", stale_after=timedelta(seconds=5))
    quote = BBOEvent(
        event_id="q1",
        asset="BTC/USDT",
        event_timestamp=T,
        received_at=T,
        bid=99,
        ask=101,
        bid_quantity=3,
        ask_quantity=1,
    )
    sync.add(quote)
    sync.add_book(book(), T)
    before = sync.snapshot(T + timedelta(seconds=1))
    digest = before.snapshot_hash
    sync.add(
        BBOEvent(
            event_id="future",
            asset="BTC/USDT",
            event_timestamp=T + timedelta(seconds=10),
            received_at=T + timedelta(seconds=10),
            bid=1,
            ask=2,
            bid_quantity=1,
            ask_quantity=1,
        )
    )
    assert sync.snapshot(T + timedelta(seconds=1)).snapshot_hash == digest
    assert sync.snapshot(T + timedelta(seconds=6)).quote is None


def test_context_history_is_bounded_and_latest_lookup_handles_future_data() -> None:
    sync = MarketContextSynchronizer("BTC/USDT")
    for index in range(1_000):
        timestamp = T + timedelta(seconds=index)
        sync.add(
            BBOEvent(
                event_id=str(index),
                asset="BTC/USDT",
                event_timestamp=timestamp,
                received_at=timestamp,
                bid=99,
                ask=101,
                bid_quantity=1,
                ask_quantity=1,
            )
        )
    assert len(sync.quotes) < 700
    decision = T + timedelta(seconds=995)
    assert sync.snapshot(decision).quote is not None


def test_microprice_depth_and_trade_imbalance() -> None:
    sync = MarketContextSynchronizer("BTC/USDT")
    sync.add_book(book(), T)
    sync.add(
        BBOEvent(
            event_id="q",
            asset="BTC/USDT",
            event_timestamp=T,
            received_at=T,
            bid=99,
            ask=101,
            bid_quantity=3,
            ask_quantity=1,
        )
    )
    for event_id, side, quantity in (("a", Side.BUY, 3), ("b", Side.SELL, 1)):
        sync.add(
            AggregateTradeEvent(
                event_id=event_id,
                asset="BTC/USDT",
                event_timestamp=T,
                received_at=T,
                price=100,
                quantity=quantity,
                side=side,
            )
        )
    features = microstructure_features(sync.snapshot(T))
    assert features["microprice"] == 100.5
    assert features["depth_imbalance"] == pytest.approx(0.25)
    assert features["trade_imbalance"] == 0.5


def test_funding_oi_alignment_dataset_determinism_and_version_isolation() -> None:
    sync = MarketContextSynchronizer("BTC/USDT")
    sync.add(
        DerivativesEvent(
            event_id="d1",
            asset="BTC/USDT",
            event_timestamp=T,
            received_at=T,
            funding_rate=0.001,
            open_interest=100,
            mark_price=101,
            index_price=100,
        )
    )
    first = sync.snapshot(T)
    sync.add(
        DerivativesEvent(
            event_id="d2",
            asset="BTC/USDT",
            event_timestamp=T + timedelta(seconds=1),
            received_at=T + timedelta(seconds=1),
            funding_rate=0.002,
            open_interest=110,
            mark_price=102,
            index_price=100,
        )
    )
    second = sync.snapshot(T + timedelta(seconds=1))
    features = derivatives_features((first, second))
    assert features["funding_change"] == 0.001 and features["open_interest_change"] == 10
    one = DatasetV2Builder().build((first, second))
    two = DatasetV2Builder().build((first, second))
    assert one.metadata.dataset_hash == two.metadata.dataset_hash
    assert one.metadata.feature_version == FEATURE_VERSION_V2 and FEATURE_VERSION_V2.startswith(
        "features-v2-"
    )
    assert not one.metadata.target_included


def test_derivatives_staleness_matches_polling_cadence() -> None:
    sync = MarketContextSynchronizer("BTC/USDT")
    sync.add(
        DerivativesEvent(
            event_id="d",
            asset="BTC/USDT",
            event_timestamp=T,
            received_at=T,
            funding_rate=0.001,
            open_interest=100,
        )
    )
    assert sync.snapshot(T + timedelta(seconds=60)).derivatives is not None
    assert sync.snapshot(T + timedelta(seconds=121)).derivatives is None


def test_separate_storage_and_replay(tmp_path: object) -> None:
    path = tmp_path / "shadow.db"  # type: ignore[operator]
    store = MarketDataStore(path)
    event = BBOEvent(
        event_id="q",
        asset="BTC/USDT",
        event_timestamp=T,
        received_at=T,
        bid=99,
        ask=101,
        bid_quantity=1,
        ask_quantity=1,
    )
    store.append(event)
    sync = MarketContextSynchronizer("BTC/USDT")
    sync.add(event)
    snap = sync.snapshot(T)
    store.save_snapshot(snap)
    assert store.replay() == (event,) and store.snapshots()[0].snapshot_hash == snap.snapshot_hash
    store.close()
    with pytest.raises(ValueError):
        MarketDataStore(tmp_path / "forward_v1.db")  # type: ignore[operator]


def test_candidate_can_enter_shadow_without_paper_promotion(tmp_path: object) -> None:
    artifact = ModelArtifact.create(
        model_name="logistic",
        feature_version=FEATURE_VERSION_V2,
        dataset_hash="dataset",
        training_start="2025-01-01",
        training_end="2025-02-01",
        validation_metrics={},
        feature_names=("x",),
        coefficients=(1.0,),
    )
    registry = ModelRegistry(tmp_path / "models.db")  # type: ignore[operator]
    registry.register(artifact)
    registry.promote_to_shadow(artifact.model_version)
    assert registry.status(artifact.model_version) is ModelStatus.SHADOW


def test_runtime_logging_initialization_and_rotation(tmp_path: object) -> None:
    target = tmp_path / "shadow.log"  # type: ignore[operator]
    logger = runtime_logger("test.shadow.rotation", log_file=target, max_bytes=160, backups=2)
    for index in range(20):
        log_event(logger, logging.INFO, "test_event", index=index, detail="x" * 40)
    for handler in logger.handlers:
        handler.flush()
        handler.close()
    assert target.exists()
    assert list(target.parent.glob("shadow.log.*"))
    assert '"event": "test_event"' in target.read_text(encoding="utf-8")


def test_duplicate_instance_rejected_and_pid_cleaned(tmp_path: object) -> None:
    path = tmp_path / "shadow.pid"  # type: ignore[operator]
    with InstanceGuard(path):
        assert path.read_text(encoding="utf-8") == str(os.getpid())
        with pytest.raises(RuntimeError, match="writer already active"):
            InstanceGuard(path).acquire()
    assert not path.exists()


def test_health_exit_codes_and_storage_window() -> None:
    now = datetime.now(UTC).isoformat()
    assert health_assessment({"health": "HEALTHY", "updated_at": now})[0] == 0
    assert health_assessment({"health": "STOPPED", "updated_at": now})[0] == 1
    assert health_assessment({"health": "FAILED", "updated_at": now})[0] == 2
    short = storage_measurement(100, 200, 10)
    assert short["mb_per_hour"] is None and short["warning"]
    long = storage_measurement(100, 1_000_100, 3600)
    assert long["mb_per_hour"] == 1 and long["projected_gb_per_day"] == 0.024
    assert storage_guardrail(None, 10, 20) == "MEASURING"
    assert storage_guardrail(15, 10, 20) == "WARNING"
    assert storage_guardrail(25, 10, 20) == "DEGRADED"
    health, reasons = operational_health(
        elapsed_seconds=3420,
        stale_ratio=0.75,
        missing_ratio=0,
        latency_p95_ms=48_181,
        reconnects=28,
        sequence_gaps=58,
        books_valid=True,
    )
    assert health == "DEGRADED"
    assert set(reasons) == {
        "high_stale_ratio",
        "high_source_latency",
        "frequent_reconnects",
        "frequent_sequence_gaps",
    }


def test_latency_is_attributed_per_asset_and_source() -> None:
    values = {"BTC/USDT:depth": deque([0.5, 48_000.0]), "BTC/USDT:bbo": deque([0.4, 0.6])}
    result = latency_percentiles(values)
    assert result["BTC/USDT:depth"]["p95_ms"] == 48_000
    assert result["BTC/USDT:bbo"]["p50_ms"] == 0.6


def test_coverage_and_readiness_are_informational(tmp_path: object) -> None:
    store = MarketDataStore(tmp_path / "coverage.db")  # type: ignore[operator]
    quote = BBOEvent(
        event_id="q",
        asset="BTC/USDT",
        event_timestamp=T,
        received_at=T,
        bid=99,
        ask=101,
        bid_quantity=1,
        ask_quantity=1,
    )
    derivative = DerivativesEvent(
        event_id="d",
        asset="BTC/USDT",
        event_timestamp=T,
        received_at=T,
        funding_rate=0.001,
        open_interest=100,
    )
    trade = AggregateTradeEvent(
        event_id="t",
        asset="BTC/USDT",
        event_timestamp=T,
        received_at=T,
        price=100,
        quantity=1,
        side=Side.BUY,
    )
    for event in (quote, derivative, trade):
        store.append(event)
    sync = MarketContextSynchronizer("BTC/USDT")
    sync.add(quote)
    sync.add(derivative)
    sync.add(trade)
    store.save_snapshot(sync.snapshot(T))
    coverage = store.coverage()
    store.close()
    asset = coverage["assets"]["BTC/USDT"]  # type: ignore[index]
    assert asset["event_counts"] == {"bbo": 1, "derivatives": 1, "trade": 1}
    assert asset["funding_observations"] == 1 and asset["oi_observations"] == 1
    report = readiness_assessment(
        coverage,
        minimum_hours=0,
        minimum_snapshots=1,
        minimum_completeness=1,
        minimum_book_validity=0,
    )
    assert report["research_ready"] is True and report["informational_only"] is True


def test_runtime_manifest_state_round_trip(tmp_path: object) -> None:
    store = MarketDataStore(tmp_path / "manifest.db")  # type: ignore[operator]
    manifest = {
        "git_commit": "abc",
        "feature_version": FEATURE_VERSION_V2,
        "process_id": 42,
        "assets": ["BTC/USDT"],
    }
    store.set_state("manifest", manifest)
    assert store.get_state("manifest") == manifest
    store.close()


@pytest.mark.asyncio
async def test_shadow_bounded_run_gracefully_flushes_and_cleans_pid(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeAdapter:
        reconnects = 0
        connection_generation = 1
        last_disconnect = None

        def __init__(self, assets: tuple[str, ...]) -> None:
            self.assets = assets

        async def book_snapshot(self, asset: str) -> OrderBookSnapshot:
            return book()

        async def derivatives(self, asset: str) -> DerivativesEvent:
            return DerivativesEvent(
                event_id="d",
                asset=asset,
                event_timestamp=T,
                received_at=T,
                funding_rate=0.001,
                open_interest=100,
            )

        async def events(self):  # type: ignore[no-untyped-def]
            yield BBOEvent(
                event_id="q",
                asset="BTC/USDT",
                event_timestamp=T,
                received_at=T,
                bid=99,
                ask=101,
                bid_quantity=1,
                ask_quantity=1,
            )

    monkeypatch.setattr("smarttrading.paper.shadow_v2.BinanceMarketDataV2", FakeAdapter)
    database = tmp_path / "shadow.db"  # type: ignore[operator]
    pid_file = tmp_path / "shadow.pid"  # type: ignore[operator]
    log_file = tmp_path / "shadow.log"  # type: ignore[operator]
    status = await run_shadow_v2(
        str(database), ("BTC/USDT",), max_events=1, pid_file=str(pid_file), log_file=str(log_file)
    )
    assert status["health"] == "STOPPED" and status["feed_state"] == "DISCONNECTED"
    assert not pid_file.exists()
    store = MarketDataStore(database)
    manifest = store.get_state("manifest")
    store.close()
    assert manifest and manifest["feature_version"] == FEATURE_VERSION_V2
    assert "graceful_shutdown" in log_file.read_text(encoding="utf-8")
    assert status["quality"]["sequence_gaps"] == 0  # type: ignore[index]


def test_compact_persistence_bounds_rows_and_replays_deterministically(tmp_path: object) -> None:
    database = tmp_path / "compact.db"  # type: ignore[operator]
    store = MarketDataStore(database)
    sync = MarketContextSynchronizer("BTC/USDT")
    sync.add_book(book(), T)
    for index in range(100):
        timestamp = T + timedelta(milliseconds=index * 10)
        trade = AggregateTradeEvent(
            event_id=f"t{index}",
            asset="BTC/USDT",
            event_timestamp=timestamp,
            received_at=timestamp,
            price=Decimal("100"),
            quantity=Decimal("0.1"),
            side=Side.BUY,
        )
        sync.add(trade)
        store.aggregate_trade(trade)
    quote = BBOEvent(
        event_id="q",
        asset="BTC/USDT",
        event_timestamp=T,
        received_at=T,
        bid=99,
        ask=101,
        bid_quantity=1,
        ask_quantity=1,
    )
    sync.add(quote)
    store.save_bbo_sample(quote)
    context = sync.snapshot(T + timedelta(milliseconds=990))
    store.save_derived_snapshot(context, microstructure_features(context), FEATURE_VERSION_V2)
    store.save_book_checkpoint(book(), T, retained_levels=1)
    store.flush(checkpoint=True)
    replay_one = store.compact_replay()
    replay_two = store.compact_replay()
    store.close()
    assert replay_one == replay_two
    assert len(replay_one["trade_buckets"]) == 1
    assert replay_one["trade_buckets"][0][5] == 100
    assert len(replay_one["derived_snapshots"]) == 1
    assert len(replay_one["book_checkpoints"]) == 1
    report = inspect_storage(database)
    assert report["rows"]["trade_buckets"] == 1  # type: ignore[index]
    assert report["wal_bytes"] == 0
