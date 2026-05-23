"""
Replayable Experiment System for APOLLO.

Enables deterministic rerun of past calibration sessions by freezing
dataset snapshots, recording deterministic ordering, and computing
hash-based session IDs.

Key design:
  - Frozen article snapshots (serialized at replay creation time)
  - Deterministic ordering (sorted by cache_key)
  - Hash-based session IDs (SHA-256 of frozen dataset + protocol version)
  - Side-by-side comparison between original and replay run
"""
import json
import hashlib
import os
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .telemetry_clock import EventEnvelope


REPLAY_DIR = Path("data/replay")


class ReplaySnapshot:
    """A frozen, self-contained replay session."""

    def __init__(
        self,
        session_id: str,
        articles: List[Dict],
        protocol_version: str,
        config: Dict,
        created_at: str = "",
    ):
        self.session_id = session_id
        self.articles = sorted(articles, key=lambda a: a.get("cache_key", ""))
        self.protocol_version = protocol_version
        self.config = config
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()

    @property
    def article_count(self) -> int:
        return len(self.articles)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "articles": self.articles,
            "protocol_version": self.protocol_version,
            "config": self.config,
            "created_at": self.created_at,
            "article_count": self.article_count,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ReplaySnapshot":
        return cls(
            session_id=data["session_id"],
            articles=data["articles"],
            protocol_version=data["protocol_version"],
            config=data.get("config", {}),
            created_at=data.get("created_at", ""),
        )


def compute_replay_session_id(
    articles: List[Dict],
    protocol_version: str,
    config_hash: str = "",
) -> str:
    """Compute deterministic session ID from frozen dataset.

    Uses SHA-256 of sorted article cache keys + protocol version.
    First 16 hex chars for readability.
    """
    sorted_keys = sorted(
        a.get("cache_key", a.get("title", "")) for a in articles
    )
    content = f"{protocol_version}:{':'.join(sorted_keys)}:{config_hash}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def freeze_replay_snapshot(
    articles: List[Any],
    protocol_version: str,
    config: Optional[Dict] = None,
    session_id: Optional[str] = None,
) -> "ReplaySnapshot":
    """Create a frozen replay snapshot from article objects.

    Converts article objects to dicts deterministically.

    Args:
        articles: List of article objects with title, abstract, cache_key
        protocol_version: Protocol version string
        config: Optional config dict to freeze
        session_id: Optional override (auto-computed if omitted)

    Returns:
        ReplaySnapshot with frozen, serialized data.
    """
    frozen_articles = []
    for art in articles:
        if hasattr(art, 'title'):
            entry = {
                "cache_key": getattr(art, 'cache_key', _compute_article_cache_key(art, protocol_version)),
                "title": getattr(art, 'title', '') or '',
                "abstract": getattr(art, 'abstract', '') or '',
                "literature_type": getattr(art, 'literature_type', 'WL'),
            }
            metadata = getattr(art, 'metadata', {})
            if isinstance(metadata, dict):
                entry["metadata"] = {
                    k: str(v) for k, v in metadata.items()
                    if k in ("year", "authors", "source", "article_id")
                }
            frozen_articles.append(entry)
        elif isinstance(art, dict):
            entry = {
                "cache_key": art.get("cache_key", ""),
                "title": art.get("title", "") or "",
                "abstract": art.get("abstract", "") or "",
                "literature_type": art.get("literature_type", "WL"),
            }
            metadata = art.get("metadata", {})
            if isinstance(metadata, dict):
                entry["metadata"] = {
                    k: str(v) for k, v in metadata.items()
                    if k in ("year", "authors", "source", "article_id")
                }
            frozen_articles.append(entry)

    if not session_id:
        config_hash = hashlib.sha256(
            json.dumps(config or {}, sort_keys=True).encode()
        ).hexdigest()[:8]
        session_id = compute_replay_session_id(frozen_articles, protocol_version, config_hash)

    return ReplaySnapshot(
        session_id=session_id,
        articles=frozen_articles,
        protocol_version=protocol_version,
        config=config or {},
    )


# ---------------------------------------------------------------------------
# Part 4: Deterministic Telemetry Replay
# ---------------------------------------------------------------------------

