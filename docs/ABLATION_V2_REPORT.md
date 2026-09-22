# V2 ablation report

Status: framework complete; empirical comparison not run.

The predeclared matrix is Logistic Regression and HistGradientBoosting over V1 OHLCV baseline, then additions of multi-timeframe, cross-asset, regime, microstructure, derivatives, and full V2. `smarttrading.models.ablation_v2.evaluate_ablation` uses the existing purged/embargoed temporal folds and emits ROC-AUC, PR-AUC, Brier, log loss, calibration ECE, sample size, return, drawdown, turnover, trades, fees, spread/slippage and abstention.

The repository has no sufficiently long, permitted historical V2 microstructure dataset. Numeric results would require Forward V1 observations or synthetic claims, both methodologically invalid here. Consequently no winner and no V2 artifact are declared. A future report must show fold uncertainty and coverage/missing/stale rates alongside point estimates.
