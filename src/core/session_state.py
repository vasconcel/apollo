"""
APOLLO Session State Model

Deterministic mutable state container for ScreeningSession.
Holds ONLY state — no orchestration, no service imports, no UI references.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SessionState:
    """Deterministic mutable state container for screening sessions.

    All fields are pure state storage. No orchestration logic.
    Field order matches serialization order for deterministic output.
    """

    session_id: str
    created_at: str
    protocol_version: str = "1.0"
    stage: str = "ec"

    articles: List = field(default_factory=list)

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

    audit_chain: List[Dict] = field(default_factory=list)
    snapshots: List[Dict] = field(default_factory=list)
