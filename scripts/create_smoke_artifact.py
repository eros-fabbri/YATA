from __future__ import annotations

import argparse
from pathlib import Path

from smarttrading.data.csv import load_bars_csv
from smarttrading.features.pipeline import CausalFeaturePipeline
from smarttrading.models.artifacts import ModelArtifact


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--probability", type=float, default=0.5)
    args = parser.parse_args()
    pipeline = CausalFeaturePipeline()
    features = pipeline.transform(load_bars_csv(args.dataset))
    if not features:
        raise ValueError("dataset is too short for feature warmup")
    artifact = ModelArtifact.create(
        model_name="smoke_constant",
        feature_version=pipeline.config.version,
        dataset_hash="SMOKE_ONLY_NOT_A_TRAINED_MODEL",
        training_start=features[0].timestamp.isoformat(),
        training_end=features[-1].timestamp.isoformat(),
        validation_metrics={},
        feature_names=tuple(features[-1].values),
        constant_probability=args.probability,
    )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    print(artifact.model_version)


if __name__ == "__main__":
    main()
