"""
APOLLO Evaluation: Error Taxonomy System

Classifies screening errors into qualitative categories
for research publication and systematic error analysis.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional


class ErrorCategory(str, Enum):
    KEYWORD_OVERLAP_FALSE_POSITIVE = "keyword_overlap_false_positive"
    WEAK_METHODOLOGICAL_GROUNDING = "weak_methodological_grounding"
    VAGUE_ABSTRACT = "vague_abstract"
    DOMAIN_MISMATCH = "domain_mismatch"
    POPULATION_MISMATCH = "population_mismatch"
    INSUFFICIENT_METADATA = "insufficient_metadata"
    SPECULATIVE_INFERENCE = "speculative_inference"
    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    CONFIDENCE_MISCALIBRATION = "confidence_miscalibration"
    UNCERTAIN_COLLAPSE = "uncertain_collapse"
    AUTONOMY_OVERRIDE = "autonomy_override"
    EVIDENCE_EXTRACTION_FAILURE = "evidence_extraction_failure"
    CRITERION_MISAPPLICATION = "criterion_misapplication"
    HALLUCINATED_EVIDENCE = "hallucinated_evidence"
    ABSTRACTION_ERROR = "abstraction_error"
    UNKNOWN = "unknown"


ERROR_SEVERITY: Dict[ErrorCategory, str] = {
    ErrorCategory.KEYWORD_OVERLAP_FALSE_POSITIVE: "medium",
    ErrorCategory.WEAK_METHODOLOGICAL_GROUNDING: "medium",
    ErrorCategory.VAGUE_ABSTRACT: "low",
    ErrorCategory.DOMAIN_MISMATCH: "high",
    ErrorCategory.POPULATION_MISMATCH: "high",
    ErrorCategory.INSUFFICIENT_METADATA: "low",
    ErrorCategory.SPECULATIVE_INFERENCE: "high",
    ErrorCategory.CONTRADICTORY_EVIDENCE: "medium",
    ErrorCategory.CONFIDENCE_MISCALIBRATION: "medium",
    ErrorCategory.UNCERTAIN_COLLAPSE: "high",
    ErrorCategory.AUTONOMY_OVERRIDE: "medium",
    ErrorCategory.EVIDENCE_EXTRACTION_FAILURE: "medium",
    ErrorCategory.CRITERION_MISAPPLICATION: "high",
    ErrorCategory.HALLUCINATED_EVIDENCE: "critical",
    ErrorCategory.ABSTRACTION_ERROR: "low",
    ErrorCategory.UNKNOWN: "medium",
}


ERROR_DESCRIPTIONS: Dict[ErrorCategory, str] = {
    ErrorCategory.KEYWORD_OVERLAP_FALSE_POSITIVE: (
        "Paper uses domain keywords (e.g. 'software', 'AI', 'ML') "
        "but addresses a completely different research question. "
        "APOLLO confuses topical keyword overlap for true relevance."
    ),
    ErrorCategory.WEAK_METHODOLOGICAL_GROUNDING: (
        "Paper is topically relevant but lacks methodological rigor "
        "(no empirical data, opinion piece, insufficient sample). "
        "APOLLO failed to detect weak methodology."
    ),
    ErrorCategory.VAGUE_ABSTRACT: (
        "Abstract is ambiguous, poorly written, or lacks sufficient detail "
        "for confident classification. APOLLO should have abstained."
    ),
    ErrorCategory.DOMAIN_MISMATCH: (
        "Research domain does not match the systematic review scope. "
        "E.g. medical AI paper classified into SE review."
    ),
    ErrorCategory.POPULATION_MISMATCH: (
        "Study population does not match review inclusion criteria. "
        "E.g. professional developers vs students."
    ),
    ErrorCategory.INSUFFICIENT_METADATA: (
        "Missing critical metadata (no abstract, no year, no authors). "
        "APOLLO attempted classification without sufficient information."
    ),
    ErrorCategory.SPECULATIVE_INFERENCE: (
        "APOLLO made an unsupported logical leap, inferring relevance "
        "without textual evidence in the available metadata."
    ),
    ErrorCategory.CONTRADICTORY_EVIDENCE: (
        "Paper contains evidence supporting both inclusion and exclusion. "
        "APOLLO resolved ambiguity incorrectly."
    ),
    ErrorCategory.CONFIDENCE_MISCALIBRATION: (
        "Confidence score does not reflect actual decision quality. "
        "High confidence on wrong decisions or low confidence on correct ones."
    ),
    ErrorCategory.UNCERTAIN_COLLAPSE: (
        "APOLLO produced a definitive INCLUDE/EXCLUDE decision when "
        "it should have abstained (UNCERTAIN). Indicates confidence inflation."
    ),
    ErrorCategory.AUTONOMY_OVERRIDE: (
        "APOLLO autonomously routed a decision that should have "
        "required human review. Threshold too aggressive."
    ),
    ErrorCategory.EVIDENCE_EXTRACTION_FAILURE: (
        "APOLLO failed to extract relevant evidence from the abstract "
        "that would have supported a different decision."
    ),
    ErrorCategory.CRITERION_MISAPPLICATION: (
        "APOLLO applied the wrong criterion or misjudged criterion satisfaction. "
        "E.g. marking a criterion as satisfied when evidence contradicts."
    ),
    ErrorCategory.HALLUCINATED_EVIDENCE: (
        "APOLLO cited evidence not present in the abstract or metadata. "
        "Critical safety concern for autonomous screening."
    ),
    ErrorCategory.ABSTRACTION_ERROR: (
        "APOLLO correctly identified topic relevance but abstracted "
        "at the wrong level of specificity for the protocol."
    ),
    ErrorCategory.UNKNOWN: (
        "Error could not be classified into a specific category."
    ),
}


@dataclass
class ClassifiedError:
    article_id: str
    apollo_decision: str
    gold_decision: str
    confidence: float
    categories: List[ErrorCategory]
    severity: str
    description: str
    rationale: str
    evidence_snippet: str = ""

    def to_dict(self) -> Dict:
        return {
            "article_id": self.article_id,
            "apollo_decision": self.apollo_decision,
            "gold_decision": self.gold_decision,
            "confidence": self.confidence,
            "categories": [c.value for c in self.categories],
            "severity": self.severity,
            "description": self.description,
            "rationale": self.rationale,
            "evidence_snippet": self.evidence_snippet,
        }


class ErrorClassifier:
    """Classifies screening errors using decision-level heuristics."""

    @staticmethod
    def classify(
        article_id: str,
        apollo_decision: str,
        gold_decision: str,
        confidence: float,
        justification: str = "",
        triggered_criteria: Optional[List[str]] = None,
        abstract: str = "",
        title: str = "",
        uncertainty_reasoning: str = "",
        domain_alignment_reasoning: str = "",
        topic_relevance: Optional[Dict[str, float]] = None,
        grounding_evidence: Optional[List[str]] = None,
    ) -> ClassifiedError:
        triggered_criteria = triggered_criteria or []
        grounding_evidence = grounding_evidence or []
        topic_relevance = topic_relevance or {}
        apollo_upper = apollo_decision.upper().strip() if apollo_decision else ""
        gold_upper = gold_decision.upper().strip() if gold_decision else ""
        categories: List[ErrorCategory] = []
        rationale_parts: List[str] = []
        apollo_include = apollo_upper in ("INCLUDE", "AUTO_INCLUDE")
        gold_include = gold_upper in ("INCLUDE", "AUTO_INCLUDE")
        apollo_exclude = apollo_upper in ("EXCLUDE", "AUTO_EXCLUDE")
        is_false_positive = apollo_include and not gold_include
        is_false_negative = apollo_exclude and gold_include
        is_uncertain_collapse = apollo_upper in ("INCLUDE", "EXCLUDE") and gold_upper in (
            "UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE"
        )

        if is_uncertain_collapse:
            categories.append(ErrorCategory.UNCERTAIN_COLLAPSE)
            rationale_parts.append(
                f"APOLLO produced {apollo_decision} but gold standard is {gold_decision}; "
                "model made definitive decision where abstention was appropriate"
            )

        domain = topic_relevance.get("domain_relevance_score", 0.5)
        rq_align = topic_relevance.get("rq_alignment_strength", 0.5)
        if is_false_positive and domain < 0.3:
            categories.append(ErrorCategory.DOMAIN_MISMATCH)
            rationale_parts.append(
                f"Low domain relevance ({domain:.2f}) despite INCLUDE decision"
            )
        if is_false_negative and gold_include and rq_align < 0.3:
            categories.append(ErrorCategory.DOMAIN_MISMATCH)
            rationale_parts.append(
                f"Low RQ alignment ({rq_align:.2f}) but gold standard says INCLUDE"
            )

        if is_false_positive and domain >= 0.5 and rq_align < 0.4:
            categories.append(ErrorCategory.KEYWORD_OVERLAP_FALSE_POSITIVE)
            rationale_parts.append(
                f"Domain relevance ({domain:.2f}) acceptable but RQ alignment ({rq_align:.2f}) low; "
                "likely keyword overlap without substantive relevance"
            )

        if not grounding_evidence and confidence >= 0.7:
            categories.append(ErrorCategory.EVIDENCE_EXTRACTION_FAILURE)
            rationale_parts.append(
                f"No grounding evidence extracted despite {confidence:.0%} confidence"
            )

        has_error = is_false_positive or is_false_negative
        if confidence >= 0.9:
            if has_error:
                categories.append(ErrorCategory.CONFIDENCE_MISCALIBRATION)
                rationale_parts.append(
                    f"Confidence {confidence:.0%} on incorrect decision; miscalibrated"
                )
        elif confidence <= 0.4 and not has_error:
            categories.append(ErrorCategory.CONFIDENCE_MISCALIBRATION)
            rationale_parts.append(
                f"Confidence {confidence:.0%} on correct decision; underconfident"
            )

        if justification and "abstract" in justification.lower() and not abstract:
            categories.append(ErrorCategory.INSUFFICIENT_METADATA)
            rationale_parts.append("Justification references abstract but none available")

        if uncertainty_reasoning and "speculati" in uncertainty_reasoning.lower():
            categories.append(ErrorCategory.SPECULATIVE_INFERENCE)
            rationale_parts.append("APOLLO acknowledged speculative reasoning")

        if not categories:
            if apollo_include and not gold_include:
                categories.append(ErrorCategory.KEYWORD_OVERLAP_FALSE_POSITIVE)
                rationale_parts.append("Unclassified false positive; attributed to keyword overlap")
            elif apollo_exclude and gold_include:
                categories.append(ErrorCategory.CRITERION_MISAPPLICATION)
                rationale_parts.append("Unclassified false negative; attributed to criterion misapplication")
            else:
                categories.append(ErrorCategory.UNKNOWN)
                rationale_parts.append("Could not determine error category")

        max_severity = "low"
        for c in categories:
            cat_sev = ERROR_SEVERITY.get(c, "medium")
            severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            if severity_order.get(cat_sev, 0) > severity_order.get(max_severity, 0):
                max_severity = cat_sev

        desc = ERROR_DESCRIPTIONS.get(categories[0], "Unclassified error")
        return ClassifiedError(
            article_id=article_id,
            apollo_decision=apollo_upper,
            gold_decision=gold_upper,
            confidence=confidence,
            categories=categories,
            severity=max_severity,
            description=desc,
            rationale="; ".join(rationale_parts),
            evidence_snippet=justification[:200] if justification else "",
        )

    @staticmethod
    def classify_batch(
        comparisons: List[Dict],
    ) -> List[ClassifiedError]:
        results: List[ClassifiedError] = []
        for comp in comparisons:
            err = ErrorClassifier.classify(
                article_id=comp.get("article_id", "unknown"),
                apollo_decision=comp.get("apollo_decision", ""),
                gold_decision=comp.get("gold_decision", ""),
                confidence=comp.get("confidence", 0.0),
                justification=comp.get("justification", ""),
                triggered_criteria=comp.get("triggered_criteria"),
                abstract=comp.get("abstract", ""),
                title=comp.get("title", ""),
                uncertainty_reasoning=comp.get("uncertainty_reasoning", ""),
                domain_alignment_reasoning=comp.get("domain_alignment_reasoning", ""),
                topic_relevance=comp.get("topic_relevance"),
                grounding_evidence=comp.get("grounding_evidence"),
            )
            results.append(err)
        return results
