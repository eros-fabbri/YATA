from __future__ import annotations

import time
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from smarttrading.domain import Bar


class PublicDataError(RuntimeError):
    pass


class BinancePublicData:
    """Credential-free historical klines with bounded retries and rate-limit handling."""

    endpoint = "https://api.binance.com/api/v3/klines"

    def fetch_bars(self, asset: str, timeframe: str, start: datetime, end: datetime) -> list[Bar]:
        current = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        output: list[Bar] = []
        with httpx.Client(timeout=20) as client:
            while current < end_ms:
                response: httpx.Response | None = None
                for attempt in range(3):
                    try:
                        response = client.get(
                            self.endpoint,
                            params={
                                "symbol": asset.replace("/", ""),
                                "interval": timeframe,
                                "startTime": current,
                                "endTime": end_ms,
                                "limit": 1000,
                            },
                        )
                        if response.status_code == 429:
                            time.sleep(min(float(response.headers.get("Retry-After", "1")), 10))
                            continue
                        response.raise_for_status()
                        break
                    except httpx.HTTPError as error:
                        if attempt == 2:
                            raise PublicDataError(
                                f"public market-data request failed: {error}"
                            ) from error
                        time.sleep(2**attempt)
                if response is None:
                    raise PublicDataError("public market-data request produced no response")
                rows = response.json()
                if not rows:
                    break
                for row in rows:
                    opened = int(row[0])
                    output.append(
                        Bar(
                            timestamp=datetime.fromtimestamp(opened / 1000, tz=UTC),
                            asset=asset,
                            timeframe=timeframe,
                            open=Decimal(row[1]),
                            high=Decimal(row[2]),
                            low=Decimal(row[3]),
                            close=Decimal(row[4]),
                            volume=Decimal(row[5]),
                        )
                    )
                next_start = int(rows[-1][0]) + 1
                if next_start <= current:
                    raise PublicDataError("market-data pagination did not advance")
                current = next_start
        return output
