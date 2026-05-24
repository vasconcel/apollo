from dataclasses import dataclass, asdict


@dataclass
class ConfusionMatrix:
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0


@dataclass
class AuditMetrics:
    total_audited: int
    confusion_matrix: ConfusionMatrix
    precision: float
    recall: float
    f1_score: float
    cohens_kappa: float
    interpretation: str


def _safe_div(num: float, den: float) -> float:
    return num / den if den != 0 else 0.0


def compute_confusion_matrix(
    ai_decisions: list[str],   # "YES" | "NO"
    human_decisions: list[str],# "YES" | "NO"
) -> ConfusionMatrix:
    cm = ConfusionMatrix()
    for ai, hu in zip(ai_decisions, human_decisions):
        if ai == "YES" and hu == "YES":
            cm.tp += 1
        elif ai == "NO" and hu == "NO":
            cm.tn += 1
        elif ai == "YES" and hu == "NO":
            cm.fp += 1
        elif ai == "NO" and hu == "YES":
            cm.fn += 1
    return cm


def compute_metrics(
    ai_decisions: list[str],
    human_decisions: list[str],
) -> AuditMetrics:
    if len(ai_decisions) != len(human_decisions):
        raise ValueError(
            f"Length mismatch: ai={len(ai_decisions)} vs human={len(human_decisions)}"
        )

    total = len(ai_decisions)
    if total == 0:
        return AuditMetrics(
            total_audited=0,
            confusion_matrix=ConfusionMatrix(),
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            cohens_kappa=0.0,
            interpretation="No audited samples available.",
        )

    cm = compute_confusion_matrix(ai_decisions, human_decisions)
    s = cm.tp + cm.tn + cm.fp + cm.fn

    precision = _safe_div(cm.tp, cm.tp + cm.fp)
    recall = _safe_div(cm.tp, cm.tp + cm.fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    # Cohen's Kappa
    po = _safe_div(cm.tp + cm.tn, s)

    p_yes_ai = _safe_div(cm.tp + cm.fp, s)
    p_yes_human = _safe_div(cm.tp + cm.fn, s)
    p_no_ai = _safe_div(cm.tn + cm.fn, s)
    p_no_human = _safe_div(cm.tn + cm.fp, s)

    pe = (p_yes_ai * p_yes_human) + (p_no_ai * p_no_human)
    kappa = _safe_div(po - pe, 1 - pe)

    # Interpretation
    if kappa < 0:
        interp = "Worse than random (κ < 0)"
    elif kappa < 0.40:
        interp = "Poor agreement (κ < 0.40)"
    elif kappa < 0.60:
        interp = "Moderate agreement (0.40 ≤ κ < 0.60)"
    elif kappa < 0.80:
        interp = "Substantial agreement (0.60 ≤ κ < 0.80)"
    else:
        interp = "Almost perfect agreement (κ ≥ 0.80)"

    return AuditMetrics(
        total_audited=total,
        confusion_matrix=cm,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1_score=round(f1, 4),
        cohens_kappa=round(kappa, 4),
        interpretation=interp,
    )


def metrics_to_dict(m: AuditMetrics) -> dict:
    return {
        "total_audited": m.total_audited,
        "confusion_matrix": asdict(m.confusion_matrix),
        "precision": m.precision,
        "recall": m.recall,
        "f1_score": m.f1_score,
        "cohens_kappa": m.cohens_kappa,
        "interpretation": m.interpretation,
    }
