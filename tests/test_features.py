from decimal import Decimal

import numpy as np

from smarttrading.features.dataset import MLDatasetBuilder
from smarttrading.features.pipeline import CausalFeaturePipeline, FeatureConfig
from smarttrading.features.target import TargetConfig
from tests.helpers import bars_from_prices


def test_all_feature_families_are_causal() -> None:
    prices = [str(100 + index + (index % 7)) for index in range(100)]
    original = bars_from_prices(prices)
    changed = list(original)
    for index in range(61, len(changed)):
        changed[index] = changed[index].model_copy(
            update={
                "open": Decimal("10000"),
                "high": Decimal("10001"),
                "low": Decimal("9999"),
                "close": Decimal("10000"),
                "volume": Decimal("99999"),
            }
        )
    pipeline = CausalFeaturePipeline(FeatureConfig())
    first = pipeline.compute_frame(original).iloc[:61]
    second = pipeline.compute_frame(changed).iloc[:61]
    feature_columns = [name for name in first if name not in {"asset", "timeframe"}]
    for name in feature_columns:
        if name == "timestamp":
            assert first[name].equals(second[name])
        else:
            np.testing.assert_allclose(first[name], second[name], equal_nan=True)


def test_warmup_is_dropped_without_imputation_and_target_is_not_in_x() -> None:
    bars = bars_from_prices([str(100 + index + index % 3) for index in range(100)])
    dataset = MLDatasetBuilder(
        CausalFeaturePipeline(), TargetConfig(prediction_horizon=3, return_threshold=0)
    ).build(bars)
    assert len(dataset.X) < len(bars)
    assert not dataset.X.isna().any().any()
    assert all("target" not in name and "future" not in name for name in dataset.X.columns)
    assert len(dataset.X) == len(dataset.y) == len(dataset.timestamps)


def test_dataset_hash_is_reproducible(tmp_path: object) -> None:
    bars = bars_from_prices([str(100 + index + index % 5) for index in range(100)])
    builder = MLDatasetBuilder(CausalFeaturePipeline(), TargetConfig(prediction_horizon=2))
    first = builder.build(bars)
    second = builder.build(bars)
    assert first.metadata.dataset_hash == second.metadata.dataset_hash
