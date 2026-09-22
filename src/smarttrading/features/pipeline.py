from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from datetime import datetime
from typing import cast

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from smarttrading.domain import Bar


class FeatureSet(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    timestamp: datetime
    asset: str
    timeframe: str
    feature_version: str
    values: dict[str, float]


class FeatureConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    sma_window: int = Field(default=20, ge=2)
    ema_window: int = Field(default=20, ge=2)
    macd_fast: int = Field(default=12, ge=2)
    macd_slow: int = Field(default=26, ge=3)
    macd_signal: int = Field(default=9, ge=2)
    rsi_window: int = Field(default=14, ge=2)
    roc_window: int = Field(default=12, ge=1)
    volatility_window: int = Field(default=20, ge=2)
    atr_window: int = Field(default=14, ge=2)
    bollinger_window: int = Field(default=20, ge=2)
    structure_window: int = Field(default=20, ge=2)
    volume_window: int = Field(default=20, ge=2)

    @property
    def version(self) -> str:
        payload = json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":"))
        return f"features-v1-{hashlib.sha256(payload.encode()).hexdigest()[:12]}"


def _frame(bars: Sequence[Bar]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [bar.timestamp for bar in bars],
            "asset": [bar.asset for bar in bars],
            "timeframe": [bar.timeframe for bar in bars],
            "open": [float(bar.open) for bar in bars],
            "high": [float(bar.high) for bar in bars],
            "low": [float(bar.low) for bar in bars],
            "close": [float(bar.close) for bar in bars],
            "volume": [float(bar.volume) for bar in bars],
        }
    )


class CausalFeaturePipeline:
    def __init__(self, config: FeatureConfig | None = None) -> None:
        self.config = config or FeatureConfig()

    def compute_frame(self, bars: Sequence[Bar]) -> pd.DataFrame:
        if not bars:
            return pd.DataFrame()
        frame = _frame(bars)
        close, high, low, volume = frame.close, frame.high, frame.low, frame.volume
        log_close = np.log(close)
        frame["log_return_1"] = log_close.diff()
        for period in (3, 6, 12, 24):
            frame[f"return_{period}"] = close.pct_change(period, fill_method=None)
        sma = close.rolling(self.config.sma_window).mean()
        ema = close.ewm(
            span=self.config.ema_window, adjust=False, min_periods=self.config.ema_window
        ).mean()
        frame["sma"] = sma
        frame["ema"] = ema
        frame["distance_from_sma"] = close / sma - 1
        frame["distance_from_ema"] = close / ema - 1
        macd_fast = close.ewm(
            span=self.config.macd_fast, adjust=False, min_periods=self.config.macd_fast
        ).mean()
        macd_slow = close.ewm(
            span=self.config.macd_slow, adjust=False, min_periods=self.config.macd_slow
        ).mean()
        macd = macd_fast - macd_slow
        macd_signal = macd.ewm(
            span=self.config.macd_signal, adjust=False, min_periods=self.config.macd_signal
        ).mean()
        frame["macd"] = macd
        frame["macd_signal"] = macd_signal
        frame["macd_histogram"] = macd - macd_signal
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(self.config.rsi_window).mean()
        loss = (-delta.clip(upper=0)).rolling(self.config.rsi_window).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs)
        rsi = rsi.mask((loss == 0) & (gain > 0), 100.0)
        rsi = rsi.mask((loss == 0) & (gain == 0), 50.0)
        frame["rsi"] = rsi
        frame["roc"] = close.pct_change(self.config.roc_window, fill_method=None)
        frame["rolling_volatility"] = frame.log_return_1.rolling(
            self.config.volatility_window
        ).std()
        previous_close = close.shift(1)
        true_range = pd.concat(
            [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
        ).max(axis=1)
        frame["atr"] = true_range.rolling(self.config.atr_window).mean()
        bollinger_mean = close.rolling(self.config.bollinger_window).mean()
        bollinger_std = close.rolling(self.config.bollinger_window).std()
        frame["bollinger_width"] = 4 * bollinger_std / bollinger_mean
        rolling_high = high.rolling(self.config.structure_window).max()
        rolling_low = low.rolling(self.config.structure_window).min()
        frame["rolling_high_distance"] = close / rolling_high - 1
        frame["rolling_low_distance"] = close / rolling_low - 1
        candle_range = (high - low).replace(0, np.nan)
        frame["candle_body_ratio"] = (close - frame.open).abs() / candle_range
        frame["upper_wick_ratio"] = (
            high - pd.concat([frame.open, close], axis=1).max(axis=1)
        ) / candle_range
        frame["lower_wick_ratio"] = (
            pd.concat([frame.open, close], axis=1).min(axis=1) - low
        ) / candle_range
        frame["volume_change"] = volume.pct_change(fill_method=None)
        volume_mean = volume.rolling(self.config.volume_window).mean()
        volume_std = volume.rolling(self.config.volume_window).std()
        frame["relative_volume"] = volume / volume_mean
        volume_zscore = (volume - volume_mean) / volume_std.replace(0, np.nan)
        frame["volume_zscore"] = volume_zscore.mask(volume_std == 0, 0.0)
        hour = frame.timestamp.dt.hour + frame.timestamp.dt.minute / 60
        weekday = frame.timestamp.dt.dayofweek
        frame["hour_sin"] = np.sin(2 * math.pi * hour / 24)
        frame["hour_cos"] = np.cos(2 * math.pi * hour / 24)
        frame["day_of_week_sin"] = np.sin(2 * math.pi * weekday / 7)
        frame["day_of_week_cos"] = np.cos(2 * math.pi * weekday / 7)
        return frame

    def transform(self, bars: Sequence[Bar]) -> list[FeatureSet]:
        frame = self.compute_frame(bars)
        identifiers = {"timestamp", "asset", "timeframe", "open", "high", "low", "close", "volume"}
        names = [column for column in frame.columns if column not in identifiers]
        complete = frame.dropna(subset=names)
        return [
            FeatureSet(
                timestamp=cast(datetime, row.timestamp),
                asset=cast(str, row.asset),
                timeframe=cast(str, row.timeframe),
                feature_version=self.config.version,
                values={name: float(getattr(row, name)) for name in names},
            )
            for row in complete.itertuples(index=False)
        ]
