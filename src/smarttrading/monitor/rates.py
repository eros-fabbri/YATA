from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

COUNTERS = ("reconnects", "sequence_gaps", "book_resyncs", "out_of_order")


@dataclass
class SessionRates:
    started: float = field(default_factory=time.monotonic)
    initial: dict[str, float] = field(default_factory=dict)
    previous: dict[str, float] = field(default_factory=dict)

    def observe(self, values: dict[str, float], now: float | None = None) -> dict[str, Any]:
        observed = time.monotonic() if now is None else now
        elapsed = max(observed - self.started, 0.0)
        result: dict[str, Any] = {"elapsed_seconds": elapsed}
        for name, value in values.items():
            if name not in self.initial or value < self.previous.get(name, value):
                self.initial[name] = value
            delta = value - self.initial[name]
            result[name] = {
                "value": value,
                "delta": delta,
                "per_hour": delta / elapsed * 3600 if elapsed > 0 else None,
            }
            self.previous[name] = value
        return result


def v2_counters(snapshot: dict[str, Any]) -> dict[str, float]:
    runtime = snapshot.get("runtime")
    if not isinstance(runtime, dict):
        return {}
    quality = runtime.get("quality")
    quality = quality if isinstance(quality, dict) else {}
    return {
        "reconnects": float(quality.get("reconnects", runtime.get("reconnects", 0)) or 0),
        "sequence_gaps": float(quality.get("sequence_gaps", 0) or 0),
        "book_resyncs": float(quality.get("book_resync_count", 0) or 0),
        "out_of_order": float(quality.get("out_of_order_events", 0) or 0),
        "database_bytes": float(snapshot.get("database_bytes", 0) or 0),
    }
