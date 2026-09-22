from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from smarttrading.domain import Bar, OrderType, ProposedOrder, Side


def test_bar_normalizes_aware_timestamp_to_utc() -> None:
    bar = Bar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        asset="BTC/USDT",
        timeframe="5m",
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("90"),
        close=Decimal("105"),
        volume=Decimal("2.5"),
    )
    assert bar.timestamp.tzinfo is UTC


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Bar(
            timestamp=datetime(2025, 1, 1),
            asset="BTC/USDT",
            timeframe="5m",
            open=100,
            high=110,
            low=90,
            close=105,
            volume=1,
        )


def test_invalid_ohlc_range_is_rejected() -> None:
    with pytest.raises(ValidationError, match="OHLC"):
        Bar(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            asset="BTC/USDT",
            timeframe="5m",
            open=100,
            high=101,
            low=90,
            close=105,
            volume=1,
        )


def test_limit_order_requires_price_and_market_forbids_it() -> None:
    base = {
        "created_at": datetime(2025, 1, 1, tzinfo=UTC),
        "asset": "BTC/USDT",
        "side": Side.BUY,
        "quantity": Decimal("0.1"),
    }
    with pytest.raises(ValidationError):
        ProposedOrder(order_type=OrderType.LIMIT, **base)
    with pytest.raises(ValidationError):
        ProposedOrder(order_type=OrderType.MARKET, limit_price=Decimal("100"), **base)
