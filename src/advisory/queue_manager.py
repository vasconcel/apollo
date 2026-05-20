"""
APOLLO Queue Management - Risk-based review queue filtering

Provides deterministic queue filtering for risk-oriented review workflow.
Includes memoization for scalability.
"""

from typing import List, Dict, Optional
from enum import Enum
from functools import lru_cache
import hashlib
import json

from .advisory_models import (
    RiskClassification,
    ValidationQueue,
    AdvisoryDecision,
    AdvisoryResult,
    AdvisoryStatus,
    compute_metadata_completeness
)
from .advisory_cache import get_advisory, get_advisory_status


class ReviewMode(str, Enum):
    """Review mode selectors."""
    FOCUSED_RISK_REVIEW = "FOCUSED_RISK_REVIEW"
    SEQUENTIAL_REVIEW = "SEQUENTIAL_REVIEW"
    CALIBRATION_REVIEW = "CALIBRATION_REVIEW"


_queue_summary_cache: Dict[str, Dict] = {}
_queue_filter_cache: Dict[str, List] = {}


def _get_articles_cache_key(articles: List, stage: str) -> str:
    """Generate deterministic cache key for article list."""
    if not articles:
        return f"empty_{stage}"
    article_ids = [str(getattr(a, 'article_id', '') or getattr(a, 'id', '') or '') for a in articles]
    ids_str = "|".join(sorted(article_ids[:100]))
    return hashlib.md5(ids_str.encode()).hexdigest()[:16]


def get_cached_queue_summary(
    articles: List,
    protocol_version: str,
    stage: str
) -> Dict:
    """
    Get cached queue summary - recomputes only when article set changes.
    """
    global _queue_summary_cache
    
    cache_key = f"{_get_articles_cache_key(articles, stage)}_{protocol_version}"
    
    if cache_key in _queue_summary_cache:
        return _queue_summary_cache[cache_key]
    
    result = compute_queue_summary(articles, protocol_version, stage)
    _queue_summary_cache[cache_key] = result
    
    if len(_queue_summary_cache) > 10:
        oldest_key = next(iter(_queue_summary_cache))
        del _queue_summary_cache[oldest_key]
    
    return result


def clear_queue_cache():
    """Clear all queue caches - call on session reset."""
    global _queue_summary_cache, _queue_filter_cache
    _queue_summary_cache.clear()
    _queue_filter_cache.clear()


def get_article_risk_info(
    article_id: str,
    title: str,
    abstract: str,
    protocol_version: str,
    stage: str
) -> Dict:
    """
    Get risk classification info for an article - DETERMINISTIC.

    Returns dict with risk_classification, requires_validation, etc.
    """
    advisory = get_advisory(title, abstract, protocol_version, stage=stage)
    status = get_advisory_status(title, abstract, protocol_version, stage=stage)

    if not advisory or status != AdvisoryStatus.COMPLETED:
        return {
            "risk_classification": "NO_ADVISORY",
            "requires_validation": False,
            "validation_queue": "NO_ADVISORY",
            "advisory_available": False,
            "confidence": 0.0,
            "metadata_completeness": 0.0
        }

    metadata_completeness = compute_metadata_completeness(title, abstract, {})

    return {
        "risk_classification": advisory.risk_classification.value if advisory.risk_classification else "UNKNOWN",
        "requires_validation": advisory.requires_validation if advisory.requires_validation else False,
        "validation_queue": advisory.validation_queue.value if advisory.validation_queue else "UNKNOWN",
        "advisory_available": True,
        "confidence": advisory.confidence if advisory.confidence else 0.0,
        "metadata_completeness": metadata_completeness,
        "risk_reason": advisory.risk_reason if advisory.risk_reason else "",
        "is_fallback": advisory.is_fallback if advisory.is_fallback else False
    }


