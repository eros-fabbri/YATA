from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from smarttrading.backtest.metrics import PerformanceMetrics, calculate_metrics
from smarttrading.data.manifest import DatasetManifest, build_manifest
from smarttrading.domain import Bar, Prediction, ProposedOrder, RiskDecisionStatus, Signal
from smarttrading.execution.simulator import ExecutionSimulator
from smarttrading.portfolio.accounting import EquityPoint, PortfolioAccount
from smarttrading.portfolio.sizing import FixedFractionSizer
from smarttrading.risk.manager import IndependentRiskManager, RiskContext


class BacktestStrategy(Protocol):
    name: str
    version: str

    def on_bar(self, history: Sequence[Bar], predictions: Sequence[Prediction] = ()) -> Signal: ...


class RunManifest(BaseModel):
    model_config = ConfigDict(frozen=True)
    run_id: str
    created_at: datetime
    dataset_sha256: str
    strategy_name: str
    strategy_version: str
    config_hash: str
    initial_capital: Decimal
    start: datetime
    end: datetime
    assets: tuple[str, ...]
    timeframe: str
    seed: int
    git_commit: str | None


class RiskSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    proposed: int
    approved: int
    resized: int
    rejected: int
    circuit_breaker_activations: int


class BacktestResult(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    manifest: RunManifest
    dataset: DatasetManifest
    curve: tuple[EquityPoint, ...]
    metrics: PerformanceMetrics
    risk: RiskSummary
    spread_cost: Decimal
    slippage_cost: Decimal
    result_hash: str

    def save(self, directory: str | Path) -> None:
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        (target / "result.json").write_text(self.model_dump_json(indent=2), encoding="utf-8")
        lines = ["timestamp,cash,positions_value,equity,realized_pnl,unrealized_pnl,fees"]
        lines.extend(
            ",".join(str(value) for value in point.model_dump().values()) for point in self.curve
        )
        (target / "equity.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


_PERIODS = {"5m": 365 * 24 * 12, "15m": 365 * 24 * 4, "1h": 365 * 24}


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


class BacktestEngine:
    def __init__(
        self,
        *,
        initial_cash: Decimal,
        strategy: BacktestStrategy,
        sizer: FixedFractionSizer,
        risk: IndependentRiskManager,
        execution: ExecutionSimulator,
        seed: int = 0,
    ) -> None:
        self.initial_cash = initial_cash
        self.strategy = strategy
        self.sizer = sizer
        self.risk = risk
        self.execution = execution
        self.seed = seed

    def run(self, bars: Sequence[Bar]) -> BacktestResult:
        ordered = sorted(bars, key=lambda bar: bar.timestamp)
        if list(bars) != ordered or not ordered:
            raise ValueError("bars must be non-empty and chronological")
        dataset = build_manifest(ordered)
        account = PortfolioAccount(self.initial_cash)
        curve: list[EquityPoint] = []
        peak = self.initial_cash
        spread_cost = Decimal("0")
        slippage_cost = Decimal("0")
        prices: dict[str, Decimal] = {}
        pending: ProposedOrder | None = None
        for index, bar in enumerate(ordered):
            prices[bar.asset] = bar.close
            if pending is not None:
                position = account.positions.get(bar.asset)
                quantity = Decimal("0") if position is None else position.quantity
                marked = account.mark(bar.timestamp, prices)
                peak = max(peak, marked.equity)
                exposure = marked.positions_value
                context = RiskContext(
                    timestamp=bar.timestamp,
                    price=bar.open,
                    cash=account.cash,
                    equity=marked.equity,
                    asset_value=quantity * bar.close,
                    portfolio_exposure=exposure,
                    position_quantity=quantity,
                    drawdown=float((peak - marked.equity) / peak),
                    estimated_cost_rate=(
                        (self.execution.costs.spread_bps / 2 + self.execution.costs.slippage_bps)
                        / Decimal("10000")
                        + self.execution.costs.taker_fee_bps / Decimal("10000")
                    ),
                )
                decision = self.risk.evaluate(pending, context)
                if decision.approved and decision.approved_quantity is not None:
                    executable = ProposedOrder(
                        **{
                            **pending.model_dump(),
                            "quantity": decision.approved_quantity,
                        }
                    )
                    fill = self.execution.execute(executable, bar)
                    if fill is not None:
                        account.apply_fill(fill)
                        spread_cost += fill.spread_cost
                        slippage_cost += fill.slippage_cost
            history = tuple(ordered[: index + 1])  # Structural no-look-ahead boundary.
            signal = self.strategy.on_bar(history, ())
            pending = self.sizer.size(signal, account, bar.close, bar.timestamp)
            curve.append(account.mark(bar.timestamp, prices))
        metrics = calculate_metrics(curve, account, _PERIODS[ordered[0].timeframe])
        config_payload = {
            "initial_cash": str(self.initial_cash),
            "sizer_fraction": str(self.sizer.fraction),
            "costs": {key: str(value) for key, value in vars(self.execution.costs).items()},
            "seed": self.seed,
        }
        config_hash = hashlib.sha256(
            json.dumps(config_payload, sort_keys=True).encode()
        ).hexdigest()
        economics = {
            "dataset": dataset.sha256,
            "strategy": self.strategy.name,
            "config": config_hash,
            "curve": [point.model_dump(mode="json") for point in curve],
        }
        result_hash = hashlib.sha256(
            json.dumps(economics, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        run_id = result_hash[:16]
        decisions = self.risk.decisions
        manifest = RunManifest(
            run_id=run_id,
            created_at=datetime.now(UTC),
            dataset_sha256=dataset.sha256,
            strategy_name=self.strategy.name,
            strategy_version=self.strategy.version,
            config_hash=config_hash,
            initial_capital=self.initial_cash,
            start=ordered[0].timestamp,
            end=ordered[-1].timestamp,
            assets=tuple(sorted({bar.asset for bar in ordered})),
            timeframe=ordered[0].timeframe,
            seed=self.seed,
            git_commit=_git_commit(),
        )
        return BacktestResult(
            manifest=manifest,
            dataset=dataset,
            curve=tuple(curve),
            metrics=metrics,
            risk=RiskSummary(
                proposed=len(decisions),
                approved=sum(item.status is RiskDecisionStatus.APPROVED for item in decisions),
                resized=sum(item.status is RiskDecisionStatus.RESIZED for item in decisions),
                rejected=sum(item.status is RiskDecisionStatus.REJECTED for item in decisions),
                circuit_breaker_activations=self.risk.circuit_breaker_activations,
            ),
            spread_cost=spread_cost,
            slippage_cost=slippage_cost,
            result_hash=result_hash,
        )


def cost_stress(
    factory: Callable[[int], BacktestEngine], bars: Sequence[Bar]
) -> dict[int, BacktestResult]:
    return {multiplier: factory(multiplier).run(bars) for multiplier in (1, 2, 3)}
