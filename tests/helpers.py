from datetime import UTC, datetime, timedelta
from decimal import Decimal

from smarttrading.config.settings import RiskSettings
from smarttrading.domain import Bar


def bars_from_prices(prices: list[str]) -> list[Bar]:
    return [
        Bar(
            timestamp=datetime(2025, 1, 1, tzinfo=UTC) + timedelta(minutes=5 * index),
            asset="BTC/USDT",
            timeframe="5m",
            open=Decimal(price),
            high=Decimal(price) + 1,
            low=Decimal(price) - 1,
            close=Decimal(price),
            volume=Decimal("100"),
        )
        for index, price in enumerate(prices)
    ]


def risk_settings(**overrides: object) -> RiskSettings:
    values: dict[str, object] = {
        "max_asset_allocation": 1.0,
        "max_portfolio_exposure": 1.0,
        "max_order_notional": Decimal("1000000"),
        "max_daily_loss": 0.10,
        "max_drawdown": 0.20,
        "stale_data_seconds": 120,
        "anomalous_price_deviation": 0.10,
    }
    values.update(overrides)
    return RiskSettings(**values)
