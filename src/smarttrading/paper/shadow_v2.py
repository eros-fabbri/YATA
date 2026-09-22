from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib.metadata
import json
import logging
import os
import signal
import subprocess
import sys
import time
from collections import defaultdict, deque
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from smarttrading.data.market_store import MarketDataStore
from smarttrading.data.market_v2 import (
    AggregateTradeEvent,
    BBOEvent,
    DepthUpdate,
    LocalOrderBook,
    MarketContextSynchronizer,
    quality_metrics,
)
from smarttrading.exchanges.binance_market_v2 import BinanceMarketDataV2
from smarttrading.features.microstructure_v2 import (
    FEATURE_VERSION_V2,
    derivatives_features,
    microstructure_features,
)
from smarttrading.monitoring.runtime import InstanceGuard, log_event, runtime_logger

MIN_RATE_WINDOW_SECONDS = 300.0


def event_source(event: AggregateTradeEvent | BBOEvent | DepthUpdate) -> str:
    if isinstance(event, AggregateTradeEvent):
        return "trade"
    if isinstance(event, BBOEvent):
        return "bbo"
    return "depth"


def latency_percentiles(values: dict[str, deque[float]]) -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {}
    for source, samples in values.items():
        ordered = sorted(samples)
        result[source] = {
            "count": float(len(ordered)),
            "p50_ms": ordered[int((len(ordered) - 1) * 0.50 + 0.5)] if ordered else None,
            "p95_ms": ordered[int((len(ordered) - 1) * 0.95 + 0.5)] if ordered else None,
        }
    return result


def operational_health(
    *,
    elapsed_seconds: float,
    stale_ratio: float,
    missing_ratio: float,
    latency_p95_ms: float | None,
    reconnects: int,
    sequence_gaps: int,
    books_valid: bool,
) -> tuple[str, tuple[str, ...]]:
    if not books_valid:
        return "UNSAFE", ("invalid_book",)
    reasons: list[str] = []
    if stale_ratio >= 0.5:
        reasons.append("high_stale_ratio")
    if missing_ratio > 0:
        reasons.append("missing_sources")
    if latency_p95_ms is not None and latency_p95_ms > 5_000:
        reasons.append("high_source_latency")
    if elapsed_seconds >= 300:
        hourly = 3600 / elapsed_seconds
        if reconnects * hourly > 6:
            reasons.append("frequent_reconnects")
        if sequence_gaps * hourly > 6:
            reasons.append("frequent_sequence_gaps")
    return ("DEGRADED", tuple(reasons)) if reasons else ("HEALTHY", ())


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def runtime_manifest(
    assets: tuple[str, ...], started: datetime, shadow_id: str
) -> dict[str, object]:
    config = {
        "assets": assets,
        "exchange": "binance",
        "feeds": ["aggTrade", "bookTicker", "depth@100ms", "premiumIndex", "openInterest"],
        "feature_version": FEATURE_VERSION_V2,
    }
    return {
        "shadow_id": shadow_id,
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "package_version": importlib.metadata.version("smarttrading"),
        "feature_version": FEATURE_VERSION_V2,
        "config_hash": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
        "start_timestamp": started.isoformat(),
        "assets": list(assets),
        "exchange": "Binance public",
        "feeds": config["feeds"],
        "process_id": os.getpid(),
    }


def database_bytes(path: Path) -> int:
    return sum(
        item.stat().st_size
        for item in (path, Path(f"{path}-wal"), Path(f"{path}-shm"))
        if item.exists()
    )


def storage_measurement(start_bytes: int, current_bytes: int, elapsed: float) -> dict[str, object]:
    result: dict[str, object] = {
        "database_bytes": current_bytes,
        "measurement_seconds": elapsed,
        "growth_bytes": max(0, current_bytes - start_bytes),
        "mb_per_hour": None,
        "projected_gb_per_day": None,
        "warning": None,
    }
    if elapsed < MIN_RATE_WINDOW_SECONDS:
        result["warning"] = "measurement window below 300s; rate suppressed"
    else:
        hourly = max(0, current_bytes - start_bytes) / elapsed * 3600
        result.update(
            mb_per_hour=hourly / 1_000_000, projected_gb_per_day=hourly * 24 / 1_000_000_000
        )
    return result


