from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AlertThresholds:
    v1_stale_seconds: float = 900.0
    v2_stale_seconds: float = 10.0
    bbo_stale_seconds: float = 10.0
    reconnects_per_hour: float = 6.0
    gaps_per_hour: float = 6.0
    resyncs_per_hour: float = 6.0
    latency_p95_ms: float = 5_000.0
    stale_ratio: float = 0.5
    storage_mb_hour: float = 100.0


DEFAULT_THRESHOLDS = AlertThresholds()


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def monitor_alerts(
    v1: dict[str, Any] | None,
    v2: dict[str, Any] | None,
    rates: dict[str, Any],
    ages: dict[str, float | None],
    thresholds: AlertThresholds = DEFAULT_THRESHOLDS,
) -> list[str]:
    alerts: list[str] = []
    if v1 is not None:
        if not v1.get("available"):
            alerts.append("V1 OFFLINE: database unavailable")
        elif (ages.get("v1_update") or 0) > thresholds.v1_stale_seconds:
            alerts.append("V1 STALE: no recent decision/update")
    if v2 is None:
        return alerts
    if not v2.get("available"):
        alerts.append("V2 OFFLINE: database unavailable")
        return alerts
    runtime = _mapping(v2.get("runtime"))
    if (ages.get("v2_update") or 0) > thresholds.v2_stale_seconds:
        alerts.append("V2 STALE: runtime snapshot is old")
    assets = _mapping(runtime.get("assets"))
    for asset, raw in assets.items():
        item = _mapping(raw)
        if not item.get("book_valid", False):
            alerts.append(f"{asset} UNSAFE: local book invalid")
        if item.get("funding") is None or item.get("open_interest") is None:
            alerts.append(f"{asset}: funding/OI unavailable")
    quality = _mapping(runtime.get("quality"))
    if float(quality.get("stale_ratio", 0) or 0) >= thresholds.stale_ratio:
        alerts.append("V2: stale ratio high")
    latency = _mapping(runtime.get("source_latency"))
    p95_values = [
        float(item["p95_ms"])
        for item in latency.values()
        if isinstance(item, dict) and item.get("p95_ms") is not None
    ]
    if quality.get("latency_ms_p95") is not None:
        p95_values.append(float(quality["latency_ms_p95"]))
    if p95_values and max(p95_values) > thresholds.latency_p95_ms:
        alerts.append("V2: source latency p95 high")
    for key, label, limit in (
        ("reconnects", "reconnect rate", thresholds.reconnects_per_hour),
        ("sequence_gaps", "sequence-gap rate", thresholds.gaps_per_hour),
        ("book_resyncs", "resync rate", thresholds.resyncs_per_hour),
    ):
        rate_item = rates.get(key)
        if (
            isinstance(rate_item, dict)
            and rate_item.get("per_hour") is not None
            and float(rate_item["per_hour"]) > limit
        ):
            alerts.append(f"V2: {label} high")
    storage = _mapping(runtime.get("storage"))
    growth = storage.get("mb_per_hour")
    if growth is not None and float(growth) > thresholds.storage_mb_hour:
        alerts.append("V2: storage growth high")
    return alerts
