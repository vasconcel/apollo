"""
APOLLO Evaluation: Statistical Analysis Utilities

Provides confidence intervals, bootstrap estimation, repeated-run aggregation,
and variance analysis for publication-quality empirical evaluation.
"""

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple
import math
import random


@dataclass
class ConfidenceInterval:
    mean: float
    lower: float
    upper: float
    std_error: float
    confidence_level: float
    n: int

    def to_dict(self) -> dict:
        return {
            "mean": self.mean,
            "lower": self.lower,
            "upper": self.upper,
            "std_error": self.std_error,
            "confidence_level": self.confidence_level,
            "n": self.n,
        }


def _z_score(confidence_level: float) -> float:
    if confidence_level >= 0.99:
        return 2.576
    elif confidence_level >= 0.95:
        return 1.960
    elif confidence_level >= 0.90:
        return 1.645
    elif confidence_level >= 0.85:
        return 1.440
    else:
        return 1.282


def compute_confidence_interval(
    values: List[float],
    confidence_level: float = 0.95,
) -> ConfidenceInterval:
    n = len(values)
    if n == 0:
        return ConfidenceInterval(0.0, 0.0, 0.0, 0.0, confidence_level, 0)
    mean = sum(values) / n
    if n == 1:
        return ConfidenceInterval(mean, mean, mean, 0.0, confidence_level, 1)
    variance = sum((v - mean) ** 2 for v in values) / (n - 1)
    std_error = math.sqrt(variance / n)
    z = _z_score(confidence_level)
    margin = z * std_error
    return ConfidenceInterval(
        mean=mean,
        lower=mean - margin,
        upper=mean + margin,
        std_error=std_error,
        confidence_level=confidence_level,
        n=n,
    )


def bootstrap_metric(
    values: List[float],
    metric_fn: Callable[[List[float]], float],
    n_iterations: int = 1000,
    confidence_level: float = 0.95,
    seed: Optional[int] = None,
) -> ConfidenceInterval:
    if seed is not None:
        random.seed(seed)
    n = len(values)
    if n == 0:
        return ConfidenceInterval(0.0, 0.0, 0.0, 0.0, confidence_level, 0)
    bootstrap_stats: List[float] = []
    for _ in range(n_iterations):
        sample = [random.choice(values) for _ in range(n)]
        try:
            stat = metric_fn(sample)
            bootstrap_stats.append(stat)
        except (ZeroDivisionError, ValueError):
            continue
    if not bootstrap_stats:
        return ConfidenceInterval(0.0, 0.0, 0.0, 0.0, confidence_level, 0)
    bootstrap_stats.sort()
    lower_idx = max(0, int(n_iterations * (1 - confidence_level) / 2))
    upper_idx = min(len(bootstrap_stats) - 1, int(n_iterations * (1 + confidence_level) / 2))
    mean = sum(bootstrap_stats) / len(bootstrap_stats)
    variance = sum((s - mean) ** 2 for s in bootstrap_stats) / (len(bootstrap_stats) - 1) if len(bootstrap_stats) > 1 else 0.0
    return ConfidenceInterval(
        mean=mean,
        lower=bootstrap_stats[lower_idx],
        upper=bootstrap_stats[upper_idx],
        std_error=math.sqrt(variance),
        confidence_level=confidence_level,
        n=n,
    )


