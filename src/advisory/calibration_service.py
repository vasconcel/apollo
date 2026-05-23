"""
Persistent Calibration Service for APOLLO.

Module-level singleton that owns CalibrationRunner instances and survives
Streamlit reruns. Provides thread-safe lifecycle management, duplicate-run
prevention, and active-run detection.

Architecture:
  - Single module-level dict mapping session_id -> CalibrationRunner
  - RLock for thread safety across UI threads and background workers
  - Never stored in st.session_state (survives reruns and exception clears)

Usage:
    from src.advisory.calibration_service import calibration_service
    runner = calibration_service.get_or_create_runner(session_id, ...)
    calibration_service.get_runner(session_id)
    calibration_service.stop_runner(session_id)
"""
import threading
import time
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

from .calibration_runner import CalibrationRunner
from .advisory_models import AdvisoryConfig


class _CalibrationService:
    """Thread-safe singleton for managing calibration runner lifecycle."""

    def __init__(self):
        self._lock = threading.RLock()
        self._runners: Dict[str, CalibrationRunner] = {}
        self._session_keys: Dict[str, str] = {}  # session_id -> runner_key

    def _runner_key(self, protocol_version: str, protocol=None) -> str:
        from .calibration_artifact import _compute_protocol_hash
        return _compute_protocol_hash(protocol_version, protocol)

    def get_or_create_runner(
        self,
        session_id: str,
        articles: list,
        protocol=None,
        protocol_version: str = "1.0",
        config: Optional[AdvisoryConfig] = None,
        sample_size: Optional[int] = None,
    ) -> CalibrationRunner:
        """Get existing runner for this session or create one.

        Prevents duplicate runners for the same session+protocol combination.
        If a runner already exists and is not completed, returns the existing one.
        """
        key = self._runner_key(protocol_version, protocol)
        with self._lock:
            existing = self._runners.get(key)
            if existing is not None:
                if existing.status in ("running", "idle"):
                    return existing
                if existing.status == "completed":
                    return existing
                if existing.status == "error":
                    pass

            runner = CalibrationRunner(
                articles=articles,
                config=config,
                protocol=protocol,
                protocol_version=protocol_version,
            )
            if sample_size is not None:
                runner.sample_size = sample_size
            self._runners[key] = runner
            self._session_keys[session_id] = key
            return runner

    def get_runner(self, session_id: str) -> Optional[CalibrationRunner]:
        """Get runner for a session, if one exists."""
        with self._lock:
            key = self._session_keys.get(session_id)
            if key is None:
                return None
            return self._runners.get(key)

    def get_runner_by_key(self, key: str) -> Optional[CalibrationRunner]:
        """Get runner by protocol hash key."""
        with self._lock:
            return self._runners.get(key)

    def stop_runner(self, session_id: str) -> bool:
        """Stop a running calibration gracefully.

        Sets stop event and waits for the thread to finish.
        Returns True if a runner was stopped, False if none existed.
        """
        with self._lock:
            key = self._session_keys.get(session_id)
            if key is None:
                return False
            runner = self._runners.get(key)
            if runner is None:
                return False
            runner.stop()
            return True

    def stop_all(self) -> int:
        """Stop all active calibration runners."""
        count = 0
        with self._lock:
            keys = list(self._runners.keys())
            for key in keys:
                runner = self._runners.get(key)
                if runner is not None:
                    runner.stop()
                    count += 1
        return count

    def remove_runner(self, session_id: str) -> bool:
        """Remove runner from service (does not stop it)."""
        with self._lock:
            key = self._session_keys.pop(session_id, None)
            if key:
                self._runners.pop(key, None)
                return True
            return False

    def list_active_runs(self) -> List[Dict]:
        """List all active calibration runs (for dashboard)."""
        active = []
        with self._lock:
            for key, runner in self._runners.items():
                active.append({
                    "key": key,
                    "status": runner.status,
                    "current_stage": runner.current_stage,
                    "sample_size": runner.sample_size,
                })
        return active

    def is_active(self, session_id: str) -> bool:
        """Check if a session has an active (running) calibration."""
        runner = self.get_runner(session_id)
        if runner is None:
            return False
        return runner.status == "running"

    def has_completed(self, session_id: str) -> bool:
        """Check if a session has a completed calibration."""
        runner = self.get_runner(session_id)
        if runner is None:
            return False
        return runner.status == "completed"

    def clear_completed(self) -> int:
        """Remove all completed runners from the service."""
        count = 0
        with self._lock:
            finished = [
                k for k, r in self._runners.items()
                if r.status in ("completed", "error")
            ]
            for k in finished:
                del self._runners[k]
                count += 1
            self._session_keys = {
                s: k for s, k in self._session_keys.items()
                if k in self._runners
            }
        return count

    def __len__(self) -> int:
        with self._lock:
            return len(self._runners)


calibration_service = _CalibrationService()
