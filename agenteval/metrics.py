from __future__ import annotations

import math
from statistics import mean, pstdev


def accuracy(predicted: list[bool], truth: list[bool]) -> float:
    return sum(p == t for p, t in zip(predicted, truth)) / len(truth) if truth else float("nan")


def balanced_accuracy(predicted: list[bool], truth: list[bool]) -> float:
    positives = [p for p, t in zip(predicted, truth) if t]
    negatives = [p for p, t in zip(predicted, truth) if not t]
    parts = []
    if positives:
        parts.append(sum(positives) / len(positives))
    if negatives:
        parts.append(sum(not p for p in negatives) / len(negatives))
    return mean(parts) if parts else float("nan")


def cohen_kappa(predicted: list[bool], truth: list[bool]) -> float:
    n = len(truth)
    if n == 0:
        return float("nan")
    observed = accuracy(predicted, truth)
    p_yes = (sum(predicted) / n) * (sum(truth) / n)
    p_no = (1 - sum(predicted) / n) * (1 - sum(truth) / n)
    expected = p_yes + p_no
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)


def confusion(predicted: list[bool], truth: list[bool]) -> dict:
    return {
        "true_pass": sum(p and t for p, t in zip(predicted, truth)),
        "false_pass": sum(p and not t for p, t in zip(predicted, truth)),
        "true_fail": sum(not p and not t for p, t in zip(predicted, truth)),
        "false_fail": sum(not p and t for p, t in zip(predicted, truth)),
    }


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def flip_rate(runs: list[list[bool]]) -> float:
    varied = [len(set(r)) > 1 for r in runs if len(r) > 1]
    return sum(varied) / len(varied) if varied else float("nan")


def mean_std(runs: list[list[float]]) -> float:
    stds = [pstdev(r) for r in runs if len(r) > 1]
    return mean(stds) if stds else float("nan")


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))
