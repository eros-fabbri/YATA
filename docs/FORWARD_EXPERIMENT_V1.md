# Forward Experiment V1

This document freezes the first genuine forward experiment. Changing configuration after
observing forward results creates a new experiment. An experiment that has started is immutable.
There is no LIVE state and no automatic retraining or promotion.

## Scope and evidence boundary

- Assets: BTC/USDT and ETH/USDT, spot, long-only, no leverage.
- Decision timeframe: 1h. Prediction horizon: 6 closed bars.
- Historical inputs: 2025-09-01 through 2026-09-01 public Binance 1h candles.
- The final 20% chronological holdout remains SEALED and is never passed to model fitting,
  validation, paper initialization, reporting or forward evaluation.
- Forward outcomes are evaluation records only and cannot become training input automatically.
- Informational windows: 24h operational smoke; 7d preliminary operations; 30d first meaningful
  review; 60/90d stronger forward evidence. None authorizes live trading.

## Frozen models and features

Feature version is `features-v1-ef85d5332160`. Target is six-bar future return strictly above
0.001. Seed is 17. No post-hoc calibration is fitted; calibration is measured on a purged
chronological validation slice within the development prefix.

| Asset | Model | Version | Weight |
|---|---|---:|---:|
| BTC/USDT | Logistic Regression | `d20f8746e2cbac68` | 0.50 |
| BTC/USDT | HistGradientBoosting | `aa070801f43e7d52` | 0.50 |
| ETH/USDT | Logistic Regression | `8abe284b5c797a1b` | 0.50 |
| ETH/USDT | HistGradientBoosting | `23b41608d8ab1c3a` | 0.50 |

Weights are uniform within each asset. They were selected before forward observation and are not
derived from the sealed holdout. The runtime only evaluates the two matching artifacts per asset.

## Frozen decision and capital policy

- Buy probability: 0.60; exit probability: 0.45.
- Minimum confidence: 0.20; disagreement penalty: 1.0.
- Estimated edge must exceed the round-trip cost estimate; ABSTAIN is valid.
- Virtual starting capital: 100,000 USDT shared by MAIN `ensemble-paper-v1`.
- Maximum asset allocation: 25%; maximum portfolio exposure: 60%; maximum order notional:
  10,000 USDT; daily loss: 3%; drawdown: 15%.
- Costs: maker 2 bps, taker 5 bps, spread 2 bps, slippage 1 bp, simulated latency 100 ms.

## Independent shadows

Model shadows are logistic and gradient for each asset. Baseline shadows are momentum,
moving-average, mean-reversion and buy-and-hold, separated by asset. Every shadow has independent
accounting and cannot mutate MAIN.

## Monitoring

Predictive metrics always show sample size and are marked preliminary below 30 matured labels.
Economic metrics are displayed side-by-side without winner ranking. Drift warning thresholds are
PSI 0.20, KS 0.10 and calibration delta 0.10. Health is HEALTHY, DEGRADED or UNSAFE; UNSAFE blocks
new exposure while monitoring and exits remain possible.

The canonical machine-readable freeze is `config/forward_v1.json`. Its deterministic experiment ID
is derived from every frozen field except the freeze timestamp, so any substantive change produces
a new ID. Frozen V1 resolves to `forward-v1-65adc165b73773872d7c`.
