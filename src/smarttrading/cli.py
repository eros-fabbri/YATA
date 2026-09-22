from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import signal
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from smarttrading.backtest.engine import BacktestEngine, BacktestResult, BacktestStrategy
from smarttrading.config import load_settings
from smarttrading.data.csv import load_bars_csv
from smarttrading.data.manifest import build_manifest
from smarttrading.data.realtime import TIMEFRAME_DELTA, CandleEvent
from smarttrading.exchanges.binance_public import BinancePublicData
from smarttrading.exchanges.binance_stream import BinanceClosedCandleProvider, ResilientCandleStream
from smarttrading.execution.simulator import CostModel, ExecutionSimulator
from smarttrading.features.dataset import MLDatasetBuilder
from smarttrading.features.pipeline import CausalFeaturePipeline
from smarttrading.features.target import TargetConfig
from smarttrading.models.artifacts import ModelArtifact, ModelRegistry
from smarttrading.models.ensemble import EnsembleConfig, WeightedEnsemble
from smarttrading.models.experiment import render_experiment, run_experiment, run_final_evaluation
from smarttrading.models.freeze import freeze_real_artifact
from smarttrading.paper.engine import PaperTradingEngine
from smarttrading.paper.forward import (
    ExperimentLock,
    FrozenExperimentConfig,
    daily_snapshot,
    export_experiment,
    mature_predictions,
    predictive_metrics,
)
from smarttrading.paper.journal import DecisionRecord, explain
from smarttrading.paper.persistence import PaperStore
from smarttrading.portfolio.sizing import FixedFractionSizer
from smarttrading.risk.manager import IndependentRiskManager
from smarttrading.strategies.baselines import (
    BuyAndHoldStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MovingAverageCrossoverStrategy,
)


def _strategy(name: str) -> BacktestStrategy:
    strategies: dict[str, BacktestStrategy] = {
        "buy_hold": BuyAndHoldStrategy(),
        "moving_average": MovingAverageCrossoverStrategy(),
        "momentum": MomentumStrategy(),
        "mean_reversion": MeanReversionStrategy(),
    }
    return strategies[name]


def _render_backtest(result: BacktestResult, benchmark: BacktestResult | None = None) -> str:
    metrics = result.metrics
    lines = [
        f"Strategy: {result.manifest.strategy_name}",
        f"Dataset: {result.dataset.dataset_id}",
        f"Period: {result.manifest.start.isoformat()} → {result.manifest.end.isoformat()}",
        f"Initial equity: {result.manifest.initial_capital}",
        f"Final equity: {result.curve[-1].equity}",
        f"Return: {metrics.total_return:.4%}",
    ]
    if benchmark is not None:
        lines.append(f"Buy & Hold: {benchmark.metrics.total_return:.4%}")
    lines.extend(
        [
            f"Sharpe: {metrics.sharpe}",
            f"Sortino: {metrics.sortino}",
            f"Max DD: {metrics.maximum_drawdown:.4%}",
            f"Trades: {metrics.number_of_trades}",
            f"Turnover: {metrics.turnover:.6f}",
            f"Fees: {metrics.total_fees}",
            f"Estimated spread cost: {result.spread_cost}",
            f"Estimated slippage: {result.slippage_cost}",
            f"Result hash: {result.result_hash}",
        ]
    )
    return "\n".join(lines)


