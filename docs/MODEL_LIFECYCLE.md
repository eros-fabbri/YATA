# Model lifecycle

States are `CANDIDATE`, `PAPER`, and `RETIRED`; there is deliberately no LIVE state. Artifacts bind
model version, feature version, dataset hash, training interval, validation metrics and ordered
feature names. The model version is a deterministic content hash and is validated on load. Feature
version mismatch aborts startup.

Promotion to PAPER is an explicit CLI action. Paper inference loads an immutable artifact and never
fits, calibrates or updates it. Drift monitoring (PSI and KS, plus future rolling calibration once
labels mature) produces warnings only. Any retraining happens offline and creates a new CANDIDATE.

Evidence levels must not be conflated:

1. Historical backtest replays known history.
2. Walk-forward OOS predicts held-out chronological folds.
3. Sealed holdout is a one-time offline confirmation and remains unopened here.
4. Paper forward test observes genuinely new data after promotion.

Real PAPER artifacts may contain a hash-verified serialized sklearn pipeline. The outer artifact
hash binds estimator bytes and all metadata; the inner SHA-256 is checked before deserialization.
Logistic Regression and HistGradientBoosting predictions are regression-tested for exact round-trip
stability. Only locally produced, explicitly promoted artifacts are trusted inputs.
