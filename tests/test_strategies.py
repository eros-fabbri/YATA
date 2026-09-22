from decimal import Decimal

import pytest
from pydantic import ValidationError

from smarttrading.domain import SignalDirection
from smarttrading.strategies.baselines import (
    MeanReversionConfig,
    MeanReversionStrategy,
    MomentumConfig,
    MomentumStrategy,
    MovingAverageConfig,
    MovingAverageCrossoverStrategy,
)
from tests.helpers import bars_from_prices


def test_moving_average_config_and_signal() -> None:
    with pytest.raises(ValidationError):
        MovingAverageConfig(fast_window=5, slow_window=5)
    strategy = MovingAverageCrossoverStrategy(MovingAverageConfig(fast_window=2, slow_window=3))
    signal = strategy.on_bar(bars_from_prices(["100", "101", "105"]))
    assert signal.direction is SignalDirection.LONG


def test_momentum_is_causal_and_configurable() -> None:
    strategy = MomentumStrategy(MomentumConfig(lookback=2, threshold=0.05))
    assert strategy.on_bar(bars_from_prices(["100", "101"])).direction is SignalDirection.FLAT
    assert (
        strategy.on_bar(bars_from_prices(["100", "101", "110"])).direction is SignalDirection.LONG
    )


def test_mean_reversion_entry_and_exit() -> None:
    config = MeanReversionConfig(lookback=3, entry_threshold=1, exit_threshold=Decimal("0.5"))
    strategy = MeanReversionStrategy(config)
    entry = strategy.on_bar(bars_from_prices(["100", "100", "90"]))
    assert entry.direction is SignalDirection.LONG
    exit_signal = strategy.on_bar(bars_from_prices(["100", "90", "100"]))
    assert exit_signal.direction is SignalDirection.FLAT
