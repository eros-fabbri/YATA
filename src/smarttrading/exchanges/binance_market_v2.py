from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import websockets

from smarttrading.data.market_v2 import AggregateTradeEvent, BBOEvent, DepthUpdate, DerivativesEvent
from smarttrading.domain import OrderBookLevel, OrderBookSnapshot, Side


def _asset(symbol: str) -> str:
    return f"{symbol[:-4]}/USDT" if symbol.endswith("USDT") else symbol


class BinanceMarketDataV2:
    spot_rest = "https://api.binance.com"
    futures_rest = "https://fapi.binance.com"

    def __init__(self, assets: tuple[str, ...], *, maximum_backoff: float = 30.0) -> None:
        self.assets = assets
        self.maximum_backoff = maximum_backoff
        self.reconnects = 0
        self.connection_generation = 0
        self.last_disconnect: dict[str, object] | None = None

    @staticmethod
    def symbol(asset: str) -> str:
        return asset.replace("/", "").upper()

    async def book_snapshot(self, asset: str, limit: int = 100) -> OrderBookSnapshot:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.spot_rest}/api/v3/depth",
                params={"symbol": self.symbol(asset), "limit": limit},
            )
            response.raise_for_status()
            raw = response.json()
        now = datetime.now(UTC)
        return OrderBookSnapshot(
            timestamp=now,
            asset=asset,
            sequence=int(raw["lastUpdateId"]),
            bids=tuple(
                OrderBookLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in raw["bids"]
            ),
            asks=tuple(
                OrderBookLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in raw["asks"]
            ),
        )

    async def derivatives(self, asset: str) -> DerivativesEvent:
        symbol = self.symbol(asset)
        async with httpx.AsyncClient(timeout=10) as client:
            premium, interest = await asyncio.gather(
                client.get(f"{self.futures_rest}/fapi/v1/premiumIndex", params={"symbol": symbol}),
                client.get(f"{self.futures_rest}/fapi/v1/openInterest", params={"symbol": symbol}),
            )
            premium.raise_for_status()
            interest.raise_for_status()
        p, oi, now = premium.json(), interest.json(), datetime.now(UTC)
        return DerivativesEvent(
            event_id=f"derivatives:{symbol}:{p['time']}",
            asset=asset,
            event_timestamp=datetime.fromtimestamp(int(p["time"]) / 1000, tz=UTC),
            received_at=now,
            funding_rate=float(p["lastFundingRate"]),
            open_interest=Decimal(oi["openInterest"]),
            mark_price=Decimal(p["markPrice"]),
            index_price=Decimal(p["indexPrice"]),
        )

    @staticmethod
    def parse(
        message: str, received_at: datetime
    ) -> AggregateTradeEvent | BBOEvent | DepthUpdate | None:
        envelope = json.loads(message)
        data = envelope.get("data", envelope)
        kind = data.get("e")
        symbol, asset = str(data.get("s", "")), _asset(str(data.get("s", "")))
        if kind == "aggTrade":
            return AggregateTradeEvent(
                event_id=f"trade:{symbol}:{data['a']}",
                asset=asset,
                event_timestamp=datetime.fromtimestamp(data["T"] / 1000, tz=UTC),
                received_at=received_at,
                price=Decimal(data["p"]),
                quantity=Decimal(data["q"]),
                side=Side.SELL if data["m"] else Side.BUY,
            )
        if kind == "depthUpdate":
            return DepthUpdate(
                event_id=f"depth:{symbol}:{data['U']}:{data['u']}",
                asset=asset,
                event_timestamp=datetime.fromtimestamp(data["E"] / 1000, tz=UTC),
                received_at=received_at,
                first_sequence=int(data["U"]),
                last_sequence=int(data["u"]),
                bids=tuple(
                    OrderBookLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in data["b"]
                ),
                asks=tuple(
                    OrderBookLevel(price=Decimal(p), quantity=Decimal(q)) for p, q in data["a"]
                ),
            )
        if "b" in data and "a" in data and symbol:
            event_time = int(data.get("E", received_at.timestamp() * 1000))
            return BBOEvent(
                event_id=f"bbo:{symbol}:{data.get('u', event_time)}",
                asset=asset,
                event_timestamp=datetime.fromtimestamp(event_time / 1000, tz=UTC),
                received_at=received_at,
                bid=Decimal(data["b"]),
                ask=Decimal(data["a"]),
                bid_quantity=Decimal(data["B"]),
                ask_quantity=Decimal(data["A"]),
            )
        return None

    async def events(self) -> AsyncIterator[AggregateTradeEvent | BBOEvent | DepthUpdate]:
        streams = "/".join(
            f"{self.symbol(asset).lower()}@{stream}"
            for asset in self.assets
            for stream in ("aggTrade", "bookTicker", "depth@100ms")
        )
        uri = f"wss://stream.binance.com:9443/stream?streams={streams}"
        backoff = 1.0
        while True:
            connected_at: float | None = None
            try:
                async with websockets.connect(
                    uri,
                    ping_interval=20,
                    ping_timeout=20,
                    open_timeout=10,
                    close_timeout=5,
                ) as socket:
                    self.connection_generation += 1
                    connected_at = time.monotonic()
                    async for raw in socket:
                        parsed = self.parse(str(raw), datetime.now(UTC))
                        if parsed is not None:
                            yield parsed
            except (OSError, TimeoutError, websockets.WebSocketException) as error:
                self.reconnects += 1
                connected_seconds = (
                    time.monotonic() - connected_at if connected_at is not None else 0.0
                )
                if connected_seconds >= 60:
                    backoff = 1.0
                received = getattr(error, "rcvd", None)
                self.last_disconnect = {
                    "type": type(error).__name__,
                    "message": str(error),
                    "close_code": getattr(received, "code", None),
                    "close_reason": getattr(received, "reason", None),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "connected_seconds": connected_seconds,
                    "next_backoff_seconds": backoff,
                }
                await asyncio.sleep(backoff)
                backoff = min(self.maximum_backoff, backoff * 2)
