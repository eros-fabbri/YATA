# SmartTrading architecture

## Objective and safety boundary

SmartTrading is a reproducible quantitative research and paper-trading platform for
BTC/USDT and ETH/USDT spot markets. It does not promise profitability. Live execution is
deliberately absent from the first release: configuration accepts only `backtest` and `paper`.
Adding live trading later requires a separate adapter, an explicit release decision, credentials
provided through a secret store, and independent hard risk limits.

## Decision flow

```text
Exchange/data source -> normalized market events -> feature pipeline
  -> strategies/models -> signals -> portfolio targets -> risk decisions
  -> approved orders -> execution adapter -> fills -> accounting
```

Strategies return signals and never receive an exchange or execution dependency. The execution
port accepts only orders carrying an approving risk-decision identifier. This is enforced at the
application boundary as well as by tests in later milestones.

## Package structure

```text
src/smarttrading/
  common/       clocks, identifiers, shared errors
  config/       validated application settings and safe loading
  data/         normalized market-data contracts and persistence ports
  features/     causal feature transformations
  strategies/   signal producers, including non-ML baselines
  models/       prediction contracts, training and model registry
  portfolio/    signal aggregation and target position sizing
  risk/         independent limits, circuit breaker and kill switch
  execution/    order state machine and simulated execution
  exchanges/    historical and streaming exchange adapters
  backtest/     event loop, accounting, metrics and experiment records
  paper/        durable real-time orchestration
  monitoring/   structured audit events, metrics and reporting
tests/           unit, integration and regression tests
scripts/         operator entry points
docker/          container assets
research/        notebooks only; never imported by production code
```

The package follows ports-and-adapters: domain code depends on typed protocols, while exchange,
database and simulator implementations depend on those protocols. Backtest and paper modes share
the signal, portfolio, risk, order, accounting and event contracts.

## Core contracts

- Market timestamps are timezone-aware UTC and bars identify the opening instant of an interval.
- Decimal values represent prices, quantities and money; floats are reserved for bounded scores.
- A `Signal` expresses direction, strength and confidence, never quantity.
- A `TargetPosition` expresses desired portfolio exposure.
- A `RiskDecision` is an immutable approval or rejection with machine-readable reasons.
- `Order` and `Fill` use client-generated identifiers for idempotency and auditability.
- Model predictions include timestamp, asset, horizon and model version.

## Reproducibility and bias controls

Datasets will be immutable snapshots identified by a content digest. Experiments record config,
dataset digest, code revision and random seed. Feature timestamps must not precede their latest
input timestamp. Training uses chronological splits; a final test interval is isolated before
tuning. Costs are explicit inputs and are stress-tested.

Feature computation is causal and target generation is a separate training-only operation. ML
preprocessing is fitted within each training fold. Walk-forward splits purge the label horizon and
apply an additional embargo before validation. Ordinary experiments cannot access the sealed final
holdout. Only OOS predictions enter `PredictionStrategy`, which remains upstream of portfolio,
risk and execution.

## Backtest execution assumptions

A strategy sees an immutable history ending at the current bar; the engine never passes the full
dataset. Orders produced after bar `T` are eligible for execution from the next bar, eliminating a
same-close decision/fill assumption. Market fills use next open adjusted adversely by half-spread
plus slippage: `buy = open * (1 + spread/2 + slippage)` and sell uses the corresponding subtraction;
fees apply to adjusted notional.

OHLCV cannot reveal queue position. A limit therefore fills only when price strictly penetrates the
limit (`low < buy limit`, `high > sell limit`), at the limit price. Touches do not fill. Partial fills
use an explicit deterministic fraction, defaulting to 100%; this is a scenario control, not a claim
about market microstructure. Trade/order-book models can replace this adapter later.

## Persistence

SQLite is the zero-service development default. PostgreSQL is supplied through Compose for paper
operation and concurrent workloads. SQLAlchemy keeps storage replaceable. Schema migrations will
be introduced with the first durable ingestion tables in Milestone 2.

## Failure model

Malformed or non-monotonic market data is rejected before strategy evaluation. Stale feeds,
anomalous prices, excessive loss/drawdown and operator intervention trip independent risk gates.
Circuit-breaker state is durable in paper mode. Restart recovery reconciles persisted orders,
fills, balances and positions before processing new events.

## Paper runtime

The async stream accepts only exchange-confirmed closed candles. A durable append-only journal and
atomic state snapshot make each decision cycle idempotent across crashes. Inference accepts only a
content-validated PAPER artifact with an exact feature-version match; training is absent from the
runtime. Ensemble and regime adjustments can reduce exposure or abstain but never bypass risk.
There is no live execution port implementation.

## Deferred decisions

The initial exchange, detailed order-book model, TimescaleDB, metrics backend, gradient-boosting
library, orchestration platform, and any alternative-data provider are intentionally deferred.
They are adapter-level choices and are not needed to validate the core research loop. Futures,
leverage, shorting and live credentials are explicitly out of scope.