class TelemetryReplay:
    """Reconstruct full system state from telemetry stream.

    Given a sorted list of EventEnvelope objects (from bus event log
    or from persistent store), this class can replay them step-by-step
    and reconstruct the system state at any point.

    Supports:
      - Exact step-by-step replay (iterate over events)
      - Deterministic ordering reconstruction (by logical_timestamp)
      - State snapshot at any point in the event sequence
    """

    def __init__(self):
        self._events: List[EventEnvelope] = []
        self._sorted: bool = False
        self._reconstructed_state: Dict = {
            "items_started": {},
            "items_completed": {},
            "items_failed": {},
            "queue_depths": {},
            "provider_calls": 0,
            "provider_failures": 0,
            "circuit_breaker_states": {},
            "retry_counts": {},
            "event_count": 0,
        }

    def load_events(self, events: List[EventEnvelope]):
        """Load events for replay. Events need not be pre-sorted."""
        self._events = list(events)
        self._sorted = False

    def load_events_from_log(self, bus_event_log: List[EventEnvelope]):
        """Load events from the TelemetryBus event log."""
        self._events = list(bus_event_log)
        self._sorted = False

    def sort_events(self):
        """Sort events by logical timestamp for deterministic replay."""
        if not self._sorted:
            self._events.sort()
            self._sorted = True

    def get_sorted_events(self) -> List[EventEnvelope]:
        """Get events sorted in replay order."""
        self.sort_events()
        return list(self._events)

    def replay_all(self) -> Dict:
        """Replay all loaded events and return final reconstructed state.

        Returns dict with:
          - items_started: {cache_key: logical_timestamp}
          - items_completed: {cache_key: decision}
          - items_failed: {cache_key: reason}
          - queue_depths: {stage: final_depth}
          - provider_calls, provider_failures: count
          - circuit_breaker_states: {provider: last_state}
          - retry_counts: {stage: count}
          - event_count: total processed
        """
        self.sort_events()
        state = {
            "items_started": {},
            "items_completed": {},
            "items_failed": {},
            "queue_depths": {},
            "provider_calls": 0,
            "provider_failures": 0,
            "circuit_breaker_states": {},
            "retry_counts": {},
            "event_count": len(self._events),
        }

        for ev in self._events:
            self._apply_event(ev, state)

        self._reconstructed_state = state
        return dict(state)

    def replay_step(self, start_index: int = 0, steps: int = 1) -> List[Dict]:
        """Replay a specific range of events and return per-step state diffs.

        Args:
            start_index: Event index to start from.
            steps: Number of events to replay.

        Returns:
            List of dicts, one per event, with event info and state after.
        """
        self.sort_events()
        results = []
        for i in range(start_index, min(start_index + steps, len(self._events))):
            ev = self._events[i]
            self._apply_event(ev, self._reconstructed_state)
            results.append({
                "index": i,
                "event": ev.to_dict(),
                "state_after": dict(self._reconstructed_state),
            })
        return results

    def get_state_snapshot(self) -> Dict:
        """Get current reconstructed state snapshot."""
        return dict(self._reconstructed_state)

    def _apply_event(self, ev: EventEnvelope, state: Dict):
        """Apply a single event to the reconstructed state."""
        metric = ev.metric
        tags = ev.tags
        cache_key = tags.get("cache_key", "")

        if metric == "item_started":
            state["items_started"][cache_key] = ev.logical_timestamp
            state["items_completed"].pop(cache_key, None)
            state["items_failed"].pop(cache_key, None)

        elif metric == "item_completed":
            state["items_completed"][cache_key] = tags.get("decision", "unknown")
            state["items_started"].pop(cache_key, None)
            state["items_failed"].pop(cache_key, None)

        elif metric == "item_failed":
            state["items_failed"][cache_key] = tags.get("reason", "unknown")

        elif metric.startswith("queue_depth_"):
            stage = metric.replace("queue_depth_", "")
            state["queue_depths"][stage] = ev.value

        elif metric == "provider_call":
            state["provider_calls"] += 1

        elif metric == "provider_failure":
            state["provider_failures"] += 1

        elif metric == "circuit_breaker_change":
            provider = tags.get("provider", "default")
            state["circuit_breaker_states"][provider] = tags.get("new_status", "unknown")

        elif metric.startswith("retry_"):
            stage = metric.replace("retry_", "")
            state["retry_counts"][stage] = state["retry_counts"].get(stage, 0) + 1

    def compute_checksum(self) -> str:
        """Compute deterministic checksum of the current event sequence.

        SHA-256 of concatenated (logical_timestamp, metric, value) tuples.
        Same event sequence → same checksum.
        """
        self.sort_events()
        import hashlib
        hasher = hashlib.sha256()
        for ev in self._events:
            hasher.update(f"{ev.logical_timestamp}|{ev.metric}|{ev.value}|".encode())
        return hasher.hexdigest()[:16]

    def verify_checksum(self, expected_checksum: str) -> bool:
        """Verify event sequence against a known checksum."""
        return self.compute_checksum() == expected_checksum


def _compute_article_cache_key(article, protocol_version: str) -> str:
    """Compute a deterministic cache key for an article object."""
    title = (getattr(article, 'title', '') or '').strip().lower()
    abstract = (getattr(article, 'abstract', '') or '').strip().lower()
    content = f"{protocol_version}:{title}:{abstract}"
    return hashlib.sha256(content.encode()).hexdigest()[:32]


class ReplayStore:
    """Persistent store for replay snapshots."""

    def __init__(self, base_dir: str = "data/replay"):
        self._dir = Path(base_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def save(self, snapshot: ReplaySnapshot) -> str:
        """Save a replay snapshot. Returns file path."""
        path = self._dir / f"{snapshot.session_id}.json"
        with self._lock:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(snapshot.to_dict(), f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
        return str(path)

    def load(self, session_id: str) -> Optional[ReplaySnapshot]:
        """Load a replay snapshot by session ID."""
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        with self._lock:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return ReplaySnapshot.from_dict(data)
            except (json.JSONDecodeError, OSError):
                return None

    def list_sessions(self) -> List[Dict]:
        """List all available replay sessions."""
        sessions = []
        for fpath in sorted(self._dir.glob("*.json")):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", fpath.stem),
                    "article_count": data.get("article_count", 0),
                    "protocol_version": data.get("protocol_version", ""),
                    "created_at": data.get("created_at", ""),
                })
            except (json.JSONDecodeError, OSError):
                pass
        return sessions

    def delete(self, session_id: str) -> bool:
        """Delete a replay snapshot."""
        path = self._dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False


_global_replay_store: Optional[ReplayStore] = None
_replay_store_lock = threading.Lock()


def get_replay_store() -> ReplayStore:
    global _global_replay_store
    if _global_replay_store is None:
        with _replay_store_lock:
            if _global_replay_store is None:
                _global_replay_store = ReplayStore()
    return _global_replay_store


def reset_replay_store():
    global _global_replay_store
    with _replay_store_lock:
        _global_replay_store = None
