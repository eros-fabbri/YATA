from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from smarttrading.domain import DecisionAction


class DecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    decision_id: str
    timestamp: datetime
    asset: str
    market_regime: dict[str, str | float]
    important_features: dict[str, float]
    model_predictions: dict[str, float]
    ensemble_prediction: dict[str, str | float | dict[str, float]]
    estimated_transaction_cost: float
    estimated_edge: float
    decision: DecisionAction
    target_weight: float
    proposed_quantity: Decimal | None
    risk_decision: dict[str, str | bool | float] | None
    order_id: str | None
    fill_id: str | None


def explain(record: DecisionRecord) -> str:
    return "\n".join(
        [
            f"Decision {record.decision_id}",
            f"Time: {record.timestamp.isoformat()}",
            f"Asset: {record.asset}",
            f"Regime: {record.market_regime}",
            f"Important features: {record.important_features}",
            f"Model predictions: {record.model_predictions}",
            f"Ensemble: {record.ensemble_prediction}",
            (
                f"Estimated edge/cost: {record.estimated_edge:.6f}/"
                f"{record.estimated_transaction_cost:.6f}"
            ),
            f"Decision: {record.decision.value}",
            f"Target weight: {record.target_weight:.4f}",
            f"Risk: {record.risk_decision}",
            f"Order/fill: {record.order_id}/{record.fill_id}",
        ]
    )
