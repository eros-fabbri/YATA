from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

import numpy as np
import sklearn
from sklearn.calibration import calibration_curve
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from smarttrading.domain import Prediction
from smarttrading.features.dataset import MLDataset
from smarttrading.models.splitting import TemporalFold

ModelName = Literal["dummy", "logistic", "gradient_boosting"]


@dataclass(frozen=True)
class ClassificationMetrics:
    class_balance: float
    accuracy: float
    balanced_accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float | None
    pr_auc: float | None
    brier_score: float
    log_loss: float
    expected_calibration_error: float


@dataclass(frozen=True)
class ModelManifest:
    model_name: str
    model_version: str
    hyperparameters: dict[str, str | int | float]
    feature_names: tuple[str, ...]
    feature_version: str
    training_start: str
    training_end: str
    dataset_hash: str
    target_definition: str
    preprocessing: str
    sklearn_version: str
    seed: int
    feature_importance: dict[str, float]


@dataclass(frozen=True)
class FoldResult:
    fold: int
    predictions: tuple[Prediction, ...]
    y_true: tuple[int, ...]
    manifest: ModelManifest


@dataclass(frozen=True)
class WalkForwardResult:
    folds: tuple[FoldResult, ...]
    predictions: tuple[Prediction, ...]
    y_true: tuple[int, ...]
    metrics: ClassificationMetrics


def make_model(name: ModelName, seed: int) -> Pipeline:
    if name == "dummy":
        return Pipeline([("model", DummyClassifier(strategy="prior", random_state=seed))])
    if name == "logistic":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("model", LogisticRegression(max_iter=1000, random_state=seed, C=1.0)),
            ]
        )
    return Pipeline(
        [
            (
                "model",
                HistGradientBoostingClassifier(
                    max_iter=100, max_depth=3, learning_rate=0.05, random_state=seed
                ),
            )
        ]
    )


def classification_metrics(y: np.ndarray, probability: np.ndarray) -> ClassificationMetrics:
    predicted = (probability >= 0.5).astype(int)
    has_both = len(np.unique(y)) == 2
    pr_auc = None
    if has_both:
        precision_points, recall_points, _ = precision_recall_curve(y, probability)
        order = np.argsort(recall_points)
        pr_auc = float(np.trapezoid(precision_points[order], recall_points[order]))
    observed, forecast = calibration_curve(y, probability, n_bins=10, strategy="uniform")
    ece = float(np.mean(np.abs(observed - forecast))) if len(observed) else 0.0
    return ClassificationMetrics(
        class_balance=float(np.mean(y)),
        accuracy=float(accuracy_score(y, predicted)),
        balanced_accuracy=(
            float(balanced_accuracy_score(y, predicted))
            if has_both
            else float(accuracy_score(y, predicted))
        ),
        precision=float(precision_score(y, predicted, zero_division=0)),
        recall=float(recall_score(y, predicted, zero_division=0)),
        f1=float(f1_score(y, predicted, zero_division=0)),
        roc_auc=float(roc_auc_score(y, probability)) if has_both else None,
        pr_auc=pr_auc,
        brier_score=float(brier_score_loss(y, probability)),
        log_loss=float(log_loss(y, probability, labels=[0, 1])),
        expected_calibration_error=ece,
    )


def walk_forward_train(
    dataset: MLDataset, folds: list[TemporalFold], model_name: ModelName, seed: int = 0
) -> WalkForwardResult:
    results: list[FoldResult] = []
    all_probabilities: list[float] = []
    all_y: list[int] = []
    all_predictions: list[Prediction] = []
    for fold_number, fold in enumerate(folds):
        train = list(fold.train)
        validation = list(fold.validation)
        model = make_model(model_name, seed)
        model.fit(dataset.X.iloc[train], dataset.y[train])
        probabilities = model.predict_proba(dataset.X.iloc[validation])
        classes = model.named_steps["model"].classes_
        if len(classes) == 1:
            probability = np.full(len(validation), float(classes[0]))
        else:
            probability = probabilities[:, list(classes).index(1)]
        config = {
            "model": model_name,
            "params": model.get_params(deep=True),
            "features": dataset.metadata.feature_names,
            "train": [train[0], train[-1]],
            "dataset": dataset.metadata.dataset_hash,
            "seed": seed,
        }
        version = hashlib.sha256(
            json.dumps(config, sort_keys=True, default=str, separators=(",", ":")).encode()
        ).hexdigest()[:16]
        predictions = tuple(
            Prediction(
                timestamp=dataset.timestamps[index],
                asset=dataset.asset[index],
                horizon=dataset.metadata.target_definition,
                expected_return=float(dataset.future_return[train].mean()) * (2 * float(prob) - 1),
                probability_up=float(prob),
                confidence=abs(float(prob) - 0.5) * 2,
                model_name=model_name,
                model_version=version,
            )
            for index, prob in zip(validation, probability, strict=True)
        )
        importance: dict[str, float] = {}
        if model_name == "logistic":
            coefficients = model.named_steps["model"].coef_[0]
            importance = {
                name: float(value)
                for name, value in zip(dataset.metadata.feature_names, coefficients, strict=True)
            }
        manifest = ModelManifest(
            model_name=model_name,
            model_version=version,
            hyperparameters={"seed": seed},
            feature_names=dataset.metadata.feature_names,
            feature_version=dataset.metadata.feature_version,
            training_start=str(dataset.timestamps[train[0]]),
            training_end=str(dataset.timestamps[train[-1]]),
            dataset_hash=dataset.metadata.dataset_hash,
            target_definition=dataset.metadata.target_definition,
            preprocessing="StandardScaler(train-only)" if model_name == "logistic" else "none",
            sklearn_version=sklearn.__version__,
            seed=seed,
            feature_importance=importance,
        )
        results.append(FoldResult(fold_number, predictions, tuple(dataset.y[validation]), manifest))
        all_predictions.extend(predictions)
        all_probabilities.extend(float(item) for item in probability)
        all_y.extend(int(item) for item in dataset.y[validation])
    y_array = np.asarray(all_y)
    return WalkForwardResult(
        folds=tuple(results),
        predictions=tuple(all_predictions),
        y_true=tuple(all_y),
        metrics=classification_metrics(y_array, np.asarray(all_probabilities)),
    )
