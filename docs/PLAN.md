# Technical delivery plan

1. Establish package boundaries, validated configuration, immutable domain contracts, quality
   gates and local/container workflows.
2. Add deterministic historical ingestion, validation, deduplication and dataset manifests.
3. Build the shared event loop, accounting and Buy & Hold benchmark.
4. Add moving-average, momentum and mean-reversion baselines.
5. Add independent risk gates and a cost/latency/partial-fill simulator.
6. Add causal features with explicit availability timestamps.
7. Add logistic-regression training, chronological walk-forward evaluation and cost stress tests.
8. Add durable streaming paper trading with reconnection and restart reconciliation.
9. Add decision lineage, metrics and reports.
10. Add the validated alternative-data interface; no direct LLM-generated orders.

Milestones 1–9 are implemented. Milestone 8 adds closed-candle streaming, persistent paper
recovery, model lifecycle, ensemble abstention, regime/context features and monitoring. Live
trading and automatic retraining remain absent. Milestone 9 freezes and locks the first real-model
forward experiment, matures evaluation-only outcomes, adds health/reconciliation, daily reports,
status/decision/export commands and independently accounted shadows.

Each milestone closes only after tests, Ruff, mypy and documentation pass. Selection criteria are
out-of-sample economic results after costs, stability and risk—not the best in-sample Sharpe.
