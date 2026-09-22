from __future__ import annotations

import hashlib
import json
import math
import pickle
import sqlite3
from base64 import b64decode, b64encode
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pandas import DataFrame
from pydantic import BaseModel, ConfigDict, Field


class ModelStatus(StrEnum):
    CANDIDATE = "candidate"
    PAPER = "paper"
    RETIRED = "retired"


class ModelArtifact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    model_name: str
    model_version: str
    feature_version: str
    dataset_hash: str
    training_start: str
    training_end: str
    validation_metrics: dict[str, float | None]
    feature_names: tuple[str, ...]
    asset: str | None = None
    timeframe: str = "1h"
    target_configuration: dict[str, object] = {}
    preprocessing_configuration: dict[str, object] = {}
    hyperparameters: dict[str, object] = {}
    seed: int = 0
    trained_at: str | None = None
    calibration: dict[str, object] = {}
    code_revision: str = "unknown"
    coefficients: tuple[float, ...] = ()
    intercept: float = 0.0
    constant_probability: float | None = Field(default=None, ge=0, le=1)
    estimator_b64: str | None = None
    estimator_sha256: str | None = None

    @classmethod
    def create(cls, **values: object) -> ModelArtifact:
        payload = dict(values)
        payload.pop("model_version", None)
        candidate = cls.model_validate({"model_version": "", **payload})
        digest_payload = candidate.model_dump(exclude={"model_version"})
        version = hashlib.sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        return candidate.model_copy(update={"model_version": version})

    def predict_probability(self, values: dict[str, float]) -> float:
        if tuple(sorted(values)) != tuple(sorted(self.feature_names)):
            raise ValueError("artifact feature names mismatch")
        if self.constant_probability is not None:
            return self.constant_probability
        if self.estimator_b64 is not None:
            payload = b64decode(self.estimator_b64)
            if hashlib.sha256(payload).hexdigest() != self.estimator_sha256:
                raise ValueError("serialized estimator hash is invalid")
            estimator = pickle.loads(payload)
            row = DataFrame(
                [[values[name] for name in self.feature_names]], columns=self.feature_names
            )
            return float(estimator.predict_proba(row)[0][1])
        score = self.intercept + sum(
            coefficient * values[name]
            for name, coefficient in zip(self.feature_names, self.coefficients, strict=True)
        )
        return 1 / (1 + math.exp(-max(-50.0, min(50.0, score))))

    @staticmethod
    def serialize_estimator(estimator: object) -> tuple[str, str]:
        payload = pickle.dumps(estimator, protocol=pickle.HIGHEST_PROTOCOL)
        return b64encode(payload).decode("ascii"), hashlib.sha256(payload).hexdigest()

    @classmethod
    def load(cls, path: str | Path, expected_feature_version: str) -> ModelArtifact:
        artifact = cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
        digest_payload = artifact.model_dump(exclude={"model_version"})
        expected_version = hashlib.sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        if artifact.model_version != expected_version:
            raise ValueError("model artifact version/hash is invalid")
        if artifact.feature_version != expected_feature_version:
            raise ValueError("model artifact feature version mismatch")
        return artifact


class ModelRegistry:
    def __init__(self, database: str | Path) -> None:
        self._connection = sqlite3.connect(str(database))
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS models("
            "model_version TEXT PRIMARY KEY,status TEXT NOT NULL,"
            "payload TEXT NOT NULL,promoted_at TEXT)"
        )
        self._connection.commit()

    def register(self, artifact: ModelArtifact) -> None:
        self._connection.execute(
            "INSERT OR IGNORE INTO models VALUES(?,?,?,NULL)",
            (artifact.model_version, ModelStatus.CANDIDATE, artifact.model_dump_json()),
        )
        self._connection.commit()

    def promote_to_paper(self, model_version: str) -> None:
        self._connection.execute(
            "UPDATE models SET status=?,promoted_at=? WHERE model_version=?",
            (ModelStatus.PAPER, datetime.now(UTC).isoformat(), model_version),
        )
        self._connection.commit()

    def status(self, model_version: str) -> ModelStatus:
        row = self._connection.execute(
            "SELECT status FROM models WHERE model_version=?", (model_version,)
        ).fetchone()
        if row is None:
            raise KeyError(model_version)
        return ModelStatus(row[0])
