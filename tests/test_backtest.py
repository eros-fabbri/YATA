from datetime import UTC, datetime
from decimal import Decimal

from smarttrading.backtest.engine import BacktestEngine
from smarttrading.backtest.metrics import calculate_metrics
from smarttrading.domain import Signal
from smarttrading.execution.simulator import CostModel, ExecutionSimulator
from smarttrading.portfolio.accounting import EquityPoint, PortfolioAccount
from smarttrading.portfolio.sizing import FixedFractionSizer
from smarttrading.risk.manager import IndependentRiskManager
from smarttrading.strategies.baselines import BuyAndHoldStrategy, MomentumConfig, MomentumStrategy
from tests.helpers import bars_from_prices, risk_settings


def engine(strategy: object, costs: CostModel | None = None) -> BacktestEngine:
    return BacktestEngine(
        initial_cash=Decimal("1000"),
        strategy=strategy,
        sizer=FixedFractionSizer(Decimal("0.5")),
        risk=IndependentRiskManager(risk_settings()),
        execution=ExecutionSimulator(costs or CostModel(0, 0, 0, 0)),
        seed=7,
    )


class AuditStrategy(BuyAndHoldStrategy):
    name = "audit"

    def __init__(self) -> None:
        self.observed: list[tuple[int, Decimal]] = []

    def on_bar(self, history: object, predictions: object = ()) -> Signal:
        sequence = list(history)
        self.observed.append((len(sequence), sequence[-1].close))
        return super().on_bar(sequence, ())


def test_no_lookahead_future_jump_is_not_visible_early() -> None:
    strategy = AuditStrategy()
    result = engine(strategy).run(bars_from_prices(["100", "100", "10000"]))
    assert strategy.observed == [(1, Decimal("100")), (2, Decimal("100")), (3, Decimal("10000"))]
    assert result.curve[0].cash == Decimal("1000")  # First signal fills on next bar.


def test_backtest_is_economically_deterministic() -> None:
    bars = bars_from_prices(["100", "101", "103", "99", "105"])
    first = engine(MomentumStrategy(MomentumConfig(lookback=1, threshold=0))).run(bars)
    second = engine(MomentumStrategy(MomentumConfig(lookback=1, threshold=0))).run(bars)
    assert first.result_hash == second.result_hash
    assert first.curve == second.curve


def test_maximum_drawdown_known_curve() -> None:
    account = PortfolioAccount(Decimal("100"))
    curve = [
        EquityPoint(
            timestamp=datetime(2025, 1, index + 1, tzinfo=UTC),
            cash=equity,
            positions_value=0,
            equity=equity,
            realized_pnl=0,
            unrealized_pnl=0,
            fees=0,
        )
        for index, equity in enumerate(
            [Decimal("100"), Decimal("120"), Decimal("90"), Decimal("108")]
        )
    ]
    metrics = calculate_metrics(curve, account, 365)
    assert metrics.maximum_drawdown == 0.25


def test_golden_end_to_end_accounting() -> None:
    result = engine(BuyAndHoldStrategy()).run(bars_from_prices(["100", "110", "120"]))
    # Signal at bar 1 buys five units on the next open and then holds without rebalancing.
    assert result.curve[-1].cash == Decimal("450")
    assert result.curve[-1].positions_value == Decimal("600")
    assert result.curve[-1].equity == Decimal("1050")
    assert result.risk.approved == 1
