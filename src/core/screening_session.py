"""
APOLLO Screening Session Management
Manages human-in-the-loop screening sessions

WORKFLOW RULES:
- EC stage: All papers reviewed. If excluded, cannot proceed.
- IC stage: Only EC-included papers reviewed. If excluded, screening is complete.
- SKIP papers: Can be recovered for later review.
- NEEDS_DISCUSSION: Tracked separately for team review.
"""
import os
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

from src.core.session_navigation import NavigationService
from src.core.session_query_service import SessionQueryService
from src.core.session_persistence_service import SessionPersistenceService
from src.core.session_ingestion_service import SessionIngestionService
from src.core.session_audit_service import SessionAuditService
from src.core.session_decision_service import SessionDecisionService
from src.core.session_orchestration_service import SessionOrchestrationService
from src.core.workflow_state_service import WorkflowStateService
from src.core.session_state import SessionState


class SessionStage(Enum):
    """Screening stages."""
    EC = "ec"  # Exclusion Criteria
    IC = "ic"  # Inclusion Criteria
    QC = "qc"  # Quality Criteria
    COMPLETE = "complete"


class ReviewDecision(Enum):
    """Researcher decisions."""
    INCLUDE = "include"
    EXCLUDE = "exclude"
    SKIP = "skip"
    NEEDS_DISCUSSION = "needs_discussion"


@dataclass
class ArticleReview:
    """Single article review state."""
    article_id: str
    title: str
    abstract: str
    metadata: Dict[str, str]
    
    ec_stage: str = ""  # Decision at EC stage
    ec_notes: str = ""
    ec_timestamp: str = ""
    ec_llm_suggestion: Dict[str, Any] = field(default_factory=dict)
    
    ic_stage: str = ""  # Decision at IC stage (only if EC passed)
    ic_notes: str = ""
    ic_timestamp: str = ""
    ic_llm_suggestion: Dict[str, Any] = field(default_factory=dict)

    qc_stage: str = ""  # Decision at QC stage (only if IC passed)
    qc_notes: str = ""
    qc_timestamp: str = ""
    qc_score: str = ""  # QC score (e.g., "6.0/8.0")
    qc_llm_suggestion: Dict[str, Any] = field(default_factory=dict)

    final_decision: str = ""
    
    cis1: str = ""  # Reviewer 1 IC code (IC1, IC2, etc. or "YES")
    ces1: str = ""  # Reviewer 1 EC code (EC1, EC2, etc.)
    revisor1: str = ""  # Researcher ID for Reviewer 1
    
    def get_year_source(self) -> str:
        """Get year source provenance flag."""
        return self.metadata.get("year_source", "unknown")

    def get_metadata_completeness(self) -> str:
        """Get metadata completeness level."""
        return self.metadata.get("metadata_completeness", "unknown")

    def get_literature_type(self) -> str:
        """Get literature type ('WL' or 'GL')."""
        return self.metadata.get("literature_type", "WL")

    def has_complete_metadata(self) -> bool:
        """Check if article has complete metadata lineage."""
        required_fields = ["title", "literature_type"]
        for field in required_fields:
            if field not in self.metadata or not self.metadata[field]:
                return False
        return self.get_metadata_completeness() in ("complete", "partial")

    def to_review_dict(self) -> Dict:
        """Export as review-ready dict with explicit metadata fields."""
        return {
            "article_id": self.article_id,
            "title": self.title,
            "abstract": self.abstract,
            "year": self.metadata.get("year"),
            "year_source": self.get_year_source(),
            "authors": self.metadata.get("authors", ""),
            "literature_type": self.get_literature_type(),
            "metadata_completeness": self.get_metadata_completeness(),
            "url": self.metadata.get("url", ""),
            "library": self.metadata.get("library", ""),
            "source_file": self.metadata.get("source_file", ""),
            "ec_decision": self.metadata.get("ec_decision", ""),
            "ic_decision": self.metadata.get("ic_decision", ""),
            "final_decision": self.final_decision,
            "ec_stage": self.ec_stage,
            "ic_stage": self.ic_stage,
        }

    def to_dict(self) -> Dict:
        """Convert to dictionary for export."""
        return asdict(self)

    @property
    def is_ec_included(self) -> bool:
        """Check if passed EC stage."""
        return self.ec_stage == "include"
    
    @property
    def is_ic_included(self) -> bool:
        """Check if passed IC stage (requires EC pass first)."""
        return self.is_ec_included and self.ic_stage == "include"

    @property
    def is_qc_included(self) -> bool:
        """Check if passed QC stage (requires IC pass first)."""
        return self.is_ic_included and self.qc_stage == "include"

    @property
    def is_discussion_needed(self) -> bool:
        """Check if needs discussion at any stage."""
        return self.ec_stage == "needs_discussion" or self.ic_stage == "needs_discussion"
    
    def get_current_stage_decision(self, stage: str) -> str:
        """Get decision for current stage."""
        if stage == "ec":
            return self.ec_stage
        elif stage == "ic":
            return self.ic_stage
        return ""
    
    def can_proceed_to_stage(self, stage: str) -> bool:
        """Check if can proceed to next stage."""
        if stage == "ic":
            return self.is_ec_included
        return True
    
    def compute_final_decision(self) -> str:
        """Compute final decision based on stage progression."""
        if not self.is_ec_included:
            return "EXCLUDE"
        if not self.is_ic_included:
            return "EXCLUDE"
        
        if self.is_discussion_needed:
            return "NEEDS_DISCUSSION"
        
        return "INCLUDE"
    
    @classmethod
    def from_article_record(cls, record) -> "ArticleReview":
        """Create from ArticleRecord with full metadata propagation."""
        base_metadata = {
            "library": record.library,
            "global_id": record.global_id,
            "local_id": record.local_id,
            "keywords": record.keywords,
            "literature_type": record.literature_type,
            "url": record.url,
            "source_file": record.source_file,
            "year": record.year,
            "authors": record.authors,
            "posicao": record.posicao,
            "ec_decision": record.ec_decision,
            "ic_decision": record.ic_decision,
            "final_decision": record.final_decision
        }
        
        if record.metadata:
            base_metadata.update(record.metadata)
        
        return cls(
            article_id=record.global_id or record.local_id or record.posicao or str(uuid.uuid4())[:8],
            title=record.title,
            abstract=record.abstract,
            metadata=base_metadata
        )


