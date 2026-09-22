from __future__ import annotations

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from smarttrading.data.validation import validate_bar_series
from smarttrading.domain import Bar


def load_bars_csv(path: str | Path) -> list[Bar]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        bars = [
            Bar(
                timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                asset=row["asset"],
                timeframe=row["timeframe"],
                open=Decimal(row["open"]),
                high=Decimal(row["high"]),
                low=Decimal(row["low"]),
                close=Decimal(row["close"]),
                volume=Decimal(row["volume"]),
            )
            for row in rows
        ]
    return validate_bar_series(bars)
