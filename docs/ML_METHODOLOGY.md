# ML methodology

## Causal features and warmup

Every feature row at bar `T` is calculated only from rows at or before `T`. Rolling windows are
trailing, exponential averages have explicit minimum periods, and future values are never
backfilled. Rows remain unavailable until every configured feature is finite; incomplete warmup
rows are excluded rather than imputed. `FeatureSet.feature_version` hashes the complete window
configuration, while the ML dataset records ordered feature names and the source dataset digest.

## Targets

Targets are built in a separate module as `close[T + horizon] / close[T] - 1`. `UP` means this
return is strictly above the configured threshold; all other labeled rows are `DOWN`. The final
`horizon` rows have no target and are excluded. Future returns and labels are never columns in `X`.
The threshold can include an estimated trading-cost hurdle.

## Temporal validation

Random splitting is prohibited. Expanding walk-forward uses a growing training prefix followed by
a validation block. Between them, `horizon` rows are purged so no training label can observe a
price at or beyond validation, followed by the configured embargo. Formally, every fold satisfies
`max(train_index) + horizon < min(validation_index)`.

The final fraction is represented by `SealedFinalHoldout`. Ordinary `train`, `evaluate`, and
`walk-forward` commands operate only on its development prefix and report `SEALED`. Only
`final-evaluate` calls the explicit opening API. That command should be run once after model,
features and thresholds are frozen—not repeatedly during exploration.

## Models and preprocessing

Available models are a prior Dummy classifier, Logistic Regression, and sklearn histogram Gradient
Boosting. Logistic scaling is inside an sklearn `Pipeline`, so each fold fits its scaler only on
training rows. Model manifests include dataset and feature versions, target, training dates,
parameters, sklearn version and seed. Versions are deterministic hashes.
Logistic manifests also retain signed coefficients. They are descriptive associations, not causal
effects. Histogram gradient boosting deliberately reports no built-in impurity importance; an OOS
permutation-importance extension can be added when experiment sizes justify its computational cost.

The report includes ROC-AUC, PR-AUC, accuracy-family metrics, Brier score, log loss and expected
calibration error. Calibration is measured OOS; no additional calibrator is fitted in this version,
avoiding a second small and potentially leaky calibration split. This is an explicit limitation.

## Economic evaluation

Only concatenated walk-forward validation predictions are converted to signals. `PredictionStrategy`
requires both a probability threshold and expected edge above estimated round-trip costs plus a
safety margin. Signals use the existing portfolio, risk, next-bar execution and accounting path.
ML and all baselines are evaluated on the same OOS date span and cost assumptions. Classification
quality does not imply economic profitability, and feature importance does not imply causality.

## Residual limitations

- OHLCV cannot model queue position, intrabar path or real liquidity.
- Expected return is a conservative probability-scaled training-fold mean, not a separately fitted
  return model.
- ECE on small samples is unstable and depends on binning.
- Multiple exploratory runs still create researcher degrees of freedom even with a sealed holdout.
- Exchange history may contain venue-specific selection and data-quality effects.

Milestone 8 does not open the final holdout or revise Milestone 7 thresholds. Newly arriving paper
events are forward evidence and cannot be reused retroactively to alter the currently promoted
artifact. Drift warnings never trigger automatic retraining.
