from datetime import UTC, datetime
from decimal import Decimal

import pytest

from smarttrading.domain import Bar, Fill, OrderType, ProposedOrder, Side
from smarttrading.execution.simulator import CostModel, ExecutionSimulator
from smarttrading.portfolio.accounting import AccountingError, PortfolioAccount


def market_order(side: Side, quantity: str = "1") -> ProposedOrder:
    return ProposedOrder(
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        asset="BTC/USDT",
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal(quantity),
    )


def bar() -> Bar:
    return Bar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        asset="BTC/USDT",
        timeframe="5m",
        open=100,
        high=110,
        low=90,
        close=105,
        volume=10,
    )


def test_market_spread_slippage_and_fee_are_exact() -> None:
    simulator = ExecutionSimulator(CostModel(2, 10, 20, 30))
    buy = simulator.execute(market_order(Side.BUY), bar())
    sell = simulator.execute(market_order(Side.SELL), bar())
    assert buy is not None and sell is not None
    assert buy.price == Decimal("100.4")
    assert sell.price == Decimal("99.6")
    assert buy.fee == Decimal("0.1004")
    assert buy.spread_cost == Decimal("0.1")
    assert buy.slippage_cost == Decimal("0.3")


def test_accounting_fee_pnl_and_invariants() -> None:
    account = PortfolioAccount(Decimal("1000"))
    account.apply_fill(
        Fill(
            fill_id="1",
            client_order_id=market_order(Side.BUY).client_order_id,
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            asset="BTC/USDT",
            side=Side.BUY,
            price=Decimal("100"),
            quantity=Decimal("2"),
            fee=Decimal("2"),
            fee_currency="USDT",
        )
    )
    account.apply_fill(
        Fill(
            fill_id="2",
            client_order_id=market_order(Side.SELL).client_order_id,
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
            asset="BTC/USDT",
            side=Side.SELL,
            price=Decimal("110"),
            quantity=Decimal("2"),
            fee=Decimal("2.2"),
            fee_currency="USDT",
        )
    )
    point = account.mark(datetime(2025, 1, 2, tzinfo=UTC), {"BTC/USDT": Decimal("110")})
    assert account.realized_pnl == Decimal("15.8")
    assert point.equity == point.cash + point.positions_value == Decimal("1015.8")
    assert account.cash >= 0
    with pytest.raises(AccountingError):
        account.apply_fill(
            Fill(
                fill_id="3",
                client_order_id=market_order(Side.SELL).client_order_id,
                timestamp=datetime(2025, 1, 3, tzinfo=UTC),
                asset="BTC/USDT",
                side=Side.SELL,
                price=100,
                quantity=1,
                fee=0,
                fee_currency="USDT",
            )
        )


def test_limit_requires_strict_penetration_and_supports_partial_fill() -> None:
    simulator = ExecutionSimulator(CostModel(2, 5, 2, 1, Decimal("0.5")))
    touched = ProposedOrder(
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        asset="BTC/USDT",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=2,
        limit_price=90,
    )
    assert simulator.execute(touched, bar()) is None
    penetrated = touched.model_copy(update={"limit_price": Decimal("91")})
    fill = simulator.execute(penetrated, bar())
    assert fill is not None and fill.quantity == Decimal("1.0")