def filter_articles_by_queue(
    articles: List,
    protocol_version: str,
    stage: str,
    queue_filter: Optional[str] = None
) -> List:
    """
    Filter articles by risk queue - DETERMINISTIC with caching.

    Args:
        articles: List of ArticleReview objects
        protocol_version: Protocol version
        stage: Screening stage (ec/ic)
        queue_filter: Optional queue name to filter by
                     (CRITICAL_REVIEW, HIGH_RISK, MEDIUM_RISK, LOW_RISK_SAMPLED, AUTO_LOW_RISK, NO_ADVISORY)

    Returns:
        Filtered list of articles (order preserved deterministically)
    """
    global _queue_filter_cache
    
    if not queue_filter or queue_filter == "ALL":
        return articles

    cache_key = f"{_get_articles_cache_key(articles, stage)}_{protocol_version}_{queue_filter}"
    
    if cache_key in _queue_filter_cache:
        return _queue_filter_cache[cache_key]

    filtered = []
    for article in articles:
        title = getattr(article, 'title', '') or ''
        article_id = getattr(article, 'article_id', '') or ''

        risk_info = get_article_risk_info(
            article_id=article_id,
            title=title,
            abstract=getattr(article, 'abstract', '') or '',
            protocol_version=protocol_version,
            stage=stage
        )

        queue = risk_info.get("validation_queue", "NO_ADVISORY")
        risk_class = risk_info.get("risk_classification", "NO_ADVISORY")
        requires_val = risk_info.get("requires_validation", False)

        if queue_filter == "CRITICAL_REVIEW":
            if risk_class == "CRITICAL_REVIEW" or queue == "CRITICAL_REVIEW":
                filtered.append(article)
        elif queue_filter == "HIGH_RISK":
            if risk_class == "HIGH_RISK" or queue == "PRIORITY_REVIEW":
                filtered.append(article)
        elif queue_filter == "MEDIUM_RISK":
            if risk_class == "MEDIUM_RISK" or queue == "PRIORITY_REVIEW":
                filtered.append(article)
        elif queue_filter == "LOW_RISK_SAMPLED":
            if risk_class == "LOW_RISK" and requires_val:
                filtered.append(article)
        elif queue_filter == "AUTO_LOW_RISK":
            if risk_class == "LOW_RISK" and not requires_val:
                filtered.append(article)
        elif queue_filter == "NO_ADVISORY":
            if not risk_info.get("advisory_available", False):
                filtered.append(article)

    _queue_filter_cache[cache_key] = filtered
    
    if len(_queue_filter_cache) > 20:
        oldest_key = next(iter(_queue_filter_cache))
        del _queue_filter_cache[oldest_key]
    
    return filtered


def compute_queue_summary(
    articles: List,
    protocol_version: str,
    stage: str
) -> Dict:
    """
    Compute queue summary statistics - DETERMINISTIC.

    Returns dict with counts for each queue.
    """
    queues = {
        "CRITICAL_REVIEW": 0,
        "HIGH_RISK": 0,
        "MEDIUM_RISK": 0,
        "LOW_RISK_SAMPLED": 0,
        "AUTO_LOW_RISK": 0,
        "NO_ADVISORY": 0
    }

    for article in articles:
        title = getattr(article, 'title', '') or ''
        article_id = getattr(article, 'article_id', '') or ''

        risk_info = get_article_risk_info(
            article_id=article_id,
            title=title,
            abstract=getattr(article, 'abstract', '') or '',
            protocol_version=protocol_version,
            stage=stage
        )

        queue = risk_info.get("validation_queue", "NO_ADVISORY")
        risk_class = risk_info.get("risk_classification", "NO_ADVISORY")
        requires_val = risk_info.get("requires_validation", False)

        if risk_class == "CRITICAL_REVIEW" or queue == "CRITICAL_REVIEW":
            queues["CRITICAL_REVIEW"] += 1
        elif risk_class == "HIGH_RISK" or queue == "PRIORITY_REVIEW":
            queues["HIGH_RISK"] += 1
        elif risk_class == "MEDIUM_RISK":
            queues["MEDIUM_RISK"] += 1
        elif risk_class == "LOW_RISK":
            if requires_val:
                queues["LOW_RISK_SAMPLED"] += 1
            else:
                queues["AUTO_LOW_RISK"] += 1
        else:
            queues["NO_ADVISORY"] += 1

    return queues