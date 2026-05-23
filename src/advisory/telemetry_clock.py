"""
Global Event Ordering System for APOLLO.

Provides a logically ordered, replayable, causally consistent event
envelope for all telemetry events in the system.

Architecture:
  - LogicalClock: Lamport-style hybrid monotonic clock (per-thread max + global epoch)
  - TelemetryEvent: Enriched event envelope with global_id, clock, source, causal parent
  - EventEnvelope: The serializable payload that gets enqueued on TelemetryBus

Every event carries:
  - global_event_id: UUID-like unique identifier (deterministic from clock + source)
  - logical_timestamp: Monotonic counter from LogicalClock (deterministic ordering)
  - source_component: worker/gateway/queue/ui
  - causal_parent_id: Optional reference to the event that caused this one

Deterministic ordering guarantee:
  - If event A causally precedes event B, then A.logical_timestamp < B.logical_timestamp
  - For concurrent events, tie-breaking by source_component priority
  - Replay equivalence: same event sequence → same logical_timestamp sequence
"""
import threading
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Component identifiers for deterministic tie-breaking
# ---------------------------------------------------------------------------

COMPONENT_PRIORITY = {
    "gateway": 0,
    "worker": 1,
    "queue": 2,
    "ui": 3,
    "replay": 4,
    "test": 5,
}

# ---------------------------------------------------------------------------
# LogicalClock
# ---------------------------------------------------------------------------

_LOCAL_STORAGE = threading.local()


class LogicalClock:
    """Lamport-style hybrid monotonic clock.

    Maintains a global monotonic counter across all threads.
    Each thread also tracks its max-seen counter to capture causality.

    Clock invariants:
      - Strictly increasing within a thread
      - Globally monotonic across threads
      - Time-aware: integrates wall-clock epoch for replay alignment

    Deterministic: pure function of prior state + current thread + wall clock.
    No random components.
    """

    def __init__(self, epoch: Optional[float] = None):
        self._global_counter: int = 0
        self._lock = threading.Lock()
        self._epoch = epoch or time.time()

    def tick(self, source: str = "test") -> int:
        """Advance the clock and return a new logical timestamp.

        Thread-safe. Each call guarantees a strictly increasing value
        across all threads.
        """
        with self._lock:
            self._global_counter += 1
            ts = self._global_counter
            self._update_local_max(ts)
            return ts

    def witness(self, other_ts: int) -> int:
        """Incorporate a timestamp from another thread/process.

        Ensures the clock never goes backward after seeing a larger
        value from elsewhere (Lamport's rule).
        """
        with self._lock:
            if other_ts > self._global_counter:
                self._global_counter = other_ts + 1
            else:
                self._global_counter += 1
            ts = self._global_counter
            self._update_local_max(ts)
            return ts

    def peek(self) -> int:
        """Read the current clock value without advancing."""
        with self._lock:
            return self._global_counter

    def get_epoch(self) -> float:
        """Return the clock epoch (wall clock at creation)."""
        return self._epoch

    def _update_local_max(self, ts: int):
        """Update per-thread max-seen counter."""
        try:
            if not hasattr(_LOCAL_STORAGE, "max_clock"):
                _LOCAL_STORAGE.max_clock = 0
            if ts > _LOCAL_STORAGE.max_clock:
                _LOCAL_STORAGE.max_clock = ts
        except AttributeError:
            pass

    def get_local_max(self) -> int:
        """Get the max clock value seen by the current thread."""
        try:
            return getattr(_LOCAL_STORAGE, "max_clock", 0)
        except AttributeError:
            return 0

    def reset(self):
        """Reset clock to zero (for testing)."""
        with self._lock:
            self._global_counter = 0
            self._epoch = time.time()


# ---------------------------------------------------------------------------
# EventEnvelope — serializable payload
# ---------------------------------------------------------------------------

@dataclass
class EventEnvelope:
    """Serializable event envelope with causal ordering metadata.

    This is the payload that flows through TelemetryBus and gets persisted.
    """
    metric: str
    value: float
    tags: Dict[str, str]
    global_event_id: str
    logical_timestamp: int
    source_component: str
    causal_parent_id: str = ""
    wall_clock: float = 0.0
    epoch: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "EventEnvelope":
        return cls(
            metric=data.get("metric", ""),
            value=data.get("value", 0.0),
            tags=data.get("tags", {}),
            global_event_id=data.get("global_event_id", ""),
            logical_timestamp=data.get("logical_timestamp", 0),
            source_component=data.get("source_component", "unknown"),
            causal_parent_id=data.get("causal_parent_id", ""),
            wall_clock=data.get("wall_clock", 0.0),
            epoch=data.get("epoch", 0.0),
        )

    def __lt__(self, other: "EventEnvelope") -> bool:
        """Deterministic total order across all events.

        Primary key: logical_timestamp
        Secondary key: source_component (by priority)
        Tertiary key: global_event_id (string comparison)
        """
        if self.logical_timestamp != other.logical_timestamp:
            return self.logical_timestamp < other.logical_timestamp
        self_prio = COMPONENT_PRIORITY.get(self.source_component, 99)
        other_prio = COMPONENT_PRIORITY.get(other.source_component, 99)
        if self_prio != other_prio:
            return self_prio < other_prio
        return self.global_event_id < other.global_event_id


# ---------------------------------------------------------------------------
# Global event counter (deterministic unique IDs)
# ---------------------------------------------------------------------------

_event_counter_lock = threading.Lock()
_event_counter: int = 0


def _next_event_id(clock: LogicalClock, source: str) -> str:
    """Generate a deterministic global event ID.

    Format: {logical_timestamp:x}-{source}-{counter:x}
    Deterministic: same clock state → same ID.
    """
    global _event_counter
    ts = clock.peek()
    with _event_counter_lock:
        _event_counter += 1
        c = _event_counter
    return f"{ts:x}-{source}-{c:x}"


# ---------------------------------------------------------------------------
# Event staming function — the integration point with TelemetryBus
# ---------------------------------------------------------------------------

_global_clock: Optional[LogicalClock] = None
_clock_lock = threading.Lock()


def get_logical_clock() -> LogicalClock:
    """Get the global LogicalClock singleton."""
    global _global_clock
    if _global_clock is None:
        with _clock_lock:
            if _global_clock is None:
                _global_clock = LogicalClock()
    return _global_clock


def reset_logical_clock():
    """Reset the global clock (for testing)."""
    global _global_clock
    with _clock_lock:
        if _global_clock is not None:
            _global_clock.reset()
        _global_clock = None


def stamp_event(
    metric: str,
    value: float,
    tags: Dict[str, str],
    source: str = "worker",
    causal_parent_id: str = "",
    clock: Optional[LogicalClock] = None,
) -> EventEnvelope:
    """Stamp a raw (metric, value, tags) tuple with causal metadata.

    This is the single integration point between TelemetryBus and the
    global ordering system. Every event must go through this function
    before enqueue.

    Args:
        metric: Metric name (e.g. "item_started")
        value: Numeric value
        tags: String key-value pairs
        source: Source component identifier
        causal_parent_id: Optional ID of the causally preceding event
        clock: Optional clock override (for testing)

    Returns:
        EventEnvelope with all ordering metadata populated.
    """
    clk = clock or get_logical_clock()
    ts = clk.tick(source)
    event_id = _next_event_id(clk, source)
    return EventEnvelope(
        metric=metric,
        value=value,
        tags=tags,
        global_event_id=event_id,
        logical_timestamp=ts,
        source_component=source,
        causal_parent_id=causal_parent_id,
        wall_clock=time.time(),
        epoch=clk.get_epoch(),
    )
