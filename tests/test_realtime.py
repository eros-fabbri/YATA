from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from smarttrading.data.realtime import (
    CandleEvent,
    ClosedCandleBuffer,
    MultiTimeframeStore,
    cross_asset_context,
)
from smarttrading.domain import Bar
from smarttrading.exchanges.binance_stream import ResilientCandleStream
from smarttrading.features.regime import RegimeDetector


def bar(index: int, *, asset: str = "BTC/USDT", timeframe: str = "5m", price: int = 100) -> Bar:
    return Bar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=5 * index),
        asset=asset,
        timeframe=timeframe,
        open=Decimal(price),
        high=Decimal(price + 1),
        low=Decimal(price - 1),
        close=Decimal(price),
        volume=Decimal("10"),
    )


def event(index: int, *, closed: bool = True, event_id: str | None = None) -> CandleEvent:
    value = bar(index)
    return CandleEvent(
        event_id=event_id or str(index),
        bar=value,
        closed=closed,
        received_at=value.timestamp + timedelta(minutes=5),
    )


def test_closed_duplicate_out_of_order_and_missing_candles() -> None:
    buffer = ClosedCandleBuffer()
    assert not buffer.accept(event(0, closed=False))
    assert buffer.accept(event(0))
    assert not buffer.accept(event(0))
    assert buffer.accept(event(2))
    assert len(buffer.missing) == 1
    assert not buffer.accept(event(1, event_id="late"))


def test_multi_timeframe_and_cross_asset_are_causal() -> None:
    store = MultiTimeframeStore()
    hourly = bar(0, timeframe="1h")
    store.add_closed(hourly)
    assert store.history("BTC/USDT", "1h", hourly.timestamp + timedelta(minutes=59)) == ()
    assert store.history("BTC/USDT", "1h", hourly.timestamp + timedelta(hours=1)) == (hourly,)
    for index in range(25):
        store.add_closed(bar(index, price=100 + index))
        store.add_closed(bar(index, asset="ETH/USDT", price=50 + index))
    decision_time = bar(24).timestamp + timedelta(minutes=5)
    before = cross_asset_context(store, decision_time, "5m")
    store.add_closed(bar(25, asset="ETH/USDT", price=9999))
    assert cross_asset_context(store, decision_time, "5m") == before


def test_regime_is_causal() -> None:
    detector = RegimeDetector(window=20)
    history = [bar(index, price=100 + index) for index in range(21)]
    first = detector.detect(history)
    future_changed = [*history, bar(21, price=2)]
    assert detector.detect(future_changed[:-1]) == first


@pytest.mark.asyncio
async def test_reconnect_and_rest_reconciliation() -> None:
    attempts = 0

    async def connect():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("disconnect")
        yield event(2)

    async def reconcile() -> list[CandleEvent]:
        return [event(1, event_id="reconciled")]

    stream = ResilientCandleStream(connect, reconcile, maximum_backoff=0)
    iterator = stream.events()
    assert (await anext(iterator)).event_id == "reconciled"
    assert (await anext(iterator)).event_id == "2"
    assert stream.reconnects == 1
    await iterator.aclose()
