"""
LLM Execution Gateway for APOLLO.

Centralized governance layer for all LLM interactions:

- CONCURRENCY: Bounded via semaphore; requests exceeding limit wait
- RATE LIMITING: Sliding window of max_requests_per_minute
- CIRCUIT BREAKER: Per-provider health tracking with auto-recovery
- DEDUPLICATION: In-flight request fingerprints prevent duplicate inference
- RETRY: Bounded, deterministic (no jitter), observable
- TELEMETRY: Frozen runtime snapshots for dashboard

ARCHITECTURE:
  Module-level singleton (llm_gateway).
  Workers call generate_advisory() which blocks until the request
  completes or fails. All governance is transparent to the caller.

  Thread-safe via RLock + Semaphore.
  Deterministic — no random values in retry or backoff.
"""
import time
import threading
import hashlib
from collections import deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Tuple
from enum import Enum

from .advisory_models import AdvisoryConfig
from .telemetry_bus import get_telemetry_bus

# ---------------------------------------------------------------------------
# Provider health states
# ---------------------------------------------------------------------------

class ProviderStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    COOLDOWN = "COOLDOWN"
    UNAVAILABLE = "UNAVAILABLE"

# ---------------------------------------------------------------------------
# Telemetry data structures
# ---------------------------------------------------------------------------

