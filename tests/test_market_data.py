from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from smarttrading.data.manifest import build_manifest
from smarttrading.data.storage import BarRepository
from smarttrading.data.validation import MarketDataError, validate_bar_series
from smarttrading.domain import Bar


def make_bar(minutes: int) -> Bar:
    return Bar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=minutes),
        asset="BTC/USDT",
        timeframe="5m",
        open=Decimal("100"),
        high=Decimal("102"),
        low=Decimal("99"),
        close=Decimal("101"),
        volume=Decimal("3"),
    )


def test_series_sorts_and_rejects_duplicates_and_gaps() -> None:
    assert [bar.timestamp for bar in validate_bar_series([make_bar(5), make_bar(0)])] == [
        make_bar(0).timestamp,
        make_bar(5).timestamp,
    ]
    with pytest.raises(MarketDataError, match="duplicate"):
        validate_bar_series([make_bar(0), make_bar(0)])
    with pytest.raises(MarketDataError, match="missing or irregular"):
        validate_bar_series([make_bar(0), make_bar(10)])


def test_manifest_is_content_deterministic() -> None:
    bars = [make_bar(0), make_bar(5)]
    assert build_manifest(bars) == build_manifest(bars)
    assert build_manifest(bars).sha256 != build_manifest([make_bar(0)]).sha256


def test_repository_round_trip_and_duplicate_protection(tmp_path: Path) -> None:
    repository = BarRepository(f"sqlite:///{tmp_path}/bars.db")
    repository.create_schema()
    bars = [make_bar(0), make_bar(5)]
    repository.add(bars)
    assert repository.get("BTC/USDT", "5m", bars[0].timestamp, bars[-1].timestamp) == bars
    with pytest.raises(IntegrityError):
        repository.add([make_bar(0)])
