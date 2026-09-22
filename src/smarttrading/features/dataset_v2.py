from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import pandas as pd
from pydantic import BaseModel, ConfigDict

from smarttrading.data.market_v2 import MarketContextSnapshot
from smarttrading.features.microstructure_v2 import (
    FEATURE_VERSION_V2,
    derivatives_features,
    microstructure_features,
)


class DatasetV2Metadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset_hash: str
    feature_version: str
    source_metadata: dict[str, str]
    coverage: dict[str, float]
    missingness: dict[str, float]
    quality: dict[str, float | int | None]
    target_included: bool = False


@dataclass(frozen=True)
class ResearchDatasetV2:
    X: pd.DataFrame
    metadata: DatasetV2Metadata


class DatasetV2Builder:
    def build(
        self,
        contexts: tuple[MarketContextSnapshot, ...],
        *,
        base_features: tuple[dict[str, float], ...] | None = None,
        source_metadata: dict[str, str] | None = None,
        quality: dict[str, float | int | None] | None = None,
    ) -> ResearchDatasetV2:
        base = base_features or tuple({} for _ in contexts)
        if len(base) != len(contexts):
            raise ValueError("base/context row mismatch")
        rows = [
            {
                **left,
                **microstructure_features(context),
                **derivatives_features(contexts[: index + 1]),
            }
            for index, (left, context) in enumerate(zip(base, contexts, strict=True))
        ]
        frame = pd.DataFrame(rows).reindex(sorted({key for row in rows for key in row}), axis=1)
        missing = {str(name): float(frame[name].isna().mean()) for name in frame.columns}
        coverage = {name: 1.0 - value for name, value in missing.items()}
        payload = {
            "version": FEATURE_VERSION_V2,
            "sources": source_metadata or {},
            "frame_json": frame.to_json(orient="records", double_precision=15),
            "times": [x.decision_time.isoformat() for x in contexts],
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return ResearchDatasetV2(
            frame,
            DatasetV2Metadata(
                dataset_hash=digest,
                feature_version=FEATURE_VERSION_V2,
                source_metadata=source_metadata or {},
                coverage=coverage,
                missingness=missing,
                quality=quality or {},
            ),
        )
