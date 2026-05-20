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


class RiskClassification(str, Enum):
    """Risk classification for advisory decisions."""
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    CRITICAL_REVIEW = "CRITICAL_REVIEW"


class ValidationQueue(str, Enum):
    """Human validation queue categorization."""
    AUTO_ACCEPT_CANDIDATES = "AUTO_ACCEPT_CANDIDATES"
    AUTO_EXCLUDE_CANDIDATES = "AUTO_EXCLUDE_CANDIDATES"
    PRIORITY_REVIEW = "PRIORITY_REVIEW"
    CRITICAL_REVIEW = "CRITICAL_REVIEW"


class ScreeningMode(str, Enum):
    """Operational screening modes."""
    STRICT_MODE = "STRICT_MODE"
    BALANCED_MODE = "BALANCED_MODE"
    ACCELERATED_MODE = "ACCELERATED_MODE"


class OverrideReason(str, Enum):
    """Human override rationale categories."""
    AMBIGUOUS_ABSTRACT = "ambiguous_abstract"
    CRITERION_MISCLASSIFICATION = "criterion_misclassification"
    DUPLICATE_ERROR = "duplicate_error"
    METADATA_INSUFFICIENCY = "metadata_insufficiency"
    PROTOCOL_INTERPRETATION = "protocol_interpretation"
    FALSE_EXCLUSION_RISK = "false_exclusion_risk"
    FALSE_INCLUSION_RISK = "false_inclusion_risk"
    OTHER = "other"


