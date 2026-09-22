from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal

import websockets

from smarttrading.data.realtime import CandleEvent
from smarttrading.domain import Bar


class ResilientCandleStream:
    def __init__(
        self,
        connect: Callable[[], AsyncIterator[CandleEvent]],
        reconcile: Callable[[], Awaitable[list[CandleEvent]]],
        *,
        maximum_backoff: float = 30.0,
    ) -> None:
        self.connect = connect
        self.reconcile = reconcile
        self.maximum_backoff = maximum_backoff
        self.reconnects = 0

    async def events(self) -> AsyncIterator[CandleEvent]:
        backoff = 1.0
        while True:
            try:
                async for event in self.connect():
                    backoff = 1.0
                    yield event
            except (OSError, TimeoutError, websockets.ConnectionClosed):
                self.reconnects += 1
                for event in await self.reconcile():
                    yield event
                await asyncio.sleep(backoff)
                backoff = min(self.maximum_backoff, backoff * 2)


class BinanceClosedCandleProvider:
    def __init__(self, assets: tuple[str, ...], timeframe: str) -> None:
        self.assets = assets
        self.timeframe = timeframe

    async def connect(self) -> AsyncIterator[CandleEvent]:
        streams = "/".join(
            f"{asset.replace('/', '').lower()}@kline_{self.timeframe}" for asset in self.assets
        )
        uri = f"wss://stream.binance.com:9443/stream?streams={streams}"
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as socket:
            async for raw in socket:
                message = json.loads(raw)
                kline = message["data"]["k"]
                bar = Bar(
                    timestamp=datetime.fromtimestamp(kline["t"] / 1000, tz=UTC),
                    asset=f"{kline['s'][:-4]}/USDT",
                    timeframe=kline["i"],
                    open=Decimal(kline["o"]),
                    high=Decimal(kline["h"]),
                    low=Decimal(kline["l"]),
                    close=Decimal(kline["c"]),
                    volume=Decimal(kline["v"]),
                )
                yield CandleEvent(
                    event_id=f"{bar.asset}:{bar.timeframe}:{bar.timestamp.isoformat()}",
                    bar=bar,
                    closed=bool(kline["x"]),
                    received_at=datetime.now(UTC),
                )
