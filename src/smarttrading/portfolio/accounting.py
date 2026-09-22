from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from smarttrading.domain import Fill, Side


class EquityPoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    timestamp: datetime
    cash: Decimal
    positions_value: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    fees: Decimal


@dataclass
class Position:
    quantity: Decimal = Decimal("0")
    average_entry_price: Decimal = Decimal("0")
    opened_at: datetime | None = None


class AccountingError(ValueError):
    pass


class PortfolioAccount:
    def __init__(self, initial_cash: Decimal) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.realized_pnl = Decimal("0")
        self.total_fees = Decimal("0")
        self.turnover = Decimal("0")
        self.closed_trades: list[tuple[Decimal, float]] = []

    def apply_fill(self, fill: Fill) -> None:
        position = self.positions.setdefault(fill.asset, Position())
        notional = fill.price * fill.quantity
        if fill.side is Side.BUY:
            cost = notional + fill.fee
            if cost > self.cash:
                raise AccountingError("insufficient cash")
            old_cost = position.quantity * position.average_entry_price
            if position.quantity == 0:
                position.opened_at = fill.timestamp
            position.quantity += fill.quantity
            position.average_entry_price = (old_cost + notional + fill.fee) / position.quantity
            self.cash -= cost
        else:
            if fill.quantity > position.quantity:
                raise AccountingError("insufficient position")
            pnl = (fill.price - position.average_entry_price) * fill.quantity - fill.fee
            self.realized_pnl += pnl
            self.cash += notional - fill.fee
            position.quantity -= fill.quantity
            if position.quantity == 0:
                seconds = 0.0
                if position.opened_at is not None:
                    seconds = (fill.timestamp - position.opened_at).total_seconds()
                self.closed_trades.append((pnl, seconds))
                position.average_entry_price = Decimal("0")
                position.opened_at = None
        self.total_fees += fill.fee
        self.turnover += notional
        if self.cash < 0:
            raise AssertionError("spot cash invariant violated")

    def mark(self, timestamp: datetime, prices: dict[str, Decimal]) -> EquityPoint:
        value = sum(
            (
                position.quantity * prices.get(asset, Decimal("0"))
                for asset, position in self.positions.items()
            ),
            Decimal("0"),
        )
        unrealized = sum(
            (
                (prices.get(asset, position.average_entry_price) - position.average_entry_price)
                * position.quantity
                for asset, position in self.positions.items()
            ),
            Decimal("0"),
        )
        return EquityPoint(
            timestamp=timestamp,
            cash=self.cash,
            positions_value=value,
            equity=self.cash + value,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=unrealized,
            fees=self.total_fees,
        )
