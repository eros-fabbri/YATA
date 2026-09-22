# SmartTrading

Safety-first quantitative crypto research and paper-trading platform. The current release is
**Milestones 1–8**: deterministic research plus persistent, closed-candle paper trading, explicit
model lifecycle, decision journal and monitoring. It cannot place live orders.

No result produced by this software is a promise of profit. Backtests are hypotheses subject to
data quality, model risk, costs, latency and market-regime change.

## Architecture

The enforced flow is data → features → signals/models → portfolio → risk → execution → exchange.
A strategy emits a signal, not an order. See [ARCHITECTURE.md](ARCHITECTURE.md) for boundaries,
invariants and deferred decisions, and [docs/PLAN.md](docs/PLAN.md) for the milestone plan.

## Requirements and setup

Python 3.12+ is required. With `uv` installed, synchronize the local package and the default
development dependency group:

```bash
uv sync
```

`uv sync --no-dev` installs only the runtime environment. Use ordinary `uv sync` (or explicitly
`uv sync --group dev`) for development. The package is installed from `src/` and exposes the
`smarttrading` console script; no `pip` or `PYTHONPATH` step is needed.

Copy `.env.example` to `.env` for local overrides; never add credentials to versioned YAML.
The default configuration is `config/default.yaml` and defaults to paper mode.

## Quality checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

The same checks can run without a local Python installation:

```bash
docker build --target test -t smarttrading-test .
docker run --rm smarttrading-test
```

## Database

SQLite is the local default. PostgreSQL is available for later durable paper operation:

```bash
docker compose up postgres
```

The Compose password is a development-only value. Production secrets must come from a secret
manager or unversioned environment variables.

## First backtest

```bash
smarttrading backtest \
  --strategy momentum \
  --config config/default.yaml \
  --dataset tests/fixtures/golden_btc_5m.csv \
  --cost-stress
```

Results are written as JSON plus an equity-curve CSV. Available strategies are `buy_hold`,
`moving_average`, `momentum`, and `mean_reversion`. Their defaults are transparent starting points,
not optimized parameters. Short samples intentionally report annualization or ratios as `None`
when the statistic is not meaningful; volatility, Sharpe and Sortino require at least 30 returns.

Market decisions fill from the next bar. See `ARCHITECTURE.md` for exact execution assumptions.

## Feature and ML workflows

```bash
smarttrading features build --dataset data/btc_1h.csv --output data/btc_ml.parquet
smarttrading ml walk-forward --dataset data/btc_1h.csv --model logistic
smarttrading ml final-evaluate --dataset data/btc_1h.csv --model logistic
```

`train`, `evaluate`, and `walk-forward` keep the final holdout sealed. `final-evaluate` is the only
command that opens it and should be used only after freezing the experiment. See
[`docs/ML_METHODOLOGY.md`](docs/ML_METHODOLOGY.md) for warmup, target, purge, embargo, calibration
and leakage limitations.

Public historical data requires no API key:

```bash
smarttrading data prepare --asset BTC/USDT --timeframe 1h \
  --start 2025-01-01T00:00:00Z --end 2026-01-01T00:00:00Z \
  --output data/btc_usdt_1h.csv
```

The adapter uses bounded retries and rate-limit handling. Public API availability is not assumed.

## Paper trading

Paper mode loads an explicitly promoted, versioned artifact and never retrains it. See
[`docs/PAPER_TRADING.md`](docs/PAPER_TRADING.md), [`docs/MARKET_DATA.md`](docs/MARKET_DATA.md) and
[`docs/MODEL_LIFECYCLE.md`](docs/MODEL_LIFECYCLE.md). Status and decision explanations are exposed
through `smarttrading paper status` and `smarttrading explain`.

Milestone 9 freezes the first genuine forward protocol in
[`docs/FORWARD_EXPERIMENT_V1.md`](docs/FORWARD_EXPERIMENT_V1.md). The daemon accepts multiple
asset-specific artifacts, resumes the same locked experiment after restart, and is stopped with
SIGINT (`Ctrl-C`) or SIGTERM. Forward outcomes are evaluation-only records.

## Current assumptions

- Spot only, no leverage, no short positions in execution.
- BTC/USDT and ETH/USDT; 5m, 15m, 1h and 4h bars.
- Timestamps are timezone-aware and normalized to UTC.
- Money, prices and quantities use decimal arithmetic.
- Live mode is not a valid configuration value.
- Costs are configuration inputs and will never default to zero.
