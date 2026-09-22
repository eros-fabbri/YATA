from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from smarttrading.domain import Bar, Prediction, Signal, SignalDirection


class PredictionStrategyConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    buy_probability_threshold: float = Field(default=0.58, gt=0.5, lt=1)
    exit_probability_threshold: float = Field(default=0.48, gt=0, lt=0.5)
    estimated_round_trip_cost: float = Field(default=0.001, ge=0)
    safety_margin: float = Field(default=0.0005, ge=0)

    @model_validator(mode="after")
    def ordered_thresholds(self) -> PredictionStrategyConfig:
        if self.exit_probability_threshold >= self.buy_probability_threshold:
            raise ValueError("exit threshold must be below buy threshold")
        return self


class PredictionStrategy:
    name = "ml_prediction"
    version = "1.0"

    def __init__(
        self, predictions: Sequence[Prediction], config: PredictionStrategyConfig | None = None
    ) -> None:
        self.config = config or PredictionStrategyConfig()
        self._predictions = {item.timestamp: item for item in predictions}
        versions = sorted({item.model_version for item in predictions})
        self.version = "+".join(versions)
        self._long = False

    def on_bar(self, history: Sequence[Bar], predictions: Sequence[Prediction] = ()) -> Signal:
        del predictions
        bar = history[-1]
        prediction = self._predictions.get(bar.timestamp)
        if prediction is None:
            direction = SignalDirection.HOLD
            confidence = 0.0
            rationale: dict[str, str | float | int] = {"prediction": "unavailable"}
        else:
            required_edge = self.config.estimated_round_trip_cost + self.config.safety_margin
            if (
                prediction.probability_up >= self.config.buy_probability_threshold
                and prediction.expected_return > required_edge
            ):
                self._long = True
            elif prediction.probability_up <= self.config.exit_probability_threshold:
                self._long = False
            direction = SignalDirection.LONG if self._long else SignalDirection.FLAT
            confidence = prediction.confidence
            rationale = {
                "probability_up": prediction.probability_up,
                "expected_return": prediction.expected_return,
                "model_version": prediction.model_version,
                "required_edge": required_edge,
            }
        return Signal(
            timestamp=bar.timestamp,
            asset=bar.asset,
            strategy=self.name,
            direction=direction,
            strength=confidence,
            confidence=confidence,
            rationale=rationale,
        )