def storage_guardrail(
    mb_per_hour: float | None, warning_threshold: float, degraded_threshold: float
) -> str:
    if mb_per_hour is None:
        return "MEASURING"
    if mb_per_hour >= degraded_threshold:
        return "DEGRADED"
    if mb_per_hour >= warning_threshold:
        return "WARNING"
    return "NORMAL"


def shadow_status(database: str) -> dict[str, object]:
    path = Path(database)
    store = MarketDataStore(path)
    try:
        state, manifest = store.get_state("runtime") or {}, store.get_state("manifest") or {}
    finally:
        store.close()
    started = manifest.get("start_timestamp")
    uptime = (
        max(0.0, (datetime.now(UTC) - datetime.fromisoformat(str(started))).total_seconds())
        if started
        else 0.0
    )
    return {
        **state,
        "uptime_seconds": uptime,
        "database_bytes": database_bytes(path),
        "feature_version": manifest.get("feature_version", FEATURE_VERSION_V2),
        "subscriptions": manifest.get("assets", []),
    }


def health_assessment(status: dict[str, object]) -> tuple[int, dict[str, object]]:
    health, updated = str(status.get("health", "FAILED")), status.get("updated_at")
    age = (
        (datetime.now(UTC) - datetime.fromisoformat(str(updated))).total_seconds()
        if updated
        else None
    )
    code = (
        2
        if health in {"FAILED", "UNSAFE"}
        else 1
        if health != "HEALTHY" or age is None or age > 30
        else 0
    )
    return code, {
        "status": "HEALTHY" if code == 0 else "DEGRADED" if code == 1 else "UNSAFE",
        "exit_code": code,
        "last_update_age_seconds": age,
        "detail": health,
    }


def readiness_assessment(
    coverage: dict[str, object],
    *,
    minimum_hours: float = 24,
    minimum_snapshots: int = 1000,
    minimum_completeness: float = 0.9,
    minimum_book_validity: float = 0.95,
) -> dict[str, object]:
    assets = coverage.get("assets", {})
    reports: dict[str, object] = {}
    if not isinstance(assets, dict):
        assets = {}
    readiness_values: list[bool] = []
    for asset, raw in assets.items():
        item = raw if isinstance(raw, dict) else {}
        counts = item.get("event_counts", {})
        counts = counts if isinstance(counts, dict) else {}
        samples = int(item.get("feature_snapshots", 0))
        has_trade = int(counts.get("trade", 0)) > 0 or int(counts.get("aggregated_trades", 0)) > 0
        completeness = (
            int(has_trade) + int(counts.get("bbo", 0) > 0) + int(counts.get("derivatives", 0) > 0)
        ) / 3
        checks = {
            "coverage": float(item.get("elapsed_seconds", 0)) >= minimum_hours * 3600,
            "samples": samples >= minimum_snapshots,
            "source_completeness": completeness >= minimum_completeness,
            "book_validity": float(item.get("valid_book_percentage", 0)) >= minimum_book_validity,
            "major_gaps": int(item.get("gaps", 0)) == 0,
        }
        ready = all(checks.values())
        readiness_values.append(ready)
        reports[str(asset)] = {
            "ready": ready,
            "checks": checks,
            "coverage_hours": float(item.get("elapsed_seconds", 0)) / 3600,
            "sample_count": samples,
            "source_completeness": completeness,
            "book_validity": item.get("valid_book_percentage", 0),
            "missingness": 1 - completeness,
            "major_gaps": item.get("gaps", 0),
        }
    return {
        "research_ready": bool(reports) and all(readiness_values),
        "informational_only": True,
        "thresholds": {
            "minimum_hours": minimum_hours,
            "minimum_snapshots": minimum_snapshots,
            "minimum_completeness": minimum_completeness,
            "minimum_book_validity": minimum_book_validity,
        },
        "assets": reports,
    }


