from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from smarttrading.config.settings import AppSettings
from smarttrading.data.realtime import TIMEFRAME_DELTA, CandleEvent, ClosedCandleBuffer
from smarttrading.domain import (
    Bar,
    DecisionAction,
    OrderType,
    ProposedOrder,
    Side,
    SignalDirection,
)
from smarttrading.execution.simulator import CostModel, ExecutionSimulator
from smarttrading.features.pipeline import CausalFeaturePipeline
from smarttrading.features.regime import RegimeDetector
from smarttrading.models.artifacts import ModelArtifact
from smarttrading.models.ensemble import WeightedEnsemble
from smarttrading.paper.forward import (
    ExperimentHealth,
    ExperimentLock,
    FrozenExperimentConfig,
    daily_snapshot,
    health_from_signals,
    mature_predictions,
    prediction_id,
    reconcile_accounting,
)
from smarttrading.paper.journal import DecisionRecord
from smarttrading.paper.persistence import PaperStore
from smarttrading.portfolio.accounting import PortfolioAccount, Position
from smarttrading.risk.manager import CircuitState, IndependentRiskManager, RiskContext
from smarttrading.strategies.baselines import (
    BuyAndHoldStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MovingAverageCrossoverStrategy,
)


class ShadowPortfolio:
    def __init__(self, names: tuple[str, ...], initial_cash: Decimal) -> None:
        self.accounts = {name: PortfolioAccount(initial_cash) for name in names}


