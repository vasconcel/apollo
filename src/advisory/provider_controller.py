"""
Global provider controller for APOLLO SIMPLE SEQUENTIAL MODE.

Manages:
- Global request rate limiting (min interval between LLM requests)
- Provider health state tracking (HEALTHY, COOLDOWN, DEGRADED)
- Provider metrics (requests, failures, 429 tracking)
"""

import time
import threading
from enum import Enum
from typing import Dict, Optional


class ProviderState(Enum):
    HEALTHY = "healthy"
    COOLDOWN = "cooldown"
    DEGRADED = "degraded"


COOLDOWN_DURATION_SECONDS = 30
CONSECUTIVE_FAILURES_THRESHOLD = 3


class ProviderController:
    """Global provider controller — rate limiting, health, metrics."""

    def __init__(self):
        self._lock = threading.Lock()

        # Rate limiting
        self._last_request_time: float = 0.0

        # Provider health
        self._state = ProviderState.HEALTHY
        self._cooldown_until: float = 0.0
        self._consecutive_failures: int = 0

        # Metrics
        self._total_requests: int = 0
        self._successful_requests: int = 0
        self._failed_requests: int = 0
        self._last_429_time: float = 0.0
        self._last_request_timestamp: float = 0.0
        self._request_times: list = []

    def wait_if_needed(self, min_interval: float = 6.0) -> None:
        """Enforce global min request interval. Sleeps if needed."""
        with self._lock:
            if self._last_request_time == 0:
                return
            elapsed = time.time() - self._last_request_time
            if elapsed >= min_interval:
                return
            remaining = min_interval - elapsed
        time.sleep(remaining)

    def check_availability(self) -> bool:
        """Check if provider is available for requests."""
        with self._lock:
            if self._state == ProviderState.COOLDOWN:
                if time.time() >= self._cooldown_until:
                    self._state = ProviderState.HEALTHY
                    self._consecutive_failures = 0
                    return True
                return False
            return self._state == ProviderState.HEALTHY

    def record_request(self) -> None:
        """Record a request attempt."""
        with self._lock:
            self._total_requests += 1
            now = time.time()
            self._last_request_time = now
            self._last_request_timestamp = now
            self._request_times.append(now)
            cutoff = now - 60
            self._request_times = [t for t in self._request_times if t > cutoff]

    def record_success(self) -> None:
        """Record a successful request. Resets consecutive failure count."""
        with self._lock:
            self._successful_requests += 1
            self._consecutive_failures = 0

    def record_failure(self, is_429: bool = False) -> None:
        """Record a failed request. Updates provider state."""
        with self._lock:
            self._failed_requests += 1
            self._consecutive_failures += 1
            if is_429:
                self._last_429_time = time.time()
                self._state = ProviderState.COOLDOWN
                self._cooldown_until = time.time() + COOLDOWN_DURATION_SECONDS
            elif self._consecutive_failures >= CONSECUTIVE_FAILURES_THRESHOLD:
                self._state = ProviderState.DEGRADED

    def get_health(self) -> Dict:
        """Get health and metrics snapshot."""
        with self._lock:
            now = time.time()
            cutoff = now - 60
            rpm = sum(1 for t in self._request_times if t > cutoff)
            return {
                "state": self._state.value,
                "cooldown_remaining": round(max(0, self._cooldown_until - now), 1)
                    if self._state == ProviderState.COOLDOWN else 0,
                "total_requests": self._total_requests,
                "successful_requests": self._successful_requests,
                "failed_requests": self._failed_requests,
                "last_429_time": self._last_429_time,
                "last_request_time": self._last_request_timestamp,
                "requests_per_minute": rpm,
                "consecutive_failures": self._consecutive_failures,
            }

    def reset(self) -> None:
        """Reset all state."""
        with self._lock:
            self._state = ProviderState.HEALTHY
            self._cooldown_until = 0.0
            self._consecutive_failures = 0
            self._total_requests = 0
            self._successful_requests = 0
            self._failed_requests = 0
            self._last_429_time = 0.0
            self._last_request_time = 0.0
            self._last_request_timestamp = 0.0
            self._request_times = []


_global_controller: Optional[ProviderController] = None
_controller_lock = threading.Lock()


def get_provider_controller() -> ProviderController:
    """Get global provider controller singleton."""
    global _global_controller
    if _global_controller is None:
        with _controller_lock:
            if _global_controller is None:
                _global_controller = ProviderController()
    return _global_controller


def reset_provider_controller() -> None:
    """Reset the global provider controller."""
    global _global_controller
    with _controller_lock:
        if _global_controller is not None:
            _global_controller.reset()
