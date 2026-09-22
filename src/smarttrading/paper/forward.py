from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from smarttrading.models.training import classification_metrics
from smarttrading.paper.persistence import PaperStore


class ExperimentHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNSAFE = "UNSAFE"


def health_from_signals(
    *,
    reconnects: int = 0,
    stale_seconds: int = 0,
    stale_limit: int = 120,
    accounting_consistent: bool = True,
    artifact_match: bool = True,
    persistence_available: bool = True,
) -> tuple[ExperimentHealth, tuple[str, ...]]:
    unsafe: list[str] = []
    if not accounting_consistent:
        unsafe.append("accounting_inconsistency")
    if not artifact_match:
        unsafe.append("artifact_mismatch")
    if not persistence_available:
        unsafe.append("persistence_failure")
    if stale_seconds > stale_limit:
        unsafe.append("persistent_stale_feed")
    if unsafe:
        return ExperimentHealth.UNSAFE, tuple(unsafe)
    degraded: list[str] = []
    if reconnects >= 3:
        degraded.append("frequent_reconnects")
    if stale_seconds:
        degraded.append("recoverable_stale_feed")
    return (
        (ExperimentHealth.DEGRADED, tuple(degraded)) if degraded else (ExperimentHealth.HEALTHY, ())
    )


class FrozenExperimentConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    protocol_version: str = "forward-v1"
    assets: tuple[str, ...] = ("BTC/USDT", "ETH/USDT")
    timeframe: str = "1h"
    artifact_versions: tuple[str, ...]
    feature_version: str
    target: dict[str, Any]
    thresholds: dict[str, float]
    ensemble_weights: dict[str, float]
    costs: dict[str, float]
    sizing: dict[str, float]
    risk_limits: dict[str, Any]
    starting_capital: Decimal = Decimal("100000")
    shadow_strategies: tuple[str, ...]
    drift_thresholds: dict[str, float]
    evaluation_metrics: tuple[str, ...]
    configuration_frozen_at: datetime

    @property
    def experiment_id(self) -> str:
        payload = self.model_dump(mode="json", exclude={"configuration_frozen_at"})
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:20]
        return f"forward-v1-{digest}"


class ExperimentMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    experiment_id: str
    configuration_frozen_at: datetime
    experiment_started_at: datetime

    @model_validator(mode="after")
    def frozen_before_start(self) -> ExperimentMetadata:
        if self.configuration_frozen_at > self.experiment_started_at:
            raise ValueError("configuration must be frozen before experiment start")
        return self


class ForwardOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    prediction_id: str
    prediction_timestamp: datetime
    maturity_timestamp: datetime
    realized_return: float
    realized_class: int = Field(ge=0, le=1)
    transaction_cost_adjusted_outcome: float


def prediction_id(experiment_id: str, asset: str, timestamp: datetime) -> str:
    return hashlib.sha256(f"{experiment_id}|{asset}|{timestamp.isoformat()}".encode()).hexdigest()[
        :24
    ]


class ExperimentLock:
    KEY = "forward_experiment"

    @classmethod
    def start_or_resume(
        cls, store: PaperStore, config: FrozenExperimentConfig, now: datetime | None = None
    ) -> ExperimentMetadata:
        existing = store.get_state(cls.KEY)
        canonical = config.model_dump(mode="json")
        if existing is not None:
            if existing["config"] != canonical or existing["experiment_id"] != config.experiment_id:
                raise ValueError("started experiment configuration is immutable; create V2")
            return ExperimentMetadata.model_validate(existing["metadata"])
        started = now or datetime.now(UTC)
        metadata = ExperimentMetadata(
            experiment_id=config.experiment_id,
            configuration_frozen_at=config.configuration_frozen_at,
            experiment_started_at=started,
        )
        store.set_state(
            cls.KEY,
            {
                "experiment_id": config.experiment_id,
                "config": canonical,
                "metadata": metadata.model_dump(mode="json"),
            },
        )
        return metadata


