from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from smarttrading.domain import Bar, Fill, OrderType, ProposedOrder, Side


@dataclass(frozen=True)
class CostModel:
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    spread_bps: Decimal
    slippage_bps: Decimal
    partial_fill_fraction: Decimal = Decimal("1")

    def __post_init__(self) -> None:
        for field_name in (
            "maker_fee_bps",
            "taker_fee_bps",
            "spread_bps",
            "slippage_bps",
            "partial_fill_fraction",
        ):
            object.__setattr__(self, field_name, Decimal(str(getattr(self, field_name))))

    def scaled(self, multiplier: int) -> CostModel:
        factor = Decimal(multiplier)
        return CostModel(
            self.maker_fee_bps * factor,
            self.taker_fee_bps * factor,
            self.spread_bps * factor,
            self.slippage_bps * factor,
            self.partial_fill_fraction,
        )


class ExecutionSimulator:
    """Deterministic OHLCV simulator; strict limit penetration is required for a fill."""

    def __init__(self, costs: CostModel) -> None:
        if not Decimal("0") < costs.partial_fill_fraction <= Decimal("1"):
            raise ValueError("partial_fill_fraction must be in (0, 1]")
        self.costs = costs
        self._fill_counter = 0

    def execute(
        self, order: ProposedOrder, bar: Bar, quantity: Decimal | None = None
    ) -> Fill | None:
        requested = order.quantity if quantity is None else quantity
        filled_quantity = requested * self.costs.partial_fill_fraction
        if order.order_type is OrderType.LIMIT:
            assert order.limit_price is not None
            penetrated = (
                bar.low < order.limit_price
                if order.side is Side.BUY
                else bar.high > order.limit_price
            )
            if not penetrated:
                return None
            price = order.limit_price
            fee_bps = self.costs.maker_fee_bps
            spread_cost = Decimal("0")
            slippage_cost = Decimal("0")
        else:
            sign = Decimal("1") if order.side is Side.BUY else Decimal("-1")
            half_spread = self.costs.spread_bps / Decimal("2") / Decimal("10000")
            slippage = self.costs.slippage_bps / Decimal("10000")
            price = bar.open * (Decimal("1") + sign * (half_spread + slippage))
            fee_bps = self.costs.taker_fee_bps
            spread_cost = bar.open * half_spread * filled_quantity
            slippage_cost = bar.open * slippage * filled_quantity
        fee = price * filled_quantity * fee_bps / Decimal("10000")
        self._fill_counter += 1
        return Fill(
            fill_id=f"sim-{self._fill_counter}",
            client_order_id=order.client_order_id,
            timestamp=bar.timestamp,
            asset=order.asset,
            side=order.side,
            price=price,
            quantity=filled_quantity,
            fee=fee,
            fee_currency=order.asset.split("/")[1],
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
        )
