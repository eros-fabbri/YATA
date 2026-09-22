from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict

from smarttrading.data.manifest import build_manifest
from smarttrading.domain import Bar
from smarttrading.features.pipeline import CausalFeaturePipeline
from smarttrading.features.target import TargetConfig, future_returns


class MLDatasetMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    dataset_hash: str
    source_dataset_hash: str
    feature_version: str
    target_definition: str
    start: str
    end: str
    feature_names: tuple[str, ...]
    rows: int


@dataclass(frozen=True)
class MLDataset:
    X: pd.DataFrame
    y: np.ndarray
    future_return: np.ndarray
    timestamps: tuple[datetime, ...]
    asset: tuple[str, ...]
    metadata: MLDatasetMetadata

    def export(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame = self.X.copy()
        frame.insert(0, "timestamp", self.timestamps)
        frame.insert(1, "asset", self.asset)
        frame["target"] = self.y
        frame["future_return"] = self.future_return
        frame.to_parquet(target, index=False)
        target.with_suffix(".metadata.json").write_text(
            self.metadata.model_dump_json(indent=2), encoding="utf-8"
        )


class MLDatasetBuilder:
    def __init__(self, features: CausalFeaturePipeline, target: TargetConfig) -> None:
        self.features = features
        self.target = target

    def build(self, bars: Sequence[Bar]) -> MLDataset:
        feature_sets = self.features.transform(bars)
        if not feature_sets:
            raise ValueError("no complete feature rows after warmup")
        returns = future_returns(bars, self.target)
        target_by_timestamp = {
            bar.timestamp: value
            for bar, value in zip(bars, returns, strict=True)
            if pd.notna(value)
        }
        usable = [item for item in feature_sets if item.timestamp in target_by_timestamp]
        if not usable:
            raise ValueError("no rows have both complete features and targets")
        names = tuple(sorted(usable[0].values))
        if any("target" in name or "future" in name for name in names):
            raise ValueError("target-like columns are forbidden in X")
        X = pd.DataFrame([{name: item.values[name] for name in names} for item in usable])
        raw_returns = np.asarray(
            [target_by_timestamp[item.timestamp] for item in usable], dtype=float
        )
        y = (raw_returns > self.target.return_threshold).astype(np.int64)
        source_hash = build_manifest(bars).sha256
        digest_payload = {
            "source": source_hash,
            "feature_version": self.features.config.version,
            "target": self.target.model_dump(),
            "timestamps": [item.timestamp.isoformat() for item in usable],
            "X": X.to_dict(orient="list"),
            "y": y.tolist(),
        }
        digest = hashlib.sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        metadata = MLDatasetMetadata(
            dataset_hash=digest,
            source_dataset_hash=source_hash,
            feature_version=self.features.config.version,
            target_definition=self.target.definition,
            start=usable[0].timestamp.isoformat(),
            end=usable[-1].timestamp.isoformat(),
            feature_names=names,
            rows=len(usable),
        )
        return MLDataset(
            X=X,
            y=y,
            future_return=raw_returns,
            timestamps=tuple(item.timestamp for item in usable),
            asset=tuple(item.asset for item in usable),
            metadata=metadata,
        )