_STATE_FIELD_ALIASES = {
    "_audit_chain": "audit_chain",
    "_snapshots": "snapshots",
}

class ScreeningSession:
    """Screening session with workflow rules and dynamic protocol.

    Public compatibility façade that owns a SessionState internally.
    All mutable state is delegated to self.state.
    """

    def __init__(
        self,
        session_id: str,
        created_at: str,
        protocol_version: str = "1.0",
        stage: Optional[str] = None,
        articles: Optional[List[ArticleReview]] = None,
        dynamic_protocol: Optional[Dict] = None,
        current_index: int = 0,
        total_count: int = 0,
        ec_completed: int = 0,
        ic_completed: int = 0,
        qc_completed: int = 0,
        included_count: int = 0,
        excluded_count: int = 0,
        skip_count: int = 0,
        discussion_count: int = 0,
        researcher_id: str = "researcher_1",
        last_saved: str = "",
        schema_version: str = "2.0",
        autosave_enabled: bool = False,
    ):
        if stage is None:
            stage = SessionStage.EC.value
        # Use __dict__ directly to bypass __setattr__ delegation
        self.__dict__["state"] = SessionState(
            session_id=session_id,
            created_at=created_at,
            protocol_version=protocol_version,
            stage=stage,
            articles=articles or [],
            dynamic_protocol=dynamic_protocol,
            current_index=current_index,
            total_count=total_count,
            ec_completed=ec_completed,
            ic_completed=ic_completed,
            qc_completed=qc_completed,
            included_count=included_count,
            excluded_count=excluded_count,
            skip_count=skip_count,
            discussion_count=discussion_count,
            researcher_id=researcher_id,
            last_saved=last_saved,
            schema_version=schema_version,
            autosave_enabled=autosave_enabled,
        )

    # --- Backward-compatible field access via __getattr__/__setattr__ ---

    def __getattr__(self, name: str):
        if name == "state":
            return self.__dict__["state"]
        state = self.__dict__.get("state")
        if state is not None:
            target = _STATE_FIELD_ALIASES.get(name, name)
            if hasattr(state, target):
                return getattr(state, target)
        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )

    def __setattr__(self, name: str, value):
        if name == "state":
            self.__dict__["state"] = value
            return
        state = self.__dict__.get("state")
        if state is not None:
            target = _STATE_FIELD_ALIASES.get(name, name)
            if hasattr(state, target):
                setattr(state, target, value)
                return
        self.__dict__[name] = value

    # --- Orchestration methods (delegate to services, operate on self.state) ---

    def add_articles(self, article_records: List) -> None:
        """Add articles to session via IngestionService."""
        self.state.articles = SessionIngestionService.add_articles(article_records)
        self.state.total_count = len(self.state.articles)

    def ingest_from_upload(
        self,
        uploaded_file,
        stage: str = "ec"
    ) -> List[ArticleReview]:
        """Ingest articles from an uploaded file via IngestionService."""
        articles = SessionIngestionService.ingest_from_bytes(
            uploaded_file.getvalue(), uploaded_file.name, stage,
        )
        self.state.articles = articles
        self.state.total_count = len(articles)
        return articles

    def get_current_article(self) -> Optional[ArticleReview]:
        """Get current article for review."""
        return NavigationService.get_current_article(
            self.state.articles, self.state.current_index,
        )

    def can_review_current_at_stage(self, stage: str) -> bool:
        """Check if current article can be reviewed at this stage."""
        return NavigationService.can_review_current_at_stage(
            self.state.articles, self.state.current_index, stage,
        )

    def record_decision(
        self,
        decision: str,
        notes: str = "",
        llm_suggestion: Optional[Dict] = None
    ) -> bool:
        """Record researcher decision. Delegates coordination to OrchestrationService."""
        result = SessionOrchestrationService.record_decision(
            self.state.articles, self.state.current_index,
            self.state.stage, decision, notes, llm_suggestion,
            self.state.researcher_id, self.state.dynamic_protocol,
            self.state.audit_chain,
        )
        if result is None:
            return False
        self._apply_decision_side_effects(result)
        return True

    def _apply_decision_side_effects(self, result: Dict) -> None:
        """Apply state-level side effects from a decision result dict."""
        for counter, delta in result["counter_increments"].items():
            setattr(self.state, counter, getattr(self.state, counter) + delta)
        self.state.last_saved = result["timestamp"]
        self.state.audit_chain.append(result["audit_event"])
        if result.get("protocol_snapshot"):
            self.state.snapshots.append(result["protocol_snapshot"])

    def verify_audit_chain(self) -> tuple:
        """Verify audit chain integrity via AuditService."""
        return SessionAuditService.verify_chain(self.state.audit_chain)

    def detect_tampering(self) -> tuple:
        """Detect tampering in audit chain via AuditService."""
        return SessionAuditService.detect_tampering(self.state.audit_chain)

    def get_audit_events(self) -> List[Dict]:
        """Get all audit events in order via AuditService."""
        return SessionAuditService.get_events(self.state.audit_chain)

    def skip_unreviewable(self) -> bool:
        """Skip articles that can't be reviewed at current stage."""
        new_index = NavigationService.skip_unreviewable(
            self.state.articles, self.state.current_index, self.state.stage,
        )
        if new_index != self.state.current_index:
            self.state.current_index = new_index
            return True
        return False

    def advance(self, skip: bool = False) -> None:
        """Move to next article with workflow rules."""
        self.state.current_index = NavigationService.advance(
            self.state.articles, self.state.current_index, self.state.stage, skip,
        )

    def apply_decision(
        self,
        article_id: str,
        stage: str,
        decision: str,
        notes: str = "",
        llm_suggestion: Optional[Dict] = None
    ) -> bool:
        """
        Apply a decision to a specific article by article_id.
        Locates article, delegates to OrchestrationService, applies side effects.
        """
        result, saved_index = SessionOrchestrationService.apply_decision_by_id(
            self.state.articles, self.state.current_index,
            article_id, stage, decision, notes, llm_suggestion,
            self.state.researcher_id, self.state.dynamic_protocol,
            self.state.audit_chain,
        )
        self.state.current_index = saved_index
        if result is None:
            return False
        self._apply_decision_side_effects(result)
        return True

    def get_discussion_articles(self) -> List[ArticleReview]:
        """Get all articles needing discussion."""
        return SessionQueryService.get_discussion_articles(self.state.articles)

    def get_skipped_articles(self) -> List[ArticleReview]:
        """Get all skipped articles."""
        return SessionQueryService.get_skipped_articles(
            self.state.articles, self.state.stage,
        )

    def get_ec_included_articles(self) -> List[ArticleReview]:
        """Get articles that passed EC."""
        return SessionQueryService.get_ec_included_articles(self.state.articles)

    def get_ic_included_articles(self) -> List[ArticleReview]:
        """Get articles that passed IC."""
        return SessionQueryService.get_ic_included_articles(self.state.articles)

    def get_wl_articles(self) -> List[ArticleReview]:
        """Get White Literature articles only."""
        return SessionQueryService.get_wl_articles(self.state.articles)

    def get_gl_articles(self) -> List[ArticleReview]:
        """Get Grey Literature articles only."""
        return SessionQueryService.get_gl_articles(self.state.articles)

    def filter_articles(self, literature_type: Optional[str] = None,
                        stage_decision: Optional[str] = None) -> List[ArticleReview]:
        """Filter articles by literature type and/or stage decision."""
        return SessionQueryService.filter_articles(
            self.state.articles, self.state.stage,
            literature_type, stage_decision,
        )

    def get_wl_progress(self) -> Dict:
        """Get WL-specific progress statistics."""
        return SessionQueryService.get_wl_progress(self.state.articles)

    def get_gl_progress(self) -> Dict:
        """Get GL-specific progress statistics."""
        return SessionQueryService.get_gl_progress(self.state.articles)

    def get_pending_for_stage(self, stage: str) -> int:
        """Get count of pending articles for stage."""
        return SessionQueryService.get_pending_for_stage(
            self.state.articles, stage,
            self.state.ec_completed, self.state.ic_completed,
            self.state.skip_count,
        )

    def is_complete(self) -> bool:
        """Check if session is complete."""
        return NavigationService.is_complete(
            self.state.current_index, self.state.total_count, self.state.stage,
        )

    def get_progress(self) -> Dict:
        """Get progress stats."""
        return SessionQueryService.get_progress(
            self.state.articles, self.state.current_index, self.state.total_count,
            self.state.stage,
            self.state.ec_completed, self.state.ic_completed,
            self.state.included_count, self.state.excluded_count,
            self.state.skip_count, self.state.discussion_count,
        )

    def save(self, output_dir: str = "sessions") -> str:
        """Save session state to file with hash for integrity."""
        now = datetime.now().isoformat()
        self.state.last_saved = now
        path = SessionPersistenceService.save(
            output_dir,
            self.state.session_id, self.state.created_at,
            self.state.protocol_version, self.state.stage,
            self.state.current_index, self.state.total_count,
            self.state.ec_completed, self.state.ic_completed,
            self.state.included_count, self.state.excluded_count,
            self.state.skip_count, self.state.discussion_count,
            self.state.researcher_id, self.state.last_saved,
            self.state.articles,
        )
        return path

    def save_to_json(self, path: str) -> str:
        """Deterministic JSON persistence with full audit chain."""
        now = datetime.now().isoformat()
        self.state.last_saved = now
        result = SessionPersistenceService.save_to_json(
            path,
            self.state.session_id, self.state.created_at,
            self.state.protocol_version, self.state.stage,
            self.state.current_index, self.state.total_count,
            self.state.ec_completed, self.state.ic_completed,
            self.state.included_count, self.state.excluded_count,
            self.state.skip_count, self.state.discussion_count,
            self.state.researcher_id, self.state.last_saved,
            self.state.schema_version,
            self.state.articles,
            self.state.dynamic_protocol,
            self.state.audit_chain,
            self.state.autosave_enabled,
        )
        return result

    def load_from_json(self, path: str) -> bool:
        """Load session from deterministic JSON with validation."""
        result = SessionPersistenceService.load_from_json(path)
        if result is None:
            return False

        self.state.session_id = result["session_id"]
        self.state.created_at = result["created_at"]
        self.state.protocol_version = result["protocol_version"]
        self.state.stage = result["stage"]
        self.state.current_index = result["current_index"]
        self.state.total_count = result["total_count"]
        self.state.ec_completed = result["ec_completed"]
        self.state.ic_completed = result["ic_completed"]
        self.state.included_count = result["included_count"]
        self.state.excluded_count = result["excluded_count"]
        self.state.skip_count = result["skip_count"]
        self.state.discussion_count = result["discussion_count"]
        self.state.researcher_id = result["researcher_id"]
        self.state.last_saved = result["last_saved"]
        self.state.schema_version = result["schema_version"]
        self.state.autosave_enabled = result["autosave_enabled"]

        self.state.articles = [ArticleReview(**a) for a in result["articles"]]

        dp = result["dynamic_protocol"]
        if dp is not None and isinstance(dp, dict):
            try:
                from src.core.dynamic_protocol import DynamicProtocol
                DynamicProtocol.from_dict(dp)
                self.state.dynamic_protocol = dp
            except (TypeError, ValueError):
                self.state.dynamic_protocol = None

        self.state.audit_chain = result["audit_chain"]

        return True

    def compute_checksum(self) -> str:
        """Compute SHA256 checksum of session canonical JSON."""
        full_data = SessionPersistenceService.to_dict_full(
            self.state.session_id, self.state.created_at,
            self.state.protocol_version, self.state.stage,
            self.state.current_index, self.state.total_count,
            self.state.ec_completed, self.state.ic_completed,
            self.state.included_count, self.state.excluded_count,
            self.state.skip_count, self.state.discussion_count,
            self.state.researcher_id, self.state.last_saved,
            self.state.schema_version,
            self.state.articles,
            self.state.dynamic_protocol,
        )
        return SessionPersistenceService.compute_checksum(full_data)

    def _to_dict_full(self) -> Dict:
        """Convert to dictionary with full metadata lineage."""
        return SessionPersistenceService.to_dict_full(
            self.state.session_id, self.state.created_at,
            self.state.protocol_version, self.state.stage,
            self.state.current_index, self.state.total_count,
            self.state.ec_completed, self.state.ic_completed,
            self.state.included_count, self.state.excluded_count,
            self.state.skip_count, self.state.discussion_count,
            self.state.researcher_id, self.state.last_saved,
            self.state.schema_version,
            self.state.articles,
            self.state.dynamic_protocol,
        )

    def _to_dict(self) -> Dict:
        """Convert to dictionary."""
        return SessionPersistenceService.to_dict(
            self.state.session_id, self.state.created_at,
            self.state.protocol_version, self.state.stage,
            self.state.current_index, self.state.total_count,
            self.state.ec_completed, self.state.ic_completed,
            self.state.included_count, self.state.excluded_count,
            self.state.skip_count, self.state.discussion_count,
            self.state.researcher_id, self.state.last_saved,
            self.state.articles,
        )

    @classmethod
    def load(cls, session_id: str, output_dir: str = "sessions") -> Optional["ScreeningSession"]:
        """Load session state from file with validation."""
        path = SessionPersistenceService.resolve_session_path(output_dir, session_id)
        data = SessionPersistenceService.load_session_data(path)
        if data is None:
            return None

        session = cls(
            session_id=data.get("session_id", ""),
            created_at=data.get("created_at", ""),
            protocol_version=data.get("protocol_version", "1.0"),
            stage=data.get("stage", SessionStage.EC.value),
            current_index=data.get("current_index", 0),
            total_count=data.get("total_count", 0),
            ec_completed=data.get("ec_completed", 0),
            ic_completed=data.get("ic_completed", 0),
            included_count=data.get("included_count", 0),
            excluded_count=data.get("excluded_count", 0),
            skip_count=data.get("skip_count", 0),
            discussion_count=data.get("discussion_count", 0),
            researcher_id=data.get("researcher_id", "researcher_1"),
            last_saved=data.get("last_saved", ""),
            schema_version=data.get("schema_version", "2.0"),
            autosave_enabled=data.get("autosave_enabled", False),
        )

        session.state.articles = [
            ArticleReview(**a) for a in data.get("articles", [])
        ]

        dp = data.get("dynamic_protocol")
        if dp is not None and isinstance(dp, dict):
            try:
                from src.core.dynamic_protocol import DynamicProtocol
                DynamicProtocol.from_dict(dp)
                session.state.dynamic_protocol = dp
            except (TypeError, ValueError):
                session.state.dynamic_protocol = None

        session.state.audit_chain = data.get("audit_chain", [])

        return session


