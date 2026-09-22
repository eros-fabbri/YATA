from datetime import UTC, datetime
from decimal import Decimal

from smarttrading.domain import OrderType, ProposedOrder, RiskDecisionStatus, Side
from smarttrading.risk.manager import CircuitState, IndependentRiskManager, RiskContext
from tests.helpers import risk_settings


def order(side: Side = Side.BUY, quantity: str = "10") -> ProposedOrder:
    return ProposedOrder(
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
        asset="BTC/USDT",
        side=side,
        order_type=OrderType.MARKET,
        quantity=Decimal(quantity),
    )


def context(**changes: object) -> RiskContext:
    values: dict[str, object] = {
        "timestamp": datetime(2025, 1, 1, tzinfo=UTC),
        "price": Decimal("100"),
        "cash": Decimal("1000"),
        "equity": Decimal("1000"),
        "asset_value": Decimal("0"),
        "portfolio_exposure": Decimal("0"),
        "position_quantity": Decimal("0"),
    }
    values.update(changes)
    return RiskContext(**values)


def test_risk_resizes_and_rejects_impossible_orders() -> None:
    manager = IndependentRiskManager(risk_settings(max_order_notional=Decimal("250")))
    resized = manager.evaluate(order(quantity="10"), context())
    assert resized.status is RiskDecisionStatus.RESIZED
    assert resized.approved_quantity == Decimal("2.5")
    rejected = manager.evaluate(order(Side.SELL, "1"), context())
    assert rejected.status is RiskDecisionStatus.REJECTED
    assert "INSUFFICIENT_POSITION" in rejected.reasons


def test_circuit_breaker_and_kill_switch_block_opening_but_allow_close() -> None:
    manager = IndependentRiskManager(risk_settings(max_drawdown=0.1))
    assert not manager.evaluate(order(), context(drawdown=0.2)).approved
    assert manager.circuit_state is CircuitState.OPEN
    assert not manager.evaluate(order(), context()).approved
    close = manager.evaluate(order(Side.SELL, "1"), context(position_quantity=Decimal("1")))
    assert close.approved

    killed = IndependentRiskManager(risk_settings())
    killed.activate_kill_switch()
    decision = killed.evaluate(order(), context())
    assert not decision.approved and "KILL_SWITCH_ACTIVE" in decision.reasons
