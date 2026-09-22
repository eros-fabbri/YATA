from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from itertools import pairwise

from smarttrading.domain import Bar

_TIMEFRAME_SECONDS = {"5m": 300, "15m": 900, "1h": 3600}


class MarketDataError(ValueError):
    """Raised when a batch cannot form a reliable historical series."""


def validate_bar_series(bars: Sequence[Bar], *, require_contiguous: bool = True) -> list[Bar]:
    """Return a sorted, validated copy without silently repairing source data."""
    if not bars:
        return []
    ordered = sorted(bars, key=lambda bar: bar.timestamp)
    identity = {(bar.asset, bar.timeframe) for bar in ordered}
    if len(identity) != 1:
        raise MarketDataError("a series must contain exactly one asset and timeframe")

    timestamps = [bar.timestamp for bar in ordered]
    if len(timestamps) != len(set(timestamps)):
        raise MarketDataError("duplicate bar timestamp")

    if require_contiguous:
        step = timedelta(seconds=_TIMEFRAME_SECONDS[ordered[0].timeframe])
        for previous, current in pairwise(ordered):
            if current.timestamp - previous.timestamp != step:
                raise MarketDataError(
                    f"missing or irregular bar between {previous.timestamp} and {current.timestamp}"
                )
    return ordered
