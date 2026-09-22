from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from smarttrading.common.time import require_utc

PositiveDecimal = Annotated[Decimal, Field(gt=0)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0)]
UnitFloat = Annotated[float, Field(ge=0.0, le=1.0)]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    @field_validator("timestamp", check_fields=False)
    @classmethod
    def all_timestamps_are_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    CREATED = "created"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class RiskDecisionStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    RESIZED = "resized"


class SignalDirection(StrEnum):
    SHORT = "short"
    FLAT = "flat"
    HOLD = "hold"
    LONG = "long"


class MarketRegime(StrEnum):
    TRENDING = "trending"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


class TrendRegime(StrEnum):
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"


class VolatilityRegime(StrEnum):
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    NORMAL = "normal"


class DecisionAction(StrEnum):
    BUY = "buy"
    EXIT = "exit"
    ABSTAIN = "abstain"


class BestBidAsk(FrozenModel):
    timestamp: datetime
    asset: str
    bid: PositiveDecimal
    ask: PositiveDecimal
    bid_quantity: NonNegativeDecimal
    ask_quantity: NonNegativeDecimal


class OrderBookLevel(FrozenModel):
    price: PositiveDecimal
    quantity: NonNegativeDecimal


class OrderBookSnapshot(FrozenModel):
    timestamp: datetime
    asset: str
    sequence: int
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]


class DerivativesContext(FrozenModel):
    timestamp: datetime
    asset: str
    funding_rate: float | None = None
    open_interest: NonNegativeDecimal | None = None


class DetectedRegime(FrozenModel):
    timestamp: datetime
    asset: str
    trend_regime: TrendRegime
    volatility_regime: VolatilityRegime
    confidence: UnitFloat
    detector_version: str


class EnsemblePrediction(FrozenModel):
    timestamp: datetime
    asset: str
    probability_up: UnitFloat
    confidence: UnitFloat
    disagreement: UnitFloat
    action: DecisionAction
    contributions: dict[str, float]
    ensemble_version: str


class Bar(FrozenModel):
    timestamp: datetime
    asset: str = Field(min_length=3)
    timeframe: str = Field(pattern=r"^[1-9][0-9]*[mhd]$")
    open: PositiveDecimal
    high: PositiveDecimal
    low: PositiveDecimal
    close: PositiveDecimal
    volume: NonNegativeDecimal

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode="after")
    def valid_range(self) -> Bar:
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC values fall outside high/low range")
        if self.low > self.high:
            raise ValueError("low must not exceed high")
        return self


class Trade(FrozenModel):
    trade_id: str
    timestamp: datetime
    asset: str
    side: Side
    price: PositiveDecimal
    quantity: PositiveDecimal

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class Prediction(FrozenModel):
    timestamp: datetime
    asset: str
    horizon: str
    expected_return: float
    probability_up: UnitFloat
    confidence: UnitFloat
    model_name: str = "unknown"
    model_version: str

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class Signal(FrozenModel):
    signal_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    asset: str
    strategy: str
    direction: SignalDirection
    strength: UnitFloat
    confidence: UnitFloat
    rationale: dict[str, str | float | int] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class TargetPosition(FrozenModel):
    timestamp: datetime
    asset: str
    target_weight: Annotated[float, Field(ge=-1.0, le=1.0)]
    source_signal_ids: tuple[UUID, ...]

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class ProposedOrder(FrozenModel):
    client_order_id: UUID = Field(default_factory=uuid4)
    created_at: datetime
    asset: str
    side: Side
    order_type: OrderType
    quantity: PositiveDecimal
    limit_price: PositiveDecimal | None = None

    @field_validator("created_at")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)

    @model_validator(mode="after")
    def limit_requires_price(self) -> ProposedOrder:
        if (self.order_type is OrderType.LIMIT) != (self.limit_price is not None):
            raise ValueError("limit orders require limit_price; market orders forbid it")
        return self


class RiskDecision(FrozenModel):
    decision_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime
    order_id: UUID
    status: RiskDecisionStatus
    approved: bool
    reasons: tuple[str, ...]
    evaluated_limits: dict[str, Decimal | float | int | bool]
    approved_quantity: Decimal | None = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)


class ApprovedOrder(FrozenModel):
    order: ProposedOrder
    risk_decision_id: UUID


class Fill(FrozenModel):
    fill_id: str
    client_order_id: UUID
    timestamp: datetime
    asset: str
    side: Side
    price: PositiveDecimal
    quantity: PositiveDecimal
    fee: NonNegativeDecimal
    fee_currency: str
    spread_cost: NonNegativeDecimal = Decimal("0")
    slippage_cost: NonNegativeDecimal = Decimal("0")

    @field_validator("timestamp")
    @classmethod
    def timestamp_is_utc(cls, value: datetime) -> datetime:
        return require_utc(value)
