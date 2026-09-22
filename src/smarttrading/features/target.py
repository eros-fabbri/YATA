from __future__ import annotations

from collections.abc import Sequence

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from smarttrading.domain import Bar


class TargetConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    prediction_horizon: int = Field(default=6, ge=1)
    return_threshold: float = 0.001

    @property
    def definition(self) -> str:
        return f"future_return_{self.prediction_horizon}>{self.return_threshold}"


def future_returns(bars: Sequence[Bar], config: TargetConfig) -> pd.Series:
    close = pd.Series([float(bar.close) for bar in bars])
    return close.shift(-config.prediction_horizon) / close - 1