def mature_predictions(
    store: PaperStore,
    *,
    experiment_id: str,
    horizon_bars: int,
    return_threshold: float,
    round_trip_cost: float,
) -> list[ForwardOutcome]:
    bars = store.events("closed_bar")
    closes: dict[str, list[tuple[datetime, float]]] = {}
    for item in bars:
        payload = item["payload"]
        closes.setdefault(payload["asset"], []).append(
            (datetime.fromisoformat(payload["timestamp"]), float(payload["close"]))
        )
    outcomes: list[ForwardOutcome] = []
    for event in store.events("forward_prediction"):
        p = event["payload"]
        if p["experiment_id"] != experiment_id:
            continue
        pid = p["prediction_id"]
        if store.exists(f"outcome:{pid}"):
            continue
        sequence = closes.get(p["asset"], [])
        timestamp = datetime.fromisoformat(p["prediction_timestamp"])
        positions = [index for index, (time, _) in enumerate(sequence) if time == timestamp]
        if not positions or positions[0] + horizon_bars >= len(sequence):
            continue
        current = sequence[positions[0]][1]
        maturity, future = sequence[positions[0] + horizon_bars]
        realized = future / current - 1
        outcome = ForwardOutcome(
            prediction_id=pid,
            prediction_timestamp=timestamp,
            maturity_timestamp=maturity,
            realized_return=realized,
            realized_class=int(realized > return_threshold),
            transaction_cost_adjusted_outcome=realized - round_trip_cost,
        )
        store.append(
            f"outcome:{pid}",
            "forward_outcome",
            maturity.isoformat(),
            outcome.model_dump(mode="json"),
        )
        outcomes.append(outcome)
    return outcomes


def predictive_metrics(store: PaperStore, minimum_sample: int = 30) -> dict[str, Any]:
    outcomes = {
        item["payload"]["prediction_id"]: item["payload"]
        for item in store.events("forward_outcome")
    }
    probabilities: list[float] = []
    labels: list[int] = []
    for event in store.events("forward_prediction"):
        payload = event["payload"]
        outcome = outcomes.get(payload["prediction_id"])
        if outcome is not None:
            probabilities.append(float(payload["probability_up"]))
            labels.append(int(outcome["realized_class"]))
    result: dict[str, Any] = {
        "sample_size": len(labels),
        "statistically_meaningful": len(labels) >= minimum_sample,
        "abstention_rate": (
            sum(event["payload"].get("decision") == "abstain" for event in store.events("decision"))
            / len(store.events("decision"))
            if store.events("decision")
            else None
        ),
    }
    if not labels:
        return result
    metrics = classification_metrics(np.asarray(labels), np.asarray(probabilities))
    result.update(asdict(metrics))
    result["prediction_distribution"] = {
        "min": min(probabilities),
        "mean": sum(probabilities) / len(probabilities),
        "max": max(probabilities),
    }
    return result


def reconcile_accounting(
    state: dict[str, Any], prices: dict[str, Decimal], tolerance: Decimal = Decimal("0.00000001")
) -> tuple[ExperimentHealth, tuple[str, ...]]:
    reasons: list[str] = []
    cash = Decimal(state.get("cash", "0"))
    if cash < 0:
        reasons.append("negative_cash")
    value = Decimal("0")
    for asset, position in state.get("positions", {}).items():
        quantity = Decimal(position["quantity"])
        if quantity < 0:
            reasons.append(f"negative_position:{asset}")
        value += quantity * prices.get(asset, Decimal(position["average_entry_price"]))
    expected = cash + value
    recorded = Decimal(state.get("equity", str(expected)))
    if abs(expected - recorded) > tolerance:
        reasons.append("equity_invariant")
    return (ExperimentHealth.UNSAFE if reasons else ExperimentHealth.HEALTHY, tuple(reasons))


