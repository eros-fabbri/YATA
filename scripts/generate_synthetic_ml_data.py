from __future__ import annotations

import argparse
import csv
import math
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/synthetic_ml_1h.csv")
    parser.add_argument("--rows", type=int, default=700)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    price = 100.0
    start = datetime(2024, 1, 1, tzinfo=UTC)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["timestamp", "asset", "timeframe", "open", "high", "low", "close", "volume"]
        )
        for index in range(args.rows):
            opened = price
            change = 0.0015 * math.sin(index / 17) + rng.gauss(0, 0.008)
            price = max(1.0, price * math.exp(change))
            high = max(opened, price) * (1 + abs(rng.gauss(0, 0.002)))
            low = min(opened, price) * (1 - abs(rng.gauss(0, 0.002)))
            volume = 1000 * (1 + abs(change) * 20 + rng.random() * 0.2)
            writer.writerow(
                [
                    (start + timedelta(hours=index)).isoformat(),
                    "BTC/USDT",
                    "1h",
                    f"{opened:.8f}",
                    f"{high:.8f}",
                    f"{low:.8f}",
                    f"{price:.8f}",
                    f"{volume:.8f}",
                ]
            )


if __name__ == "__main__":
    main()
