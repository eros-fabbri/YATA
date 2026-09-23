# Rich table declarations and composed status lines are intentionally kept together.
# ruff: noqa: E501
from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from smarttrading.monitor.alerts import monitor_alerts
from smarttrading.monitor.rates import SessionRates, v2_counters
from smarttrading.monitor.readers import read_v1, read_v2


def parse_timestamp(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def age_seconds(value: object, now: datetime | None = None) -> float | None:
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    current = datetime.now(UTC) if now is None else now
    return max(0.0, (current - parsed).total_seconds())


def _duration(seconds: object) -> str:
    if seconds is None:
        return "N/A"
    value = max(0, int(float(str(seconds))))
    days, value = divmod(value, 86_400)
    hours, value = divmod(value, 3_600)
    minutes, secs = divmod(value, 60)
    return (f"{days}d " if days else "") + f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _age(value: object) -> str:
    seconds = age_seconds(value)
    if seconds is None:
        return "N/A"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f}m"
    return f"{seconds / 3600:.1f}h"


def _fmt(value: object, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _health(snapshot: dict[str, Any] | None, *, v2: bool = False) -> str:
    if snapshot is None:
        return "NOT CONFIGURED"
    if not snapshot.get("available"):
        return "OFFLINE"
    if v2:
        runtime = snapshot.get("runtime")
        return str(runtime.get("health", "UNKNOWN")) if isinstance(runtime, dict) else "UNKNOWN"
    raw = snapshot.get("health")
    if isinstance(raw, dict):
        return str(raw.get("state", raw.get("health", "UNKNOWN")))
    return str(raw or "UNKNOWN")


def _v1_panel(v1: dict[str, Any]) -> Panel:
    if not v1.get("available"):
        return Panel(str(v1.get("error", "database unavailable")), title="Forward V1 — OFFLINE")
    paper = _mapping(v1.get("paper"))
    equity = _mapping(v1.get("equity"))
    counts = _mapping(v1.get("counts"))
    started = v1.get("started_at")
    overview = Table.grid(expand=True)
    overview.add_column()
    overview.add_column()
    overview.add_row(
        f"Experiment: {_fmt(v1.get('experiment_id'))}",
        f"SYSTEM HEALTH: {_health(v1)}",
    )
    overview.add_row(
        f"Uptime: {_duration(age_seconds(started))}  Last update age: {_age(v1.get('last_update'))}",
        f"DB: {v1.get('database')} ({float(v1.get('database_bytes', 0)) / 1_000_000:.1f} MB)",
    )
    overview.add_row(
        "Portfolio: "
        f"cash={_fmt(paper.get('cash'))} equity={_fmt(equity.get('equity'))} "
        f"realized={_fmt(paper.get('realized_pnl'))} unrealized={_fmt(paper.get('unrealized_pnl'))} "
        f"drawdown={_fmt(paper.get('drawdown'))}",
        f"Risk: circuit={_fmt(paper.get('circuit_state'))} kill={_fmt(paper.get('kill_switch'))}",
    )
    stats = "  ".join(
        f"{name}={counts.get(kind, 0)}"
        for name, kind in (
            ("decisions", "decision"),
            ("labels", "forward_outcome"),
            ("orders", "order"),
            ("fills", "fill"),
            ("trades", "trade"),
        )
    )
    decisions = int(counts.get("decision", 0) or 0)
    abstain = sum(
        int(item.get("decision") == "abstain")
        for item in (v1.get("decisions") or {}).values()
        if isinstance(item, dict)
    )
    stats += f"  recent-abstain={abstain}/{min(decisions, 20)}"
    assets = Table(
        "Asset",
        "Prediction age",
        "Ensemble",
        "Models",
        "Confidence",
        "Disagree",
        "Regime",
        "Vol",
        "Decision",
        "Edge",
        "Cost",
        "Position",
        expand=True,
    )
    predictions = _mapping(v1.get("predictions"))
    asset_decisions = _mapping(v1.get("decisions"))
    positions = _mapping(paper.get("positions"))
    for asset in sorted(set(predictions) | set(asset_decisions) | set(positions)):
        prediction = _mapping(predictions.get(asset))
        decision = _mapping(asset_decisions.get(asset))
        models = prediction.get("model_probabilities")
        models_text = (
            ", ".join(f"{k}:{float(v):.3f}" for k, v in models.items())
            if isinstance(models, dict)
            else "N/A"
        )
        ensemble = prediction.get("probability_up")
        if ensemble is None and isinstance(decision.get("ensemble_prediction"), dict):
            ensemble = decision["ensemble_prediction"].get("probability_up")
        regime = _mapping(decision.get("market_regime"))
        assets.add_row(
            str(asset),
            _age(prediction.get("prediction_timestamp")),
            _fmt(ensemble, 3),
            models_text,
            _fmt(prediction.get("confidence"), 3),
            _fmt(prediction.get("disagreement"), 3),
            _fmt(regime.get("regime", regime.get("state"))),
            _fmt(regime.get("volatility_regime")),
            _fmt(decision.get("decision")),
            _fmt(decision.get("estimated_edge"), 4),
            _fmt(decision.get("estimated_transaction_cost"), 4),
            _fmt(positions.get(asset)),
        )
    shadows = _mapping(v1.get("baselines")) or _mapping(paper.get("shadows"))
    shadow_text = (
        "  ".join(
            f"{name}: equity={_fmt(item.get('equity'))} pnl={_fmt(item.get('pnl', item.get('realized_pnl')))}"
            for name, item in shadows.items()
            if isinstance(item, dict)
        )
        or "N/A"
    )
    return Panel(
        Group(overview, Text(stats), assets, Text(f"Baselines: {shadow_text}")),
        title="Forward Experiment V1",
    )


def _rate(rates: dict[str, Any], name: str) -> str:
    item = rates.get(name)
    if not isinstance(item, dict):
        return "N/A"
    hourly = item.get("per_hour")
    return f"{int(float(item.get('value', 0)))} (+{int(float(item.get('delta', 0)))}, {_fmt(hourly, 1)}/h)"


def _v2_panel(v2: dict[str, Any], rates: dict[str, Any]) -> Panel:
    if not v2.get("available"):
        return Panel(str(v2.get("error", "database unavailable")), title="Shadow V2 — OFFLINE")
    runtime = _mapping(v2.get("runtime"))
    quality = _mapping(runtime.get("quality"))
    storage = _mapping(runtime.get("storage"))
    persistence = _mapping(runtime.get("persistence"))
    overview = Table.grid(expand=True)
    overview.add_column()
    overview.add_column()
    overview.add_row(
        f"Shadow: {_fmt(v2.get('shadow_id'))}  Feature: {_fmt(v2.get('feature_version'))}",
        f"SYSTEM HEALTH: {_health(v2, v2=True)}  Feed: {_fmt(runtime.get('feed_state'))}",
    )
    overview.add_row(
        f"Uptime: {_duration(age_seconds(v2.get('started_at')))}  Snapshot age: {_age(runtime.get('latest_snapshot'))}",
        f"Events: {_fmt(runtime.get('events'))} ({_fmt(runtime.get('events_per_second'))}/s)",
    )
    assets = Table(
        "Asset",
        "Bid",
        "Ask",
        "Spread bps",
        "Bid qty",
        "Ask qty",
        "Book",
        "Funding",
        "OI",
        "Market age",
        expand=True,
    )
    raw_assets = _mapping(runtime.get("assets"))
    for asset, raw in sorted(raw_assets.items()):
        item = _mapping(raw)
        bbo = _mapping(item.get("bbo"))
        bid, ask = bbo.get("bid_price"), bbo.get("ask_price")
        spread = None
        try:
            bid_f, ask_f = float(str(bid)), float(str(ask))
            spread = (ask_f - bid_f) / ((ask_f + bid_f) / 2) * 10_000
        except (TypeError, ValueError, ZeroDivisionError):
            pass
        sources = _mapping(item.get("sources"))
        timestamps = [
            source.get("event_timestamp") for source in sources.values() if isinstance(source, dict)
        ]
        market_ts = max((str(value) for value in timestamps if value), default=None)
        assets.add_row(
            str(asset),
            _fmt(bid),
            _fmt(ask),
            _fmt(spread, 2),
            _fmt(bbo.get("bid_quantity")),
            _fmt(bbo.get("ask_quantity")),
            "VALID" if item.get("book_valid") else "INVALID",
            _fmt(item.get("funding")),
            _fmt(item.get("open_interest")),
            _age(market_ts),
        )
    latency = _mapping(runtime.get("source_latency"))
    latency_text = (
        "  ".join(
            f"{name}:p50={_fmt(item.get('p50_ms'))}ms p95={_fmt(item.get('p95_ms'))}ms"
            for name, item in latency.items()
            if isinstance(item, dict)
        )
        or "N/A"
    )
    quality_text = (
        f"Reconnects {_rate(rates, 'reconnects')}  Gaps {_rate(rates, 'sequence_gaps')}  "
        f"Resyncs {_rate(rates, 'book_resyncs')}  Out-of-order {_rate(rates, 'out_of_order')}\n"
        f"duplicates={_fmt(quality.get('duplicate_events'))} missing={_fmt(quality.get('missing_ratio'))} "
        f"stale={_fmt(quality.get('stale_ratio'))} "
        f"p50={_fmt(quality.get('latency_ms_p50'))}ms p95={_fmt(quality.get('latency_ms_p95'))}ms  "
        f"By-source {latency_text}"
    )
    growth_rate = rates.get("database_bytes", {})
    session_growth = growth_rate.get("delta") if isinstance(growth_rate, dict) else None
    persistence_text = (
        f"DB={float(v2.get('database_bytes', 0)) / 1_000_000:.1f}MB "
        f"session_growth={_fmt(None if session_growth is None else float(session_growth) / 1_000_000)}MB "
        f"measured={_fmt(storage.get('mb_per_hour'))}MB/h projected={_fmt(storage.get('projected_gb_per_day'), 3)}GB/day "
        f"guardrail={_fmt(runtime.get('storage_guardrail'))}\n"
        f"checkpoint={_fmt(persistence.get('book_checkpoint_seconds'))}s/{_fmt(persistence.get('book_checkpoint_levels'))} levels "
        f"snapshot={_fmt(persistence.get('derived_snapshot_seconds'))}s trade_bucket={_fmt(persistence.get('trade_bucket_seconds'))}s "
        f"raw_BBO={_fmt(persistence.get('raw_bbo_enabled'))}"
    )
    return Panel(
        Group(overview, assets, Text(quality_text), Text(persistence_text)),
        title="Market Data / Shadow V2",
    )


def collect_snapshot(v1_db: str | None, v2_db: str | None, session: SessionRates) -> dict[str, Any]:
    v1 = read_v1(v1_db) if v1_db else None
    v2 = read_v2(v2_db) if v2_db else None
    rates = session.observe(v2_counters(v2)) if v2 else {}
    ages = {
        "v1_update": age_seconds(v1.get("last_update")) if v1 else None,
        "v2_update": age_seconds(v2.get("last_update")) if v2 else None,
    }
    alerts = monitor_alerts(v1, v2, rates, ages)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "v1": v1,
        "v2": v2,
        "rates": rates,
        "freshness_seconds": ages,
        "monitor_warnings": alerts,
    }


