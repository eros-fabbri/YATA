# Paper trading

Paper mode is the only continuous runtime. It consumes only closed candles and follows the existing
feature → prediction → ensemble/signal → sizing → risk → conservative execution → accounting path.
There is no live exchange order adapter.

SQLite uses WAL mode and stores append-only typed events plus an atomic latest-state snapshot.
Event identifiers and decision identifiers are deterministic. On restart, closed-bar history,
portfolio, pending orders, kill switch and circuit breaker are restored; already journaled decision
cycles are skipped. Missing candles are recorded and must be reconciled from REST before inference.

```bash
smarttrading model promote --artifact models/model.json
smarttrading paper run --artifact models/model.json --database data/paper.db
smarttrading paper smoke --artifact models/model.json --database data/paper.db
smarttrading paper status --database data/paper.db
smarttrading explain DECISION_ID --database data/paper.db
```

The smoke-only constant artifact generator exists to test plumbing and must never be interpreted as
a trained model. Runtime never retrains or promotes a model automatically.

Shadow portfolios are isolated account containers and their decisions can be journaled against the
same market stream. They cannot mutate the main account. Full long-duration shadow performance
statistics require forward events and are not inferred from the smoke run.

## Forward experiment V1

The frozen protocol is defined by `config/forward_v1.json` and documented in
`docs/FORWARD_EXPERIMENT_V1.md`. Starting it stores the complete canonical configuration and
deterministic experiment ID in the paper database. A restart must provide the identical freeze;
artifact, threshold, cost, risk or feature changes are rejected and require V2.

`smarttrading experiment status`, `decisions`, `report` and `export` inspect the durable state.
Reports include sample sizes and suppress Sharpe/Sortino below 30 returns. An `UNSAFE` health state
blocks new long exposure but preserves monitoring and exit capability. SIGINT and SIGTERM trigger
the runtime cleanup path; no live-order adapter exists.
