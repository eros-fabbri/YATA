from __future__ import annotations

from dataclasses import asdict, dataclass

from smarttrading.features.dataset import MLDataset
from smarttrading.models.splitting import TemporalFold
from smarttrading.models.training import ModelName, walk_forward_train


@dataclass(frozen=True)
class EconomicMetrics:
    total_return: float
    maximum_drawdown: float
    turnover: float
    trades: int
    fees: float
    spread_slippage: float
    abstention: float


def evaluate_ablation(
    dataset: MLDataset,
    folds: list[TemporalFold],
    model: ModelName,
    economic: EconomicMetrics,
    *,
    family: str,
    seed: int = 17,
) -> dict[str, object]:
    """Evaluate one predeclared feature family with the existing purged temporal folds."""
    result = walk_forward_train(dataset, folds, model, seed)
    metrics = result.metrics
    return {
        "family": family,
        "model": model,
        "sample_size": len(result.y_true),
        "predictive": {
            "roc_auc": metrics.roc_auc,
            "pr_auc": metrics.pr_auc,
            "brier": metrics.brier_score,
            "log_loss": metrics.log_loss,
            "calibration_ece": metrics.expected_calibration_error,
        },
        "economic": asdict(economic),
    }
