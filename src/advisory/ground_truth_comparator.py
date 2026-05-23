"""
Ground Truth Comparator Layer for APOLLO.

Enables optional evaluation mode: compares advisory outputs against
human-provided ground truth labels.

Computes:
  - Precision, Recall, F1 (per decision outcome)
  - Per-criterion accuracy
  - Confusion matrix

All functions are PURE and DETERMINISTIC.
Gracefully handles missing ground truth (returns None for metrics).
"""
from typing import Dict, List, Optional, Tuple


def _normalize_decision(decision: str) -> str:
    """Normalize decision string for comparison."""
    mapping = {
        "INCLUDE": "INCLUDE",
        "EXCLUDE": "EXCLUDE",
        "SKIP": "SKIP",
        "UNCERTAIN": "UNCERTAIN",
        "INSUFFICIENT_EVIDENCE": "UNCERTAIN",
        "CANNOT_DETERMINE": "UNCERTAIN",
        "UNAVAILABLE": "UNCERTAIN",
        "INSUFFICIENT_METADATA": "UNCERTAIN",
    }
    return mapping.get(decision.upper(), "UNCERTAIN")


def compute_confusion_matrix(
    advisory_decisions: List[str],
    ground_truth_decisions: List[str],
) -> Dict:
    """Compute confusion matrix comparing advisory decisions to ground truth.

    Decisions are normalized to INCLUDE, EXCLUDE, SKIP, UNCERTAIN before comparison.

    Args:
        advisory_decisions: List of decisions from advisory system
        ground_truth_decisions: List of human-provided decisions

    Returns:
        Dict with confusion matrix and derived metrics.
    """
    if not advisory_decisions or not ground_truth_decisions:
        return _empty_result()

    n = min(len(advisory_decisions), len(ground_truth_decisions))
    labels = ["INCLUDE", "EXCLUDE", "SKIP", "UNCERTAIN"]

    matrix = {pred: {actual: 0 for actual in labels} for pred in labels}
    for i in range(n):
        pred = _normalize_decision(advisory_decisions[i])
        actual = _normalize_decision(ground_truth_decisions[i])
        if pred in matrix and actual in matrix[pred]:
            matrix[pred][actual] += 1

    return {
        "confusion_matrix": matrix,
        "labels": labels,
        "count": n,
        "derived_metrics": _derive_metrics(matrix, labels),
    }


def _derive_metrics(
    matrix: Dict[str, Dict[str, int]],
    labels: List[str],
) -> Dict:
    """Derive precision, recall, F1 per label from confusion matrix."""
    metrics = {}
    for label in labels:
        tp = matrix.get(label, {}).get(label, 0)
        fp = sum(matrix.get(label, {}).get(l, 0) for l in labels if l != label)
        fn = sum(matrix.get(l, {}).get(label, 0) for l in labels if l != label)
        
        support = tp + fn
        if tp + fp == 0:
            precision = 1.0
        else:
            precision = tp / (tp + fp)
        recall = 1.0 if support == 0 else tp / support
        if support == 0 and fp == 0 and tp == 0:
            f1 = 1.0
        elif precision == 0.0 and recall == 0.0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / max(precision + recall, 1e-10)
        
        metrics[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": support,
        }

    # Macro averages
    avg_precision = sum(m["precision"] for m in metrics.values()) / len(metrics)
    avg_recall = sum(m["recall"] for m in metrics.values()) / len(metrics)
    avg_f1 = sum(m["f1"] for m in metrics.values()) / len(metrics)

    return {
        "per_label": metrics,
        "macro_avg": {
            "precision": round(avg_precision, 4),
            "recall": round(avg_recall, 4),
            "f1": round(avg_f1, 4),
        },
    }


def compute_per_criterion_accuracy(
    advisory_criteria: List[Dict],
    ground_truth_criteria: List[Dict],
) -> Dict:
    """Compute per-criterion accuracy comparing triggered criteria.

    Args:
        advisory_criteria: List of {criterion_id, satisfied} from advisory
        ground_truth_criteria: List of {criterion_id, satisfied} from human

    Returns:
        Dict with per-criterion accuracy and aggregate.
    """
    gt_map = {}
    for c in ground_truth_criteria:
        cid = c.get("criterion_id", c.get("id", ""))
        gt_map[cid] = c.get("satisfied", False)

    results = {}
    correct = 0
    total = 0
    for c in advisory_criteria:
        cid = c.get("criterion_id", c.get("id", ""))
        predicted = c.get("satisfied", False)
        if cid in gt_map:
            actual = gt_map[cid]
            match = predicted == actual
            results[cid] = {
                "predicted": predicted,
                "actual": actual,
                "correct": match,
            }
            if match:
                correct += 1
            total += 1

    return {
        "per_criterion": results,
        "accuracy": round(correct / max(total, 1), 4),
        "correct": correct,
        "total": total,
        "missing_ground_truth": len(advisory_criteria) - total,
    }


def compute_ground_truth_summary(
    advisory_decisions: List[str],
    ground_truth_decisions: List[str],
    advisory_criteria: Optional[List[Dict]] = None,
    ground_truth_criteria: Optional[List[Dict]] = None,
) -> Dict:
    """Compute full ground truth comparison summary.

    Args:
        advisory_decisions: List of decisions from advisory system
        ground_truth_decisions: List of human-provided decisions
        advisory_criteria: Optional list of criteria from advisory
        ground_truth_criteria: Optional list of criteria from human

    Returns:
        Dict with confusion matrix, derived metrics, and optional criterion accuracy.
    """
    confusion = compute_confusion_matrix(advisory_decisions, ground_truth_decisions)
    result: Dict = {
        "confusion_matrix": confusion["confusion_matrix"],
        "labels": confusion["labels"],
        "total_comparisons": confusion["count"],
        "derived_metrics": confusion["derived_metrics"],
    }

    if advisory_criteria and ground_truth_criteria:
        criterion_acc = compute_per_criterion_accuracy(advisory_criteria, ground_truth_criteria)
        result["criterion_accuracy"] = criterion_acc

    return result


def _empty_result() -> Dict:
    return {
        "confusion_matrix": {},
        "labels": [],
        "count": 0,
        "derived_metrics": {
            "per_label": {},
            "macro_avg": {"precision": 0.0, "recall": 0.0, "f1": 0.0},
        },
    }
