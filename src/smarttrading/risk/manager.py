from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from smarttrading.config.settings import RiskSettings
from smarttrading.domain import ProposedOrder, RiskDecision, RiskDecisionStatus, Side


class RiskReason(StrEnum):
    MAX_ASSET_ALLOCATION = "MAX_ASSET_ALLOCATION"
    MAX_PORTFOLIO_EXPOSURE = "MAX_PORTFOLIO_EXPOSURE"
    MAX_ORDER_NOTIONAL = "MAX_ORDER_NOTIONAL"
    MAX_DAILY_LOSS = "MAX_DAILY_LOSS"
    MAX_DRAWDOWN = "MAX_DRAWDOWN"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    INSUFFICIENT_POSITION = "INSUFFICIENT_POSITION"
    STALE_DATA = "STALE_DATA"
    INVALID_PRICE = "INVALID_PRICE"
    CIRCUIT_BREAKER_ACTIVE = "CIRCUIT_BREAKER_ACTIVE"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"


@dataclass(frozen=True)
class RiskContext:
    timestamp: datetime
    price: Decimal
    cash: Decimal
    equity: Decimal
    asset_value: Decimal
    portfolio_exposure: Decimal
    position_quantity: Decimal
    daily_pnl_fraction: float = 0.0
    drawdown: float = 0.0
    data_age_seconds: float = 0.0
    estimated_cost_rate: Decimal = Decimal("0")


class IndependentRiskManager:
    def __init__(
        self,
        settings: RiskSettings,
        *,
        allow_closing_when_blocked: bool = True,
        max_execution_errors: int = 3,
    ) -> None:
        self.settings = settings
        self.allow_closing_when_blocked = allow_closing_when_blocked
        self.max_execution_errors = max_execution_errors
        self.circuit_state = CircuitState.CLOSED
        self.kill_switch = False
        self.execution_errors = 0
        self.decisions: list[RiskDecision] = []
        self.circuit_breaker_activations = 0

    def activate_kill_switch(self) -> None:
        self.kill_switch = True

    def record_execution_error(self) -> None:
        self.execution_errors += 1
        if self.execution_errors >= self.max_execution_errors:
            self._open_circuit()

    def _open_circuit(self) -> None:
        if self.circuit_state is CircuitState.CLOSED:
            self.circuit_breaker_activations += 1
        self.circuit_state = CircuitState.OPEN

    def evaluate(self, order: ProposedOrder, context: RiskContext) -> RiskDecision:
        reasons: list[str] = []
        price = context.price
        is_reduction = order.side is Side.SELL and order.quantity <= context.position_quantity
        if price <= 0:
            reasons.append(RiskReason.INVALID_PRICE)
            self._open_circuit()
        if context.data_age_seconds > self.settings.stale_data_seconds:
            reasons.append(RiskReason.STALE_DATA)
            self._open_circuit()
        if context.daily_pnl_fraction <= -self.settings.max_daily_loss:
            reasons.append(RiskReason.MAX_DAILY_LOSS)
            self._open_circuit()
        if context.drawdown >= self.settings.max_drawdown:
            reasons.append(RiskReason.MAX_DRAWDOWN)
            self._open_circuit()
        blocked = self.kill_switch or self.circuit_state is CircuitState.OPEN
        if blocked and not (is_reduction and self.allow_closing_when_blocked):
            reasons.append(
                RiskReason.KILL_SWITCH_ACTIVE
                if self.kill_switch
                else RiskReason.CIRCUIT_BREAKER_ACTIVE
            )
        if order.side is Side.SELL and order.quantity > context.position_quantity:
            reasons.append(RiskReason.INSUFFICIENT_POSITION)

        quantity = order.quantity
        if order.side is Side.BUY and not reasons:
            limits = [
                (self.settings.max_order_notional, RiskReason.MAX_ORDER_NOTIONAL),
                (
                    Decimal(str(self.settings.max_asset_allocation)) * context.equity
                    - context.asset_value,
                    RiskReason.MAX_ASSET_ALLOCATION,
                ),
                (
                    Decimal(str(self.settings.max_portfolio_exposure)) * context.equity
                    - context.portfolio_exposure,
                    RiskReason.MAX_PORTFOLIO_EXPOSURE,
                ),
                (
                    context.cash / (Decimal("1") + context.estimated_cost_rate),
                    RiskReason.INSUFFICIENT_CASH,
                ),
            ]
            for allowed_notional, reason in limits:
                allowed_quantity = max(Decimal("0"), allowed_notional / price)
                if quantity > allowed_quantity:
                    quantity = allowed_quantity
                    reasons.append(reason)

        if quantity <= 0 or (reasons and quantity == order.quantity):
            status = RiskDecisionStatus.REJECTED
            approved = False
            approved_quantity = None
        elif quantity < order.quantity:
            status = RiskDecisionStatus.RESIZED
            approved = True
            approved_quantity = quantity
        else:
            status = RiskDecisionStatus.APPROVED
            approved = True
            approved_quantity = quantity
        decision = RiskDecision(
            timestamp=context.timestamp,
            order_id=order.client_order_id,
            status=status,
            approved=approved,
            reasons=tuple(str(reason) for reason in reasons),
            approved_quantity=approved_quantity,
            evaluated_limits={"price": price, "equity": context.equity},
        )
        self.decisions.append(decision)
        return decision
