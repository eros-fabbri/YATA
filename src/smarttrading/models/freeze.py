from __future__ import annotations

import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from smarttrading.data.csv import load_bars_csv
from smarttrading.features.dataset import MLDatasetBuilder
from smarttrading.features.pipeline import CausalFeaturePipeline
from smarttrading.features.target import TargetConfig
from smarttrading.models.artifacts import ModelArtifact
from smarttrading.models.splitting import chronological_holdout, seal_final_holdout
from smarttrading.models.training import ModelName, classification_metrics, make_model


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "uncommitted"


def freeze_real_artifact(
    dataset_path: str | Path,
    *,
    model_name: ModelName,
    asset: str,
    output: str | Path,
    seed: int = 17,
    horizon: int = 6,
    return_threshold: float = 0.001,
    final_fraction: float = 0.2,
    validation_fraction: float = 0.2,
) -> ModelArtifact:
    """Fit a frozen PAPER artifact without opening the final holdout."""
    bars = load_bars_csv(dataset_path)
    target = TargetConfig(prediction_horizon=horizon, return_threshold=return_threshold)
    dataset = MLDatasetBuilder(CausalFeaturePipeline(), target).build(bars)
    sealed = seal_final_holdout(len(dataset.X), final_fraction)
    development = list(sealed.development)
    validation_size = max(30, int(len(development) * validation_fraction))
    split = chronological_holdout(len(development), validation_size, horizon, embargo=1)
    train = [development[index] for index in split.train]
    validation = [development[index] for index in split.validation]
    validation_model = make_model(model_name, seed)
    validation_model.fit(dataset.X.iloc[train], dataset.y[train])
    probability = np.asarray(validation_model.predict_proba(dataset.X.iloc[validation]))[:, 1]
    metrics = classification_metrics(dataset.y[validation], probability)
    final_model = make_model(model_name, seed)
    final_model.fit(dataset.X.iloc[development], dataset.y[development])
    encoded, estimator_hash = ModelArtifact.serialize_estimator(final_model)
    public_name = "gradient" if model_name == "gradient_boosting" else model_name
    slug = asset.split("/")[0].lower()
    artifact = ModelArtifact.create(
        model_name=f"{public_name}-{slug}",
        feature_version=dataset.metadata.feature_version,
        dataset_hash=dataset.metadata.dataset_hash,
        training_start=dataset.timestamps[development[0]].isoformat(),
        training_end=dataset.timestamps[development[-1]].isoformat(),
        validation_metrics=asdict(metrics),
        feature_names=dataset.metadata.feature_names,
        asset=asset,
        timeframe="1h",
        target_configuration=target.model_dump(),
        preprocessing_configuration={
            "pipeline": "StandardScaler+LogisticRegression"
            if model_name == "logistic"
            else "HistGradientBoostingClassifier",
            "fit_scope": "development_prefix_only",
            "final_holdout": "SEALED",
        },
        hyperparameters={
            key: value
            for key, value in final_model.get_params(deep=True).items()
            if isinstance(value, (str, int, float, bool)) or value is None
        },
        seed=seed,
        trained_at=datetime.now(UTC).isoformat(),
        calibration={
            "method": "none",
            "expected_calibration_error": metrics.expected_calibration_error,
            "source": "purged_development_validation",
        },
        code_revision=_git_revision(),
        estimator_b64=encoded,
        estimator_sha256=estimator_hash,
    )
    target_path = Path(output)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    return artifact