@dataclass
class GatewayTelemetry:
    """Runtime telemetry for the LLM gateway."""
    active_requests: int = 0
    queued_requests: int = 0
    total_requests: int = 0
    total_successful: int = 0
    total_failed: int = 0
    total_deduplicated: int = 0
    total_retries: int = 0
    cooldown_activations: int = 0
    rate_limit_waits: int = 0
    concurrency_waits: int = 0
    mean_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    throughput_per_minute: float = 0.0
    latest_cost_estimate_usd: float = 0.0
    retry_counts: Dict[str, int] = field(default_factory=dict)
    provider_states: Dict[str, str] = field(default_factory=dict)
    latest_timestamp: float = 0.0

    def snapshot(self) -> Dict:
        """Return a frozen copy for dashboard consumption."""
        return {
            "active_requests": self.active_requests,
            "queued_requests": self.queued_requests,
            "total_requests": self.total_requests,
            "total_successful": self.total_successful,
            "total_failed": self.total_failed,
            "total_deduplicated": self.total_deduplicated,
            "total_retries": self.total_retries,
            "cooldown_activations": self.cooldown_activations,
            "rate_limit_waits": self.rate_limit_waits,
            "concurrency_waits": self.concurrency_waits,
            "mean_latency_ms": round(self.mean_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "throughput_per_minute": round(self.throughput_per_minute, 2),
            "latest_cost_estimate_usd": round(self.latest_cost_estimate_usd, 6),
            "retry_counts": dict(self.retry_counts),
            "provider_states": dict(self.provider_states),
            "timestamp": self.latest_timestamp,
        }


@dataclass
class InFlightRequest:
    """Tracks an in-flight or completed request for deduplication."""
    fingerprint: str
    event: threading.Event = field(default_factory=threading.Event)
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: float = 0.0

# ---------------------------------------------------------------------------
# Rate limiter (sliding window)
# ---------------------------------------------------------------------------

class _SlidingWindowRateLimiter:
    """Deterministic sliding window rate limiter."""

    def __init__(self, max_per_minute: int):
        self._max = max_per_minute
        self._window: deque = deque()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0, cancel_event: Optional[threading.Event] = None) -> bool:
        """Wait until a slot is available or timeout expires.

        Uses interruptible sleep: if cancel_event is set, returns False
        immediately.

        Returns True if slot acquired, False on timeout or cancellation.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cancel_event and cancel_event.is_set():
                return False
            with self._lock:
                now = time.time()
                while self._window and now - self._window[0] > 60.0:
                    self._window.popleft()
                if len(self._window) < self._max:
                    self._window.append(now)
                    return True
            wait = 1.0
            if time.time() + wait > deadline:
                wait = deadline - time.time()
            if wait > 0:
                if cancel_event:
                    interrupt = min(wait, 0.1)
                    time.sleep(interrupt)
                else:
                    time.sleep(min(wait, 1.0))
        return False

    def release(self):
        """Release a slot (no-op — slots expire naturally)."""
        pass

# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class _CircuitBreaker:
    """Per-provider circuit breaker with deterministic recovery."""

    def __init__(self, config: AdvisoryConfig):
        self._config = config
        self._states: Dict[str, _ProviderState] = {}
        self._lock = threading.Lock()

    def _ensure(self, provider: str):
        if provider not in self._states:
            self._states[provider] = _ProviderState()

    def record_success(self, provider: str):
        with self._lock:
            self._ensure(provider)
            old_status = self._states[provider].status.value
            self._states[provider].consecutive_failures = 0
            if self._states[provider].status == ProviderStatus.COOLDOWN:
                self._states[provider].status = ProviderStatus.HEALTHY
                self._emit_cb_change(provider, old_status, "HEALTHY")

    def record_failure(self, provider: str):
        with self._lock:
            self._ensure(provider)
            ps = self._states[provider]
            old_status = ps.status.value
            ps.consecutive_failures += 1
            ps.last_failure_time = time.time()
            if ps.consecutive_failures >= self._config.provider_cooldown_threshold:
                ps.status = ProviderStatus.COOLDOWN
                ps.cooldown_until = time.time() + self._config.provider_cooldown_seconds
                self._emit_cb_change(provider, old_status, "COOLDOWN")

    def _emit_cb_change(self, provider: str, old_status: str, new_status: str):
        try:
            bus = get_telemetry_bus()
            bus.record_circuit_breaker_change(provider, old_status, new_status)
        except Exception:
            pass

    def get_status(self, provider: str) -> ProviderStatus:
        with self._lock:
            self._ensure(provider)
            ps = self._states[provider]
            if ps.status == ProviderStatus.COOLDOWN:
                if time.time() >= ps.cooldown_until:
                    ps.status = ProviderStatus.HEALTHY
                    ps.consecutive_failures = 0
            return ps.status

    def get_all_states(self) -> Dict[str, str]:
        with self._lock:
            return {p: s.status.value for p, s in self._states.items()}


@dataclass
class _ProviderState:
    status: ProviderStatus = ProviderStatus.HEALTHY
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    cooldown_until: float = 0.0

# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------

def compute_request_fingerprint(
    protocol_hash: str,
    article_hash: str,
    stage: str,
    model: str = "",
    advisory_version: str = "1.0",
) -> str:
    """Compute deterministic fingerprint for request deduplication.

    Uses SHA-256 of the concatenated fields.
    No random components — same inputs → same fingerprint.
    """
    raw = f"{protocol_hash}|{article_hash}|{stage}|{model}|{advisory_version}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def compute_article_hash(title: str, abstract: str, protocol_version: str) -> str:
    """Compute stable hash of an article for fingerprinting."""
    raw = f"{protocol_version}:{title.strip().lower()}:{abstract.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]

# ---------------------------------------------------------------------------
# Gateway
# ---------------------------------------------------------------------------

class LLMGateway:
    """Centralized LLM execution governance.

    Module-level singleton. Thread-safe.
    """

    def __init__(self, config: Optional[AdvisoryConfig] = None):
        self._config = config or AdvisoryConfig()
        self._semaphore = threading.BoundedSemaphore(self._config.max_concurrent_requests)
        self._rate_limiter = _SlidingWindowRateLimiter(self._config.max_requests_per_minute_gateway)
        self._circuit_breaker = _CircuitBreaker(self._config)
        self._lock = threading.RLock()
        self._in_flight: Dict[str, InFlightRequest] = {}
        self._telemetry = GatewayTelemetry()
        self._latency_samples: deque = deque(maxlen=100)
        self._throughput_window: deque = deque(maxlen=120)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_advisory(
        self,
        request,
        execute_fn: Callable,
        provider: str = "default",
        fingerprint: Optional[str] = None,
        timeout: float = 300.0,
        cancel_event: Optional[threading.Event] = None,
    ) -> Any:
        """Execute an advisory generation through the governance layer.

        Args:
            request: Advisory request object (used for fingerprinting).
            execute_fn: Callable that performs the actual LLM call.
            provider: Provider name for circuit breaker tracking.
            fingerprint: Pre-computed fingerprint (computed from request if None).
            timeout: Maximum time to wait for a concurrency slot.
            cancel_event: Optional threading.Event. If set during retry backoff
                          or rate limiting, the call is aborted immediately.

        Returns:
            The result from execute_fn, or the result of a duplicate in-flight request.

        Governance applied (in order):
            1. Check circuit breaker
            2. Check deduplication
            3. Acquire rate limit slot
            4. Acquire concurrency slot
            5. Execute with retry
            6. Release slots
            7. Update telemetry
        """
        fp = fingerprint or self._compute_fingerprint(request)
        provider_key = provider

        # Step 0: check provider health
        provider_status = self._circuit_breaker.get_status(provider_key)
        if provider_status == ProviderStatus.UNAVAILABLE:
            raise RuntimeError(f"Provider '{provider_key}' is UNAVAILABLE")

        # Step 1: deduplication check
        dedup_result = self._check_dedup(fp)
        if dedup_result is not None:
            return dedup_result

        # Step 2: rate limit (interruptible)
        if cancel_event and cancel_event.is_set():
            raise RuntimeError("Cancelled before rate limit acquire")
        if not self._rate_limiter.acquire(timeout=30.0, cancel_event=cancel_event):
            self._telemetry.rate_limit_waits += 1
            raise RuntimeError("Rate limit timeout: too many requests per minute")

        # Step 3: concurrency slot
        if cancel_event and cancel_event.is_set():
            self._rate_limiter.release()
            raise RuntimeError("Cancelled before concurrency acquire")
        self._telemetry.concurrency_waits += 1
        acquired = self._semaphore.acquire(blocking=True, timeout=timeout)
        if not acquired:
            self._rate_limiter.release()
            raise RuntimeError("Concurrency slot timeout: all slots busy")

        try:
            get_telemetry_bus().record_provider_call(provider_key)
        except Exception:
            pass

        start_time = time.time()
        with self._lock:
            self._telemetry.active_requests += 1
            self._telemetry.total_requests += 1

        try:
            # Step 4: execute with retry (interruptible)
            result, error, retries = self._execute_with_retry(
                execute_fn, provider_key, cancel_event=cancel_event,
            )

            elapsed = time.time() - start_time

            with self._lock:
                self._telemetry.active_requests -= 1
                self._telemetry.latest_timestamp = time.time()
                self._latency_samples.append(elapsed * 1000)
                if len(self._latency_samples) >= 3:
                    sorted_samples = sorted(self._latency_samples)
                    n = len(sorted_samples)
                    self._telemetry.p95_latency_ms = sorted_samples[int(n * 0.95)]
                self._telemetry.mean_latency_ms = (
                    sum(self._latency_samples) / max(len(self._latency_samples), 1)
                )
                self._throughput_window.append(time.time())
                self._telemetry.throughput_per_minute = self._compute_throughput()
                self._telemetry.latest_cost_estimate_usd = (
                    self._estimate_cost(elapsed, error)
                )
                self._telemetry.total_retries += retries
                if retries > 0:
                    key = str(retries)
                    self._telemetry.retry_counts[key] = self._telemetry.retry_counts.get(key, 0) + 1

                if error:
                    self._telemetry.total_failed += 1
                    try:
                        get_telemetry_bus().record_provider_failure(provider_key, error[:64])
                    except Exception:
                        pass
                else:
                    self._telemetry.total_successful += 1

            # Step 5: complete dedup
            self._complete_dedup(fp, result, error)

            if error:
                raise RuntimeError(error)
            return result

        finally:
            self._semaphore.release()

    def acquire_generation_slot(self) -> bool:
        """Non-blocking concurrency slot acquisition."""
        return self._semaphore.acquire(blocking=False)

    def release_generation_slot(self):
        """Release a previously acquired slot."""
        self._semaphore.release()

    def estimate_budget(self, n_requests: int) -> Dict:
        """Estimate if n_requests can be processed within limits.

        Returns dict with:
            - feasible: bool
            - estimated_wait_seconds: float
            - bottleneck: str (concurrency | rate_limit | provider)
        """
        available_concurrent = self._config.max_concurrent_requests - self._telemetry.active_requests
        if available_concurrent < n_requests:
            return {
                "feasible": False,
                "estimated_wait_seconds": 30.0,
                "bottleneck": "concurrency",
                "available_slots": available_concurrent,
            }
        return {
            "feasible": True,
            "estimated_wait_seconds": 0.0,
            "bottleneck": "none",
            "available_slots": available_concurrent,
        }

    def get_runtime_stats(self) -> Dict:
        """Thread-safe frozen snapshot of gateway telemetry."""
        with self._lock:
            telemetry = self._telemetry.snapshot()
            telemetry["provider_states"] = self._circuit_breaker.get_all_states()
            telemetry["active_requests"] = self._telemetry.active_requests
            telemetry["in_flight_count"] = len(self._in_flight)
            return telemetry

    # ------------------------------------------------------------------
    # Circuit breaker helpers
    # ------------------------------------------------------------------

    def get_provider_status(self, provider: str = "default") -> str:
        """Get current provider health status."""
        return self._circuit_breaker.get_status(provider).value

    def record_provider_success(self, provider: str = "default"):
        """Record a successful provider call."""
        self._circuit_breaker.record_success(provider)

    def record_provider_failure(self, provider: str = "default"):
        """Record a failed provider call."""
        self._circuit_breaker.record_failure(provider)
        with self._lock:
            self._telemetry.cooldown_activations += 1

    # ------------------------------------------------------------------
    # Internal: fingerprint
    # ------------------------------------------------------------------

    def _compute_fingerprint(self, request) -> str:
        """Compute fingerprint from a request object."""
        try:
            title = getattr(request, 'title', '')
            abstract = getattr(request, 'abstract', '')
            pv = getattr(request, 'protocol_version', '1.0')
            stage = "ic"
            if hasattr(request, 'metadata') and request.metadata:
                stage = request.metadata.get('stage', 'ic')
            article_hash = compute_article_hash(title, abstract, pv)
            return compute_request_fingerprint(pv, article_hash, stage)
        except Exception:
            return hashlib.sha256(str(id(request)).encode()).hexdigest()[:32]

    # ------------------------------------------------------------------
    # Internal: deduplication
    # ------------------------------------------------------------------

    def _check_dedup(self, fingerprint: str) -> Optional[Any]:
        """Check if an identical request is in-flight or completed.

        If in-flight: wait for the existing request to complete,
        then return its result. Does NOT execute a duplicate.

        Returns:
            Existing result if deduplicated, None if no duplicate found.
        """
        with self._lock:
            existing = self._in_flight.get(fingerprint)
            if existing is None:
                # Register this fingerprint as in-flight
                entry = InFlightRequest(fingerprint=fingerprint, start_time=time.time())
                self._in_flight[fingerprint] = entry
                return None

        # Duplicate found — wait for original to complete
        existing.event.wait(timeout=300.0)
        with self._lock:
            self._telemetry.total_deduplicated += 1
        if existing.error:
            raise RuntimeError(existing.error)
        return existing.result

    def _complete_dedup(self, fingerprint: str, result: Any, error: Optional[str]):
        """Mark an in-flight request as completed and signal waiters."""
        with self._lock:
            entry = self._in_flight.pop(fingerprint, None)
            if entry is None:
                return
            entry.result = result
            entry.error = error
            entry.event.set()

    # ------------------------------------------------------------------
    # Internal: retry
    # ------------------------------------------------------------------

    def _execute_with_retry(
        self,
        execute_fn: Callable,
        provider: str,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[Any, Optional[str], int]:
        """Execute the provider call with deterministic retry.

        Uses interruptible sleep: if cancel_event is set during backoff,
        the retry loop is aborted immediately.

        Returns:
            (result, error_string, retry_count)
        """
        bus = get_telemetry_bus()
        last_error: Optional[str] = None
        retries = 0
        total_timeout = self._config.max_retry_total_timeout_seconds
        start_time = time.time()

        for attempt in range(self._config.max_retries_per_request + 1):
            if cancel_event and cancel_event.is_set():
                return None, "Cancelled during retry", retries

            if time.time() - start_time > total_timeout:
                return None, f"Retry total timeout exceeded ({total_timeout}s)", retries

            provider_status = self._circuit_breaker.get_status(provider)
            if provider_status == ProviderStatus.UNAVAILABLE:
                return None, f"Provider '{provider}' is UNAVAILABLE", retries

            if provider_status == ProviderStatus.COOLDOWN:
                return None, f"Provider '{provider}' in COOLDOWN", retries

            try:
                result = execute_fn()
                self._circuit_breaker.record_success(provider)
                return result, None, retries
            except Exception as e:
                last_error = str(e)
                self._circuit_breaker.record_failure(provider)

                if attempt < self._config.max_retries_per_request:
                    backoff = self._deterministic_backoff(attempt)
                    retries += 1
                    try:
                        bus.record_retry(f"gateway_{provider}")
                    except Exception:
                        pass
                    self._interruptible_sleep(backoff, cancel_event)
                    if cancel_event and cancel_event.is_set():
                        return None, "Cancelled during retry backoff", retries
                else:
                    break

        return None, last_error or "Max retries exceeded", retries

    @staticmethod
    def _interruptible_sleep(
        duration: float,
        cancel_event: Optional[threading.Event] = None,
    ):
        """Sleep for `duration` seconds, waking early if cancel_event is set.

        Uses small polling intervals (0.1s) so cancellation is responsive
        without busy-waiting.
        """
        if cancel_event is None:
            time.sleep(duration)
            return
        deadline = time.time() + duration
        while time.time() < deadline:
            if cancel_event.is_set():
                return
            remaining = deadline - time.time()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.1))

    def _deterministic_backoff(self, attempt: int) -> float:
        """Deterministic exponential backoff — NO JITTER.

        backoff = retry_backoff_seconds * (2 ** attempt)
        capped at backoff_max from config

        This is purely deterministic: same attempt number → same backoff.
        """
        base = self._config.retry_backoff_seconds
        backoff = base * (2 ** attempt)
        return min(backoff, self._config.backoff_max)

    # ------------------------------------------------------------------
    # Internal: throughput
    # ------------------------------------------------------------------

    @staticmethod
    def _estimate_cost(duration_seconds: float, error: Optional[str]) -> float:
        """Estimate API cost based on request duration.

        Approximate: assumes ~500 input tokens, ~200 output tokens
        for a typical advisory request at $0.59/$0.79 per 1M tokens.
        Failed requests cost nothing (no output charged).
        """
        from .cost_model import estimate_request_cost
        if error:
            return 0.0
        est = estimate_request_cost(
            prompt_chars=2000,  # avg prompt ~500 tokens
            response_chars=800 if duration_seconds < 30 else 400,
            model="llama-3.3-70b-versatile",
        )
        return est["estimated_cost_usd"]

    def _compute_throughput(self) -> float:
        """Compute requests per minute over the last 60 seconds."""
        now = time.time()
        while self._throughput_window and now - self._throughput_window[0] > 60.0:
            self._throughput_window.popleft()
        return len(self._throughput_window)


_global_gateway: Optional[LLMGateway] = None
_gateway_lock = threading.Lock()


def get_llm_gateway(config: Optional[AdvisoryConfig] = None) -> LLMGateway:
    """Get the global LLM gateway singleton."""
    global _global_gateway
    if _global_gateway is None:
        with _gateway_lock:
            if _global_gateway is None:
                _global_gateway = LLMGateway(config)
    return _global_gateway


def reset_llm_gateway():
    """Reset the global gateway (for testing)."""
    global _global_gateway
    with _gateway_lock:
        _global_gateway = None
