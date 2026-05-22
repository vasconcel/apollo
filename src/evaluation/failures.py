"""
APOLLO Evaluation: Failure Analysis Support

Captures, categorizes, and summarizes execution failures
for structured post-experiment failure analysis.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from collections import Counter
import json
import os
import time


FAILURE_CATEGORIES = {
    "parsing_failure": "Failed to parse LLM response into structured advisory",
    "malformed_response": "LLM returned malformed or incomplete JSON",
    "timeout_failure": "LLM request timed out",
    "rate_limit": "API rate limit exceeded",
    "empty_evidence": "Advisory produced with no grounding evidence",
    "routing_inconsistency": "Routing decision inconsistent with advisory decision",
    "llm_unavailable": "LLM service was unavailable",
    "empty_response": "LLM returned empty or null response",
    "unknown_error": "Unclassified failure",
}


@dataclass
class FailureRecord:
    article_id: str
    stage: str
    category: str
    error_message: str
    apollo_decision: str = ""
    confidence: float = 0.0
    routing: str = ""
    raw_response_preview: str = ""
    timestamp: str = ""
    protocol_version: str = "1.0"

    def to_dict(self) -> Dict:
        return {
            "article_id": self.article_id,
            "stage": self.stage,
            "category": self.category,
            "error_message": self.error_message,
            "apollo_decision": self.apollo_decision,
            "confidence": self.confidence,
            "routing": self.routing,
            "raw_response_preview": self.raw_response_preview[:500],
            "timestamp": self.timestamp,
            "protocol_version": self.protocol_version,
        }


def classify_advisory_failure(
    article_id: str,
    stage: str,
    advisory_result: Any,
    raw_response: str = "",
) -> FailureRecord:
    from src.advisory.advisory_models import AdvisoryResult
    error = None
    if isinstance(advisory_result, AdvisoryResult):
        error = advisory_result.error
    elif isinstance(advisory_result, dict):
        error = advisory_result.get("error", "")
    else:
        error = str(advisory_result) if advisory_result else "unknown"
    error_lower = (error or "").lower()
    if not error:
        category = "unknown_error"
    elif "429" in error or "rate" in error_lower:
        category = "rate_limit"
    elif "timeout" in error_lower:
        category = "timeout_failure"
    elif "unavailable" in error_lower or "llm" in error_lower:
        category = "llm_unavailable"
    elif "empty" in error_lower or "null" in error_lower:
        category = "empty_response"
    elif "parse" in error_lower or "json" in error_lower:
        category = "parsing_failure"
    elif "malformed" in error_lower or "invalid" in error_lower:
        category = "malformed_response"
    else:
        category = "unknown_error"
    decision = ""
    confidence = 0.0
    routing = ""
    if isinstance(advisory_result, AdvisoryResult):
        decision = advisory_result.decision.value if advisory_result.decision else ""
        confidence = advisory_result.confidence
    elif isinstance(advisory_result, dict):
        decision = advisory_result.get("decision", "")
        confidence = advisory_result.get("confidence", 0.0)
        routing = advisory_result.get("routing", "")
    preview = raw_response[:300] if raw_response else (error or "")[:300]
    return FailureRecord(
        article_id=article_id,
        stage=stage,
        category=category,
        error_message=error or "unknown",
        apollo_decision=decision,
        confidence=confidence,
        routing=routing,
        raw_response_preview=preview,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )


@dataclass
class FailureSummary:
    total_failures: int = 0
    total_articles: int = 0
    failure_rate: float = 0.0
    category_counts: Dict[str, int] = field(default_factory=dict)
    category_rates: Dict[str, float] = field(default_factory=dict)
    top_errors: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "total_failures": self.total_failures,
            "total_articles": self.total_articles,
            "failure_rate": self.failure_rate,
            "category_counts": self.category_counts,
            "category_rates": self.category_rates,
            "top_errors": self.top_errors[:20],
        }


class FailureAnalyzer:
    """Analyzes and summarizes advisory execution failures."""

    @staticmethod
    def analyze(failure_records: List[FailureRecord], total_articles: int) -> FailureSummary:
        n = len(failure_records)
        category_counter: Counter = Counter(r.category for r in failure_records)
        category_counts = dict(category_counter.most_common())
        category_rates = {
            cat: count / total_articles if total_articles > 0 else 0.0
            for cat, count in category_counts.items()
        }
        error_counter: Counter = Counter(r.error_message for r in failure_records)
        top_errors = [
            {"error": err, "count": count, "category": next(
                (r.category for r in failure_records if r.error_message == err), "unknown"
            )}
            for err, count in error_counter.most_common(20)
        ]
        return FailureSummary(
            total_failures=n,
            total_articles=total_articles,
            failure_rate=n / total_articles if total_articles > 0 else 0.0,
            category_counts=category_counts,
            category_rates=category_rates,
            top_errors=top_errors,
        )

    @staticmethod
    def generate_report(summary: FailureSummary, output_path: str = ""):
        lines = ["## Failure Analysis Summary\n"]
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Failures | {summary.total_failures} |")
        lines.append(f"| Total Articles | {summary.total_articles} |")
        lines.append(f"| Failure Rate | {summary.failure_rate:.2%} |")
        lines.append("")
        if summary.category_counts:
            lines.append("### Failure Categories\n")
            lines.append("| Category | Count | Rate | Description |")
            lines.append("|----------|-------|------|-------------|")
            for cat, count in summary.category_counts.items():
                desc = FAILURE_CATEGORIES.get(cat, "Unknown")
                rate = summary.category_rates.get(cat, 0.0)
                lines.append(f"| {cat} | {count} | {rate:.2%} | {desc} |")
            lines.append("")
        if summary.top_errors:
            lines.append("### Most Frequent Errors\n")
            lines.append("| Error | Count | Category |")
            lines.append("|-------|-------|----------|")
            for err in summary.top_errors[:10]:
                lines.append(f"| {err['error'][:80]} | {err['count']} | {err['category']} |")
            lines.append("")
        report = "\n".join(lines)
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
        return report


def check_routing_consistency(
    decision: str,
    routing: str,
    confidence: float,
    uncertainty_score: float,
) -> Optional[str]:
    decision_upper = decision.upper().strip() if decision else ""
    routing_upper = routing.upper().strip() if routing else ""
    if decision_upper in ("UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE", "UNAVAILABLE"):
        if routing_upper in ("AUTO_INCLUDE", "AUTO_EXCLUDE"):
            return "Autonomous routing applied to abstention/uncertain decision"
    if confidence < 0.5 and routing_upper in ("AUTO_INCLUDE", "AUTO_EXCLUDE"):
        return "Autonomous routing applied with sub-0.5 confidence"
    if uncertainty_score is not None and uncertainty_score > 0.7 and routing_upper in ("AUTO_INCLUDE", "AUTO_EXCLUDE"):
        return "Autonomous routing applied with high uncertainty score"
    return None