async def run_shadow_v2(
    database: str,
    assets: tuple[str, ...],
    max_events: int | None = None,
    max_seconds: float | None = None,
    *,
    pid_file: str | None = None,
    log_file: str = "logs/shadow_v2.log",
    log_level: str = "INFO",
    log_max_bytes: int = 10 * 1024 * 1024,
    log_backups: int = 5,
    trade_bucket_seconds: int = 1,
    bbo_sample_seconds: int = 1,
    derived_snapshot_seconds: int = 1,
    book_checkpoint_seconds: int = 60,
    book_checkpoint_levels: int = 20,
    raw_retention_days: int = 7,
    storage_warning_mb_hour: float = 100.0,
    storage_degraded_mb_hour: float = 250.0,
    suspend_raw_on_degraded: bool = True,
) -> dict[str, object]:
    path = Path(database)
    if path.name == "forward_v1.db":
        raise ValueError("Shadow V2 cannot use Forward V1 database")
    intervals = (
        trade_bucket_seconds,
        bbo_sample_seconds,
        derived_snapshot_seconds,
        book_checkpoint_seconds,
        book_checkpoint_levels,
    )
    if any(value <= 0 for value in intervals):
        raise ValueError("persistence intervals and retained levels must be positive")
    logger = runtime_logger(
        "smarttrading.shadow.v2",
        level=log_level,
        log_file=log_file,
        max_bytes=log_max_bytes,
        backups=log_backups,
    )
    guard = InstanceGuard(pid_file or f"{database}.pid")
    guard.acquire()
    store: MarketDataStore | None = None
    stop = asyncio.Event()
    health = "STARTING"
    started = datetime.now(UTC)
    shadow_id = f"shadow-v2-{uuid4()}"
    start = time.monotonic()
    processed = 0
    latencies: deque[float] = deque(maxlen=50_000)
    source_latencies: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=10_000))
    start_bytes = database_bytes(path)
    adapter = BinanceMarketDataV2(assets)
    books = {asset: LocalOrderBook(asset) for asset in assets}
    sync = {asset: MarketContextSynchronizer(asset) for asset in assets}
    derivatives_at = {asset: start for asset in assets}
    book_checkpoint_at = {asset: 0.0 for asset in assets}
    last_bbo_bucket: dict[str, int] = {}
    last_derived_bucket: dict[str, int] = {}
    derivative_values: dict[str, tuple[object, ...]] = {}
    raw_bbo_enabled = True
    storage_warning_logged = False
    storage_degraded_logged = False
    last_checkpoint = start
    last_retention = start
    connection_generation = 0
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        log_event(logger, logging.INFO, "shutdown_requested", shadow_id=shadow_id)
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, request_stop)
    try:
        store = MarketDataStore(path)
        manifest = runtime_manifest(assets, started, shadow_id)
        persistence_config = {
            "trade_bucket_seconds": trade_bucket_seconds,
            "bbo_sample_seconds": bbo_sample_seconds,
            "derived_snapshot_seconds": derived_snapshot_seconds,
            "book_checkpoint_seconds": book_checkpoint_seconds,
            "book_checkpoint_levels": book_checkpoint_levels,
            "raw_retention_days": raw_retention_days,
            "storage_warning_mb_hour": storage_warning_mb_hour,
            "storage_degraded_mb_hour": storage_degraded_mb_hour,
            "suspend_raw_on_degraded": suspend_raw_on_degraded,
        }
        manifest["persistence"] = persistence_config
        manifest["config_hash"] = hashlib.sha256(
            json.dumps(
                {
                    "assets": assets,
                    "feature_version": FEATURE_VERSION_V2,
                    "persistence": persistence_config,
                },
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        store.set_state("manifest", manifest)
        log_event(logger, logging.INFO, "process_startup", **manifest)
        log_event(
            logger,
            logging.INFO,
            "subscription",
            assets=assets,
            streams=["aggTrade", "bookTicker", "depth@100ms"],
        )
        for asset in assets:
            derivative = await adapter.derivatives(asset)
            sync[asset].add(derivative)
            store.append(derivative)
            derivative_values[asset] = (
                derivative.funding_rate,
                derivative.open_interest,
                derivative.mark_price,
                derivative.index_price,
            )
        health = "HEALTHY"
        log_event(logger, logging.INFO, "feed_connected", exchange="binance")
        last_event = time.monotonic()

        async def consume() -> None:
            nonlocal processed, health, last_event, raw_bbo_enabled
            nonlocal storage_warning_logged, storage_degraded_logged
            nonlocal last_checkpoint, last_retention, connection_generation
            reconnects, last_write = 0, 0.0
            async for event in adapter.events():
                if stop.is_set():
                    return
                processed += 1
                current = time.monotonic()
                last_event = current
                generation = getattr(adapter, "connection_generation", 0)
                if generation != connection_generation:
                    previous_generation = connection_generation
                    connection_generation = generation
                    if previous_generation:
                        log_event(
                            logger,
                            logging.WARNING,
                            "feed_reconnect",
                            reconnects=adapter.reconnects,
                            disconnect=getattr(adapter, "last_disconnect", None),
                        )
                    for asset in assets:
                        log_event(
                            logger,
                            logging.INFO,
                            "rest_reconciliation",
                            asset=asset,
                            reason="connection_generation",
                        )
                        replacement = await adapter.book_snapshot(asset)
                        received = datetime.now(UTC)
                        books[asset].apply_snapshot(replacement)
                        sync[asset].add_book(replacement, received)
                        store.save_book_checkpoint(
                            replacement, received, retained_levels=book_checkpoint_levels
                        )
                        book_checkpoint_at[asset] = current
                        log_event(
                            logger,
                            logging.INFO,
                            "book_resync",
                            asset=asset,
                            sequence=replacement.sequence,
                        )
                if adapter.reconnects > reconnects:
                    reconnects = adapter.reconnects
                if current - derivatives_at[event.asset] >= 60:
                    log_event(
                        logger,
                        logging.INFO,
                        "rest_reconciliation",
                        asset=event.asset,
                        source="derivatives",
                    )
                    derivative = await adapter.derivatives(event.asset)
                    sync[event.asset].add(derivative)
                    values = (
                        derivative.funding_rate,
                        derivative.open_interest,
                        derivative.mark_price,
                        derivative.index_price,
                    )
                    if derivative_values.get(event.asset) != values:
                        store.append(derivative)
                        derivative_values[event.asset] = values
                    derivatives_at[event.asset] = current
                latency = max(
                    0.0, (event.received_at - event.event_timestamp).total_seconds() * 1000
                )
                if not isinstance(event, BBOEvent):
                    latencies.append(latency)
                    source_latencies[f"{event.asset}:{event_source(event)}"].append(latency)
                if isinstance(event, DepthUpdate):
                    book = books[event.asset]
                    if not book.apply_update(event) and not book.valid:
                        health = "DEGRADED"
                        log_event(
                            logger,
                            logging.WARNING,
                            "health_transition",
                            previous="HEALTHY",
                            current="DEGRADED",
                            reason="sequence_gap",
                        )
                        log_event(
                            logger,
                            logging.WARNING,
                            "sequence_gap",
                            asset=event.asset,
                            first=event.first_sequence,
                            last=event.last_sequence,
                        )
                        log_event(logger, logging.WARNING, "book_invalidation", asset=event.asset)
                        replacement = await adapter.book_snapshot(event.asset)
                        book.apply_snapshot(replacement)
                        received = datetime.now(UTC)
                        sync[event.asset].add_book(replacement, received)
                        store.save_book_checkpoint(
                            replacement, received, retained_levels=book_checkpoint_levels
                        )
                        book_checkpoint_at[event.asset] = current
                        health = "HEALTHY"
                        log_event(
                            logger,
                            logging.INFO,
                            "health_transition",
                            previous="DEGRADED",
                            current="HEALTHY",
                            reason="book_resync",
                        )
                        log_event(
                            logger,
                            logging.INFO,
                            "book_resync",
                            asset=event.asset,
                            sequence=replacement.sequence,
                        )
                    else:
                        snapshot = book.snapshot(event.event_timestamp)
                        if snapshot:
                            sync[event.asset].add_book(snapshot, event.received_at)
                            if current - book_checkpoint_at[event.asset] >= book_checkpoint_seconds:
                                store.save_book_checkpoint(
                                    snapshot,
                                    event.received_at,
                                    retained_levels=book_checkpoint_levels,
                                )
                                book_checkpoint_at[event.asset] = current
                else:
                    sync[event.asset].add(event)
                    if isinstance(event, AggregateTradeEvent):
                        store.aggregate_trade(event, bucket_seconds=trade_bucket_seconds)
                    elif isinstance(event, BBOEvent) and raw_bbo_enabled:
                        bbo_bucket = int(event.event_timestamp.timestamp()) // bbo_sample_seconds
                        if last_bbo_bucket.get(event.asset) != bbo_bucket:
                            store.save_bbo_sample(event, bucket_seconds=bbo_sample_seconds)
                            last_bbo_bucket[event.asset] = bbo_bucket
                derived_bucket = int(event.received_at.timestamp()) // derived_snapshot_seconds
                if last_derived_bucket.get(event.asset) == derived_bucket:
                    if max_events is not None and processed >= max_events:
                        return
                    continue
                context = sync[event.asset].snapshot(event.received_at)
                features = {
                    **microstructure_features(context),
                    **derivatives_features((context,)),
                }
                store.save_derived_snapshot(
                    context,
                    features,
                    FEATURE_VERSION_V2,
                    bucket_seconds=derived_snapshot_seconds,
                )
                last_derived_bucket[event.asset] = derived_bucket
                if current - last_write >= 1:
                    quality = quality_metrics(
                        context,
                        books.values(),
                        reconnects=adapter.reconnects,
                        latencies_ms=latencies,
                    )
                    elapsed = max(current - start, 1e-9)
                    assessed_health, health_reasons = operational_health(
                        elapsed_seconds=elapsed,
                        stale_ratio=quality.stale_ratio,
                        missing_ratio=quality.missing_ratio,
                        latency_p95_ms=quality.latency_ms_p95,
                        reconnects=quality.reconnects,
                        sequence_gaps=quality.sequence_gaps,
                        books_valid=all(book.valid for book in books.values()),
                    )
                    if assessed_health != health:
                        log_event(
                            logger,
                            logging.WARNING if assessed_health != "HEALTHY" else logging.INFO,
                            "health_transition",
                            previous=health,
                            current=assessed_health,
                            reasons=health_reasons,
                        )
                    health = assessed_health
                    storage = storage_measurement(start_bytes, database_bytes(path), elapsed)
                    rate = storage.get("mb_per_hour")
                    guardrail = storage_guardrail(
                        rate if isinstance(rate, float) else None,
                        storage_warning_mb_hour,
                        storage_degraded_mb_hour,
                    )
                    if guardrail in {"WARNING", "DEGRADED"} and not storage_warning_logged:
                        log_event(
                            logger,
                            logging.WARNING,
                            "storage_growth_warning",
                            mb_per_hour=rate,
                            threshold=storage_warning_mb_hour,
                        )
                        storage_warning_logged = True
                    if guardrail == "DEGRADED":
                        health = "DEGRADED"
                        if suspend_raw_on_degraded:
                            raw_bbo_enabled = False
                        if not storage_degraded_logged:
                            log_event(
                                logger,
                                logging.ERROR,
                                "storage_growth_degraded",
                                mb_per_hour=rate,
                                threshold=storage_degraded_mb_hour,
                                raw_bbo_suspended=not raw_bbo_enabled,
                            )
                            storage_degraded_logged = True
                    asset_state = {}
                    for name in assets:
                        snap = sync[name].snapshot(event.received_at)
                        asset_state[name] = {
                            "bbo": snap.quote.model_dump(mode="json") if snap.quote else None,
                            "book_valid": books[name].valid,
                            "funding": snap.derivatives.funding_rate if snap.derivatives else None,
                            "open_interest": str(snap.derivatives.open_interest)
                            if snap.derivatives and snap.derivatives.open_interest is not None
                            else None,
                            "sources": {
                                source: status.model_dump(mode="json")
                                for source, status in snap.sources.items()
                            },
                        }
                    store.set_state(
                        "runtime",
                        {
                            "shadow_id": shadow_id,
                            "health": health,
                            "feed_state": "CONNECTED",
                            "updated_at": datetime.now(UTC).isoformat(),
                            "events": processed,
                            "events_per_second": processed / elapsed,
                            "latest_snapshot": context.decision_time.isoformat(),
                            "assets": asset_state,
                            "quality": quality.model_dump(mode="json"),
                            "source_latency": latency_percentiles(source_latencies),
                            "latency_semantics": {
                                "bbo": "unavailable: bookTicker has no exchange event timestamp",
                                "trade": "exchange trade time to local receive time",
                                "depth": "exchange event time to local receive time",
                            },
                            "health_reasons": health_reasons,
                            "connection": {
                                "generation": connection_generation,
                                "last_disconnect": getattr(adapter, "last_disconnect", None),
                            },
                            "storage": storage,
                            "storage_guardrail": guardrail,
                            "persistence": {
                                "raw_bbo_enabled": raw_bbo_enabled,
                                "trade_bucket_seconds": trade_bucket_seconds,
                                "derived_snapshot_seconds": derived_snapshot_seconds,
                                "book_checkpoint_seconds": book_checkpoint_seconds,
                                "book_checkpoint_levels": book_checkpoint_levels,
                            },
                        },
                    )
                    if current - last_checkpoint >= 60:
                        store.flush(checkpoint=True)
                        last_checkpoint = current
                    if raw_retention_days > 0 and current - last_retention >= 3600:
                        deleted = store.compact_raw_retention(raw_retention_days)
                        log_event(
                            logger,
                            logging.INFO,
                            "raw_retention",
                            deleted=deleted,
                            retention_days=raw_retention_days,
                        )
                        last_retention = current
                    last_write = current
                if max_events is not None and processed >= max_events:
                    return

        async def watchdog() -> None:
            nonlocal health
            stale_logged = False
            while not stop.is_set():
                await asyncio.sleep(5)
                if time.monotonic() - last_event > 30:
                    health = "DEGRADED"
                    if not stale_logged:
                        log_event(
                            logger,
                            logging.WARNING,
                            "stale_feed",
                            age_seconds=time.monotonic() - last_event,
                        )
                        log_event(
                            logger,
                            logging.WARNING,
                            "health_transition",
                            previous="HEALTHY",
                            current="DEGRADED",
                            reason="stale_feed",
                        )
                        stale_logged = True
                    state = store.get_state("runtime") or {}
                    state.update(
                        {
                            "health": health,
                            "feed_state": "STALE",
                            "updated_at": datetime.now(UTC).isoformat(),
                        }
                    )
                    store.set_state("runtime", state)

        consume_task = asyncio.create_task(consume())
        stop_task = asyncio.create_task(stop.wait())
        watchdog_task = asyncio.create_task(watchdog())
        try:
            done, _ = await asyncio.wait(
                {consume_task, stop_task},
                timeout=max_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if consume_task in done:
                await consume_task
            else:
                consume_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await consume_task
        finally:
            stop_task.cancel()
            watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await stop_task
            with contextlib.suppress(asyncio.CancelledError):
                await watchdog_task
    except Exception:
        health = "FAILED"
        logger.exception("fatal_error")
        if store is not None:
            store.set_state(
                "runtime",
                {
                    "shadow_id": shadow_id,
                    "health": health,
                    "feed_state": "FAILED",
                    "updated_at": datetime.now(UTC).isoformat(),
                },
            )
        raise
    finally:
        if store is not None:
            state = store.get_state("runtime") or {}
            state.update(
                {
                    "shadow_id": shadow_id,
                    "health": "STOPPED" if health != "FAILED" else health,
                    "feed_state": "DISCONNECTED",
                    "updated_at": datetime.now(UTC).isoformat(),
                }
            )
            store.set_state("runtime", state)
            store.close()
        guard.release()
        log_event(
            logger,
            logging.INFO,
            "graceful_shutdown",
            shadow_id=shadow_id,
            events=processed,
            health=health,
        )
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.remove_signal_handler(sig)
    return shadow_status(database)


def run_shadow_command(
    database: str,
    assets: tuple[str, ...],
    max_events: int | None,
    max_seconds: float | None,
    *,
    pid_file: str | None = None,
    log_file: str = "logs/shadow_v2.log",
    log_level: str = "INFO",
    log_max_bytes: int = 10 * 1024 * 1024,
    log_backups: int = 5,
    trade_bucket_seconds: int = 1,
    bbo_sample_seconds: int = 1,
    derived_snapshot_seconds: int = 1,
    book_checkpoint_seconds: int = 60,
    book_checkpoint_levels: int = 20,
    raw_retention_days: int = 7,
    storage_warning_mb_hour: float = 100.0,
    storage_degraded_mb_hour: float = 250.0,
    suspend_raw_on_degraded: bool = True,
) -> None:
    print(
        json.dumps(
            asyncio.run(
                run_shadow_v2(
                    database,
                    assets,
                    max_events,
                    max_seconds,
                    pid_file=pid_file,
                    log_file=log_file,
                    log_level=log_level,
                    log_max_bytes=log_max_bytes,
                    log_backups=log_backups,
                    trade_bucket_seconds=trade_bucket_seconds,
                    bbo_sample_seconds=bbo_sample_seconds,
                    derived_snapshot_seconds=derived_snapshot_seconds,
                    book_checkpoint_seconds=book_checkpoint_seconds,
                    book_checkpoint_levels=book_checkpoint_levels,
                    raw_retention_days=raw_retention_days,
                    storage_warning_mb_hour=storage_warning_mb_hour,
                    storage_degraded_mb_hour=storage_degraded_mb_hour,
                    suspend_raw_on_degraded=suspend_raw_on_degraded,
                )
            ),
            indent=2,
        )
    )
