from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

from smarttrading.portfolio.accounting import EquityPoint, PortfolioAccount


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    sharpe: float | None
    sortino: float | None
    maximum_drawdown: float
    calmar: float | None
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    turnover: float
    number_of_trades: int
    average_holding_seconds: float | None
    total_fees: Decimal


def calculate_metrics(
    curve: list[EquityPoint], account: PortfolioAccount, periods_per_year: int
) -> PerformanceMetrics:
    if not curve:
        raise ValueError("equity curve cannot be empty")
    equities = [float(point.equity) for point in curve]
    returns = [current / previous - 1 for previous, current in pairwise(equities) if previous]
    total_return = equities[-1] / equities[0] - 1
    years = len(returns) / periods_per_year
    annualized_return = (1 + total_return) ** (1 / years) - 1 if years >= 0.25 else None
    volatility = None
    sharpe = None
    sortino = None
    # Fewer than 30 observations is too little for an annualized dispersion/risk ratio.
    if len(returns) >= 30:
        mean = sum(returns) / len(returns)
        variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
        std = math.sqrt(variance)
        volatility = std * math.sqrt(periods_per_year)
        sharpe = mean / std * math.sqrt(periods_per_year) if std else None
        downside = [min(0.0, item) for item in returns]
        downside_deviation = math.sqrt(sum(item * item for item in downside) / len(downside))
        sortino = (
            mean / downside_deviation * math.sqrt(periods_per_year) if downside_deviation else None
        )
    peak = equities[0]
    max_drawdown = 0.0
    for equity in equities:
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak if peak else 0.0)
    calmar = (
        annualized_return / max_drawdown if annualized_return is not None and max_drawdown else None
    )
    pnls = [float(item[0]) for item in account.closed_trades]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    count = len(pnls)
    profit_factor = sum(wins) / abs(sum(losses)) if losses else None
    return PerformanceMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=volatility,
        sharpe=sharpe,
        sortino=sortino,
        maximum_drawdown=max_drawdown,
        calmar=calmar,
        win_rate=len(wins) / count if count else None,
        profit_factor=profit_factor,
        expectancy=sum(pnls) / count if count else None,
        turnover=float(account.turnover / account.initial_cash),
        number_of_trades=count,
        average_holding_seconds=(
            sum(item[1] for item in account.closed_trades) / count if count else None
        ),
        total_fees=account.total_fees,
    )
