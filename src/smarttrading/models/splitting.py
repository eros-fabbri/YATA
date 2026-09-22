from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalFold:
    train: tuple[int, ...]
    validation: tuple[int, ...]


def chronological_holdout(
    size: int, validation_size: int, horizon: int, embargo: int = 0
) -> TemporalFold:
    validation_start = size - validation_size
    train_end = validation_start - horizon - embargo
    if train_end <= 0 or validation_size <= 0:
        raise ValueError("insufficient rows for purged chronological holdout")
    return TemporalFold(tuple(range(train_end)), tuple(range(validation_start, size)))


def expanding_walk_forward(
    size: int,
    *,
    minimum_train_size: int,
    validation_size: int,
    step_size: int,
    horizon: int,
    embargo: int = 0,
    max_folds: int | None = None,
) -> list[TemporalFold]:
    if min(minimum_train_size, validation_size, step_size, horizon) <= 0 or embargo < 0:
        raise ValueError("split sizes and horizon must be positive; embargo cannot be negative")
    folds: list[TemporalFold] = []
    train_end = minimum_train_size
    while True:
        validation_start = train_end + horizon + embargo
        validation_end = validation_start + validation_size
        if validation_end > size or (max_folds is not None and len(folds) >= max_folds):
            break
        folds.append(
            TemporalFold(tuple(range(train_end)), tuple(range(validation_start, validation_end)))
        )
        train_end += step_size
    if not folds:
        raise ValueError("configuration produces no walk-forward folds")
    return folds


class SealedFinalHoldout:
    def __init__(self, development: tuple[int, ...], holdout: tuple[int, ...]) -> None:
        self.development = development
        self._holdout = holdout

    def __repr__(self) -> str:
        return "SealedFinalHoldout(final_test=SEALED)"

    def open(self, *, explicit_final_evaluation: bool = False) -> tuple[int, ...]:
        if not explicit_final_evaluation:
            raise PermissionError("final holdout is sealed; use explicit final evaluation")
        return self._holdout


def seal_final_holdout(size: int, fraction: float = 0.2) -> SealedFinalHoldout:
    if not 0 < fraction < 0.5:
        raise ValueError("final holdout fraction must be in (0, 0.5)")
    split = int(size * (1 - fraction))
    return SealedFinalHoldout(tuple(range(split)), tuple(range(split, size)))
