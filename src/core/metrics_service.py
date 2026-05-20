"""
Operational Metrics Service - Telemetry structure for future analytics.

This module provides a structured layer for operational metrics.
It is currently a skeleton - actual metrics collection is NOT IMPLEMENTED.

Purpose:
- Define metrics data structures
- Provide collection hooks
- Prepare for future analytics dashboards

IMPORTANT:
This is infrastructure only - no actual metrics collection implemented.
No invasive telemetry. No external tracking. LOCAL ONLY.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScreeningMetrics:
    """Screening session metrics structure."""
    session_id: str
    protocol_version: str
    stage: str
    
    total_articles: int = 0
    reviewed_articles: int = 0
    pending_articles: int = 0
    
    queue_distribution: Dict[str, int] = field(default_factory=dict)
    
    review_mode: str = "SEQUENTIAL_REVIEW"
    
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


@dataclass
class CalibrationMetrics:
    """Calibration metrics structure."""
    session_id: str
    
    total_events: int = 0
    agreement_count: int = 0
    disagreement_count: int = 0
    
    override_severity_distribution: Dict[str, int] = field(default_factory=dict)
    
    agreement_rate: Optional[float] = None
    override_rate: Optional[float] = None
    
    false_inclusion_count: int = 0
    false_exclusion_count: int = 0


@dataclass
class AdvisoryMetrics:
    """Advisory generation metrics structure."""
    total_generated: int = 0
    fallback_count: int = 0
    
    confidence_distribution: Dict[str, int] = field(default_factory=dict)
    grounding_distribution: Dict[str, int] = field(default_factory=dict)
    
    hallucination_risk_distribution: Dict[str, int] = field(default_factory=dict)
    
    average_confidence: Optional[float] = None
    average_grounding: Optional[float] = None
    average_hallucination_risk: Optional[float] = None


class MetricsCollector:
    """
    Metrics collection coordinator.
    
    NOTE: Currently NOT IMPLEMENTED - this is infrastructure only.
    """
    
    def __init__(self):
        self._sessions: List[ScreeningMetrics] = []
        self._current_session: Optional[ScreeningMetrics] = None
    
    def start_session(self, session_id: str, protocol_version: str, stage: str) -> ScreeningMetrics:
        """Start tracking a new screening session."""
        # NOT IMPLEMENTED - placeholder only
        pass
    
    def end_session(self) -> Optional[ScreeningMetrics]:
        """End current session and return final metrics."""
        # NOT IMPLEMENTED - placeholder only
        pass
    
    def record_review_action(self, article_id: str, action: str) -> None:
        """Record a review action (confirm, override, escalate)."""
        # NOT IMPLEMENTED - placeholder only
        pass
    
    def record_queue_switch(self, from_queue: str, to_queue: str) -> None:
        """Record a queue filter change."""
        # NOT IMPLEMENTED - placeholder only
        pass
    
    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """Get summary metrics for a session."""
        # NOT IMPLEMENTED - placeholder only
        pass


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    if 'metrics_collector' not in globals():
        globals()['metrics_collector'] = MetricsCollector()
    return globals()['metrics_collector']


NOT_IMPLEMENTED = True