@dataclass
class CalibrationEvent:
    """
    Calibration event - tracks disagreement between AI advisory and human decision.

    Used to build empirical calibration dataset for future reliability estimation.
    """
    article_id: str
    protocol_version: str
    stage: str

    ai_decision: str
    human_decision: str
    ai_confidence: float

    metadata_completeness: float
    risk_classification: str
    ambiguity_detected: bool
    fallback_used: bool
    triggered_criteria: List[str] = field(default_factory=list)
    validation_queue: str = ""

    disagreement: bool = False
    override_reason: str = ""
    override_severity: str = ""

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSONL persistence."""
        return {
            "article_id": self.article_id,
            "protocol_version": self.protocol_version,
            "stage": self.stage,
            "ai_decision": self.ai_decision,
            "human_decision": self.human_decision,
            "ai_confidence": self.ai_confidence,
            "metadata_completeness": self.metadata_completeness,
            "risk_classification": self.risk_classification,
            "ambiguity_detected": self.ambiguity_detected,
            "fallback_used": self.fallback_used,
            "triggered_criteria": self.triggered_criteria,
            "validation_queue": self.validation_queue,
            "disagreement": self.disagreement,
            "override_reason": self.override_reason,
            "override_severity": self.override_severity,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationEvent":
        """Deserialize from dictionary."""
        return cls(
            article_id=data.get("article_id", ""),
            protocol_version=data.get("protocol_version", "1.0"),
            stage=data.get("stage", ""),
            ai_decision=data.get("ai_decision", ""),
            human_decision=data.get("human_decision", ""),
            ai_confidence=data.get("ai_confidence", 0.0),
            metadata_completeness=data.get("metadata_completeness", 0.0),
            risk_classification=data.get("risk_classification", ""),
            ambiguity_detected=data.get("ambiguity_detected", False),
            fallback_used=data.get("fallback_used", False),
            triggered_criteria=data.get("triggered_criteria", []),
            validation_queue=data.get("validation_queue", ""),
            disagreement=data.get("disagreement", False),
            override_reason=data.get("override_reason", ""),
            override_severity=data.get("override_severity", ""),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat())
        )


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


def compute_risk_classification(
    confidence: float,
    metadata_completeness: float,
    decision: AdvisoryDecision,
    is_fallback: bool = False,
    error: str = None,
    ambiguity_detected: bool = False,
    criterion_grounding_score: float = 1.0
) -> tuple[RiskClassification, str]:
    """
    Compute risk classification for an advisory - DETERMINISTIC.

    Returns tuple of (RiskClassification, reason)

    Risk factors:
    - Confidence level
    - Metadata completeness
    - Fallback usage (indicates parsing issues)
    - Error presence (advisory generation failed)
    - Ambiguity signals
    - Criterion grounding strength
    """
    reasons = []

    if is_fallback or error:
        return RiskClassification.CRITICAL_REVIEW, "Advisory generation failed or used fallback"

    if decision == AdvisoryDecision.INSUFFICIENT_METADATA:
        return RiskClassification.CRITICAL_REVIEW, "Insufficient metadata for reliable evaluation"

    if decision == AdvisoryDecision.UNAVAILABLE:
        return RiskClassification.CRITICAL_REVIEW, "Advisory unavailable"

    if criterion_grounding_score < 0.5:
        reasons.append("weak_criterion_grounding")
        return RiskClassification.HIGH_RISK, f"Weak criterion grounding: {criterion_grounding_score:.2f}"

    if ambiguity_detected:
        reasons.append("ambiguity_detected")
        if confidence < 0.7 or metadata_completeness < 0.5:
            return RiskClassification.HIGH_RISK, "Ambiguity with low confidence/metadata"

    if metadata_completeness < 0.3:
        reasons.append("sparse_metadata")
        if confidence < 0.8:
            return RiskClassification.HIGH_RISK, "Sparse metadata with moderate confidence"
        return RiskClassification.MEDIUM_RISK, "Sparse metadata but high confidence"

    if confidence < 0.5:
        reasons.append("low_confidence")
        return RiskClassification.HIGH_RISK, f"Low confidence: {confidence:.2f}"

    if metadata_completeness < 0.5 and confidence < 0.7:
        reasons.append("moderate_uncertainty")
        return RiskClassification.MEDIUM_RISK, "Moderate uncertainty in both confidence and metadata"

    if confidence >= 0.85 and metadata_completeness >= 0.7 and criterion_grounding_score >= 0.8:
        return RiskClassification.LOW_RISK, "High confidence, complete metadata, strong grounding"

    if confidence >= 0.7 and metadata_completeness >= 0.5:
        return RiskClassification.MEDIUM_RISK, "Adequate confidence and metadata"

    return RiskClassification.MEDIUM_RISK, "Default medium risk classification"


def get_validation_queue(
    risk_classification: RiskClassification,
    decision: AdvisoryDecision,
    sampling_deterministic_hash: str = ""
) -> ValidationQueue:
    """
    Map risk classification to validation queue - DETERMINISTIC.

    Returns the appropriate queue for human validation.
    """
    if risk_classification == RiskClassification.CRITICAL_REVIEW:
        return ValidationQueue.CRITICAL_REVIEW

    if risk_classification == RiskClassification.HIGH_RISK:
        return ValidationQueue.PRIORITY_REVIEW

    if risk_classification == RiskClassification.MEDIUM_RISK:
        return ValidationQueue.PRIORITY_REVIEW

    if decision == AdvisoryDecision.INCLUDE:
        return ValidationQueue.AUTO_ACCEPT_CANDIDATES
    else:
        return ValidationQueue.AUTO_EXCLUDE_CANDIDATES


def validate_grounding(
    justification: str,
    title: str,
    abstract: str,
    criterion_evaluations: List["CriterionEvaluation"],
    metadata: dict = None
) -> tuple[float, List[str], Dict[str, str], bool]:
    """
    Validate that advisory rationale is grounded in source evidence.

    Returns:
        (grounding_strength, evidence_snippets, criterion_grounding, unsupported_detected)

    Grounding Strength: 0.0-1.0
    Evidence Snippets: List of extracted text supporting decision
    Criterion Grounding: {criterion_id: matched_evidence}
    Unsupported Detected: True if significant claims lack source support
    """
    if not justification or not title:
        return 0.0, [], {}, True

    evidence_snippets = []
    criterion_grounding = {}
    total_grounded = 0

    source_text = f"{title} {abstract or ''}".lower()
    if metadata:
        for key, value in metadata.items():
            if value and isinstance(value, str):
                source_text += f" {value}".lower()

    justification_words = set(justification.lower().split())
    source_words = set(source_text.split())

    grounded_words = justification_words & source_words
    grounding_ratio = len(grounded_words) / len(justification_words) if justification_words else 0.0

    if grounding_ratio >= 0.6:
        grounding_strength = 0.9
    elif grounding_ratio >= 0.4:
        grounding_strength = 0.7
    elif grounding_ratio >= 0.2:
        grounding_strength = 0.5
    else:
        grounding_strength = 0.3

    for ce in criterion_evaluations:
        if ce.evidence and ce.evidence.lower() in source_text:
            criterion_grounding[ce.criterion_id] = ce.evidence
            total_grounded += 1

    if grounding_strength < 0.5 or total_grounded < len(criterion_evaluations) * 0.5:
        unsupported_detected = True
    else:
        unsupported_detected = False

    if abstract and len(abstract.split()) < 20:
        grounding_strength = min(grounding_strength, 0.5)

    if len(justification.split()) > 100:
        grounding_strength = min(grounding_strength, 0.7)

    return grounding_strength, evidence_snippets, criterion_grounding, unsupported_detected


def compute_hallucination_risk(
    is_fallback: bool,
    grounding_strength: float,
    unsupported_claims: bool,
    confidence: float,
    metadata_completeness: float,
    error: str = None
) -> float:
    """
    Compute deterministic hallucination risk score (0.0-1.0).

    HIGH RISK (>= 0.7):
    - Fallback mode triggered
    - Low grounding strength
    - Unsupported claims detected
    - Very high confidence with sparse metadata

    LOW RISK (<= 0.3):
    - Strong grounding
    - Complete metadata
    - No errors
    """
    risk_score = 0.0

    if is_fallback:
        risk_score += 0.4

    if grounding_strength < 0.5:
        risk_score += 0.3
    elif grounding_strength < 0.7:
        risk_score += 0.1

    if unsupported_claims:
        risk_score += 0.3

    if confidence > 0.9 and metadata_completeness < 0.3:
        risk_score += 0.2

    if error:
        risk_score += 0.2

    return min(risk_score, 1.0)


def should_validate(
    risk_classification: RiskClassification,
    decision: AdvisoryDecision,
    sampling_rate: float = 0.05,  # TODO: Make configurable via protocol settings
    deterministic_hash: str = ""
) -> bool:
    """
    Determine if advisory requires human validation - DETERMINISTIC.

    Uses stable hash for reproducible sampling.

    Args:
        risk_classification: Risk level of the advisory
        decision: The advisory decision
        sampling_rate: Rate for random-looking but deterministic sampling (0.0-1.0)
        deterministic_hash: Stable hash for reproducibility
    """
    import hashlib

    if risk_classification in (RiskClassification.HIGH_RISK, RiskClassification.CRITICAL_REVIEW):
        return True

    if risk_classification == RiskClassification.MEDIUM_RISK:
        return True

    if not deterministic_hash:
        return False

    hash_input = f"{deterministic_hash}_{decision.value}_{risk_classification.value}"
    hash_value = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16)
    normalized = (hash_value % 10000) / 10000.0

    return normalized < sampling_rate


def populate_risk_classification(
    advisory: AdvisoryResult,
    metadata_completeness: float = 0.0,
    criterion_grounding_score: float = 1.0,
    ambiguity_detected: bool = False,
    deterministic_hash: str = "",
    sampling_rate: float = 0.05
) -> AdvisoryResult:
    """
    Populate risk classification and validation fields on an AdvisoryResult.

    This is called after advisory generation to add risk-based routing.

    Returns the advisory with populated risk_classification, risk_reason,
    validation_queue, and requires_validation fields.
    """
    risk_class, risk_reason = compute_risk_classification(
        confidence=advisory.confidence,
        metadata_completeness=metadata_completeness,
        decision=advisory.decision,
        is_fallback=advisory.is_fallback,
        error=advisory.error,
        ambiguity_detected=ambiguity_detected,
        criterion_grounding_score=criterion_grounding_score
    )

    advisory.risk_classification = risk_class
    advisory.risk_reason = risk_reason

    advisory.validation_queue = get_validation_queue(
        risk_classification=risk_class,
        decision=advisory.decision,
        deterministic_hash=deterministic_hash
    )

    advisory.requires_validation = should_validate(
        risk_classification=risk_class,
        decision=advisory.decision,
        sampling_rate=sampling_rate,
        deterministic_hash=deterministic_hash
    )

    return advisory


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

    risk_classification: Optional[RiskClassification] = None
    risk_reason: str = ""
    validation_queue: Optional[ValidationQueue] = None
    requires_validation: bool = False

    grounding_evidence: List[str] = field(default_factory=list)
    criterion_grounding: Dict[str, str] = field(default_factory=dict)
    grounding_strength: float = 0.0
    unsupported_claims_detected: bool = False
    hallucination_risk_score: float = 0.0

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
            "risk_classification": safe_enum_value(self.risk_classification, "UNKNOWN"),
            "risk_reason": self.risk_reason or "",
            "validation_queue": safe_enum_value(self.validation_queue, "UNKNOWN"),
            "requires_validation": bool(self.requires_validation),
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