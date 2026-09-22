from __future__ import annotations

import math
from collections.abc import Sequence


def population_stability_index(
    reference: Sequence[float], current: Sequence[float], bins: int = 10
) -> float:
    if not reference or not current or bins < 2:
        raise ValueError("PSI requires non-empty samples and at least two bins")
    ordered = sorted(reference)
    boundaries = [
        ordered[min(len(ordered) - 1, int(len(ordered) * index / bins))] for index in range(1, bins)
    ]

    def proportions(values: Sequence[float]) -> list[float]:
        counts = [0] * bins
        for value in values:
            bucket = sum(value > boundary for boundary in boundaries)
            counts[bucket] += 1
        return [max(count / len(values), 1e-6) for count in counts]

    expected, actual = proportions(reference), proportions(current)
    return sum(
        (actual_value - expected_value) * math.log(actual_value / expected_value)
        for expected_value, actual_value in zip(expected, actual, strict=True)
    )


def ks_statistic(reference: Sequence[float], current: Sequence[float]) -> float:
    if not reference or not current:
        raise ValueError("KS requires non-empty samples")
    points = sorted(set(reference) | set(current))
    return max(
        abs(
            sum(value <= point for value in reference) / len(reference)
            - sum(value <= point for value in current) / len(current)
        )
        for point in points
    )


def calibration_degradation(
    reference_brier: float,
    labels: Sequence[int],
    probabilities: Sequence[float],
    *,
    minimum_labels: int = 30,
) -> float | None:
    if len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must have equal length")
    if len(labels) < minimum_labels:
        return None
    current_brier = sum(
        (probability - label) ** 2 for label, probability in zip(labels, probabilities, strict=True)
    ) / len(labels)
    return current_brier - reference_brier


def class_balance_change(reference: Sequence[int], current: Sequence[int]) -> float:
    if not reference or not current:
        raise ValueError("class-balance drift requires non-empty labels")
    return sum(current) / len(current) - sum(reference) / len(reference)
