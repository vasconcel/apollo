"""
Worker Watchdog for APOLLO.

Monitors worker health via heartbeat timestamps and detects:
- Stuck workers (heartbeat not advancing)
- Dead threads with active PROCESSING queue items
- Stale PROCESSING items orphaned by crashes

Recovery actions:
- Requeue stale PROCESSING items back to PENDING
- Log recovery events to telemetry
- Prevent duplicate worker recreation

Architecture:
  - Module-level singleton with background polling thread
  - Configurable heartbeat timeout (default 300s)
  - Non-blocking check with interruptible sleep
"""
import time
import threading
from typing import Optional, Dict, List
from pathlib import Path

from .advisory_models import AdvisoryConfig, AdvisoryStatus
from .advisory_queue import lookup_queue
from .advisory_orchestrator import lookup_orchestrator
from .advisory_metrics import get_metrics, _RecoveryEvent
from .runtime_telemetry import get_runtime_telemetry


class WorkerWatchdog:
    """Monitors worker health and recovers stale state.

    Thread-safe. Singleton pattern. Background polling thread.
    """

    def __init__(self, config: Optional[AdvisoryConfig] = None):
        self._config = config or AdvisoryConfig()
        self._heartbeat_timeout: float = 300.0  # 5 minutes
        self._poll_interval: float = 30.0  # check every 30s
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._start_lock = threading.Lock()
        self._last_check_time: float = 0.0
        self._stale_recoveries: int = 0
        self._dead_thread_detections: int = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the watchdog background thread (idempotent)."""
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="advisory-watchdog",
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the watchdog background thread gracefully."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def configure(self, heartbeat_timeout: float = 300.0, poll_interval: float = 30.0) -> None:
        """Configure watchdog parameters."""
        with self._lock:
            self._heartbeat_timeout = max(heartbeat_timeout, 30.0)
            self._poll_interval = max(poll_interval, 5.0)

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Background polling loop with interruptible sleep."""
        while not self._stop_event.is_set():
            try:
                self._check_all_stages()
            except Exception as e:
                print(f"[WATCHDOG] Check error: {e}")
            self._last_check_time = time.time()
            # Interruptible sleep: check stop event every 0.5s
            deadline = time.time() + self._poll_interval
            while time.time() < deadline:
                if self._stop_event.is_set():
                    return
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                time.sleep(min(remaining, 0.5))

    def _check_all_stages(self) -> None:
        """Check all stages for stale workers and orphaned items."""
        for stage in ("ec", "ic", "qc"):
            self._check_stage(stage)

    def _check_stage(self, stage: str) -> None:
        """Check a single stage for stale state."""
        orch = lookup_orchestrator(stage)
        q = lookup_queue(stage)

        if orch is not None and q is not None:
            thread_alive = (
                orch._worker_thread is not None and orch._worker_thread.is_alive()
            )

            if thread_alive:
                # Check if worker has a heartbeat we can inspect
                worker = getattr(orch, '_worker', None)
                if worker is not None:
                    try:
                        hb = worker.get_heartbeat_stats()
                        now = time.monotonic()
                        last_progress = hb.get("last_progress_at", 0.0)
                        if last_progress > 0 and (now - last_progress) > self._heartbeat_timeout:
                            self._handle_stuck_worker(stage, orch, q)
                    except Exception:
                        pass

            # Check for orphaned PROCESSING items (dead thread but PROCESSING items remain)
            if not thread_alive:
                stale = self._requeue_stale_processing(q)
                if stale:
                    telemetry = get_runtime_telemetry()
                    telemetry.record_worker_event(
                        "stale_processing_recovery",
                        stage,
                        f"requeued {stale} items"
                    )

    def _handle_stuck_worker(self, stage: str, orch, q) -> None:
        """Handle a worker whose heartbeat has not advanced."""
        metrics = get_metrics()
        telemetry = get_runtime_telemetry()

        print(f"[WATCHDOG] Stuck worker detected for stage: {stage}")
        self._stale_recoveries += 1

        # Requeue any PROCESSING items
        stale = self._requeue_stale_processing(q)
        if stale:
            metrics.stale_processing_requeues += stale
            metrics.record_recovery_event(_RecoveryEvent(
                event_type="watchdog_stuck_worker",
                stage=stage,
                outcome="requeued",
                detail=f"heartbeat timeout, requeued {stale} items",
            ))
            telemetry.record_worker_event(
                "watchdog_stuck_worker", stage,
                f"requeued {stale} items"
            )

        # Stop the stuck worker
        try:
            orch.stop_worker()
            self._dead_thread_detections += 1
        except Exception as e:
            print(f"[WATCHDOG] Error stopping stuck worker: {e}")

    def _requeue_stale_processing(self, q) -> int:
        """Return PROCESSING items back to PENDING. Returns count."""
        if q is None:
            return 0
        try:
            return q._requeue_stale_processing(q.state)
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict:
        """Get watchdog statistics (frozen snapshot)."""
        with self._lock:
            return {
                "is_running": self.is_running,
                "heartbeat_timeout": self._heartbeat_timeout,
                "poll_interval": self._poll_interval,
                "last_check_time": self._last_check_time,
                "stale_recoveries": self._stale_recoveries,
                "dead_thread_detections": self._dead_thread_detections,
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_watchdog: Optional[WorkerWatchdog] = None
_watchdog_lock = threading.Lock()


def get_watchdog(config: Optional[AdvisoryConfig] = None) -> WorkerWatchdog:
    """Get the global watchdog singleton."""
    global _global_watchdog
    if _global_watchdog is None:
        with _watchdog_lock:
            if _global_watchdog is None:
                _global_watchdog = WorkerWatchdog(config)
    return _global_watchdog


def reset_watchdog():
    """Reset the global watchdog (for testing)."""
    global _global_watchdog
    with _watchdog_lock:
        if _global_watchdog is not None:
            _global_watchdog.stop()
        _global_watchdog = None