def save_screening_session(session: ScreeningSession, output_dir: str = "sessions") -> str:
    """Save session with auto-save and crash recovery support."""
    return session.save(output_dir)


def load_screening_session(session_id: str, output_dir: str = "sessions") -> Optional[ScreeningSession]:
    """Load session with validation."""
    return ScreeningSession.load(session_id, output_dir)


def list_sessions(output_dir: str = "sessions") -> List[Dict[str, str]]:
    """List all saved sessions."""
    return SessionPersistenceService.list_sessions(output_dir)


def recover_session(output_dir: str = "sessions") -> Optional[ScreeningSession]:
    """Recover most recent session from crash."""
    session_id = SessionPersistenceService.recover_session(output_dir)
    if session_id is None:
        return None
    return load_screening_session(session_id, output_dir)


def create_session(article_records: List, protocol_version: str = "1.0") -> ScreeningSession:
    """Create new screening session with default dynamic protocol."""
    from src.core.dynamic_protocol import DynamicProtocol, create_default_protocol
    
    session = ScreeningSession(
        session_id=datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(uuid.uuid4())[:4],
        created_at=datetime.now().isoformat(),
        protocol_version=protocol_version,
        stage=SessionStage.EC.value
    )
    session.add_articles(article_records)
    
    default_protocol = create_default_protocol()
    session.dynamic_protocol = default_protocol.to_dict()
    
    return session