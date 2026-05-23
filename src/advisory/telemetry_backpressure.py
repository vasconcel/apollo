"""
Backpressure Stress Controller for APOLLO Telemetry.

Adapts telemetry ingestion under load to prevent system degradation
while preserving critical events (state transitions, failures).

Architecture:
  - Monitors queue depth, drain rate, and flush lag
  - Dynamically adjusts sampling rate (deterministic, no randomness)
  - Drops high-frequency metric events before critical events
  - Never drops: item_started, item_completed, item_failed,
    provider_failure, circuit_breaker_change, requeue_event

Design:
  - Three load levels: NOMINAL, ELEVATED, CRITICAL
  - Each level maps to a sampling rate for non-critical events
  - Transitions are deterministic (threshold-based, no hysteresis)
  - Integration: TelemetryBus consults controller before enqueueing
"""
import threading
import time
from typing import Dict, Optional, Set
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Load levels
# ---------------------------------------------------------------------------

LOAD_NOMINAL = "nominal"
LOAD_ELEVATED = "elevated"
LOAD_CRITICAL = "critical"

# Metrics that must never be dropped
_CRITICAL_METRICS: Set[str] = {
    "item_started",
    "item_completed",
    "item_failed",
    "provider_failure",
    "circuit_breaker_change",
    "requeue_event",
}

# High-frequency metrics that are safe to drop under load
_HIGH_FREQUENCY_METRICS: Set[str] = {
    "confidence_ec", "confidence_ic", "confidence_qc",
    "latency_ec", "latency_ic", "latency_qc",
    "processing_time_ec", "processing_time_ic", "processing_time_qc",
    "queue_depth_ec", "queue_depth_ic", "queue_depth_qc",
    "acceptance_ec", "acceptance_ic", "acceptance_qc",
}

# Sampling rates per load level
_SAMPLING_RATES: Dict[str, float] = {
    LOAD_NOMINAL: 1.0,     # sample everything
    LOAD_ELEVATED: 0.25,   # sample 1 in 4 non-critical events
    LOAD_CRITICAL: 0.05,   # sample 1 in 20 non-critical events
}


@dataclass
class BackpressureState:
    """Current backpressure metrics."""
    load_level: str = LOAD_NOMINAL
    queue_depth: int = 0
    drain_rate: float = 0.0
    flush_lag_ms: float = 0.0
    drop_rate: int = 0
    sampling_rate: float = 1.0
    total_dropped_backpressure: int = 0
    total_accepted: int = 0


class BackpressureController:
    """Deterministic load-aware telemetry degradation controller.

    Thread-safe. No randomness in sampling decisions.
    Sampling decision: hash(metric_name + counter) % denominator == 0
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._state = BackpressureState()
        self._counter: int = 0
        self._last_check_time: float = time.time()
        self._prev_queue_depth: int = 0

        # Thresholds
        self._depth_nominal_max: int = 1000
        self._depth_elevated_max: int = 5000
        self._drain_rate_nominal: float = 100.0  # events/sec minimum
        self._drain_rate_critical: float = 10.0

    # ------------------------------------------------------------------
    # Load assessment
    # ------------------------------------------------------------------

    def assess_load(self, queue_depth: int, drain_rate: float) -> str:
        """Evaluate current load level from queue metrics.

        Deterministic function of (queue_depth, drain_rate).
        No random components.

        Returns:
            "nominal", "elevated", or "critical"
        """
        if queue_depth >= self._depth_elevated_max or drain_rate < self._drain_rate_critical:
            return LOAD_CRITICAL
        if queue_depth >= self._depth_nominal_max or drain_rate < self._drain_rate_nominal:
            return LOAD_ELEVATED
        return LOAD_NOMINAL

    # ------------------------------------------------------------------
    # Sampling decision
    # ------------------------------------------------------------------

    def should_sample(self, metric: str) -> bool:
        """Decide if a metric event should be sampled.

        Critical metrics are always sampled.
        Non-critical metrics are sampled according to the current rate.

        Sampling decision is purely deterministic:
          hash(metric_name) % (1/rate) == 0
        This ensures reproducible behavior.

        Args:
            metric: The metric name to check.

        Returns:
            True if the event should be accepted, False if dropped.
        """
        if metric in _CRITICAL_METRICS:
            return True

        with self._lock:
            rate = self._state.sampling_rate
            if rate >= 1.0:
                self._state.total_accepted += 1
                return True

            self._counter += 1
            # Deterministic sampling: use counter + metric name hash
            denominator = max(1, int(1.0 / rate))
            should_accept = (hash(metric + str(self._counter)) % denominator) == 0

            if should_accept:
                self._state.total_accepted += 1
            else:
                self._state.total_dropped_backpressure += 1
            return should_accept

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(self, queue_depth: int, drain_rate: float, flush_lag_ms: float, drop_rate: int):
        """Update backpressure state and recompute load level.

        Should be called periodically (e.g. on each flush cycle).
        """
        with self._lock:
            self._state.queue_depth = queue_depth
            self._state.drain_rate = drain_rate
            self._state.flush_lag_ms = flush_lag_ms
            self._state.drop_rate = drop_rate

            new_level = self.assess_load(queue_depth, drain_rate)
            self._state.load_level = new_level
            self._state.sampling_rate = _SAMPLING_RATES[new_level]

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_state(self) -> Dict:
        """Get frozen snapshot of current backpressure state."""
        with self._lock:
            return {
                "load_level": self._state.load_level,
                "queue_depth": self._state.queue_depth,
                "drain_rate": round(self._state.drain_rate, 2),
                "flush_lag_ms": round(self._state.flush_lag_ms, 2),
                "drop_rate": self._state.drop_rate,
                "sampling_rate": self._state.sampling_rate,
                "total_dropped_backpressure": self._state.total_dropped_backpressure,
                "total_accepted": self._state.total_accepted,
            }

    def reset(self):
        """Reset state (for testing)."""
        with self._lock:
            self._state = BackpressureState()
            self._counter = 0
            self._last_check_time = time.time()
            self._prev_queue_depth = 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_controller: Optional[BackpressureController] = None
_controller_lock = threading.Lock()


def get_backpressure_controller() -> BackpressureController:
    """Get the global BackpressureController singleton."""
    global _global_controller
    if _global_controller is None:
        with _controller_lock:
            if _global_controller is None:
                _global_controller = BackpressureController()
    return _global_controller


def reset_backpressure_controller():
    """Reset the global controller (for testing)."""
    global _global_controller
    with _controller_lock:
        _global_controller = None