class PaperTradingEngine:
    def __init__(
        self,
        settings: AppSettings,
        store: PaperStore,
        artifacts: tuple[ModelArtifact, ...],
        ensemble: WeightedEnsemble,
        *,
        shadow_names: tuple[str, ...] = (),
        experiment: FrozenExperimentConfig | None = None,
        report_root: str = "reports/forward",
    ) -> None:
        self.settings = settings
        self.store = store
        self.artifacts = artifacts
        self.ensemble = ensemble
        self.features = CausalFeaturePipeline()
        for artifact in artifacts:
            if artifact.feature_version != self.features.config.version:
                raise ValueError("feature version mismatch at paper startup")
        self.regime = RegimeDetector()
        self.buffer = ClosedCandleBuffer()
        self.histories: dict[str, list[Bar]] = {}
        self.account = PortfolioAccount(settings.initial_cash)
        self.risk = IndependentRiskManager(settings.risk)
        self.execution = ExecutionSimulator(
            CostModel(
                Decimal(str(settings.execution.maker_fee_bps)),
                Decimal(str(settings.execution.taker_fee_bps)),
                Decimal(str(settings.execution.spread_bps)),
                Decimal(str(settings.execution.slippage_bps)),
            )
        )
        self.pending: dict[str, ProposedOrder] = {}
        self.shadows = ShadowPortfolio(shadow_names, settings.initial_cash)
        self.shadow_strategies = {
            name: strategy
            for name in shadow_names
            for prefix, strategy in (
                ("momentum-", MomentumStrategy()),
                ("moving-average-", MovingAverageCrossoverStrategy()),
                ("mean-reversion-", MeanReversionStrategy()),
                ("buy-and-hold-", BuyAndHoldStrategy()),
            )
            if name.startswith(prefix)
        }
        self.shadow_pending: dict[str, ProposedOrder] = {}
        self.experiment = experiment
        self.report_root = report_root
        self.experiment_metadata = (
            ExperimentLock.start_or_resume(store, experiment) if experiment is not None else None
        )
        self.started_at = (
            self.experiment_metadata.experiment_started_at
            if self.experiment_metadata is not None
            else datetime.now(UTC)
        )
        self.health = ExperimentHealth.HEALTHY
        self.health_reasons: tuple[str, ...] = ()
        self.reconnects = 0
        self.stale_events = 0
        self.errors = 0
        self._restore()

    def _restore(self) -> None:
        for stored in self.store.events("closed_bar"):
            bar = Bar.model_validate(stored["payload"])
            self.histories.setdefault(bar.asset, []).append(bar)
            self.buffer.accept(
                CandleEvent(
                    event_id=f"restored:{bar.asset}:{bar.timeframe}:{bar.timestamp.isoformat()}",
                    bar=bar,
                    closed=True,
                    received_at=bar.timestamp,
                )
            )
        state = self.store.get_state("paper")
        if state is None:
            return
        self.account.cash = Decimal(state["cash"])
        self.account.realized_pnl = Decimal(state["realized_pnl"])
        self.account.total_fees = Decimal(state["fees"])
        self.account.turnover = Decimal(state["turnover"])
        self.account.positions = {
            asset: Position(
                quantity=Decimal(value["quantity"]),
                average_entry_price=Decimal(value["average_entry_price"]),
                opened_at=(
                    datetime.fromisoformat(value["opened_at"]) if value["opened_at"] else None
                ),
            )
            for asset, value in state["positions"].items()
        }
        self.risk.kill_switch = bool(state["kill_switch"])
        self.risk.circuit_state = CircuitState(state["circuit_state"])
        self.pending = {
            asset: ProposedOrder.model_validate(value) for asset, value in state["pending"].items()
        }
        for name, value in state.get("shadows", {}).items():
            if name in self.shadows.accounts:
                account = self.shadows.accounts[name]
                account.cash = Decimal(value["cash"])
                account.realized_pnl = Decimal(value.get("realized_pnl", "0"))
                account.total_fees = Decimal(value.get("fees", "0"))
                account.turnover = Decimal(value.get("turnover", "0"))
                account.positions = {
                    asset: Position(
                        quantity=Decimal(position["quantity"]),
                        average_entry_price=Decimal(position["average_entry_price"]),
                        opened_at=(
                            datetime.fromisoformat(position["opened_at"])
                            if position.get("opened_at")
                            else None
                        ),
                    )
                    for asset, position in value.get("positions", {}).items()
                }
        self.shadow_pending = {
            name: ProposedOrder.model_validate(value)
            for name, value in state.get("shadow_pending", {}).items()
        }

    def _persist_state(self) -> None:
        self.store.set_state(
            "paper",
            {
                "cash": str(self.account.cash),
                "realized_pnl": str(self.account.realized_pnl),
                "fees": str(self.account.total_fees),
                "turnover": str(self.account.turnover),
                "positions": {
                    asset: {
                        "quantity": str(position.quantity),
                        "average_entry_price": str(position.average_entry_price),
                        "opened_at": position.opened_at.isoformat() if position.opened_at else None,
                    }
                    for asset, position in self.account.positions.items()
                },
                "kill_switch": self.risk.kill_switch,
                "circuit_state": self.risk.circuit_state,
                "pending": {
                    asset: order.model_dump(mode="json") for asset, order in self.pending.items()
                },
                "shadows": {
                    name: {
                        "cash": str(account.cash),
                        "realized_pnl": str(account.realized_pnl),
                        "fees": str(account.total_fees),
                        "turnover": str(account.turnover),
                        "positions": {
                            asset: {
                                "quantity": str(position.quantity),
                                "average_entry_price": str(position.average_entry_price),
                                "opened_at": (
                                    position.opened_at.isoformat() if position.opened_at else None
                                ),
                            }
                            for asset, position in account.positions.items()
                        },
                    }
                    for name, account in self.shadows.accounts.items()
                },
                "shadow_pending": {
                    name: order.model_dump(mode="json")
                    for name, order in self.shadow_pending.items()
                },
                "equity": self._latest_equity(),
                "health": self.health,
                "health_reasons": self.health_reasons,
                "reconnects": self.reconnects,
                "errors": self.errors,
            },
        )

    def _latest_equity(self) -> str:
        prices = {asset: bars[-1].close for asset, bars in self.histories.items() if bars}
        return str(self.account.mark(datetime.now(UTC), prices).equity)

    def _reconcile(self) -> None:
        state = {
            "cash": str(self.account.cash),
            "positions": {
                asset: {
                    "quantity": str(position.quantity),
                    "average_entry_price": str(position.average_entry_price),
                }
                for asset, position in self.account.positions.items()
            },
            "equity": self._latest_equity(),
        }
        prices = {asset: bars[-1].close for asset, bars in self.histories.items() if bars}
        accounting_health, accounting_reasons = reconcile_accounting(state, prices)
        if accounting_health is ExperimentHealth.UNSAFE:
            self.health = accounting_health
            self.health_reasons = tuple((*self.health_reasons, *accounting_reasons))
        self.store.set_state("paper_health", {"state": self.health, "reasons": self.health_reasons})

    def _execute_shadow_pending(self, bar: Bar) -> None:
        for name, order in list(self.shadow_pending.items()):
            if order.asset != bar.asset:
                continue
            account = self.shadows.accounts[name]
            fill = self.execution.execute(order, bar)
            if fill is not None:
                try:
                    account.apply_fill(fill)
                    self.store.append(
                        f"shadow-fill:{name}:{order.client_order_id}",
                        "shadow_fill",
                        bar.timestamp.isoformat(),
                        {"strategy": name, **fill.model_dump(mode="json")},
                    )
                except ValueError:
                    pass
            self.shadow_pending.pop(name, None)

    def warmup(self, bars: list[Bar]) -> None:
        """Load closed pre-start context without creating forward predictions or decisions."""
        for bar in bars:
            event = CandleEvent(
                event_id=f"warmup:{bar.asset}:{bar.timeframe}:{bar.timestamp.isoformat()}",
                bar=bar,
                closed=True,
                received_at=datetime.now(UTC),
            )
            if not self.buffer.accept(event):
                continue
            self.histories.setdefault(bar.asset, []).append(bar)
            self.store.append(
                f"bar:{bar.asset}:{bar.timeframe}:{bar.timestamp.isoformat()}",
                "closed_bar",
                bar.timestamp.isoformat(),
                bar.model_dump(mode="json"),
            )

    def _execute_pending(self, bar: Bar) -> tuple[str | None, dict[str, Any] | None]:
        order = self.pending.pop(bar.asset, None)
        if order is None:
            return None, None
        position = self.account.positions.get(bar.asset, Position())
        point = self.account.mark(bar.timestamp, {bar.asset: bar.open})
        context = RiskContext(
            timestamp=bar.timestamp,
            price=bar.open,
            cash=self.account.cash,
            equity=point.equity,
            asset_value=position.quantity * bar.open,
            portfolio_exposure=point.positions_value,
            position_quantity=position.quantity,
        )
        risk = self.risk.evaluate(order, context)
        self.store.append(
            f"risk:{risk.decision_id}",
            "risk_decision",
            bar.timestamp.isoformat(),
            risk.model_dump(mode="json"),
        )
        if not risk.approved or risk.approved_quantity is None:
            return None, {"status": risk.status, "reasons": ",".join(risk.reasons)}
        fill = self.execution.execute(order, bar, risk.approved_quantity)
        if fill is None:
            return None, {"status": risk.status, "reasons": "no_fill"}
        if not self.store.append(
            f"fill:{fill.fill_id}:{order.client_order_id}",
            "fill",
            bar.timestamp.isoformat(),
            fill.model_dump(mode="json"),
        ):
            return None, {"status": "duplicate_fill"}
        self.account.apply_fill(fill)
        return fill.fill_id, {"status": risk.status, "reasons": ",".join(risk.reasons)}

    def process(self, event: CandleEvent) -> DecisionRecord | None:
        self.store.append(
            f"raw:{event.event_id}",
            "raw_market_event",
            event.received_at.isoformat(),
            event.model_dump(mode="json"),
        )
        if not self.buffer.accept(event):
            return None
        bar = event.bar
        stale_seconds = max(
            0,
            int(
                (
                    event.received_at - (bar.timestamp + TIMEFRAME_DELTA[bar.timeframe])
                ).total_seconds()
            ),
        )
        self.health, self.health_reasons = health_from_signals(
            reconnects=self.reconnects,
            stale_seconds=stale_seconds,
            stale_limit=self.settings.risk.stale_data_seconds,
        )
        if self.buffer.missing and self.health is ExperimentHealth.HEALTHY:
            self.health = ExperimentHealth.DEGRADED
            self.health_reasons = ("recoverable_market_data_gap",)
        decision_id = hashlib.sha256(
            f"{bar.asset}|{bar.timeframe}|{bar.timestamp.isoformat()}".encode()
        ).hexdigest()[:24]
        if self.store.exists(f"decision:{decision_id}"):
            return None
        self.store.append(
            f"bar:{bar.asset}:{bar.timeframe}:{bar.timestamp.isoformat()}",
            "closed_bar",
            bar.timestamp.isoformat(),
            bar.model_dump(mode="json"),
        )
        fill_id, prior_risk = self._execute_pending(bar)
        self._execute_shadow_pending(bar)
        history = self.histories.setdefault(bar.asset, [])
        history.append(bar)
        feature_sets = self.features.transform(history)
        regime_payload: dict[str, str | float] = {"status": "warmup"}
        feature_values: dict[str, float] = {}
        probabilities: dict[str, float] = {}
        if feature_sets and feature_sets[-1].timestamp == bar.timestamp:
            feature = feature_sets[-1]
            feature_values = feature.values
            self.store.append(
                f"features:{decision_id}",
                "feature_snapshot",
                bar.timestamp.isoformat(),
                feature.model_dump(mode="json"),
            )
            for artifact in self.artifacts:
                if artifact.asset is not None and artifact.asset != bar.asset:
                    continue
                probabilities[artifact.model_name] = artifact.predict_probability(feature.values)
        if len(history) >= self.regime.window + 1:
            detected = self.regime.detect(history)
            regime_payload = detected.model_dump(mode="json")
            self.store.append(
                f"regime:{decision_id}",
                "regime",
                bar.timestamp.isoformat(),
                detected.model_dump(mode="json"),
            )
        if probabilities:
            ensemble = self.ensemble.combine(bar.timestamp, bar.asset, probabilities)
            action = ensemble.action
            edge = (ensemble.probability_up - 0.5) * 0.02
            ensemble_payload: dict[str, Any] = ensemble.model_dump(mode="json")
            self.store.append(
                f"ensemble:{decision_id}",
                "ensemble_prediction",
                bar.timestamp.isoformat(),
                ensemble_payload,
            )
            if self.experiment_metadata is not None:
                pid = prediction_id(
                    self.experiment_metadata.experiment_id, bar.asset, bar.timestamp
                )
                self.store.append(
                    f"prediction:{pid}",
                    "forward_prediction",
                    bar.timestamp.isoformat(),
                    {
                        "prediction_id": pid,
                        "experiment_id": self.experiment_metadata.experiment_id,
                        "prediction_timestamp": bar.timestamp.isoformat(),
                        "asset": bar.asset,
                        "probability_up": ensemble.probability_up,
                        "confidence": ensemble.confidence,
                        "disagreement": ensemble.disagreement,
                        "model_probabilities": probabilities,
                    },
                )
        else:
            action = DecisionAction.ABSTAIN
            edge = 0.0
            ensemble_payload = {"action": "abstain", "reason": "warmup_or_no_model"}
        estimated_cost = float(
            (
                self.execution.costs.taker_fee_bps * 2
                + self.execution.costs.spread_bps
                + self.execution.costs.slippage_bps * 2
            )
            / Decimal("10000")
        )
        if action is DecisionAction.BUY and edge <= estimated_cost:
            action = DecisionAction.ABSTAIN
            ensemble_payload["cost_aware_override"] = "edge_not_above_round_trip_cost"
        target_weight = (
            self.settings.risk.max_asset_allocation if action is DecisionAction.BUY else 0.0
        )
        proposed: ProposedOrder | None = None
        if action is DecisionAction.BUY and self.health is ExperimentHealth.UNSAFE:
            action = DecisionAction.ABSTAIN
            ensemble_payload["health_override"] = "unsafe_blocks_new_exposure"
        if action is DecisionAction.BUY:
            quantity = self.account.cash * Decimal(str(target_weight)) / bar.close
            if quantity > 0:
                proposed = ProposedOrder(
                    client_order_id=uuid5(NAMESPACE_URL, f"{decision_id}:buy"),
                    created_at=bar.timestamp,
                    asset=bar.asset,
                    side=Side.BUY,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                )
        elif action is DecisionAction.EXIT:
            position = self.account.positions.get(bar.asset, Position())
            if position.quantity > 0:
                proposed = ProposedOrder(
                    client_order_id=uuid5(NAMESPACE_URL, f"{decision_id}:sell"),
                    created_at=bar.timestamp,
                    asset=bar.asset,
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=position.quantity,
                )
        if proposed is not None:
            self.pending[bar.asset] = proposed
            self.store.append(
                f"order:{proposed.client_order_id}",
                "order",
                bar.timestamp.isoformat(),
                proposed.model_dump(mode="json"),
            )
        for shadow_name in self.shadows.accounts:
            asset_slug = bar.asset.split("/")[0].lower()
            if shadow_name.endswith(("-btc", "-eth")) and not shadow_name.endswith(
                f"-{asset_slug}"
            ):
                continue
            shadow_probability = probabilities.get(shadow_name.removesuffix("-shadow"))
            baseline = self.shadow_strategies.get(shadow_name)
            if baseline is not None:
                signal = baseline.on_bar(history)
                shadow_action = "buy" if signal.direction is SignalDirection.LONG else "exit"
            else:
                shadow_action = (
                    "buy"
                    if shadow_probability is not None and shadow_probability >= 0.6
                    else "exit"
                    if shadow_probability is not None and shadow_probability <= 0.45
                    else "abstain"
                )
            shadow_account = self.shadows.accounts[shadow_name]
            shadow_position = shadow_account.positions.get(bar.asset, Position())
            if shadow_action == "buy" and shadow_position.quantity == 0:
                quantity = shadow_account.cash * Decimal("0.25") / bar.close
                self.shadow_pending[shadow_name] = ProposedOrder(
                    client_order_id=uuid5(NAMESPACE_URL, f"{decision_id}:{shadow_name}:buy"),
                    created_at=bar.timestamp,
                    asset=bar.asset,
                    side=Side.BUY,
                    order_type=OrderType.MARKET,
                    quantity=quantity,
                )
            elif shadow_action == "exit" and shadow_position.quantity > 0:
                self.shadow_pending[shadow_name] = ProposedOrder(
                    client_order_id=uuid5(NAMESPACE_URL, f"{decision_id}:{shadow_name}:sell"),
                    created_at=bar.timestamp,
                    asset=bar.asset,
                    side=Side.SELL,
                    order_type=OrderType.MARKET,
                    quantity=shadow_position.quantity,
                )
            self.store.append(
                f"shadow:{shadow_name}:{decision_id}",
                "shadow_decision",
                bar.timestamp.isoformat(),
                {
                    "strategy": shadow_name,
                    "action": shadow_action,
                    "probability": shadow_probability,
                    "cash": str(self.shadows.accounts[shadow_name].cash),
                    "isolated_from_main": True,
                },
            )
            shadow_point = shadow_account.mark(bar.timestamp, {bar.asset: bar.close})
            self.store.append(
                f"shadow-equity:{shadow_name}:{decision_id}",
                "shadow_equity_snapshot",
                bar.timestamp.isoformat(),
                {"strategy": shadow_name, **shadow_point.model_dump(mode="json")},
            )
        record = DecisionRecord(
            decision_id=decision_id,
            timestamp=bar.timestamp,
            asset=bar.asset,
            market_regime=regime_payload,
            important_features=dict(list(feature_values.items())[:8]),
            model_predictions=probabilities,
            ensemble_prediction=ensemble_payload,
            estimated_transaction_cost=estimated_cost,
            estimated_edge=edge,
            decision=action,
            target_weight=target_weight,
            proposed_quantity=proposed.quantity if proposed else None,
            risk_decision=prior_risk,
            order_id=str(proposed.client_order_id) if proposed else None,
            fill_id=fill_id,
        )
        self.store.append(
            f"decision:{decision_id}",
            "decision",
            bar.timestamp.isoformat(),
            record.model_dump(mode="json"),
        )
        point = self.account.mark(bar.timestamp, {bar.asset: bar.close})
        self.store.append(
            f"equity:{decision_id}",
            "equity_snapshot",
            bar.timestamp.isoformat(),
            point.model_dump(mode="json"),
        )
        self._reconcile()
        self._persist_state()
        if self.experiment_metadata is not None:
            if self.experiment is None:
                raise AssertionError("experiment metadata requires frozen config")
            mature_predictions(
                self.store,
                experiment_id=self.experiment_metadata.experiment_id,
                horizon_bars=int(self.experiment.target["prediction_horizon"]),
                return_threshold=float(self.experiment.target["return_threshold"]),
                round_trip_cost=estimated_cost,
            )
            daily_snapshot(self.store, self.report_root, bar.timestamp)
        return record

    def status(self) -> dict[str, Any]:
        state = self.store.get_state("paper") or {}
        decisions = self.store.events("decision")
        fills = self.store.events("fill")
        risk_decisions = self.store.events("risk_decision")
        equities = self.store.events("equity_snapshot")
        regimes = self.store.events("regime")
        ensemble_predictions = self.store.events("ensemble_prediction")
        abstentions = sum(item["payload"]["decision"] == "abstain" for item in decisions)
        confidences = [
            float(item["payload"]["ensemble_prediction"].get("confidence", 0)) for item in decisions
        ]
        edges = [float(item["payload"]["estimated_edge"]) for item in decisions]
        last_equity = equities[-1]["payload"] if equities else {}
        return {
            "uptime_seconds": (datetime.now(UTC) - self.started_at).total_seconds(),
            "feed_status": "running",
            "cash": str(self.account.cash),
            "positions": state.get("positions", {}),
            "equity": last_equity.get("equity"),
            "total_pnl": (
                str(Decimal(last_equity["equity"]) - self.settings.initial_cash)
                if last_equity.get("equity") is not None
                else None
            ),
            "current_regime": regimes[-1]["payload"] if regimes else None,
            "current_prediction": (
                ensemble_predictions[-1]["payload"] if ensemble_predictions else None
            ),
            "circuit_breaker": self.risk.circuit_state,
            "kill_switch": self.risk.kill_switch,
            "decisions": len(decisions),
            "fills": len(fills),
            "risk_rejected": sum(
                item["payload"]["status"] == "rejected" for item in risk_decisions
            ),
            "risk_resized": sum(item["payload"]["status"] == "resized" for item in risk_decisions),
            "abstention_rate": abstentions / len(decisions) if decisions else None,
            "average_confidence": sum(confidences) / len(confidences) if confidences else None,
            "average_estimated_edge": sum(edges) / len(edges) if edges else None,
            "shadow_decisions": len(self.store.events("shadow_decision")),
            "shadow_portfolios": {
                name: {
                    "cash": str(account.cash),
                    "positions": {
                        asset: str(position.quantity)
                        for asset, position in account.positions.items()
                    },
                }
                for name, account in self.shadows.accounts.items()
            },
            "reconnects": self.reconnects,
            "stale_feed_events": self.stale_events,
            "errors": self.errors,
            "health": self.health,
            "health_reasons": self.health_reasons,
            "experiment_id": (
                self.experiment_metadata.experiment_id
                if self.experiment_metadata is not None
                else None
            ),
        }
