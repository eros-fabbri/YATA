from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from pathlib import Path

from smarttrading.config import load_settings
from smarttrading.data.csv import load_bars_csv
from smarttrading.data.realtime import CandleEvent
from smarttrading.models.artifacts import ModelArtifact
from smarttrading.models.ensemble import EnsembleConfig, WeightedEnsemble
from smarttrading.paper.engine import PaperTradingEngine
from smarttrading.paper.forward import FrozenExperimentConfig
from smarttrading.paper.persistence import PaperStore

ARTIFACTS = (
    "models/forward-v1/logistic-btc.json",
    "models/forward-v1/gradient-btc.json",
    "models/forward-v1/logistic-eth.json",
    "models/forward-v1/gradient-eth.json",
)


def main() -> None:
    config = FrozenExperimentConfig.model_validate_json(
        Path("config/forward_v1.json").read_text(encoding="utf-8")
    )
    artifacts = tuple(ModelArtifact.load(path, config.feature_version) for path in ARTIFACTS)
    versions = tuple(artifact.model_version for artifact in artifacts)
    if versions != config.artifact_versions:
        raise ValueError("frozen artifact versions do not match config")
    settings = load_settings()
    ensemble = WeightedEnsemble(
        EnsembleConfig(weights=config.ensemble_weights, **config.thresholds)
    )
    shadows = config.shadow_strategies
    btc = load_bars_csv("data/btc_usdt_1h_2025-09_2026-09.csv")[-50:]
    eth = load_bars_csv("data/eth_usdt_1h_2025-09_2026-09.csv")[-50:]
    with tempfile.TemporaryDirectory(prefix="smarttrading-forward-v1-") as directory:
        database = Path(directory) / "dry-run.db"
        store = PaperStore(database)
        engine = PaperTradingEngine(
            settings,
            store,
            artifacts,
            ensemble,
            shadow_names=shadows,
            experiment=config,
            report_root=str(Path(directory) / "reports"),
        )
        engine.warmup(sorted([*btc[:-1], *eth[:-1]], key=lambda bar: bar.timestamp))
        records = []
        for bar in (btc[-1], eth[-1]):
            records.append(
                engine.process(
                    CandleEvent(
                        event_id=f"dry-run:{bar.asset}:{bar.timestamp.isoformat()}",
                        bar=bar,
                        closed=True,
                        received_at=bar.timestamp + timedelta(hours=1),
                    )
                )
            )
        before = {
            "decisions": len(store.events("decision")),
            "predictions": len(store.events("forward_prediction")),
            "fills": len(store.events("fill")),
        }
        store.close()
        recovered_store = PaperStore(database)
        PaperTradingEngine(
            settings,
            recovered_store,
            artifacts,
            ensemble,
            shadow_names=shadows,
            experiment=config,
            report_root=str(Path(directory) / "reports"),
        )
        after = {
            "decisions": len(recovered_store.events("decision")),
            "predictions": len(recovered_store.events("forward_prediction")),
            "fills": len(recovered_store.events("fill")),
        }
        if before != after:
            raise AssertionError("restart changed durable event counts")
        modified = config.model_copy(
            update={"thresholds": {**config.thresholds, "buy_threshold": 0.61}}
        )
        lock_rejected = False
        try:
            PaperTradingEngine(
                settings,
                recovered_store,
                artifacts,
                ensemble,
                experiment=modified,
            )
        except ValueError:
            lock_rejected = True
        if not lock_rejected:
            raise AssertionError("experiment lock accepted a modified threshold")
        print(
            json.dumps(
                {
                    "experiment_id": config.experiment_id,
                    "artifact_versions": versions,
                    "feature_version": config.feature_version,
                    "decision_actions": [
                        record.decision if record is not None else None for record in records
                    ],
                    "restart_counts_stable": before == after,
                    "modified_config_rejected": lock_rejected,
                    "final_holdout": "SEALED",
                },
                indent=2,
                default=str,
            )
        )
        recovered_store.close()


if __name__ == "__main__":
    main()
