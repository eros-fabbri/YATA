from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from smarttrading.backtest.engine import BacktestEngine, BacktestResult, BacktestStrategy
from smarttrading.config.settings import AppSettings
from smarttrading.domain import Bar
from smarttrading.execution.simulator import CostModel, ExecutionSimulator
from smarttrading.features.dataset import MLDataset
from smarttrading.models.splitting import (
    chronological_holdout,
    expanding_walk_forward,
    seal_final_holdout,
)
from smarttrading.models.training import ModelName, WalkForwardResult, walk_forward_train
from smarttrading.portfolio.sizing import FixedFractionSizer
from smarttrading.risk.manager import IndependentRiskManager
from smarttrading.strategies.baselines import (
    BuyAndHoldStrategy,
    MeanReversionStrategy,
    MomentumStrategy,
    MovingAverageCrossoverStrategy,
)
from smarttrading.strategies.ml import PredictionStrategy, PredictionStrategyConfig


@dataclass(frozen=True)
class EconomicEvaluation:
    ml: BacktestResult
    baselines: dict[str, BacktestResult]
    cost_stress: dict[int, BacktestResult]


@dataclass(frozen=True)
class ExperimentResult:
    predictive: WalkForwardResult
    economic: EconomicEvaluation
    final_holdout_status: str


def _costs(settings: AppSettings, multiplier: int = 1) -> CostModel:
    factor = Decimal(multiplier)
    return CostModel(
        Decimal(str(settings.execution.maker_fee_bps)) * factor,
        Decimal(str(settings.execution.taker_fee_bps)) * factor,
        Decimal(str(settings.execution.spread_bps)) * factor,
        Decimal(str(settings.execution.slippage_bps)) * factor,
    )


def _engine(
    settings: AppSettings, strategy: BacktestStrategy, costs: CostModel, seed: int
) -> BacktestEngine:
    return BacktestEngine(
        initial_cash=settings.initial_cash,
        strategy=strategy,
        sizer=FixedFractionSizer(Decimal(str(settings.risk.max_asset_allocation))),
        risk=IndependentRiskManager(settings.risk),
        execution=ExecutionSimulator(costs),
        seed=seed,
    )


def economic_evaluation(
    bars: list[Bar], result: WalkForwardResult, settings: AppSettings, seed: int
) -> EconomicEvaluation:
    first_timestamp = result.predictions[0].timestamp
    evaluation_bars = [bar for bar in bars if bar.timestamp >= first_timestamp]
    strategy_config = PredictionStrategyConfig(
        estimated_round_trip_cost=(
            settings.execution.taker_fee_bps * 2
            + settings.execution.spread_bps
            + settings.execution.slippage_bps * 2
        )
        / 10000
    )
    ml = _engine(
        settings,
        PredictionStrategy(result.predictions, strategy_config),
        _costs(settings),
        seed,
    ).run(evaluation_bars)
    strategies: dict[str, BacktestStrategy] = {
        "buy_hold": BuyAndHoldStrategy(),
        "moving_average": MovingAverageCrossoverStrategy(),
        "momentum": MomentumStrategy(),
        "mean_reversion": MeanReversionStrategy(),
    }
    baselines = {
        name: _engine(settings, strategy, _costs(settings), seed).run(evaluation_bars)
        for name, strategy in strategies.items()
    }
    stress = {
        multiplier: _engine(
            settings,
            PredictionStrategy(result.predictions, strategy_config),
            _costs(settings, multiplier),
            seed,
        ).run(evaluation_bars)
        for multiplier in (1, 2, 3)
    }
    return EconomicEvaluation(ml=ml, baselines=baselines, cost_stress=stress)


def run_experiment(
    dataset: MLDataset,
    bars: list[Bar],
    settings: AppSettings,
    *,
    model_name: ModelName = "logistic",
    seed: int = 0,
    minimum_train_size: int = 100,
    validation_size: int = 30,
    step_size: int = 30,
    embargo: int = 1,
    max_folds: int | None = None,
    final_fraction: float = 0.2,
) -> ExperimentResult:
    sealed = seal_final_holdout(len(dataset.X), final_fraction)
    development_size = len(sealed.development)
    horizon = int(dataset.metadata.target_definition.split("_")[2].split(">")[0])
    folds = expanding_walk_forward(
        development_size,
        minimum_train_size=minimum_train_size,
        validation_size=validation_size,
        step_size=step_size,
        horizon=horizon,
        embargo=embargo,
        max_folds=max_folds,
    )
    predictive = walk_forward_train(dataset, folds, model_name, seed)
    return ExperimentResult(
        predictive=predictive,
        economic=economic_evaluation(bars, predictive, settings, seed),
        final_holdout_status="SEALED",
    )


def run_final_evaluation(
    dataset: MLDataset,
    bars: list[Bar],
    settings: AppSettings,
    *,
    model_name: ModelName = "logistic",
    seed: int = 0,
    final_fraction: float = 0.2,
    embargo: int = 1,
) -> ExperimentResult:
    sealed = seal_final_holdout(len(dataset.X), final_fraction)
    holdout = sealed.open(explicit_final_evaluation=True)
    horizon = int(dataset.metadata.target_definition.split("_")[2].split(">")[0])
    fold = chronological_holdout(len(dataset.X), len(holdout), horizon, embargo)
    predictive = walk_forward_train(dataset, [fold], model_name, seed)
    return ExperimentResult(
        predictive=predictive,
        economic=economic_evaluation(bars, predictive, settings, seed),
        final_holdout_status="OPENED_BY_EXPLICIT_FINAL_EVALUATION",
    )


def render_experiment(result: ExperimentResult) -> str:
    predictive = result.predictive.metrics
    economic = result.economic.ml
    lines = [
        f"MODEL\n{result.predictive.folds[0].manifest.model_name}",
        f"TARGET\n{result.predictive.folds[0].manifest.target_definition}",
        (
            f"DATA\nwalk-forward folds: {len(result.predictive.folds)}\n"
            f"final holdout: {result.final_holdout_status}"
        ),
        "PREDICTIVE METRICS OOS",
        f"ROC-AUC: {predictive.roc_auc}",
        f"PR-AUC: {predictive.pr_auc}",
        f"Brier: {predictive.brier_score:.6f}",
        f"Log loss: {predictive.log_loss:.6f}",
        f"Balanced accuracy: {predictive.balanced_accuracy:.6f}",
        "ECONOMIC OOS",
        f"Return: {economic.metrics.total_return:.4%}",
        f"Sharpe: {economic.metrics.sharpe}",
        f"Sortino: {economic.metrics.sortino}",
        f"Max DD: {economic.metrics.maximum_drawdown:.4%}",
        f"Turnover: {economic.metrics.turnover:.6f}",
        f"Trades: {economic.metrics.number_of_trades}",
        f"Fees: {economic.metrics.total_fees}",
        f"Spread cost: {economic.spread_cost}",
        f"Slippage: {economic.slippage_cost}",
        "BASELINES SAME PERIOD",
    ]
    lines.extend(
        f"{name}: return={baseline.metrics.total_return:.4%} sharpe={baseline.metrics.sharpe} "
        f"max_dd={baseline.metrics.maximum_drawdown:.4%}"
        for name, baseline in result.economic.baselines.items()
    )
    lines.append("COST STRESS")
    lines.extend(
        f"{multiplier}x: return={stressed.metrics.total_return:.4%} "
        f"costs={stressed.metrics.total_fees + stressed.spread_cost + stressed.slippage_cost}"
        for multiplier, stressed in result.economic.cost_stress.items()
    )
    lines.append("Classification quality does not imply trading profitability.")
    return "\n".join(lines)
