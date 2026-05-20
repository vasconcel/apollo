"""
APOLLO Session Persistence Service

Deterministic persistence/serialization for screening sessions.
Handles JSON serialization, filesystem I/O, checksum computation,
and session recovery.

Contains no Streamlit, advisory, navigation, or query logic.
"""

import json
import os
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any

from src.core.logging_config import get_logger

logger = get_logger("session_persistence")

CHECKSUM_FIELDS = [
    "session_id", "created_at", "protocol_version", "stage",
    "current_index", "total_count", "ec_completed", "ic_completed",
    "included_count", "excluded_count", "skip_count",
    "discussion_count", "researcher_id", "last_saved", "schema_version",
    "articles", "dynamic_protocol"
]


class SessionPersistenceService:
    """Deterministic persistence service for ScreeningSession.

    All methods are @staticmethod — no instance state.
    Pure serialization, filesystem I/O, and checksum computation.
    """

    # ------------------------------------------------------------------
    # Serialization — dict construction
    # ------------------------------------------------------------------

    @staticmethod
    def build_article_dicts(articles: List[Any]) -> List[Dict]:
        """Convert article objects to serializable dicts."""
        return [a.to_dict() for a in articles]

    @staticmethod
    def to_dict(
        session_id: str,
        created_at: str,
        protocol_version: str,
        stage: str,
        current_index: int,
        total_count: int,
        ec_completed: int,
        ic_completed: int,
        included_count: int,
        excluded_count: int,
        skip_count: int,
        discussion_count: int,
        researcher_id: str,
        last_saved: str,
        articles: List[Any],
    ) -> Dict[str, Any]:
        """Build basic serialization dict from explicit field values."""
        return {
            "session_id": session_id,
            "created_at": created_at,
            "protocol_version": protocol_version,
            "stage": stage,
            "current_index": current_index,
            "total_count": total_count,
            "ec_completed": ec_completed,
            "ic_completed": ic_completed,
            "included_count": included_count,
            "excluded_count": excluded_count,
            "skip_count": skip_count,
            "discussion_count": discussion_count,
            "researcher_id": researcher_id,
            "last_saved": last_saved,
            "articles": SessionPersistenceService.build_article_dicts(articles),
        }

    @staticmethod
    def to_dict_full(
        session_id: str,
        created_at: str,
        protocol_version: str,
        stage: str,
        current_index: int,
        total_count: int,
        ec_completed: int,
        ic_completed: int,
        included_count: int,
        excluded_count: int,
        skip_count: int,
        discussion_count: int,
        researcher_id: str,
        last_saved: str,
        schema_version: str,
        articles: List[Any],
        dynamic_protocol: Optional[Dict],
    ) -> Dict[str, Any]:
        """Build full serialization dict including protocol."""
        data = SessionPersistenceService.to_dict(
            session_id, created_at, protocol_version, stage,
            current_index, total_count,
            ec_completed, ic_completed,
            included_count, excluded_count,
            skip_count, discussion_count,
            researcher_id, last_saved,
            articles,
        )
        data["schema_version"] = schema_version
        data["dynamic_protocol"] = dynamic_protocol
        return data

    # ------------------------------------------------------------------
    # Checksum computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_checksum(full_data: Dict[str, Any]) -> str:
        """Compute SHA256 checksum from full session data dict."""
        data_for_check = {
            k: full_data.get(k) for k in CHECKSUM_FIELDS if k in full_data
        }
        canonical_json = json.dumps(
            data_for_check, sort_keys=True, ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode()).hexdigest()

    @staticmethod
    def compute_session_hash(data: Dict[str, Any]) -> str:
        """Compute short session hash (first 16 hex chars) for integrity."""
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Filesystem I/O
    # ------------------------------------------------------------------

    @staticmethod
    def write_json(path: str, data: Dict[str, Any]) -> None:
        """Write JSON dict to file with consistent formatting."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def read_json(path: str) -> Optional[Dict[str, Any]]:
        """Read JSON file and return parsed dict, or None on failure."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, FileNotFoundError):
            return None

    @staticmethod
    def exists(path: str) -> bool:
        """Check if a file exists at the given path."""
        return os.path.exists(path)

    @staticmethod
    def resolve_session_path(output_dir: str, session_id: str) -> str:
        """Resolve filesystem path for a session file."""
        return os.path.join(output_dir, f"session_{session_id}.json")

    @staticmethod
    def ensure_dir(output_dir: str) -> None:
        """Ensure output directory exists."""
        os.makedirs(output_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Save operations
    # ------------------------------------------------------------------

    @staticmethod
    def save(
        output_dir: str,
        session_id: str,
        created_at: str,
        protocol_version: str,
        stage: str,
        current_index: int,
        total_count: int,
        ec_completed: int,
        ic_completed: int,
        included_count: int,
        excluded_count: int,
        skip_count: int,
        discussion_count: int,
        researcher_id: str,
        last_saved: str,
        articles: List[Any],
    ) -> str:
        """Save session state to file with hash for integrity.

        Returns the path to which the file was saved.
        """
        SessionPersistenceService.ensure_dir(output_dir)
        path = SessionPersistenceService.resolve_session_path(output_dir, session_id)

        data = SessionPersistenceService.to_dict(
            session_id, created_at, protocol_version, stage,
            current_index, total_count,
            ec_completed, ic_completed,
            included_count, excluded_count,
            skip_count, discussion_count,
            researcher_id, last_saved,
            articles,
        )

        data["session_hash"] = SessionPersistenceService.compute_session_hash(data)
        SessionPersistenceService.write_json(path, data)

        return path

    @staticmethod
    def save_to_json(
        path: str,
        session_id: str,
        created_at: str,
        protocol_version: str,
        stage: str,
        current_index: int,
        total_count: int,
        ec_completed: int,
        ic_completed: int,
        included_count: int,
        excluded_count: int,
        skip_count: int,
        discussion_count: int,
        researcher_id: str,
        last_saved: str,
        schema_version: str,
        articles: List[Any],
        dynamic_protocol: Optional[Dict],
        audit_chain: List[Dict],
        autosave_enabled: bool,
    ) -> str:
        """Deterministic JSON persistence with full audit chain.

        Returns the path to which the file was saved.
        """
        data = SessionPersistenceService.to_dict_full(
            session_id, created_at, protocol_version, stage,
            current_index, total_count,
            ec_completed, ic_completed,
            included_count, excluded_count,
            skip_count, discussion_count,
            researcher_id, last_saved,
            schema_version,
            articles,
            dynamic_protocol,
        )

        data["session_checksum"] = SessionPersistenceService.compute_checksum(data)
        data["audit_chain"] = audit_chain
        data["autosave_enabled"] = autosave_enabled

        if dynamic_protocol:
            from src.core.dynamic_protocol import DynamicProtocol
            try:
                protocol = DynamicProtocol.from_dict(dynamic_protocol)
                data["protocol_hash"] = protocol.protocol_hash
            except Exception:
                data["protocol_hash"] = ""

        SessionPersistenceService.write_json(path, data)
        return path

    # ------------------------------------------------------------------
    # Load operations
    # ------------------------------------------------------------------

    @staticmethod
    def load_session_data(
        path: str,
    ) -> Optional[Dict[str, Any]]:
        """Load session data from file. Returns parsed dict or None."""
        if not SessionPersistenceService.exists(path):
            return None
        return SessionPersistenceService.read_json(path)

    @staticmethod
    def load_from_json(
        path: str,
    ) -> Optional[Dict[str, Any]]:
        """Load session from deterministic JSON with checksum verification.

        Returns a dict of reconstructed field values, or None on failure.
        The caller applies these to the session instance.
        """
        if not SessionPersistenceService.exists(path):
            return None

        data = SessionPersistenceService.read_json(path)
        if data is None:
            return None

        expected_checksum = data.get("session_checksum", "")
        data_for_check = {
            k: data.get(k) for k in CHECKSUM_FIELDS if k in data
        }
        actual_checksum = hashlib.sha256(
            json.dumps(data_for_check, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

        result = {
            "session_id": data.get("session_id", ""),
            "created_at": data.get("created_at", ""),
            "protocol_version": data.get("protocol_version", "1.0"),
            "stage": data.get("stage", "ec"),
            "current_index": data.get("current_index", 0),
            "total_count": data.get("total_count", 0),
            "ec_completed": data.get("ec_completed", 0),
            "ic_completed": data.get("ic_completed", 0),
            "included_count": data.get("included_count", 0),
            "excluded_count": data.get("excluded_count", 0),
            "skip_count": data.get("skip_count", 0),
            "discussion_count": data.get("discussion_count", 0),
            "researcher_id": data.get("researcher_id", "researcher_1"),
            "last_saved": data.get("last_saved", ""),
            "schema_version": data.get("schema_version", "2.0"),
            "autosave_enabled": data.get("autosave_enabled", False),
            "articles": data.get("articles", []),
            "dynamic_protocol": data.get("dynamic_protocol"),
            "audit_chain": data.get("audit_chain", []),
            "expected_checksum": expected_checksum,
            "actual_checksum": actual_checksum,
        }
        return result

    # ------------------------------------------------------------------
    # Session listing and recovery
    # ------------------------------------------------------------------

    @staticmethod
    def list_sessions(
        output_dir: str = "sessions",
    ) -> List[Dict[str, str]]:
        """List all saved sessions."""
        if not SessionPersistenceService.exists(output_dir):
            return []

        sessions = []
        try:
            for f in os.listdir(output_dir):
                if f.startswith("session_") and f.endswith(".json"):
                    path = os.path.join(output_dir, f)
                    try:
                        mtime = os.path.getmtime(path)
                        sessions.append({
                            "session_id": f.replace("session_", "").replace(".json", ""),
                            "path": path,
                            "modified": datetime.fromtimestamp(mtime).isoformat(),
                        })
                    except OSError:
                        pass
        except OSError:
            pass

        return sorted(sessions, key=lambda x: x["modified"], reverse=True)

    @staticmethod
    def recover_session(
        output_dir: str = "sessions",
    ) -> Optional[str]:
        """Get session_id of most recent session for recovery.

        Returns session_id or None if no sessions exist.
        """
        sessions = SessionPersistenceService.list_sessions(output_dir)
        if not sessions:
            return None
        return sessions[0]["session_id"]
