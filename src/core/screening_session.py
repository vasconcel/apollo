"""
APOLLO Screening Session Management
Manages human-in-the-loop screening sessions

WORKFLOW RULES:
- EC stage: All papers reviewed. If excluded, cannot proceed.
- IC stage: Only EC-included papers reviewed. If excluded, cannot proceed to QC.
- QC stage: Only IC-included papers reviewed.
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
    qc_llm_suggestion: Dict[str, Any] = field(default_factory=dict)
    
    final_decision: str = ""
    
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
        return self.ec_stage == "needs_discussion" or self.ic_stage == "needs_discussion" or self.qc_stage == "needs_discussion"
    
    def get_current_stage_decision(self, stage: str) -> str:
        """Get decision for current stage."""
        if stage == "ec":
            return self.ec_stage
        elif stage == "ic":
            return self.ic_stage
        elif stage == "qc":
            return self.qc_stage
        return ""
    
    def can_proceed_to_stage(self, stage: str) -> bool:
        """Check if can proceed to next stage."""
        if stage == "ic":
            return self.is_ec_included
        elif stage == "qc":
            return self.is_ic_included
        return True
    
    def compute_final_decision(self) -> str:
        """Compute final decision based on stage progression."""
        if not self.is_ec_included:
            return "EXCLUDE"
        if not self.is_ic_included:
            return "EXCLUDE"
        if not self.is_qc_included:
            return "EXCLUDE"
        
        if self.is_discussion_needed:
            return "NEEDS_DISCUSSION"
        
        return "INCLUDE"
    
    @classmethod
    def from_article_record(cls, record) -> "ArticleReview":
        """Create from ArticleRecord."""
        return cls(
            article_id=record.global_id or record.local_id or record.posicao or str(uuid.uuid4())[:8],
            title=record.title,
            abstract=record.abstract,
            metadata={
                "library": record.library,
                "global_id": record.global_id,
                "local_id": record.local_id,
                "keywords": record.keywords,
                "literature_type": record.literature_type,
                "url": record.url,
                "source_file": record.source_file
            }
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
    
    def add_articles(self, article_records: List) -> None:
        """Add articles to session."""
        self.articles = [ArticleReview.from_article_record(r) for r in article_records]
        self.total_count = len(self.articles)
    
    def get_current_article(self) -> Optional[ArticleReview]:
        """Get current article for review."""
        if 0 <= self.current_index < len(self.articles):
            return self.articles[self.current_index]
        return None
    
    def can_review_current_at_stage(self, stage: str) -> bool:
        """Check if current article can be reviewed at this stage."""
        article = self.get_current_article()
        if not article:
            return False
        return article.can_proceed_to_stage(stage)
    
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
            
        elif stage == "qc":
            if not article.can_proceed_to_stage("qc"):
                return False
            article.qc_stage = decision
            article.qc_notes = notes
            article.qc_timestamp = timestamp
            if llm_suggestion:
                article.qc_llm_suggestion = llm_suggestion
            self.qc_completed += 1
        
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
        return True
    
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
        article = self.get_current_article()
        if not article:
            return False
        
        if not article.can_proceed_to_stage(self.stage):
            self.current_index += 1
            return True
        return False
    
    def advance(self, skip: bool = False) -> None:
        """Move to next article with workflow rules."""
        if skip:
            self.current_index += 1
            return
        
        while self.current_index < len(self.articles):
            article = self.articles[self.current_index]
            decision = article.get_current_stage_decision(self.stage)
            
            if decision == "":
                break
            
            self.current_index += 1
    
    def get_discussion_articles(self) -> List[ArticleReview]:
        """Get all articles needing discussion."""
        return [a for a in self.articles if a.is_discussion_needed]
    
    def get_skipped_articles(self) -> List[ArticleReview]:
        """Get all skipped articles."""
        result = []
        for a in self.articles:
            stage_field = self._get_stage_field(self.stage)
            if getattr(a, stage_field, "") == "skip":
                result.append(a)
        return result
    
    def get_ec_included_articles(self) -> List[ArticleReview]:
        """Get articles that passed EC."""
        return [a for a in self.articles if a.is_ec_included]
    
    def get_ic_included_articles(self) -> List[ArticleReview]:
        """Get articles that passed IC."""
        return [a for a in self.articles if a.is_ic_included]
    
    def get_pending_for_stage(self, stage: str) -> int:
        """Get count of pending articles for stage."""
        if stage == "ec":
            return self.total_count - self.ec_completed - self.skip_count
        elif stage == "ic":
            return len(self.get_ec_included_articles()) - self.ic_completed - self.skip_count
        elif stage == "qc":
            return len(self.get_ic_included_articles()) - self.qc_completed - self.skip_count
        return 0
    
    def is_complete(self) -> bool:
        """Check if session is complete."""
        return self.stage == "complete" or self.current_index >= self.total_count
    
    def _get_stage_field(self, stage: str) -> str:
        """Get stage field name."""
        stage_map = {
            SessionStage.EC.value: "ec_stage",
            SessionStage.IC.value: "ic_stage", 
            SessionStage.QC.value: "qc_stage"
        }
        return stage_map.get(stage, "")
    
    def get_progress(self) -> Dict:
        """Get progress stats."""
        return {
            "current": self.current_index + 1,
            "total": self.total_count,
            "stage": self.stage,
            "ec_completed": self.ec_completed,
            "ic_completed": self.ic_completed,
            "qc_completed": self.qc_completed,
            "ec_pending": self.get_pending_for_stage("ec"),
            "ic_pending": self.get_pending_for_stage("ic"),
            "qc_pending": self.get_pending_for_stage("qc"),
            "included": self.included_count,
            "excluded": self.excluded_count,
            "skipped": self.skip_count,
            "discussion": self.discussion_count
        }
    
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
            "qc_completed": self.qc_completed,
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
            qc_completed=data.get("qc_completed", 0),
            included_count=data.get("included_count", 0),
            excluded_count=data.get("excluded_count", 0),
            skip_count=data.get("skip_count", 0),
            discussion_count=data.get("discussion_count", 0),
            researcher_id=data.get("researcher_id", "researcher_1"),
            last_saved=data.get("last_saved", "")
        )
        
        session.articles = [
            ArticleReview(**a) for a in data.get("articles", [])
        ]
        
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
            
            if a.qc_stage and not a.is_ic_included:
                issues.append(f"Article {i}: QC decision without IC pass")
        
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