from __future__ import annotations

import math
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smarttrading.domain import Bar, Prediction, Signal, SignalDirection


class StrategyConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MovingAverageConfig(StrategyConfig):
    fast_window: int = Field(default=10, ge=1)
    slow_window: int = Field(default=30, ge=2)

    @model_validator(mode="after")
    def ordered_windows(self) -> MovingAverageConfig:
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        return self


class MomentumConfig(StrategyConfig):
    lookback: int = Field(default=12, ge=1)
    threshold: float = Field(default=0.002, ge=0)


class MeanReversionConfig(StrategyConfig):
    lookback: int = Field(default=20, ge=2)
    entry_threshold: float = Field(default=2.0, gt=0)
    exit_threshold: float = Field(default=0.5, ge=0)

    @model_validator(mode="after")
    def thresholds_are_ordered(self) -> MeanReversionConfig:
        if self.exit_threshold >= self.entry_threshold:
            raise ValueError("exit_threshold must be smaller than entry_threshold")
        return self


class BaseStrategy:
    name = "base"
    version = "1.0"

    def _signal(
        self,
        bar: Bar,
        direction: SignalDirection,
        strength: float,
        rationale: dict[str, str | float | int],
    ) -> Signal:
        return Signal(
            timestamp=bar.timestamp,
            asset=bar.asset,
            strategy=self.name,
            direction=direction,
            strength=min(1.0, max(0.0, strength)),
            confidence=min(1.0, max(0.0, strength)),
            rationale=rationale,
        )


class BuyAndHoldStrategy(BaseStrategy):
    name = "buy_hold"

    def on_bar(self, history: Sequence[Bar], predictions: Sequence[Prediction] = ()) -> Signal:
        del predictions
        direction = SignalDirection.LONG if len(history) == 1 else SignalDirection.HOLD
        return self._signal(history[-1], direction, 1.0, {"bars_seen": len(history)})


class MovingAverageCrossoverStrategy(BaseStrategy):
    name = "moving_average"

    def __init__(self, config: MovingAverageConfig | None = None) -> None:
        self.config = config or MovingAverageConfig()

    def on_bar(self, history: Sequence[Bar], predictions: Sequence[Prediction] = ()) -> Signal:
        del predictions
        bar = history[-1]
        if len(history) < self.config.slow_window:
            return self._signal(bar, SignalDirection.FLAT, 0.0, {"warmup": 1})
        closes = [float(item.close) for item in history]
        fast = sum(closes[-self.config.fast_window :]) / self.config.fast_window
        slow = sum(closes[-self.config.slow_window :]) / self.config.slow_window
        direction = SignalDirection.LONG if fast > slow else SignalDirection.FLAT
        return self._signal(bar, direction, abs(fast / slow - 1), {"fast": fast, "slow": slow})


class MomentumStrategy(BaseStrategy):
    name = "momentum"

    def __init__(self, config: MomentumConfig | None = None) -> None:
        self.config = config or MomentumConfig()

    def on_bar(self, history: Sequence[Bar], predictions: Sequence[Prediction] = ()) -> Signal:
        del predictions
        bar = history[-1]
        if len(history) <= self.config.lookback:
            return self._signal(bar, SignalDirection.FLAT, 0.0, {"warmup": 1})
        change = float(bar.close / history[-self.config.lookback - 1].close - 1)
        direction = SignalDirection.LONG if change > self.config.threshold else SignalDirection.FLAT
        return self._signal(bar, direction, abs(change), {"return": change})


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def __init__(self, config: MeanReversionConfig | None = None) -> None:
        self.config = config or MeanReversionConfig()
        self._long = False

    def on_bar(self, history: Sequence[Bar], predictions: Sequence[Prediction] = ()) -> Signal:
        del predictions
        bar = history[-1]
        if len(history) < self.config.lookback:
            return self._signal(bar, SignalDirection.FLAT, 0.0, {"warmup": 1})
        values = [float(item.close) for item in history[-self.config.lookback :]]
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        zscore = 0.0 if variance == 0 else (values[-1] - mean) / math.sqrt(variance)
        if not self._long and zscore <= -self.config.entry_threshold:
            self._long = True
        elif self._long and zscore >= -self.config.exit_threshold:
            self._long = False
        direction = SignalDirection.LONG if self._long else SignalDirection.FLAT
        return self._signal(bar, direction, min(1.0, abs(zscore) / 3), {"zscore": zscore})
