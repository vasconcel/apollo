"""
Advisory data models and schemas for APOLLO.

Defines typed dataclasses for:
- AdvisoryRequest: input for advisory generation
- AdvisoryResult: output from LLM
- AdvisoryStatus: tracking states
- QueueItem: queue entry representation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Literal, Any
from datetime import datetime
from enum import Enum
import json
import hashlib


def safe_enum_value(enum_obj: Any, default: str = "UNKNOWN") -> str:
    """Safe access to enum value - single source of truth for enum handling."""
    if enum_obj is None:
        return default
    try:
        if hasattr(enum_obj, 'value'):
            return enum_obj.value
        return str(enum_obj)
    except Exception:
        return default


def safe_decision(decision: Any, default: str = "UNAVAILABLE") -> str:
    """Safe access to advisory decision value."""
    if decision is None:
        return default
    try:
        if hasattr(decision, 'value'):
            return decision.value
        return str(decision)
    except Exception:
        return default


def safe_status(status: Any, default: str = "UNKNOWN") -> str:
    """Safe access to advisory status value."""
    if status is None:
        return default
    try:
        if hasattr(status, 'value'):
            return status.value
        return str(status)
    except Exception:
        return default


class AdvisoryStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class AdvisoryDecision(str, Enum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    SKIP = "SKIP"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_METADATA = "INSUFFICIENT_METADATA"


def compute_metadata_completeness(title: str, abstract: str, metadata: dict = None) -> float:
    """
    Calculate metadata completeness score for confidence calibration.

    Returns 0.0-1.0 indicating how much information is available.

    Factors:
    - Title presence and length
    - Abstract presence and length
    - Year availability
    - Authors presence
    - Source/venue presence
    """
    score = 0.0
    weights = {
        "title": 0.2,
        "abstract": 0.35,
        "year": 0.15,
        "authors": 0.15,
        "source": 0.15
    }

    if title and title not in ("", "nan", "None"):
        score += weights["title"] * min(len(title) / 20, 1.0)

    if abstract and abstract not in ("", "nan", "None"):
        abstract_words = len(str(abstract).split())
        score += weights["abstract"] * min(abstract_words / 50, 1.0)

    if metadata:
        year = metadata.get("year", "")
        if year and year not in ("", "nan", "None"):
            score += weights["year"]

        authors = metadata.get("authors", "")
        if authors and authors not in ("", "nan", "None"):
            score += weights["authors"]

        source = metadata.get("source", "")
        if source and source not in ("", "nan", "None"):
            score += weights["source"]

    return min(score, 1.0)


def calibrate_confidence(base_confidence: float, metadata_completeness: float) -> float:
    """
    Calibrate confidence based on metadata availability.

    If metadata is sparse, reduce confidence ceiling.
    """
    if metadata_completeness < 0.3:
        return min(base_confidence, 0.45)
    elif metadata_completeness < 0.5:
        return min(base_confidence, 0.65)
    elif metadata_completeness < 0.7:
        return min(base_confidence, 0.85)
    else:
        return base_confidence


@dataclass
class CriterionEvaluation:
    """Single criterion evaluation from LLM."""
    criterion_id: str
    criterion_name: str
    satisfied: bool
    evidence: str
    confidence: float


@dataclass
class AdvisoryResult:
    """
    Advisory output from LLM inference.
    This is the canonical advisory artifact.
    """
    cache_key: str
    protocol_version: str
    
    decision: AdvisoryDecision
    confidence: float
    
    triggered_criteria: List[str] = field(default_factory=list)
    criterion_evaluations: List[CriterionEvaluation] = field(default_factory=list)
    
    justification: str = ""
    error: Optional[str] = None
    
    is_fallback: bool = False
    is_placeholder: bool = False
    
    generated_at: Optional[str] = None
    generation_duration_ms: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON persistence - SAFE."""
        return {
            "cache_key": self.cache_key or "",
            "protocol_version": self.protocol_version or "1.0",
            "decision": safe_enum_value(self.decision, "UNAVAILABLE"),
            "confidence": self.confidence if self.confidence is not None else 0.0,
            "triggered_criteria": self.triggered_criteria or [],
            "criterion_evaluations": [
                {
                    "criterion_id": ce.criterion_id,
                    "criterion_name": ce.criterion_name,
                    "satisfied": ce.satisfied,
                    "evidence": ce.evidence,
                    "confidence": ce.confidence
                }
                for ce in (self.criterion_evaluations or [])
            ],
            "justification": self.justification or "",
            "error": self.error,
            "is_fallback": bool(self.is_fallback),
            "is_placeholder": bool(self.is_placeholder),
            "generated_at": self.generated_at,
            "generation_duration_ms": self.generation_duration_ms
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AdvisoryResult":
        """Deserialize from dictionary - DEFENSIVE HANDLING."""
        criterion_evaluations = []
        for ce in data.get("criterion_evaluations", []):
            if ce and isinstance(ce, dict):
                criterion_evaluations.append(CriterionEvaluation(
                    criterion_id=ce.get("criterion_id", "unknown"),
                    criterion_name=ce.get("criterion_name", "Unknown"),
                    satisfied=bool(ce.get("satisfied", False)),
                    evidence=ce.get("evidence", ""),
                    confidence=float(ce.get("confidence", 0.0))
                ))

        decision_str = data.get("decision", "UNAVAILABLE")
        try:
            decision = AdvisoryDecision(decision_str)
        except (ValueError, TypeError):
            decision = AdvisoryDecision.UNAVAILABLE

        return cls(
            cache_key=data.get("cache_key", ""),
            protocol_version=data.get("protocol_version", "1.0"),
            decision=decision,
            confidence=data.get("confidence", 0.0),
            triggered_criteria=data.get("triggered_criteria", []),
            criterion_evaluations=criterion_evaluations,
            justification=data.get("justification", ""),
            error=data.get("error"),
            is_fallback=data.get("is_fallback", False),
            is_placeholder=data.get("is_placeholder", False),
            generated_at=data.get("generated_at"),
            generation_duration_ms=data.get("generation_duration_ms")
        )
    
    def is_available(self) -> bool:
        """Check if advisory has actual content (not failed/placeholder)."""
        if self.decision is None:
            return False
        try:
            return (
                self.decision != AdvisoryDecision.UNAVAILABLE
                and not self.is_placeholder
                and self.error is None
            )
        except Exception:
            return False
    
    @staticmethod
    def create_unavailable(reason: str = "Not yet generated") -> "AdvisoryResult":
        """Create placeholder for unavailable advisories."""
        return AdvisoryResult(
            cache_key="",
            protocol_version="1.0",
            decision=AdvisoryDecision.UNAVAILABLE,
            confidence=0.0,
            justification=reason,
            is_placeholder=True,
            error=reason
        )
    
    @staticmethod
    def create_failed(reason: str, cache_key: str = "", protocol_version: str = "1.0") -> "AdvisoryResult":
        """Create failure artifact."""
        return AdvisoryResult(
            cache_key=cache_key,
            protocol_version=protocol_version,
            decision=AdvisoryDecision.UNAVAILABLE,
            confidence=0.0,
            justification=f"Advisory generation failed: {reason}",
            is_placeholder=False,
            error=reason,
            generated_at=datetime.utcnow().isoformat()
        )


@dataclass
class AdvisoryRequest:
    """Input required for advisory generation."""
    cache_key: str
    protocol_version: str
    title: str
    abstract: str
    literature_type: str
    metadata: Dict = field(default_factory=dict)
    
    @classmethod
    def from_article(cls, article, protocol_version: str = "1.0") -> "AdvisoryRequest":
        """Construct request from article object."""
        if hasattr(article, 'get_literature_type'):
            title = getattr(article, 'title', '')
            abstract = getattr(article, 'abstract', '')
            literature_type = article.get_literature_type()
            metadata = getattr(article, 'metadata', {})
        else:
            title = article.get("title", "") if hasattr(article, 'get') else ""
            abstract = article.get("abstract", "") if hasattr(article, 'get') else ""
            literature_type = article.get("literature_type", "WL") if hasattr(article, 'get') else "WL"
            metadata = article if hasattr(article, 'get') else {}
        
        content = f"{protocol_version}:{title.strip().lower()}:{abstract.strip().lower()}"
        cache_key = hashlib.sha256(content.encode()).hexdigest()[:32]
        
        return cls(
            cache_key=cache_key,
            protocol_version=protocol_version,
            title=title,
            abstract=abstract,
            literature_type=literature_type,
            metadata=metadata
        )
    
    @property
    def article_id(self) -> str:
        """Extract article identifier."""
        if self.metadata:
            return self.metadata.get("article_id", self.cache_key)
        return self.cache_key


@dataclass
class QueueItem:
    """Queue entry representation."""
    cache_key: str
    protocol_version: str
    article_id: str
    stage: str = "ic"

    status: AdvisoryStatus = AdvisoryStatus.PENDING
    priority: int = 0
    
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    retry_count: int = 0
    last_error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "cache_key": self.cache_key,
            "protocol_version": self.protocol_version,
            "article_id": self.article_id,
            "stage": self.stage,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "last_error": self.last_error
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QueueItem":
        return cls(
            cache_key=data["cache_key"],
            protocol_version=data["protocol_version"],
            article_id=data["article_id"],
            stage=data.get("stage", "ic"),
            status=AdvisoryStatus(data.get("status", "PENDING")),
            priority=data.get("priority", 0),
            created_at=data.get("created_at", ""),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            retry_count=data.get("retry_count", 0),
            last_error=data.get("last_error")
        )


@dataclass
class QueueState:
    """Queue metadata and progress tracking."""
    total: int = 0
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    items: List[QueueItem] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "pending": self.pending,
            "processing": self.processing,
            "completed": self.completed,
            "failed": self.failed,
            "last_updated": self.last_updated,
            "items": [item.to_dict() for item in self.items]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "QueueState":
        return cls(
            total=data.get("total", 0),
            pending=data.get("pending", 0),
            processing=data.get("processing", 0),
            completed=data.get("completed", 0),
            failed=data.get("failed", 0),
            last_updated=data.get("last_updated", ""),
            items=[QueueItem.from_dict(item) for item in data.get("items", [])]
        )
    
    @property
    def completion_rate(self) -> float:
        """Calculate completion percentage."""
        if self.total == 0:
            return 0.0
        return (self.completed + self.failed) / self.total
    
    @property
    def status_summary(self) -> str:
        """Human-readable status summary."""
        return f"{self.completed}/{self.total} completed ({self.completion_rate:.1%}), {self.pending} pending, {self.failed} failed"


@dataclass
class AdvisoryConfig:
    """Configuration for advisory pipeline."""
    cache_dir: str = "data/cache/advisories"
    queue_state_path: str = "data/cache/queue_state.json"
    
    max_requests_per_minute: int = 20
    sleep_seconds: float = 3.0
    max_retries: int = 5
    
    backoff_base: float = 2.0
    backoff_max: float = 60.0
    jitter: float = 0.1
    
    enable_disk_cache: bool = True
    enable_queue_state: bool = True
    
    def to_dict(self) -> dict:
        return {
            "cache_dir": self.cache_dir,
            "queue_state_path": self.queue_state_path,
            "max_requests_per_minute": self.max_requests_per_minute,
            "sleep_seconds": self.sleep_seconds,
            "max_retries": self.max_retries,
            "backoff_base": self.backoff_base,
            "backoff_max": self.backoff_max,
            "jitter": self.jitter,
            "enable_disk_cache": self.enable_disk_cache,
            "enable_queue_state": self.enable_queue_state
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AdvisoryConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})