def economic_metrics(store: PaperStore, strategy: str | None = None) -> dict[str, Any]:
    event_type = "equity_snapshot" if strategy is None else "shadow_equity_snapshot"
    curve = [
        item["payload"]
        for item in store.events(event_type)
        if strategy is None or item["payload"].get("strategy") == strategy
    ]
    fill_type = "fill" if strategy is None else "shadow_fill"
    fills = [
        item["payload"]
        for item in store.events(fill_type)
        if strategy is None or item["payload"].get("strategy") == strategy
    ]
    if not curve:
        return {"sample_size": 0, "warning": "insufficient observations"}
    equities = [float(item["equity"]) for item in curve]
    returns = [current / previous - 1 for previous, current in pairwise(equities) if previous]
    peak = equities[0]
    drawdown = 0.0
    for equity in equities:
        peak = max(peak, equity)
        drawdown = max(drawdown, (peak - equity) / peak if peak else 0.0)
    sharpe = sortino = None
    warning = None
    if len(returns) >= 30:
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
        deviation = variance**0.5
        sharpe = mean / deviation * (365 * 24) ** 0.5 if deviation else None
        downside = (sum(min(0.0, value) ** 2 for value in returns) / len(returns)) ** 0.5
        sortino = mean / downside * (365 * 24) ** 0.5 if downside else None
    else:
        warning = "Sharpe/Sortino suppressed below 30 returns"
    fees = sum(Decimal(str(fill.get("fee", 0))) for fill in fills)
    spread = sum(Decimal(str(fill.get("spread_cost", 0))) for fill in fills)
    slippage = sum(Decimal(str(fill.get("slippage_cost", 0))) for fill in fills)
    positions: dict[str, tuple[Decimal, Decimal, datetime]] = {}
    closed: list[tuple[Decimal, float]] = []
    for fill in fills:
        asset = str(fill["asset"])
        quantity = Decimal(str(fill["quantity"]))
        price = Decimal(str(fill["price"]))
        fee = Decimal(str(fill.get("fee", 0)))
        timestamp = datetime.fromisoformat(str(fill["timestamp"]))
        if fill["side"] == "buy":
            old_quantity, old_cost, opened = positions.get(
                asset, (Decimal("0"), Decimal("0"), timestamp)
            )
            positions[asset] = (
                old_quantity + quantity,
                old_cost + price * quantity + fee,
                opened,
            )
        elif asset in positions:
            old_quantity, old_cost, opened = positions[asset]
            sold = min(quantity, old_quantity)
            allocated_cost = old_cost * sold / old_quantity
            pnl = price * sold - fee - allocated_cost
            closed.append((pnl, (timestamp - opened).total_seconds()))
            remaining = old_quantity - sold
            if remaining:
                positions[asset] = (
                    remaining,
                    old_cost - allocated_cost,
                    opened,
                )
            else:
                positions.pop(asset)
    wins = [float(pnl) for pnl, _ in closed if pnl > 0]
    losses = [float(pnl) for pnl, _ in closed if pnl < 0]
    decisions = (
        store.events("decision")
        if strategy is None
        else [
            item
            for item in store.events("shadow_decision")
            if item["payload"].get("strategy") == strategy
        ]
    )
    return {
        "sample_size": len(curve),
        "equity": equities[-1],
        "return": equities[-1] / equities[0] - 1 if equities[0] else None,
        "realized_pnl": curve[-1].get("realized_pnl"),
        "unrealized_pnl": curve[-1].get("unrealized_pnl"),
        "max_drawdown": drawdown,
        "sharpe": sharpe,
        "sortino": sortino,
        "turnover": sum(
            float(fill.get("price", 0)) * float(fill.get("quantity", 0)) for fill in fills
        ),
        "trades": len(fills),
        "win_rate": len(wins) / len(closed) if closed else None,
        "profit_factor": sum(wins) / abs(sum(losses)) if losses else None,
        "fees": str(fees),
        "spread_cost": str(spread),
        "slippage": str(slippage),
        "average_holding_time": (
            sum(seconds for _, seconds in closed) / len(closed) if closed else None
        ),
        "exposure": float(curve[-1].get("positions_value", 0)) / equities[-1]
        if equities[-1]
        else 0.0,
        "warning": warning,
        "abstention_rate": (
            sum(
                item["payload"].get("decision", item["payload"].get("action")) == "abstain"
                for item in decisions
            )
            / len(decisions)
            if decisions
            else None
        ),
    }