def _add_ml_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--config", default="config/default.yaml")
    parser.add_argument(
        "--model", choices=["dummy", "logistic", "gradient_boosting"], default="logistic"
    )
    parser.add_argument("--horizon", type=int, default=6)
    parser.add_argument("--return-threshold", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--minimum-train-size", type=int, default=100)
    parser.add_argument("--validation-size", type=int, default=30)
    parser.add_argument("--step-size", type=int, default=30)
    parser.add_argument("--embargo", type=int, default=1)
    parser.add_argument("--max-folds", type=int, default=5)


def _backtest(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    bars = load_bars_csv(args.dataset)

    def run(name: str, multiplier: int = 1) -> BacktestResult:
        costs = CostModel(
            Decimal(str(settings.execution.maker_fee_bps)) * multiplier,
            Decimal(str(settings.execution.taker_fee_bps)) * multiplier,
            Decimal(str(settings.execution.spread_bps)) * multiplier,
            Decimal(str(settings.execution.slippage_bps)) * multiplier,
        )
        return BacktestEngine(
            initial_cash=settings.initial_cash,
            strategy=_strategy(name),
            sizer=FixedFractionSizer(Decimal(str(settings.risk.max_asset_allocation))),
            risk=IndependentRiskManager(settings.risk),
            execution=ExecutionSimulator(costs),
        ).run(bars)

    result = run(args.strategy)
    benchmark = run("buy_hold") if args.strategy != "buy_hold" else None
    print(_render_backtest(result, benchmark))
    if args.cost_stress:
        print("Cost stress:")
        for multiplier in (1, 2, 3):
            stressed = run(args.strategy, multiplier)
            total = stressed.metrics.total_fees + stressed.spread_cost + stressed.slippage_cost
            print(f"  {multiplier}x return={stressed.metrics.total_return:.4%} costs={total}")
    result.save(args.output)


def _features(args: argparse.Namespace) -> None:
    bars = load_bars_csv(args.dataset)
    dataset = MLDatasetBuilder(
        CausalFeaturePipeline(),
        TargetConfig(prediction_horizon=args.horizon, return_threshold=args.return_threshold),
    ).build(bars)
    dataset.export(args.output)
    print(dataset.metadata.model_dump_json(indent=2))


def _ml(args: argparse.Namespace) -> None:
    bars = load_bars_csv(args.dataset)
    settings = load_settings(args.config)
    dataset = MLDatasetBuilder(
        CausalFeaturePipeline(),
        TargetConfig(prediction_horizon=args.horizon, return_threshold=args.return_threshold),
    ).build(bars)
    common = {"model_name": args.model, "seed": args.seed, "embargo": args.embargo}
    if args.ml_command == "final-evaluate":
        result = run_final_evaluation(dataset, bars, settings, **common)
    else:
        result = run_experiment(
            dataset,
            bars,
            settings,
            minimum_train_size=args.minimum_train_size,
            validation_size=args.validation_size,
            step_size=args.step_size,
            max_folds=args.max_folds,
            **common,
        )
    print(render_experiment(result))


def _prepare_data(args: argparse.Namespace) -> None:
    start = datetime.fromisoformat(args.start.replace("Z", "+00:00")).astimezone(UTC)
    end = datetime.fromisoformat(args.end.replace("Z", "+00:00")).astimezone(UTC)
    bars = BinancePublicData().fetch_bars(args.asset, args.timeframe, start, end)
    if not bars:
        raise RuntimeError("public source returned no bars")
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["timestamp", "asset", "timeframe", "open", "high", "low", "close", "volume"]
        )
        writer.writerows(
            [
                bar.timestamp.isoformat(),
                bar.asset,
                bar.timeframe,
                bar.open,
                bar.high,
                bar.low,
                bar.close,
                bar.volume,
            ]
            for bar in bars
        )
    manifest = build_manifest(bars)
    target.with_suffix(".manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    print(manifest.model_dump_json(indent=2))


def _paper_smoke(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    raw = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    artifact = ModelArtifact.load(args.artifact, raw["feature_version"])
    now = datetime.now(UTC)
    bars = BinancePublicData().fetch_bars(
        args.asset, args.timeframe, now - timedelta(hours=args.lookback_hours), now
    )
    closed = [bar for bar in bars if bar.timestamp + TIMEFRAME_DELTA[bar.timeframe] <= now]
    store = PaperStore(args.database)
    engine = PaperTradingEngine(
        settings,
        store,
        (artifact,),
        WeightedEnsemble(EnsembleConfig(weights={artifact.model_name: 1.0})),
        shadow_names=(
            f"{artifact.model_name}-shadow",
            "momentum-shadow",
            "mean-reversion-shadow",
        ),
    )
    last: DecisionRecord | None = None
    for bar in closed:
        record = engine.process(
            CandleEvent(
                event_id=f"smoke:{bar.asset}:{bar.timeframe}:{bar.timestamp.isoformat()}",
                bar=bar,
                closed=True,
                received_at=now,
            )
        )
        if record is not None:
            last = record
    print(json.dumps(engine.status(), indent=2, default=str))
    if last is not None:
        print(explain(last))
    store.close()


async def _paper_run_async(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    artifact_paths = tuple(args.artifact)
    artifacts = tuple(
        ModelArtifact.load(path, json.loads(Path(path).read_text())["feature_version"])
        for path in artifact_paths
    )
    experiment = (
        FrozenExperimentConfig.model_validate_json(
            Path(args.experiment_config).read_text(encoding="utf-8")
        )
        if args.experiment_config
        else None
    )
    store = PaperStore(args.database)
    engine = PaperTradingEngine(
        settings,
        store,
        artifacts,
        WeightedEnsemble(
            EnsembleConfig(
                weights=(
                    experiment.ensemble_weights
                    if experiment is not None
                    else {artifact.model_name: 1.0 for artifact in artifacts}
                ),
                **(experiment.thresholds if experiment is not None else {}),
            )
        ),
        shadow_names=(
            experiment.shadow_strategies
            if experiment is not None
            else tuple(f"{artifact.model_name}-shadow" for artifact in artifacts)
        ),
        experiment=experiment,
    )
    provider = BinanceClosedCandleProvider(tuple(args.assets), args.timeframe)

    async def reconcile() -> list[CandleEvent]:
        now = datetime.now(UTC)
        events: list[CandleEvent] = []
        for asset in args.assets:
            bars = await asyncio.to_thread(
                BinancePublicData().fetch_bars,
                asset,
                args.timeframe,
                now - TIMEFRAME_DELTA[args.timeframe] * 3,
                now,
            )
            events.extend(
                CandleEvent(
                    event_id=f"reconcile:{bar.asset}:{bar.timeframe}:{bar.timestamp.isoformat()}",
                    bar=bar,
                    closed=True,
                    received_at=now,
                )
                for bar in bars
                if bar.timestamp + TIMEFRAME_DELTA[bar.timeframe] <= now
            )
        return sorted(events, key=lambda event: event.bar.timestamp)

    stream = ResilientCandleStream(provider.connect, reconcile)
    processed = 0
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    if task is not None and hasattr(loop, "add_signal_handler"):
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
    try:
        if not store.events("closed_bar"):
            now = datetime.now(UTC)
            warmup_bars = []
            for asset in args.assets:
                warmup_bars.extend(
                    await asyncio.to_thread(
                        BinancePublicData().fetch_bars,
                        asset,
                        args.timeframe,
                        now - TIMEFRAME_DELTA[args.timeframe] * 72,
                        now,
                    )
                )
            engine.warmup(
                sorted(
                    (
                        bar
                        for bar in warmup_bars
                        if bar.timestamp + TIMEFRAME_DELTA[bar.timeframe] <= now
                    ),
                    key=lambda bar: bar.timestamp,
                )
            )
        async for event in stream.events():
            engine.reconnects = stream.reconnects
            engine.process(event)
            processed += 1
            if args.max_events and processed >= args.max_events:
                break
    except asyncio.CancelledError:
        pass
    finally:
        print(json.dumps(engine.status(), indent=2, default=str))
        store.close()


def _experiment_status(args: argparse.Namespace) -> None:
    store = PaperStore(args.database)
    lock = store.get_state(ExperimentLock.KEY)
    state = store.get_state("paper") or {}
    decisions = store.events("decision")
    predictions = store.events("forward_prediction")
    last_by_asset: dict[str, dict[str, object]] = {}
    for item in predictions:
        last_by_asset[item["payload"]["asset"]] = item["payload"]
    output = {
        "experiment": None if lock is None else lock["experiment_id"],
        "started": None if lock is None else lock["metadata"]["experiment_started_at"],
        "feed": "offline_snapshot",
        "health": store.get_state("paper_health"),
        "main": {
            "cash": state.get("cash"),
            "equity": state.get("equity"),
            "positions": state.get("positions", {}),
            "realized_pnl": state.get("realized_pnl"),
        },
        "last_predictions": last_by_asset,
        "last_decision": decisions[-1]["payload"] if decisions else None,
        "matured_labels": len(store.events("forward_outcome")),
        "predictive": predictive_metrics(store),
        "risk": {
            "kill_switch": state.get("kill_switch"),
            "circuit_breaker": state.get("circuit_state"),
        },
        "shadows": state.get("shadows", {}),
    }
    print(json.dumps(output, indent=2, default=str))
    store.close()


def _experiment_decisions(args: argparse.Namespace) -> None:
    store = PaperStore(args.database)
    for item in store.events("decision")[-args.last :]:
        payload = item["payload"]
        print(
            json.dumps(
                {
                    key: payload.get(key)
                    for key in (
                        "timestamp",
                        "asset",
                        "model_predictions",
                        "ensemble_prediction",
                        "estimated_edge",
                        "estimated_transaction_cost",
                        "decision",
                        "risk_decision",
                        "fill_id",
                    )
                },
                default=str,
            )
        )
    store.close()


def _experiment_report(args: argparse.Namespace) -> None:
    store = PaperStore(args.database)
    mature_predictions(
        store,
        experiment_id=args.experiment_id,
        horizon_bars=args.horizon,
        return_threshold=args.return_threshold,
        round_trip_cost=args.round_trip_cost,
    )
    paths = daily_snapshot(store, args.output)
    print("\n".join(str(path) for path in paths))
    store.close()


def _experiment_export(args: argparse.Namespace) -> None:
    store = PaperStore(args.database)
    print(export_experiment(store, args.output, tuple(args.artifact)))
    store.close()


def _freeze_model(args: argparse.Namespace) -> None:
    artifact = freeze_real_artifact(
        args.dataset,
        model_name=args.model,
        asset=args.asset,
        output=args.output,
        seed=args.seed,
        horizon=args.horizon,
        return_threshold=args.return_threshold,
    )
    print(artifact.model_dump_json(indent=2, exclude={"estimator_b64"}))


def _paper_run(args: argparse.Namespace) -> None:
    pid_path = Path(args.pid_file) if args.pid_file else None
    if pid_path is not None:
        pid_path.parent.mkdir(parents=True, exist_ok=True)
        pid_path.write_text(str(os.getpid()), encoding="utf-8")
    try:
        asyncio.run(_paper_run_async(args))
    finally:
        if pid_path is not None:
            pid_path.unlink(missing_ok=True)


def _paper_status(args: argparse.Namespace) -> None:
    store = PaperStore(args.database)
    state = store.get_state("paper") or {}
    output = {
        "feed_status": "offline_snapshot",
        "cash": state.get("cash"),
        "positions": state.get("positions", {}),
        "kill_switch": state.get("kill_switch"),
        "circuit_breaker": state.get("circuit_state"),
        "decisions": len(store.events("decision")),
        "orders": len(store.events("order")),
        "fills": len(store.events("fill")),
        "risk_decisions": len(store.events("risk_decision")),
    }
    print(json.dumps(output, indent=2, default=str))
    store.close()


def _explain_decision(args: argparse.Namespace) -> None:
    store = PaperStore(args.database)
    matching = [
        item
        for item in store.events("decision")
        if item["payload"]["decision_id"] == args.decision_id
    ]
    if not matching:
        raise KeyError(f"decision not found: {args.decision_id}")
    print(explain(DecisionRecord.model_validate(matching[0]["payload"])))
    store.close()


def _promote_model(args: argparse.Namespace) -> None:
    raw = json.loads(Path(args.artifact).read_text(encoding="utf-8"))
    artifact = ModelArtifact.load(args.artifact, raw["feature_version"])
    registry = ModelRegistry(args.registry)
    registry.register(artifact)
    registry.promote_to_paper(artifact.model_version)
    print(f"promoted {artifact.model_version} to PAPER")


def main() -> None:
    parser = argparse.ArgumentParser(prog="smarttrading")
    commands = parser.add_subparsers(dest="command", required=True)
    backtest = commands.add_parser("backtest")
    backtest.add_argument(
        "--strategy",
        choices=["buy_hold", "moving_average", "momentum", "mean_reversion"],
        required=True,
    )
    backtest.add_argument("--config", default="config/default.yaml")
    backtest.add_argument("--dataset", required=True)
    backtest.add_argument("--output", default="reports/latest")
    backtest.add_argument("--cost-stress", action="store_true")
    features = commands.add_parser("features")
    feature_commands = features.add_subparsers(dest="features_command", required=True)
    build = feature_commands.add_parser("build")
    build.add_argument("--dataset", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--horizon", type=int, default=6)
    build.add_argument("--return-threshold", type=float, default=0.001)
    ml = commands.add_parser("ml")
    ml_commands = ml.add_subparsers(dest="ml_command", required=True)
    for name in ("train", "evaluate", "walk-forward", "final-evaluate"):
        _add_ml_arguments(ml_commands.add_parser(name))
    data = commands.add_parser("data")
    data_commands = data.add_subparsers(dest="data_command", required=True)
    prepare = data_commands.add_parser("prepare")
    prepare.add_argument("--asset", choices=["BTC/USDT", "ETH/USDT"], required=True)
    prepare.add_argument("--timeframe", choices=["5m", "15m", "1h", "4h"], required=True)
    prepare.add_argument("--start", required=True)
    prepare.add_argument("--end", required=True)
    prepare.add_argument("--output", required=True)
    paper = commands.add_parser("paper")
    paper_commands = paper.add_subparsers(dest="paper_command", required=True)
    smoke = paper_commands.add_parser("smoke")
    smoke.add_argument("--artifact", required=True)
    smoke.add_argument("--database", default="data/paper.db")
    smoke.add_argument("--config", default="config/default.yaml")
    smoke.add_argument("--asset", default="BTC/USDT", choices=["BTC/USDT", "ETH/USDT"])
    smoke.add_argument("--timeframe", default="5m", choices=["5m", "15m", "1h", "4h"])
    smoke.add_argument("--lookback-hours", type=int, default=6)
    run = paper_commands.add_parser("run")
    run.add_argument("--artifact", action="append", required=True)
    run.add_argument("--database", default="data/paper.db")
    run.add_argument("--config", default="config/default.yaml")
    run.add_argument("--assets", nargs="+", default=["BTC/USDT", "ETH/USDT"])
    run.add_argument("--timeframe", default="5m", choices=["5m", "15m", "1h", "4h"])
    run.add_argument("--max-events", type=int, default=0)
    run.add_argument("--experiment-config")
    run.add_argument("--pid-file")
    status = paper_commands.add_parser("status")
    status.add_argument("--database", default="data/paper.db")
    explain_command = commands.add_parser("explain")
    explain_command.add_argument("decision_id")
    explain_command.add_argument("--database", default="data/paper.db")
    model = commands.add_parser("model")
    model_commands = model.add_subparsers(dest="model_command", required=True)
    promote = model_commands.add_parser("promote")
    promote.add_argument("--artifact", required=True)
    promote.add_argument("--registry", default="data/models.db")
    freeze = model_commands.add_parser("freeze")
    freeze.add_argument("--dataset", required=True)
    freeze.add_argument("--asset", choices=["BTC/USDT", "ETH/USDT"], required=True)
    freeze.add_argument("--model", choices=["logistic", "gradient_boosting"], required=True)
    freeze.add_argument("--output", required=True)
    freeze.add_argument("--seed", type=int, default=17)
    freeze.add_argument("--horizon", type=int, default=6)
    freeze.add_argument("--return-threshold", type=float, default=0.001)
    experiment = commands.add_parser("experiment")
    experiment_commands = experiment.add_subparsers(dest="experiment_command", required=True)
    experiment_status = experiment_commands.add_parser("status")
    experiment_status.add_argument("--database", default="data/forward_v1.db")
    decisions = experiment_commands.add_parser("decisions")
    decisions.add_argument("--database", default="data/forward_v1.db")
    decisions.add_argument("--last", type=int, default=20)
    report = experiment_commands.add_parser("report")
    report.add_argument("--database", default="data/forward_v1.db")
    report.add_argument("--experiment-id", required=True)
    report.add_argument("--horizon", type=int, default=6)
    report.add_argument("--return-threshold", type=float, default=0.001)
    report.add_argument("--round-trip-cost", type=float, default=0.0014)
    report.add_argument("--output", default="reports/forward")
    export = experiment_commands.add_parser("export")
    export.add_argument("--database", default="data/forward_v1.db")
    export.add_argument("--output", required=True)
    export.add_argument("--artifact", action="append", default=[])
    args = parser.parse_args()
    if args.command == "backtest":
        _backtest(args)
    elif args.command == "features":
        _features(args)
    elif args.command == "ml":
        _ml(args)
    elif args.command == "data":
        _prepare_data(args)
    elif args.command == "paper":
        if args.paper_command == "smoke":
            _paper_smoke(args)
        elif args.paper_command == "run":
            _paper_run(args)
        else:
            _paper_status(args)
    elif args.command == "explain":
        _explain_decision(args)
    elif args.command == "model":
        if args.model_command == "promote":
            _promote_model(args)
        else:
            _freeze_model(args)
    elif args.experiment_command == "status":
        _experiment_status(args)
    elif args.experiment_command == "decisions":
        _experiment_decisions(args)
    elif args.experiment_command == "report":
        _experiment_report(args)
    else:
        _experiment_export(args)


if __name__ == "__main__":
    main()
