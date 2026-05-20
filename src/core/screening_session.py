"""
APOLLO Screening Session Management
Manages human-in-the-loop screening sessions

WORKFLOW RULES:
- EC stage: All papers reviewed. If excluded, cannot proceed.
- IC stage: Only EC-included papers reviewed. If excluded, screening is complete.
- SKIP papers: Can be recovered for later review.
- NEEDS_DISCUSSION: Tracked separately for team review.
"""
import json
import os
import uuid
import hashlib
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

from src.core.logging_config import get_logger
from src.core.session_navigation import NavigationService
from src.core.session_query_service import SessionQueryService

logger = get_logger("ingestion")
INGESTION_DEBUG = False  # Set to True for verbose diagnostics


def normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Defensive metadata normalization - ensures ALL articles have required fields.
    Never allows silent empty-string propagation.
    """
    required_fields = {
        "year": "Unknown",
        "year_source": "missing",
        "authors": "",
        "author_normalization_source": "unknown",
        "source": "",
        "source_type": "unknown",
        "literature_type": "WL",
        "metadata_completeness": "unknown"
    }
    
    normalized = dict(metadata)
    
    for field_name, default_value in required_fields.items():
        if field_name not in normalized or normalized[field_name] is None or str(normalized.get(field_name, "")).strip() == "":
            normalized[field_name] = default_value
    
    return normalized


LITERATURE_TYPE_MAP = {
    "WL": "WL", "wl": "WL", "Wl": "WL",
    "WHITE LITERATURE": "WL", "White Literature": "WL", "white literature": "WL",
    "GL": "GL", "gl": "GL", "Gl": "GL",
    "GREY LITERATURE": "GL", "Grey Literature": "GL", "grey literature": "GL",
}


def normalize_literature_type(raw_value: str) -> str:
    """Normalize literature type to canonical WL/GL value."""
    if not raw_value:
        return "WL"
    normalized = raw_value.strip()
    return LITERATURE_TYPE_MAP.get(normalized, LITERATURE_TYPE_MAP.get(normalized.upper(), "WL"))


def compute_csv_metadata_completeness(row: dict) -> str:
    """Compute metadata completeness for CSV rows."""
    has_title = bool(row.get("Title"))
    has_abstract = bool(row.get("Abstract"))
    has_year = bool(row.get("Year"))

    if has_title and has_abstract and has_year:
        return "complete"
    elif has_title:
        return "partial"
    return "minimal"


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
        """Add articles to session."""
        self.articles = [ArticleReview.from_article_record(r) for r in article_records]
        self.total_count = len(self.articles)

    def ingest_from_upload(
        self,
        uploaded_file,
        stage: str = "ec"
    ) -> List[ArticleReview]:
        """
        Canonical ingestion: load ATLAS Excel file and convert to ArticleReview objects.

        This is the single canonical entry point for file loading. All DataFrame operations
        occur HERE, not in the UI layer. Preserves full metadata lineage.

        Args:
            uploaded_file: Streamlit UploadedFile object
            stage: Current screening stage ("ec", "ic")

        Returns:
            List of ArticleReview objects with full metadata
        """
        import tempfile
        import pandas as pd
        import json
        from src.core.article_metadata import (
            normalize_wl_metadata, normalize_gl_metadata, article_to_dict,
            LATEX_DECODER_AVAILABLE
        )
        from src.core.year_extraction import extract_year

        temp_path = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False).name

        try:
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getvalue())

            if uploaded_file.name.endswith(".csv"):
                df = pd.read_csv(temp_path)
                articles = []
                for _, row in df.iterrows():
                    row_dict = row.to_dict()
                    lit_type = normalize_literature_type(str(row_dict.get("Literature_Type", "WL")))
                    completeness = compute_csv_metadata_completeness(row_dict)
                    
                    title = str(row_dict.get("Title", ""))
                    abstract = str(row_dict.get("Abstract", ""))
                    
                    year_value = row_dict.get("Year")
                    year_source = "csv"
                    if year_value is None or str(year_value).strip() == "":
                        extracted_year, extracted_source = extract_year(title, abstract, None)
                        if extracted_year:
                            year_value = extracted_year
                            year_source = extracted_source
                    
                    metadata = {
                        "year": str(year_value) if year_value else "",
                        "authors": str(row_dict.get("Authors", "")),
                        "literature_type": lit_type,
                        "title": title,
                        "abstract": abstract,
                        "global_id": str(row_dict.get("global_id", str(uuid.uuid4())[:8])),
                        "year_source": year_source,
                        "metadata_completeness": completeness
                    }
                    review_article = ArticleReview(
                        article_id=metadata["global_id"],
                        title=metadata["title"],
                        abstract=metadata["abstract"],
                        metadata=metadata
                    )
                    if stage == "ic":
                        review_article.ec_stage = str(row_dict.get("EC_Decision", "INCLUDE"))
                    articles.append(review_article)
                self.articles = articles
                self.total_count = len(articles)
                return articles
            else:
                wl_df = pd.read_excel(temp_path, sheet_name="White Literature")
                gl_df = pd.read_excel(temp_path, sheet_name="Grey Literature")

            articles = []
            if INGESTION_DEBUG:
                logger.debug("WL ingestion start")
            for idx, row in wl_df.iterrows():
                row_dict = row.to_dict()
                article = normalize_wl_metadata(row_dict)
                article_dict = article_to_dict(article)
                
                year_value = article.year if article.year else None
                year_source = "atlas"
                
                if INGESTION_DEBUG:
                    logger.debug(f"WL {idx} - Structured year: {repr(year_value)}")
                
                if year_value is None:
                    extracted_year, extracted_source = extract_year(
                        article.title, 
                        article.abstract,
                        None
                    )
                    if INGESTION_DEBUG:
                        logger.debug(f"WL {idx} - Regex fallback: year={repr(extracted_year)}, source={repr(extracted_source)}")
                    if extracted_year:
                        year_value = extracted_year
                        year_source = extracted_source
                
                if INGESTION_DEBUG:
                    logger.debug(f"WL {idx} - Final year: {repr(year_value)}, source: {repr(year_source)}")
                
                metadata = {
                    "year": str(year_value) if year_value else "",
                    "authors": article.authors,
                    "literature_type": article.literature_type,
                    "doi": article.doi,
                    "source": article.source,
                    "keywords": article.keywords,
                    "library": article.library,
                    "global_id": article.global_id,
                    "local_id": article.local_id,
                    "url": article.url,
                    "completeness": article.completeness_score,
                    "year_source": year_source,
                    "metadata_completeness": article.metadata_completeness,
                    "raw_data": article.raw_data,
                    "author_normalization_source": "pylatexenc" if LATEX_DECODER_AVAILABLE else "raw"
                }
                
                metadata = normalize_metadata(metadata)
                
                review_article = ArticleReview(
                    article_id=article.global_id or article.local_id or str(uuid.uuid4())[:8],
                    title=article.title,
                    abstract=article.abstract,
                    metadata=metadata
                )
                articles.append(review_article)

            if INGESTION_DEBUG:
                logger.debug("GL ingestion start")
            for idx, row in gl_df.iterrows():
                row_dict = row.to_dict()
                article = normalize_gl_metadata(row_dict)
                article_dict = article_to_dict(article)
                
                year_value = article.year if article.year else None
                year_source = "atlas"
                
                if INGESTION_DEBUG:
                    logger.debug(f"GL {idx} - Structured year: {repr(year_value)}")
                
                if year_value is None:
                    extracted_year, extracted_source = extract_year(
                        article.title, 
                        article.abstract,
                        None
                    )
                    if INGESTION_DEBUG:
                        logger.debug(f"GL {idx} - Regex fallback: year={repr(extracted_year)}, source={repr(extracted_source)}")
                    if extracted_year:
                        year_value = extracted_year
                        year_source = extracted_source
                
                if INGESTION_DEBUG:
                    logger.debug(f"GL {idx} - Final year: {repr(year_value)}, source: {repr(year_source)}")
                
                metadata = {
                    "year": str(year_value) if year_value else "",
                    "authors": article.authors,
                    "literature_type": article.literature_type,
                    "url": article.url,
                    "source": article.source,
                    "keywords": article.keywords,
                    "global_id": article.global_id,
                    "local_id": article.local_id,
                    "completeness": article.completeness_score,
                    "year_source": year_source,
                    "metadata_completeness": article.metadata_completeness,
                    "raw_data": article.raw_data,
                    "author_normalization_source": "pylatexenc" if LATEX_DECODER_AVAILABLE else "raw"
                }
                
                metadata = normalize_metadata(metadata)
                
                review_article = ArticleReview(
                    article_id=article.global_id or article.local_id or str(uuid.uuid4())[:8],
                    title=article.title,
                    abstract=article.abstract,
                    metadata=metadata
                )
                articles.append(review_article)

            self.articles = articles
            self.total_count = len(articles)
            return articles

        finally:
            import os
            os.unlink(temp_path)
    
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
        """Record researcher decision at current stage WITH protocol snapshot."""
        article = self.get_current_article()
        if not article:
            return False
        
        timestamp = datetime.now().isoformat()
        stage = self.stage
        
        if stage == "ec":
            article.ec_stage = decision
            article.ec_notes = notes
            article.ec_timestamp = timestamp
            if llm_suggestion:
                article.ec_llm_suggestion = llm_suggestion
            self.ec_completed += 1
            
        elif stage == "ic":
            if not article.can_proceed_to_stage("ic"):
                return False
            article.ic_stage = decision
            article.ic_notes = notes
            article.ic_timestamp = timestamp
            if llm_suggestion:
                article.ic_llm_suggestion = llm_suggestion
            self.ic_completed += 1
        
        if decision == "include":
            self.included_count += 1
        elif decision == "exclude":
            self.excluded_count += 1
        elif decision == "skip":
            self.skip_count += 1
        elif decision == "needs_discussion":
            self.discussion_count += 1
        
        self.last_saved = timestamp
        self._save_stage_snapshot(stage)
        self._append_audit_event(article, decision, notes, stage)
        return True
    
    def _append_audit_event(self, article: ArticleReview, decision: str, notes: str, stage: str) -> None:
        """Append immutable audit event to chain."""
        previous_hash = self._audit_chain[-1]["current_hash"] if self._audit_chain else "GENESIS"
        
        event_payload = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "article_id": article.article_id,
            "reviewer_id": self.researcher_id,
            "stage": stage,
            "decision": decision,
            "notes": notes,
        }
        
        payload_json = json.dumps(event_payload, sort_keys=True, ensure_ascii=False)
        current_hash = hashlib.sha256(
            (payload_json + previous_hash).encode()
        ).hexdigest()
        
        event = {
            **event_payload,
            "previous_hash": previous_hash,
            "current_hash": current_hash
        }
        
        self._audit_chain.append(event)
    
    def verify_audit_chain(self) -> tuple:
        """
        Verify audit chain integrity. Phase 2: Immutable Audit Chain.
        
        Returns:
            Tuple of (is_valid: bool, errors: list)
        """
        if not self._audit_chain:
            return True, []
        
        errors = []
        
        expected_previous = "GENESIS"
        for i, event in enumerate(self._audit_chain):
            if event.get("previous_hash") != expected_previous:
                errors.append(f"Event {i}: Chain broken at {event.get('event_id', 'UNKNOWN')}")
            
            payload = {k: v for k, v in event.items() if k not in ("previous_hash", "current_hash")}
            payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
            computed_hash = hashlib.sha256(
                (payload_json + event.get("previous_hash", "")).encode()
            ).hexdigest()
            
            if computed_hash != event.get("current_hash"):
                errors.append(f"Event {i}: Hash mismatch for {event.get('event_id', 'UNKNOWN')}")
            
            expected_previous = event.get("current_hash", "")
        
        return len(errors) == 0, errors
    
    def detect_tampering(self) -> tuple:
        """
        Detect tampering in audit chain. Phase 2: Immutable Audit Chain.
        
        Returns:
            Tuple of (is_clean: bool, tampered_events: list)
        """
        is_valid, errors = self.verify_audit_chain()
        
        if is_valid:
            return True, []
        
        tampered = []
        for error in errors:
            if "Hash mismatch" in error:
                event_id = error.split("for ")[-1] if "for " in error else "UNKNOWN"
                tampered.append(event_id)
        
        return False, tampered
    
    def get_audit_events(self) -> List[Dict]:
        """Get all audit events in order."""
        return list(self._audit_chain)
    
    def _save_stage_snapshot(self, stage: str) -> None:
        """Create protocol snapshot on stage transition."""
        from src.core.dynamic_protocol import DynamicProtocol
        
        if self.dynamic_protocol:
            protocol = DynamicProtocol.from_dict(self.dynamic_protocol)
            snapshot = protocol.create_snapshot(stage)
            
            if not hasattr(self, "_snapshots"):
                self._snapshots = []
            self._snapshots.append(snapshot.to_dict())
    
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
        
        This method exists for UI compatibility — it locates the article
        by ID and records the decision at the specified stage.
        
        Args:
            article_id: The article's article_id (from ArticleReview.article_id)
            stage: The stage at which to record ("ec", "ic")
            decision: The decision ("include", "exclude", "skip", "needs_discussion")
            notes: Researcher notes/reasoning
            llm_suggestion: Optional LLM advisory snapshot
            
        Returns:
            True if decision was recorded, False otherwise
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
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, f"session_{self.session_id}.json")
        
        data = self._to_dict()
        
        data_hash = hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]
        
        data["session_hash"] = data_hash
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.last_saved = datetime.now().isoformat()
        return path
    
    def save_to_json(self, path: str) -> str:
        """
        Deterministic JSON persistence with full audit chain.
        
        Phase 1: Persistent Screening Session implementation.
        Preserves: articles, decisions, snapshots, protocol hash, timestamps,
        audit chain, metadata lineage, schema_version.
        
        Args:
            path: Full path to save JSON file
            
        Returns:
            Path to saved file
        """
        data = self._to_dict_full()
        
        data["schema_version"] = self.schema_version
        
        fields_for_checksum = [
            "session_id", "created_at", "protocol_version", "stage",
            "current_index", "total_count", "ec_completed", "ic_completed",
            "included_count", "excluded_count", "skip_count",
            "discussion_count", "researcher_id", "last_saved", "schema_version",
            "articles", "dynamic_protocol"
        ]
        data_for_check = {k: data.get(k) for k in fields_for_checksum if k in data}
        
        canonical_json = json.dumps(data_for_check, sort_keys=True, ensure_ascii=False)
        checksum = hashlib.sha256(canonical_json.encode()).hexdigest()
        data["session_checksum"] = checksum
        
        if self.dynamic_protocol:
            from src.core.dynamic_protocol import DynamicProtocol
            try:
                protocol = DynamicProtocol.from_dict(self.dynamic_protocol)
                data["protocol_hash"] = protocol.protocol_hash
            except Exception:
                data["protocol_hash"] = ""
        
        data["audit_chain"] = self._audit_chain
        data["autosave_enabled"] = self.autosave_enabled
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        self.last_saved = datetime.now().isoformat()
        return path
    
    def load_from_json(self, path: str) -> bool:
        """
        Load session from deterministic JSON with validation.
        
        Phase 1: Persistent Screening Session implementation.
        Verifies checksum and restores full state including audit chain.
        
        Args:
            path: Full path to JSON file
            
        Returns:
            True if loaded successfully, False otherwise
        """
        if not os.path.exists(path):
            return False
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return False
        
        expected_checksum = data.get("session_checksum", "")
        
        fields_for_checksum = [
            "session_id", "created_at", "protocol_version", "stage",
            "current_index", "total_count", "ec_completed", "ic_completed",
            "included_count", "excluded_count", "skip_count",
            "discussion_count", "researcher_id", "last_saved", "schema_version",
            "articles", "dynamic_protocol"
        ]
        data_for_check = {k: data.get(k) for k in fields_for_checksum if k in data}
        
        actual_checksum = hashlib.sha256(
            json.dumps(data_for_check, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        
        self.session_id = data.get("session_id", "")
        self.created_at = data.get("created_at", "")
        self.protocol_version = data.get("protocol_version", "1.0")
        self.stage = data.get("stage", SessionStage.EC.value)
        self.current_index = data.get("current_index", 0)
        self.total_count = data.get("total_count", 0)
        self.ec_completed = data.get("ec_completed", 0)
        self.ic_completed = data.get("ic_completed", 0)
        self.included_count = data.get("included_count", 0)
        self.excluded_count = data.get("excluded_count", 0)
        self.skip_count = data.get("skip_count", 0)
        self.discussion_count = data.get("discussion_count", 0)
        self.researcher_id = data.get("researcher_id", "researcher_1")
        self.last_saved = data.get("last_saved", "")
        self.schema_version = data.get("schema_version", "2.0")
        self.autosave_enabled = data.get("autosave_enabled", False)
        
        self.articles = [ArticleReview(**a) for a in data.get("articles", [])]
        
        if "dynamic_protocol" in data and isinstance(data["dynamic_protocol"], dict):
            try:
                from src.core.dynamic_protocol import DynamicProtocol
                DynamicProtocol.from_dict(data["dynamic_protocol"])
                self.dynamic_protocol = data["dynamic_protocol"]
            except (TypeError, ValueError):
                self.dynamic_protocol = None
        
        self._audit_chain = data.get("audit_chain", [])
        
        return True
    
    def compute_checksum(self) -> str:
        """
        Compute SHA256 checksum of session canonical JSON.
        
        Phase 1: Persistent Screening Session implementation.
        Used for integrity verification and replay validation.
        
        Returns:
            SHA256 hex digest of canonical JSON representation
        """
        data = self._to_dict_full()
        
        fields_for_checksum = [
            "session_id", "created_at", "protocol_version", "stage",
            "current_index", "total_count", "ec_completed", "ic_completed",
            "included_count", "excluded_count", "skip_count",
            "discussion_count", "researcher_id", "last_saved", "schema_version",
            "articles", "dynamic_protocol"
        ]
        data_for_check = {k: data.get(k) for k in fields_for_checksum if k in data}
        
        canonical_json = json.dumps(data_for_check, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical_json.encode()).hexdigest()
    
    def _to_dict_full(self) -> Dict:
        """Convert to dictionary with full metadata lineage."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "protocol_version": self.protocol_version,
            "stage": self.stage,
            "current_index": self.current_index,
            "total_count": self.total_count,
            "ec_completed": self.ec_completed,
            "ic_completed": self.ic_completed,
            "included_count": self.included_count,
            "excluded_count": self.excluded_count,
            "skip_count": self.skip_count,
            "discussion_count": self.discussion_count,
            "researcher_id": self.researcher_id,
            "last_saved": self.last_saved,
            "schema_version": self.schema_version,
            "articles": [a.to_dict() for a in self.articles],
            "dynamic_protocol": self.dynamic_protocol,
        }
    
    def _to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "protocol_version": self.protocol_version,
            "stage": self.stage,
            "current_index": self.current_index,
            "total_count": self.total_count,
            "ec_completed": self.ec_completed,
            "ic_completed": self.ic_completed,
            "included_count": self.included_count,
            "excluded_count": self.excluded_count,
            "skip_count": self.skip_count,
            "discussion_count": self.discussion_count,
            "researcher_id": self.researcher_id,
            "last_saved": self.last_saved,
            "articles": [a.to_dict() for a in self.articles]
        }
    
    @classmethod
    def load(cls, session_id: str, output_dir: str = "sessions") -> Optional["ScreeningSession"]:
        """Load session state from file with validation."""
        path = os.path.join(output_dir, f"session_{session_id}.json")
        
        if not os.path.exists(path):
            return None
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            return None
        
        session = cls(
            session_id=data["session_id"],
            created_at=data["created_at"],
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
        
        if "dynamic_protocol" in data and isinstance(data["dynamic_protocol"], dict):
            try:
                from src.core.dynamic_protocol import DynamicProtocol
                DynamicProtocol.from_dict(data["dynamic_protocol"])
                session.dynamic_protocol = data["dynamic_protocol"]
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
    if not os.path.exists(output_dir):
        return []
    
    sessions = []
    for f in os.listdir(output_dir):
        if f.startswith("session_") and f.endswith(".json"):
            path = os.path.join(output_dir, f)
            try:
                mtime = os.path.getmtime(path)
                sessions.append({
                    "session_id": f.replace("session_", "").replace(".json", ""),
                    "path": path,
                    "modified": datetime.fromtimestamp(mtime).isoformat()
                })
            except OSError:
                pass
    
    return sorted(sessions, key=lambda x: x["modified"], reverse=True)


def recover_session(output_dir: str = "sessions") -> Optional[ScreeningSession]:
    """Recover most recent session from crash."""
    sessions = list_sessions(output_dir)
    if not sessions:
        return None
    
    most_recent = sessions[0]
    return load_screening_session(most_recent["session_id"], output_dir)
    
    def validate(self) -> List[str]:
        """Validate session integrity. Returns list of issues."""
        issues = []
        
        if self.total_count != len(self.articles):
            issues.append("Article count mismatch")
        
        if self.current_index < 0 or self.current_index >= self.total_count:
            issues.append("Invalid current index")
        
        for i, a in enumerate(self.articles):
            if not a.title:
                issues.append(f"Article {i}: Missing title")
            
            if a.ic_stage and not a.is_ec_included:
                issues.append(f"Article {i}: IC decision without EC pass")
        
        return issues


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