def render_snapshot(snapshot: dict[str, Any]) -> Group:
    sections: list[Any] = []
    v1, v2 = snapshot.get("v1"), snapshot.get("v2")
    rates = _mapping(snapshot.get("rates"))
    if isinstance(v1, dict):
        sections.append(_v1_panel(v1))
    if isinstance(v2, dict):
        sections.append(_v2_panel(v2, rates))
    warnings = snapshot.get("monitor_warnings")
    warning_list = warnings if isinstance(warnings, list) else []
    text = (
        "No observational warnings"
        if not warning_list
        else "\n".join(f"! {item}" for item in warning_list)
    )
    sections.append(Panel(text, title=f"MONITOR WARNINGS: {len(warning_list)}"))
    sections.append(Text("Ctrl+C quit  •  refresh is read-only  •  UTC timestamps"))
    return Group(*sections)


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def diagnostic(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "smarttrading-monitor-diagnostic", "git_commit": _git_commit(), **snapshot}


def run_monitor(
    *,
    v1_db: str | None,
    v2_db: str | None,
    refresh: float,
    once: bool,
    json_output: bool,
    diagnostic_output: bool,
) -> None:
    if not v1_db and not v2_db:
        raise ValueError("at least one of --v1-db or --v2-db is required")
    if refresh <= 0:
        raise ValueError("--refresh must be positive")
    session = SessionRates()
    snapshot = collect_snapshot(v1_db, v2_db, session)
    if json_output or diagnostic_output:
        output = diagnostic(snapshot) if diagnostic_output else snapshot
        print(json.dumps(output, indent=2, default=str))
        return
    console = Console()
    if once:
        console.print(render_snapshot(snapshot))
        return
    try:
        with Live(
            render_snapshot(snapshot), console=console, refresh_per_second=4, screen=True
        ) as live:
            while True:
                time.sleep(refresh)
                snapshot = collect_snapshot(v1_db, v2_db, session)
                live.update(render_snapshot(snapshot), refresh=True)
    except KeyboardInterrupt:
        return
