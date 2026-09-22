from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from smarttrading.domain import OrderType, ProposedOrder, Side, Signal, SignalDirection
from smarttrading.portfolio.accounting import PortfolioAccount


class FixedFractionSizer:
    def __init__(self, fraction: Decimal = Decimal("0.25")) -> None:
        if not Decimal("0") < fraction <= Decimal("1"):
            raise ValueError("fraction must be in (0, 1]")
        self.fraction = fraction

    def size(
        self, signal: Signal, account: PortfolioAccount, price: Decimal, timestamp: datetime
    ) -> ProposedOrder | None:
        if signal.direction is SignalDirection.HOLD:
            return None
        position = account.positions.get(signal.asset)
        current_quantity = Decimal("0") if position is None else position.quantity
        equity = account.cash + current_quantity * price
        target_quantity = (
            equity * self.fraction / price
            if signal.direction is SignalDirection.LONG
            else Decimal("0")
        )
        delta = target_quantity - current_quantity
        if abs(delta) < Decimal("0.00000001"):
            return None
        return ProposedOrder(
            created_at=timestamp,
            asset=signal.asset,
            side=Side.BUY if delta > 0 else Side.SELL,
            order_type=OrderType.MARKET,
            quantity=abs(delta),
        )