def daily_snapshot(
    store: PaperStore, destination: str | Path, now: datetime | None = None
) -> tuple[Path, Path]:
    current = now or datetime.now(UTC)
    locked = store.get_state(ExperimentLock.KEY)
    if locked is None:
        raise ValueError("no forward experiment is started")
    experiment_id = str(locked["experiment_id"])
    day = current.date().isoformat()
    decisions = store.events("decision")
    today = [item for item in decisions if item["timestamp"].startswith(day)]
    state = store.get_state("paper") or {}
    health = store.get_state("paper_health") or {"state": ExperimentHealth.HEALTHY, "reasons": []}
    snapshot = {
        "forward_experiment": {
            "experiment_id": experiment_id,
            "started": locked["metadata"]["experiment_started_at"],
            "generated_at": current.isoformat(),
        },
        "market_data_health": health,
        "main_portfolio": {
            "cash": state.get("cash"),
            "positions": state.get("positions", {}),
            "equity": state.get("equity"),
            "realized_pnl": state.get("realized_pnl"),
            "fees": state.get("fees"),
        },
        "today": {
            "predictions": len(today),
            "buy": sum(x["payload"]["decision"] == "buy" for x in today),
            "exit": sum(x["payload"]["decision"] == "exit" for x in today),
            "abstain": sum(x["payload"]["decision"] == "abstain" for x in today),
            "orders": len(store.events("order")),
            "fills": len(store.events("fill")),
        },
        "predictive": predictive_metrics(store),
        "costs": {
            "fees": state.get("fees", "0"),
            "spread": sum(
                Decimal(str(x["payload"].get("spread_cost", 0))) for x in store.events("fill")
            ),
            "slippage": sum(
                Decimal(str(x["payload"].get("slippage_cost", 0))) for x in store.events("fill")
            ),
        },
        "risk": {
            "events": len(store.events("risk_decision")),
            "kill_switch": state.get("kill_switch"),
            "circuit_breaker": state.get("circuit_state"),
        },
        "drift": store.get_state("drift") or {"status": "insufficient_data"},
        "shadow_strategies": state.get("shadows", {}),
        "system": {
            "errors": state.get("errors", 0),
            "reconnects": state.get("reconnects", 0),
            "missing_candles": state.get("missing_candles", 0),
        },
    }
    snapshot["main_portfolio"]["metrics"] = economic_metrics(store)
    snapshot["shadow_strategies"] = {
        name: economic_metrics(store, name) for name in state.get("shadows", {})
    }
    root = Path(destination) / experiment_id
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / f"{day}.json"
    markdown_path = root / f"{day}.md"
    rendered = json.dumps(snapshot, indent=2, sort_keys=True, default=str)
    json_path.write_text(rendered + "\n", encoding="utf-8")
    markdown_path.write_text(
        "# FORWARD EXPERIMENT\n\n```json\n" + rendered + "\n```\n", encoding="utf-8"
    )
    return json_path, markdown_path


def export_experiment(
    store: PaperStore, destination: str | Path, artifact_paths: tuple[str, ...] = ()
) -> Path:
    locked = store.get_state(ExperimentLock.KEY)
    if locked is None:
        raise ValueError("no forward experiment is started")
    root = Path(destination)
    root.mkdir(parents=True, exist_ok=True)
    (root / "frozen_config.json").write_text(
        json.dumps(locked, indent=2, sort_keys=True), encoding="utf-8"
    )
    event_types = (
        "decision",
        "forward_prediction",
        "forward_outcome",
        "order",
        "fill",
        "equity_snapshot",
        "risk_decision",
        "drift",
    )
    for event_type in event_types:
        (root / f"{event_type}.json").write_text(
            json.dumps(store.events(event_type), indent=2, sort_keys=True), encoding="utf-8"
        )
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    for value in artifact_paths:
        source = Path(value)
        shutil.copy2(source, artifacts / source.name)
    daily_snapshot(store, root / "daily_reports")
    return root
