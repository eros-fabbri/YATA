from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from smarttrading.domain import BestBidAsk, OrderBookLevel, OrderBookSnapshot, Side, Trade


class SourceValidity(StrEnum):
    VALID = "valid"
    STALE = "stale"
    MISSING = "missing"
    INVALID = "invalid"


class TimedEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_id: str
    asset: str
    event_timestamp: datetime
    received_at: datetime


class AggregateTradeEvent(TimedEvent):
    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    side: Side

    def trade(self) -> Trade:
        return Trade(
            trade_id=self.event_id,
            timestamp=self.event_timestamp,
            asset=self.asset,
            price=self.price,
            quantity=self.quantity,
            side=self.side,
        )


class BBOEvent(TimedEvent):
    bid: Decimal = Field(gt=0)
    ask: Decimal = Field(gt=0)
    bid_quantity: Decimal = Field(ge=0)
    ask_quantity: Decimal = Field(ge=0)

    def quote(self) -> BestBidAsk:
        return BestBidAsk(
            timestamp=self.event_timestamp,
            asset=self.asset,
            bid=self.bid,
            ask=self.ask,
            bid_quantity=self.bid_quantity,
            ask_quantity=self.ask_quantity,
        )


class DepthUpdate(TimedEvent):
    first_sequence: int
    last_sequence: int
    bids: tuple[OrderBookLevel, ...] = ()
    asks: tuple[OrderBookLevel, ...] = ()


class DerivativesEvent(TimedEvent):
    funding_rate: float | None = None
    open_interest: Decimal | None = Field(default=None, ge=0)
    mark_price: Decimal | None = Field(default=None, gt=0)
    index_price: Decimal | None = Field(default=None, gt=0)


