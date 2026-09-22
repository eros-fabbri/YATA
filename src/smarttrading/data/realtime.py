from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from pydantic import BaseModel, ConfigDict

from smarttrading.domain import Bar

TIMEFRAME_DELTA = {
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
}


class CandleEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_id: str
    bar: Bar
    closed: bool
    received_at: datetime


class ClosedCandleBuffer:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self._last: dict[tuple[str, str], datetime] = {}
        self.missing: list[tuple[str, str, datetime, datetime]] = []

    def accept(self, event: CandleEvent) -> bool:
        if not event.closed or event.event_id in self._seen:
            return False
        key = (event.bar.asset, event.bar.timeframe)
        previous = self._last.get(key)
        if previous is not None:
            expected = previous + TIMEFRAME_DELTA[event.bar.timeframe]
            if event.bar.timestamp < expected:
                return False
            if event.bar.timestamp > expected:
                self.missing.append((key[0], key[1], expected, event.bar.timestamp))
        self._seen.add(event.event_id)
        self._last[key] = event.bar.timestamp
        return True


class MultiTimeframeStore:
    def __init__(self) -> None:
        self._bars: dict[tuple[str, str], list[Bar]] = defaultdict(list)

    def add_closed(self, bar: Bar) -> None:
        key = (bar.asset, bar.timeframe)
        values = self._bars[key]
        if values and bar.timestamp <= values[-1].timestamp:
            if bar.timestamp == values[-1].timestamp:
                return
            raise ValueError("out-of-order closed bar")
        values.append(bar)

    def history(self, asset: str, timeframe: str, decision_time: datetime) -> tuple[Bar, ...]:
        delta = TIMEFRAME_DELTA[timeframe]
        return tuple(
            bar for bar in self._bars[(asset, timeframe)] if bar.timestamp + delta <= decision_time
        )

    def latest_context(
        self, asset: str, timeframes: tuple[str, ...], decision_time: datetime
    ) -> dict[str, Bar]:
        output: dict[str, Bar] = {}
        for timeframe in timeframes:
            history = self.history(asset, timeframe, decision_time)
            if history:
                output[timeframe] = history[-1]
        return output


def cross_asset_context(
    store: MultiTimeframeStore,
    decision_time: datetime,
    timeframe: str,
    left: str = "BTC/USDT",
    right: str = "ETH/USDT",
    window: int = 20,
) -> dict[str, float]:
    left_bars = store.history(left, timeframe, decision_time)
    right_bars = store.history(right, timeframe, decision_time)
    right_by_time = {bar.timestamp: bar for bar in right_bars}
    pairs = [
        (bar, right_by_time[bar.timestamp]) for bar in left_bars if bar.timestamp in right_by_time
    ]
    if len(pairs) < window + 1:
        return {}
    pairs = pairs[-(window + 1) :]
    left_returns = [
        float(pairs[index][0].close / pairs[index - 1][0].close - 1)
        for index in range(1, len(pairs))
    ]
    right_returns = [
        float(pairs[index][1].close / pairs[index - 1][1].close - 1)
        for index in range(1, len(pairs))
    ]
    left_mean = sum(left_returns) / window
    right_mean = sum(right_returns) / window
    covariance = (
        sum(
            (x - left_mean) * (y - right_mean)
            for x, y in zip(left_returns, right_returns, strict=True)
        )
        / window
    )
    right_variance = sum((value - right_mean) ** 2 for value in right_returns) / window
    left_variance = sum((value - left_mean) ** 2 for value in left_returns) / window
    denominator = (left_variance * right_variance) ** 0.5
    return {
        "btc_return": left_returns[-1],
        "eth_return": right_returns[-1],
        "relative_strength": left_returns[-1] - right_returns[-1],
        "rolling_correlation": covariance / denominator if denominator else 0.0,
        "rolling_beta": covariance / right_variance if right_variance else 0.0,
        "return_divergence": left_mean - right_mean,
        "relative_volatility": (left_variance / right_variance) ** 0.5 if right_variance else 0.0,
    }
