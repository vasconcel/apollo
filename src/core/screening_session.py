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


@dataclass
class ScreeningSession:
    """Screening session state with workflow rules and dynamic protocol."""
    session_id: str
    created_at: str
    protocol_version: str = "1.0"
    stage: str = SessionStage.EC.value
    
    articles: List[ArticleReview] = field(default_factory=list)
    
    dynamic_protocol: Optional[Dict] = field(default_factory=lambda: None)
    
    current_index: int = 0
    total_count: int = 0
    
    ec_completed: int = 0
    ic_completed: int = 0
    qc_completed: int = 0

    included_count: int = 0
    excluded_count: int = 0
    skip_count: int = 0
    discussion_count: int = 0
    
    researcher_id: str = "researcher_1"
    last_saved: str = ""
    
    schema_version: str = "2.0"
    autosave_enabled: bool = False
    _audit_chain: List[Dict] = field(default_factory=list)
    
    def add_articles(self, article_records: List) -> None:
        """Add articles to session via IngestionService."""
        self.articles = SessionIngestionService.add_articles(article_records)
        self.total_count = len(self.articles)

    def ingest_from_upload(
        self,
        uploaded_file,
        stage: str = "ec"
    ) -> List[ArticleReview]:
        """Ingest articles from an uploaded file via IngestionService."""
        articles = SessionIngestionService.ingest_from_bytes(
            uploaded_file.getvalue(), uploaded_file.name, stage,
        )
        self.articles = articles
        self.total_count = len(articles)
        return articles
    
    def get_current_article(self) -> Optional[ArticleReview]:
        """Get current article for review."""
        return NavigationService.get_current_article(self.articles, self.current_index)
    
    def can_review_current_at_stage(self, stage: str) -> bool:
        """Check if current article can be reviewed at this stage."""
        return NavigationService.can_review_current_at_stage(self.articles, self.current_index, stage)
    
    def record_decision(
        self,
        decision: str,
        notes: str = "",
        llm_suggestion: Optional[Dict] = None
    ) -> bool:
        """Record researcher decision at current stage via DecisionService."""
        article = self.get_current_article()
        if not article:
            return False

        result = SessionDecisionService.apply_review_decision(
            article, self.stage, decision, notes, llm_suggestion,
            self.researcher_id, self.dynamic_protocol, self._audit_chain,
        )

        if not result["success"]:
            return False

        for key, value in result["article_field_updates"].items():
            setattr(article, key, value)

        for counter, delta in result["counter_increments"].items():
            setattr(self, counter, getattr(self, counter) + delta)

        self.last_saved = result["timestamp"]
        self._audit_chain.append(result["audit_event"])

        if result["protocol_snapshot"]:
            if not hasattr(self, "_snapshots"):
                self._snapshots = []
            self._snapshots.append(result["protocol_snapshot"])

        return True
    
    def _append_audit_event(self, article: ArticleReview, decision: str, notes: str, stage: str) -> None:
        """Append immutable audit event to chain via AuditService."""
        event = SessionAuditService.append_event(
            self._audit_chain, self.researcher_id, article, decision, notes, stage,
        )
        self._audit_chain.append(event)
    
    def verify_audit_chain(self) -> tuple:
        """Verify audit chain integrity via AuditService."""
        return SessionAuditService.verify_chain(self._audit_chain)

    def detect_tampering(self) -> tuple:
        """Detect tampering in audit chain via AuditService."""
        return SessionAuditService.detect_tampering(self._audit_chain)

    def get_audit_events(self) -> List[Dict]:
        """Get all audit events in order via AuditService."""
        return SessionAuditService.get_events(self._audit_chain)
    
    def skip_unreviewable(self) -> bool:
        """Skip articles that can't be reviewed at current stage."""
        new_index = NavigationService.skip_unreviewable(self.articles, self.current_index, self.stage)
        if new_index != self.current_index:
            self.current_index = new_index
            return True
        return False
    
    def advance(self, skip: bool = False) -> None:
        """Move to next article with workflow rules."""
        self.current_index = NavigationService.advance(self.articles, self.current_index, self.stage, skip)
    
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
        Locates article, temporarily sets index, and records decision.
        """
        for idx, article in enumerate(self.articles):
            if article.article_id == article_id:
                saved_index = self.current_index
                self.current_index = idx
                result = self.record_decision(decision, notes, llm_suggestion)
                self.current_index = saved_index
                return result
        return False
    
    def get_discussion_articles(self) -> List[ArticleReview]:
        """Get all articles needing discussion."""
        return SessionQueryService.get_discussion_articles(self.articles)
    
    def get_skipped_articles(self) -> List[ArticleReview]:
        """Get all skipped articles."""
        return SessionQueryService.get_skipped_articles(self.articles, self.stage)
    
    def get_ec_included_articles(self) -> List[ArticleReview]:
        """Get articles that passed EC."""
        return SessionQueryService.get_ec_included_articles(self.articles)
    
    def get_ic_included_articles(self) -> List[ArticleReview]:
        """Get articles that passed IC."""
        return SessionQueryService.get_ic_included_articles(self.articles)
    
    def get_wl_articles(self) -> List[ArticleReview]:
        """
        Get White Literature articles only.
        """
        return SessionQueryService.get_wl_articles(self.articles)
    
    def get_gl_articles(self) -> List[ArticleReview]:
        """
        Get Grey Literature articles only.
        """
        return SessionQueryService.get_gl_articles(self.articles)
    
    def filter_articles(self, literature_type: Optional[str] = None,
                        stage_decision: Optional[str] = None) -> List[ArticleReview]:
        """
        Filter articles by literature type and/or stage decision.
        """
        return SessionQueryService.filter_articles(
            self.articles, self.stage, literature_type, stage_decision,
        )
    
    def get_wl_progress(self) -> Dict:
        """Get WL-specific progress statistics."""
        return SessionQueryService.get_wl_progress(self.articles)
    
    def get_gl_progress(self) -> Dict:
        """Get GL-specific progress statistics."""
        return SessionQueryService.get_gl_progress(self.articles)
    
    def get_pending_for_stage(self, stage: str) -> int:
        """Get count of pending articles for stage."""
        return SessionQueryService.get_pending_for_stage(
            self.articles, stage,
            self.ec_completed, self.ic_completed, self.skip_count,
        )
    
    def is_complete(self) -> bool:
        """Check if session is complete."""
        return NavigationService.is_complete(self.current_index, self.total_count, self.stage)
    
    def _get_stage_field(self, stage: str) -> str:
        """Get stage field name."""
        stage_map = {
            SessionStage.EC.value: "ec_stage",
            SessionStage.IC.value: "ic_stage"
        }
        return stage_map.get(stage, "")
    
    def get_progress(self) -> Dict:
        """Get progress stats."""
        return SessionQueryService.get_progress(
            self.articles, self.current_index, self.total_count, self.stage,
            self.ec_completed, self.ic_completed,
            self.included_count, self.excluded_count,
            self.skip_count, self.discussion_count,
        )
    
    def save(self, output_dir: str = "sessions") -> str:
        """Save session state to file with hash for integrity."""
        path = SessionPersistenceService.save(
            output_dir,
            self.session_id, self.created_at, self.protocol_version, self.stage,
            self.current_index, self.total_count,
            self.ec_completed, self.ic_completed,
            self.included_count, self.excluded_count,
            self.skip_count, self.discussion_count,
            self.researcher_id, self.last_saved,
            self.articles,
        )
        self.last_saved = datetime.now().isoformat()
        return path
    
    def save_to_json(self, path: str) -> str:
        """
        Deterministic JSON persistence with full audit chain.
        """
        result = SessionPersistenceService.save_to_json(
            path,
            self.session_id, self.created_at, self.protocol_version, self.stage,
            self.current_index, self.total_count,
            self.ec_completed, self.ic_completed,
            self.included_count, self.excluded_count,
            self.skip_count, self.discussion_count,
            self.researcher_id, self.last_saved,
            self.schema_version,
            self.articles,
            self.dynamic_protocol,
            self._audit_chain,
            self.autosave_enabled,
        )
        self.last_saved = datetime.now().isoformat()
        return result
    
    def load_from_json(self, path: str) -> bool:
        """
        Load session from deterministic JSON with validation.
        """
        result = SessionPersistenceService.load_from_json(path)
        if result is None:
            return False

        self.session_id = result["session_id"]
        self.created_at = result["created_at"]
        self.protocol_version = result["protocol_version"]
        self.stage = result["stage"]
        self.current_index = result["current_index"]
        self.total_count = result["total_count"]
        self.ec_completed = result["ec_completed"]
        self.ic_completed = result["ic_completed"]
        self.included_count = result["included_count"]
        self.excluded_count = result["excluded_count"]
        self.skip_count = result["skip_count"]
        self.discussion_count = result["discussion_count"]
        self.researcher_id = result["researcher_id"]
        self.last_saved = result["last_saved"]
        self.schema_version = result["schema_version"]
        self.autosave_enabled = result["autosave_enabled"]

        self.articles = [ArticleReview(**a) for a in result["articles"]]

        dp = result["dynamic_protocol"]
        if dp is not None and isinstance(dp, dict):
            try:
                from src.core.dynamic_protocol import DynamicProtocol
                DynamicProtocol.from_dict(dp)
                self.dynamic_protocol = dp
            except (TypeError, ValueError):
                self.dynamic_protocol = None

        self._audit_chain = result["audit_chain"]

        return True
    
    def compute_checksum(self) -> str:
        """Compute SHA256 checksum of session canonical JSON."""
        full_data = SessionPersistenceService.to_dict_full(
            self.session_id, self.created_at, self.protocol_version, self.stage,
            self.current_index, self.total_count,
            self.ec_completed, self.ic_completed,
            self.included_count, self.excluded_count,
            self.skip_count, self.discussion_count,
            self.researcher_id, self.last_saved,
            self.schema_version,
            self.articles,
            self.dynamic_protocol,
        )
        return SessionPersistenceService.compute_checksum(full_data)
    
    def _to_dict_full(self) -> Dict:
        """Convert to dictionary with full metadata lineage."""
        return SessionPersistenceService.to_dict_full(
            self.session_id, self.created_at, self.protocol_version, self.stage,
            self.current_index, self.total_count,
            self.ec_completed, self.ic_completed,
            self.included_count, self.excluded_count,
            self.skip_count, self.discussion_count,
            self.researcher_id, self.last_saved,
            self.schema_version,
            self.articles,
            self.dynamic_protocol,
        )
    
    def _to_dict(self) -> Dict:
        """Convert to dictionary."""
        return SessionPersistenceService.to_dict(
            self.session_id, self.created_at, self.protocol_version, self.stage,
            self.current_index, self.total_count,
            self.ec_completed, self.ic_completed,
            self.included_count, self.excluded_count,
            self.skip_count, self.discussion_count,
            self.researcher_id, self.last_saved,
            self.articles,
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
            autosave_enabled=data.get("autosave_enabled", False)
        )

        session.articles = [
            ArticleReview(**a) for a in data.get("articles", [])
        ]

        dp = data.get("dynamic_protocol")
        if dp is not None and isinstance(dp, dict):
            try:
                from src.core.dynamic_protocol import DynamicProtocol
                DynamicProtocol.from_dict(dp)
                session.dynamic_protocol = dp
            except (TypeError, ValueError):
                session.dynamic_protocol = None

        session._audit_chain = data.get("audit_chain", [])

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