def bootstrap_classification_metrics(
    apollo_decisions: List[str],
    gold_decisions: List[str],
    n_iterations: int = 1000,
    confidence_level: float = 0.95,
    seed: Optional[int] = None,
) -> dict:
    from src.evaluation.metrics import MetricsComputer

    def compute_f1(apollo_sample: List[str], gold_sample: List[str]) -> float:
        cm = MetricsComputer.compute_classification(apollo_sample, gold_sample)
        return cm.f1_score

    n = len(apollo_decisions)
    indices = list(range(n))
    if seed is not None:
        random.seed(seed)

    f1_values: List[float] = []
    recall_values: List[float] = []
    precision_values: List[float] = []
    specificity_values: List[float] = []

    for _ in range(n_iterations):
        sample_idx = [random.choice(indices) for _ in range(n)]
        apollo_sample = [apollo_decisions[i] for i in sample_idx]
        gold_sample = [gold_decisions[i] for i in sample_idx]
        try:
            cm = MetricsComputer.compute_classification(apollo_sample, gold_sample)
            f1_values.append(cm.f1_score)
            recall_values.append(cm.recall)
            precision_values.append(cm.precision)
            specificity_values.append(cm.specificity)
        except (ZeroDivisionError, ValueError):
            continue

    def _to_ci(vals: List[float]) -> dict:
        if not vals:
            return {"mean": 0.0, "lower": 0.0, "upper": 0.0, "std_error": 0.0}
        vals.sort()
        li = max(0, int(n_iterations * (1 - confidence_level) / 2))
        ui = min(len(vals) - 1, int(n_iterations * (1 + confidence_level) / 2))
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1) if len(vals) > 1 else 0.0
        return {
            "mean": mean,
            "lower": vals[li],
            "upper": vals[ui],
            "std_error": math.sqrt(var),
        }

    return {
        "f1_score": _to_ci(f1_values),
        "recall": _to_ci(recall_values),
        "precision": _to_ci(precision_values),
        "specificity": _to_ci(specificity_values),
        "n_iterations": n_iterations,
        "confidence_level": confidence_level,
    }


def aggregate_runs(run_results: List[dict]) -> dict:
    if not run_results:
        return {}
    aggregated: dict = {}
    f1_scores = [
        r.get("evaluation_metrics", {}).get("classification", {}).get("f1_score", 0.0)
        for r in run_results
    ]
    recalls = [
        r.get("evaluation_metrics", {}).get("classification", {}).get("recall", 0.0)
        for r in run_results
    ]
    precisions = [
        r.get("evaluation_metrics", {}).get("classification", {}).get("precision", 0.0)
        for r in run_results
    ]
    coverages = [
        r.get("evaluation_metrics", {}).get("autonomy", {}).get("autonomous_coverage", 0.0)
        for r in run_results
    ]
    for name, values in [
        ("f1_score", f1_scores),
        ("recall", recalls),
        ("precision", precisions),
        ("autonomous_coverage", coverages),
    ]:
        if values:
            ci = compute_confidence_interval(values)
            aggregated[name] = ci.to_dict()
    n = len(run_results)
    if f1_scores:
        variance = sum((f - sum(f1_scores) / n) ** 2 for f in f1_scores) / (n - 1) if n > 1 else 0.0
        aggregated["variance"] = {"f1_score": variance, "n_runs": n}
    return aggregated


def compare_threshold_pairs(
    results_a: List[float],
    results_b: List[float],
    n_iterations: int = 1000,
    seed: Optional[int] = None,
) -> dict:
    if seed is not None:
        random.seed(seed)
    n = len(results_a)
    m = len(results_b)
    if n == 0 or m == 0:
        return {"effect_size": 0.0, "p_value_estimate": 1.0, "superior": False}
    mean_a = sum(results_a) / n
    mean_b = sum(results_b) / m
    pooled_std = math.sqrt(
        (sum((a - mean_a) ** 2 for a in results_a) + sum((b - mean_b) ** 2 for b in results_b))
        / (n + m - 2)
    ) if (n + m) > 2 else 0.0
    effect_size = (mean_a - mean_b) / pooled_std if pooled_std > 0 else 0.0
    combined = results_a + results_b
    observed_diff = mean_a - mean_b
    count_extreme = 0
    for _ in range(n_iterations):
        random.shuffle(combined)
        perm_a = combined[:n]
        perm_b = combined[n:]
        perm_diff = (sum(perm_a) / n) - (sum(perm_b) / m)
        if abs(perm_diff) >= abs(observed_diff):
            count_extreme += 1
    p_estimate = count_extreme / n_iterations
    return {
        "mean_a": mean_a,
        "mean_b": mean_b,
        "observed_difference": observed_diff,
        "effect_size": effect_size,
        "p_value_estimate": p_estimate,
        "superior": observed_diff > 0 and p_estimate < 0.05,
    }
