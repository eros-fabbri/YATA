from __future__ import annotations

import math
from collections.abc import Sequence

from smarttrading.domain import Bar, DetectedRegime, TrendRegime, VolatilityRegime


class RegimeDetector:
    version = "regime-v1"

    def __init__(
        self,
        window: int = 20,
        trend_threshold: float = 0.01,
        high_vol: float = 0.02,
        low_vol: float = 0.005,
    ) -> None:
        self.window = window
        self.trend_threshold = trend_threshold
        self.high_vol = high_vol
        self.low_vol = low_vol

    def detect(self, bars: Sequence[Bar]) -> DetectedRegime:
        if len(bars) < self.window + 1:
            raise ValueError("insufficient causal history for regime")
        values = bars[-(self.window + 1) :]
        returns = [
            float(values[index].close / values[index - 1].close - 1)
            for index in range(1, len(values))
        ]
        trend = float(values[-1].close / values[0].close - 1)
        mean = sum(returns) / len(returns)
        volatility = math.sqrt(sum((value - mean) ** 2 for value in returns) / len(returns))
        if trend > self.trend_threshold:
            trend_regime = TrendRegime.TRENDING_UP
        elif trend < -self.trend_threshold:
            trend_regime = TrendRegime.TRENDING_DOWN
        else:
            trend_regime = TrendRegime.RANGING
        if volatility >= self.high_vol:
            volatility_regime = VolatilityRegime.HIGH_VOLATILITY
        elif volatility <= self.low_vol:
            volatility_regime = VolatilityRegime.LOW_VOLATILITY
        else:
            volatility_regime = VolatilityRegime.NORMAL
        confidence = min(
            1.0,
            max(
                abs(trend) / max(self.trend_threshold, 1e-12),
                volatility / max(self.high_vol, 1e-12),
            )
            / 2,
        )
        return DetectedRegime(
            timestamp=values[-1].timestamp,
            asset=values[-1].asset,
            trend_regime=trend_regime,
            volatility_regime=volatility_regime,
            confidence=confidence,
            detector_version=self.version,
        )
