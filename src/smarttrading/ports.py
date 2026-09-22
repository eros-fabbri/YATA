from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from typing import Protocol

from smarttrading.domain import ApprovedOrder, Bar, Fill, Prediction, RiskDecision, Signal


class HistoricalMarketData(Protocol):
    async def bars(
        self, asset: str, timeframe: str, start: datetime, end: datetime
    ) -> Sequence[Bar]: ...


class StreamingMarketData(Protocol):
    def stream_bars(self, assets: Sequence[str], timeframe: str) -> AsyncIterator[Bar]: ...


class Strategy(Protocol):
    @property
    def name(self) -> str: ...

    def on_bar(self, history: Sequence[Bar], predictions: Sequence[Prediction]) -> Signal: ...


class RiskManager(Protocol):
    def evaluate(self, order: object) -> RiskDecision: ...


class ExecutionVenue(Protocol):
    async def submit(self, order: ApprovedOrder) -> str: ...

    async def fills(self) -> AsyncIterator[Fill]: ...
