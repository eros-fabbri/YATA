from __future__ import annotations

import hashlib
import json
import statistics
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from smarttrading.domain import DecisionAction, EnsemblePrediction


class EnsembleConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    weights: dict[str, float]
    buy_threshold: float = Field(default=0.60, gt=0.5, lt=1)
    exit_threshold: float = Field(default=0.45, gt=0, lt=0.5)
    abstain_confidence: float = Field(default=0.20, ge=0, le=1)
    disagreement_penalty: float = Field(default=1.0, ge=0, le=2)


class WeightedEnsemble:
    def __init__(self, config: EnsembleConfig) -> None:
        if not config.weights or sum(config.weights.values()) <= 0:
            raise ValueError("ensemble weights must have positive total")
        self.config = config
        payload = json.dumps(config.model_dump(), sort_keys=True, separators=(",", ":"))
        self.version = f"ensemble-v1-{hashlib.sha256(payload.encode()).hexdigest()[:12]}"

    def combine(
        self,
        timestamp: datetime,
        asset: str,
        probabilities: dict[str, float],
        regime_adjustment: float = 0.0,
    ) -> EnsemblePrediction:
        available = {
            name: value for name, value in probabilities.items() if name in self.config.weights
        }
        if not available:
            raise ValueError("no configured ensemble input is available")
        total_weight = sum(self.config.weights[name] for name in available)
        contributions = {
            name: value * self.config.weights[name] / total_weight
            for name, value in available.items()
        }
        probability = min(1.0, max(0.0, sum(contributions.values()) + regime_adjustment))
        disagreement = statistics.pstdev(available.values()) if len(available) > 1 else 0.0
        confidence = max(
            0.0,
            min(1.0, abs(probability - 0.5) * 2 - disagreement * self.config.disagreement_penalty),
        )
        if confidence < self.config.abstain_confidence:
            action = DecisionAction.ABSTAIN
        elif probability >= self.config.buy_threshold:
            action = DecisionAction.BUY
        elif probability <= self.config.exit_threshold:
            action = DecisionAction.EXIT
        else:
            action = DecisionAction.ABSTAIN
        contributions["regime_adjustment"] = regime_adjustment
        return EnsemblePrediction(
            timestamp=timestamp,
            asset=asset,
            probability_up=probability,
            confidence=confidence,
            disagreement=min(1.0, disagreement),
            action=action,
            contributions=contributions,
            ensemble_version=self.version,
        )