class SourceStatus(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    event_timestamp: datetime | None
    received_at: datetime | None
    age_seconds: float | None
    validity: SourceValidity


class MarketContextSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    decision_time: datetime
    asset: str
    quote: BestBidAsk | None
    book: OrderBookSnapshot | None
    trades: tuple[Trade, ...]
    derivatives: DerivativesEvent | None
    sources: dict[str, SourceStatus]

    @property
    def snapshot_hash(self) -> str:
        raw = self.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


class DataQualityMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    stale_ratio: float
    missing_ratio: float
    book_resync_count: int
    sequence_gaps: int
    duplicate_events: int
    out_of_order_events: int
    pre_snapshot_discards: int
    reconnects: int
    latency_ms_p50: float | None
    latency_ms_p95: float | None


class LocalOrderBook:
    def __init__(self, asset: str, retained_levels: int = 100) -> None:
        self.asset, self.retained_levels = asset, retained_levels
        self.bids: dict[Decimal, Decimal] = {}
        self.asks: dict[Decimal, Decimal] = {}
        self.sequence: int | None = None
        self.valid = False
        self.sequence_gaps = self.duplicates = self.out_of_order = self.resyncs = 0
        self.pre_snapshot_discards = 0
        self.awaiting_bridge = False
        self._seen: set[str] = set()

    def apply_snapshot(self, snapshot: OrderBookSnapshot) -> None:
        if snapshot.asset != self.asset:
            raise ValueError("snapshot asset mismatch")
        self.bids = {x.price: x.quantity for x in snapshot.bids if x.quantity > 0}
        self.asks = {x.price: x.quantity for x in snapshot.asks if x.quantity > 0}
        self.sequence, self.valid = snapshot.sequence, True
        self.awaiting_bridge = True
        self.resyncs += 1

    def apply_update(self, update: DepthUpdate) -> bool:
        if update.asset != self.asset:
            raise ValueError("update asset mismatch")
        if update.event_id in self._seen:
            self.duplicates += 1
            return False
        self._seen.add(update.event_id)
        if self.sequence is None or not self.valid:
            return False
        if update.last_sequence <= self.sequence:
            if self.awaiting_bridge:
                self.pre_snapshot_discards += 1
            else:
                self.out_of_order += 1
            return False
        expected = self.sequence + 1
        if not (update.first_sequence <= expected <= update.last_sequence):
            self.sequence_gaps += 1
            self.valid = False
            return False
        for side, changes in ((self.bids, update.bids), (self.asks, update.asks)):
            for level in changes:
                if level.quantity == 0:
                    side.pop(level.price, None)
                else:
                    side[level.price] = level.quantity
        self.sequence = update.last_sequence
        self.awaiting_bridge = False
        return True

    def snapshot(self, timestamp: datetime) -> OrderBookSnapshot | None:
        if not self.valid or self.sequence is None:
            return None
        bids = sorted(self.bids.items(), reverse=True)[: self.retained_levels]
        asks = sorted(self.asks.items())[: self.retained_levels]
        return OrderBookSnapshot(
            timestamp=timestamp,
            asset=self.asset,
            sequence=self.sequence,
            bids=tuple(OrderBookLevel(price=p, quantity=q) for p, q in bids),
            asks=tuple(OrderBookLevel(price=p, quantity=q) for p, q in asks),
        )


class MarketContextSynchronizer:
    def __init__(
        self,
        asset: str,
        *,
        stale_after: timedelta | None = None,
        trade_window: timedelta = timedelta(seconds=60),
        history_retention: timedelta = timedelta(minutes=10),
    ) -> None:
        self.asset, self.trade_window, self.history_retention = (
            asset,
            trade_window,
            history_retention,
        )
        common = stale_after
        self.stale_after = {
            "quote": common or timedelta(seconds=5),
            "book": common or timedelta(seconds=5),
            "trades": common or timedelta(seconds=15),
            "derivatives": common or timedelta(seconds=120),
        }
        self.quotes: list[BBOEvent] = []
        self.books: list[tuple[datetime, datetime, OrderBookSnapshot]] = []
        self.trades: list[AggregateTradeEvent] = []
        self.derivatives: list[DerivativesEvent] = []

    def add(self, event: BBOEvent | AggregateTradeEvent | DerivativesEvent) -> None:
        target = (
            self.quotes
            if isinstance(event, BBOEvent)
            else self.trades
            if isinstance(event, AggregateTradeEvent)
            else self.derivatives
        )
        if not target or event.event_timestamp >= target[-1].event_timestamp:
            target.append(event)  # type: ignore[arg-type]
        else:
            position = bisect_right(
                [item.event_timestamp for item in target], event.event_timestamp
            )
            target.insert(position, event)  # type: ignore[arg-type]
        cutoff = event.event_timestamp - self.history_retention
        if target and target[0].event_timestamp < cutoff - timedelta(minutes=1):
            keep_from = bisect_right([item.event_timestamp for item in target], cutoff)
            del target[:keep_from]
        if isinstance(event, AggregateTradeEvent):
            cutoff = event.event_timestamp - self.trade_window
            self.trades = [trade for trade in self.trades if trade.event_timestamp >= cutoff]

    def add_book(self, snapshot: OrderBookSnapshot, received_at: datetime) -> None:
        item = (snapshot.timestamp, received_at, snapshot)
        if not self.books or snapshot.timestamp >= self.books[-1][0]:
            self.books.append(item)
        else:
            position = bisect_right([value[0] for value in self.books], snapshot.timestamp)
            self.books.insert(position, item)
        cutoff = snapshot.timestamp - self.history_retention
        if self.books and self.books[0][0] < cutoff - timedelta(minutes=1):
            keep_from = bisect_right([value[0] for value in self.books], cutoff)
            del self.books[:keep_from]

    def _latest(self, items: Iterable[TimedEvent], at: datetime) -> TimedEvent | None:
        values = tuple(items)
        for item in reversed(values):
            if item.event_timestamp <= at and item.received_at <= at:
                return item
        return None

    def _status(
        self, event: TimedEvent | None, at: datetime, *, source: str, valid: bool = True
    ) -> SourceStatus:
        if event is None:
            return SourceStatus(
                event_timestamp=None,
                received_at=None,
                age_seconds=None,
                validity=SourceValidity.MISSING,
            )
        age = (at - event.event_timestamp).total_seconds()
        validity = (
            SourceValidity.INVALID
            if not valid
            else SourceValidity.STALE
            if age > self.stale_after[source].total_seconds()
            else SourceValidity.VALID
        )
        return SourceStatus(
            event_timestamp=event.event_timestamp,
            received_at=event.received_at,
            age_seconds=age,
            validity=validity,
        )

    def snapshot(self, at: datetime) -> MarketContextSnapshot:
        quote = self._latest(self.quotes, at)
        derivative = self._latest(self.derivatives, at)
        book_item = next(
            (item for item in reversed(self.books) if item[0] <= at and item[1] <= at), None
        )
        window_start = at - self.trade_window
        trades = tuple(
            x.trade()
            for x in self.trades
            if window_start <= x.event_timestamp <= at and x.received_at <= at
        )
        book_event = (
            TimedEvent(
                event_id="book",
                asset=self.asset,
                event_timestamp=book_item[0],
                received_at=book_item[1],
            )
            if book_item
            else None
        )
        trade_latest = self._latest(self.trades, at)
        sources = {
            "quote": self._status(quote, at, source="quote"),
            "book": self._status(book_event, at, source="book"),
            "trades": self._status(trade_latest, at, source="trades"),
            "derivatives": self._status(derivative, at, source="derivatives"),
        }
        return MarketContextSnapshot(
            decision_time=at,
            asset=self.asset,
            quote=quote.quote()
            if isinstance(quote, BBOEvent) and sources["quote"].validity is SourceValidity.VALID
            else None,
            book=book_item[2]
            if book_item and sources["book"].validity is SourceValidity.VALID
            else None,
            trades=trades,
            derivatives=derivative
            if isinstance(derivative, DerivativesEvent)
            and sources["derivatives"].validity is SourceValidity.VALID
            else None,
            sources=sources,
        )


def quality_metrics(
    snapshot: MarketContextSnapshot,
    books: Iterable[LocalOrderBook],
    *,
    reconnects: int,
    latencies_ms: Iterable[float],
) -> DataQualityMetrics:
    states = tuple(x.validity for x in snapshot.sources.values())
    latencies = sorted(latencies_ms)

    def percentile(fraction: float) -> float | None:
        return (
            latencies[min(len(latencies) - 1, int((len(latencies) - 1) * fraction))]
            if latencies
            else None
        )

    book_list = tuple(books)
    return DataQualityMetrics(
        stale_ratio=sum(x is SourceValidity.STALE for x in states) / len(states),
        missing_ratio=sum(x is SourceValidity.MISSING for x in states) / len(states),
        book_resync_count=sum(x.resyncs for x in book_list),
        sequence_gaps=sum(x.sequence_gaps for x in book_list),
        duplicate_events=sum(x.duplicates for x in book_list),
        out_of_order_events=sum(x.out_of_order for x in book_list),
        pre_snapshot_discards=sum(x.pre_snapshot_discards for x in book_list),
        reconnects=reconnects,
        latency_ms_p50=percentile(0.5),
        latency_ms_p95=percentile(0.95),
    )
