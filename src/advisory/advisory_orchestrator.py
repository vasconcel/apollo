"""
Advisory worker orchestration for APOLLO.

Provides automatic background worker management:
- Automatic queue creation after session init
- Background worker thread that survives reruns
- Progress tracking and status reporting
- Session lifecycle integration
"""

import threading
import time
import os
from typing import Optional, Dict, List, Callable
from datetime import datetime

from .advisory_models import AdvisoryConfig, AdvisoryStatus
from .advisory_queue import get_advisory_queue, build_queue
from .advisory_worker import AdvisoryWorker
from .advisory_cache import get_advisory_cache, get_cache_stats
from .prefilter import get_prefilter
class AdvisoryWorkerOrchestrator:
    """
    Manages background advisory worker lifecycle.
    
    Key features:
    - Automatic queue creation
    - Background worker execution
    - Progress persistence
    - Session integration
    """
    
    def __init__(self, config: Optional[AdvisoryConfig] = None, stage: str = "ic", protocol=None):
        self.config = config or AdvisoryConfig()
        self._stage = stage
        self._protocol = protocol
        self._worker: Optional[AdvisoryWorker] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._start_lock = threading.Lock()
    
    def set_protocol(self, protocol) -> None:
        """Set the protocol object for criteria retrieval."""
        self._protocol = protocol

    def initialize_queue(self, articles: List, protocol_version: str = "1.0", stage: str = "ic", protocol=None) -> Dict:
        """
        Initialize advisory queue from articles.

        Called automatically after session creation/upload.
        """
        if protocol is not None:
            self._protocol = protocol

        # Reset prefilter dedup state per pipeline init (session-scoped isolation)
        get_prefilter(stage=stage).reset()

        queue = get_advisory_queue(self.config, stage=stage)
        queue.clear()
        state = queue.build_from_articles(
            articles,
            protocol_version=protocol_version,
            stage=stage,
            skip_existing=True
        )
        print(f"[QUEUE] Built {state.total} items for stage {stage}")
        return queue.get_stats()
    
    def start_worker(self, max_items: Optional[int] = None) -> None:
        """
        Start background worker thread.

        Runs independently from Streamlit reruns.
        """
        with self._start_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                print(f"[WORKER] Duplicate spawn blocked for {self._stage}")
                return

            self._stop_event.clear()
            self._worker = AdvisoryWorker(self.config, protocol=self._protocol)

            def run_worker_loop():
                try:
                    self._worker.process_all(max_items, stage=self._stage, stop_event=self._stop_event)
                except Exception as e:
                    print(f"[WORKER] Error: {e}")
                finally:
                    print(f"[WORKER] Stopped for {self._stage}")

            self._worker_thread = threading.Thread(
                target=run_worker_loop,
                daemon=True,
                name=f"advisory-worker-{self._stage}"
            )
            self._worker_thread.start()

    def _is_active(self) -> bool:
        """Check if worker should be considered active."""
        return not self._stop_event.is_set()
    
    def stop_worker(self) -> None:
        """Stop background worker gracefully."""
        self._stop_event.set()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
    
    def get_status(self, stage: str = "ic") -> Dict:
        """Get worker status for specific stage."""
        queue_stats = get_advisory_queue(self.config, stage=stage).get_stats()
        cache_stats = get_cache_stats()
        thread_alive = self._worker_thread.is_alive() if self._worker_thread else False
        is_active = self._is_active() and thread_alive
        
        return {
            "is_running": is_active,
            "thread_alive": thread_alive,
            "workers_active": 1 if is_active else 0,
            "queue": queue_stats,
            "cache": cache_stats,
            "generated_count": queue_stats.get("completed", 0),
            "pending_count": queue_stats.get("pending", 0),
            "failed_count": queue_stats.get("failed", 0)
        }
    
    def is_generating(self) -> bool:
        """Check if worker is actively processing."""
        return self._is_active() and (
            self._worker_thread.is_alive() if self._worker_thread else False
        )


_global_orchestrator_ec: Optional[AdvisoryWorkerOrchestrator] = None
_global_orchestrator_ic: Optional[AdvisoryWorkerOrchestrator] = None
_global_orchestrator_qc: Optional[AdvisoryWorkerOrchestrator] = None


def lookup_orchestrator(stage: str = "ic") -> Optional[AdvisoryWorkerOrchestrator]:
    """
    PURE READ-ONLY orchestrator lookup - NEVER creates runtime.

    Args:
        stage: Advisory stage

    Returns:
        Existing orchestrator instance or None if not initialized

    Raises:
        ValueError: If stage is invalid
    """
    if stage not in ("ec", "ic", "qc"):
        raise ValueError(f"Invalid stage: {stage}. Must be 'ec', 'ic', or 'qc'.")

    global _global_orchestrator_ec, _global_orchestrator_ic, _global_orchestrator_qc

    stage_lower = stage.lower()
    if stage_lower == "ec":
        return _global_orchestrator_ec
    elif stage_lower == "ic":
        return _global_orchestrator_ic
    else:
        return _global_orchestrator_qc


def get_orchestrator(config: Optional[AdvisoryConfig] = None, stage: str = "ic") -> AdvisoryWorkerOrchestrator:
    """Get stage-scoped orchestrator instance - CREATES if absent."""
    global _global_orchestrator_ec, _global_orchestrator_ic, _global_orchestrator_qc

    stage_lower = stage.lower()
    if stage_lower == "ec":
        if _global_orchestrator_ec is None:
            _global_orchestrator_ec = AdvisoryWorkerOrchestrator(config, stage="ec")
        return _global_orchestrator_ec
    elif stage_lower == "ic":
        if _global_orchestrator_ic is None:
            _global_orchestrator_ic = AdvisoryWorkerOrchestrator(config, stage="ic")
        return _global_orchestrator_ic
    else:
        if _global_orchestrator_qc is None:
            _global_orchestrator_qc = AdvisoryWorkerOrchestrator(config, stage="qc")
        return _global_orchestrator_qc


def _can_reset_stage(stage: str) -> bool:
    """Check if it is safe to reset a stage's orchestrator/queue.

    Returns False if:
      - A calibration run is in progress for this stage (checked via CalibrationService)
      - Worker thread is still alive
    """
    orch = lookup_orchestrator(stage)
    if orch is not None and orch._worker_thread is not None and orch._worker_thread.is_alive():
        print(f"[RESET GUARD] Worker thread still alive for {stage} — reset blocked")
        return False
    return True


def reset_orchestrator_for_stage(stage: str = "ic", force: bool = False):
    """Reset orchestrator for specific stage (stops worker, discards instance).

    Args:
        stage: Advisory stage
        force: If True, skip safety checks (for calibration runner which
               manages its own lifecycle explicitly).

    Raises:
        RuntimeError: If stage is active and force=False
    """
    if not force and not _can_reset_stage(stage):
        raise RuntimeError(
            f"Cannot reset orchestrator for stage {stage}: worker is still active. "
            f"Stop the worker or use force=True."
        )

    global _global_orchestrator_ec, _global_orchestrator_ic, _global_orchestrator_qc
    stage_lower = stage.lower()
    old = None
    if stage_lower == "ec":
        old = _global_orchestrator_ec
        _global_orchestrator_ec = None
    elif stage_lower == "ic":
        old = _global_orchestrator_ic
        _global_orchestrator_ic = None
    else:
        old = _global_orchestrator_qc
        _global_orchestrator_qc = None
    if old is not None:
        old.stop_worker()


def initialize_advisory_pipeline(
    articles: List,
    protocol_version: str = "1.0",
    stage: str = "ic",
    auto_start: bool = True,
    max_items: Optional[int] = None,
    protocol=None
) -> Dict:
    """
    Initialize advisory pipeline after session creation.

    This is the main entry point called after upload.

    Steps:
    1. Build queue from articles (with stage)
    2. Start background worker (if auto_start=True)
    3. Return status for UI display
    """
    orchestrator = get_orchestrator(stage=stage)

    try:
        from src.advisory.advisory_scheduler import set_active_stage
        set_active_stage(stage)
    except ImportError:
        pass

    stats = orchestrator.initialize_queue(articles, protocol_version, stage=stage, protocol=protocol)

    if auto_start:
        orchestrator.start_worker(max_items)

    return {
        "queue_initialized": True,
        "worker_started": auto_start,
        "stage": stage,
        "total_articles": stats.get("total", 0),
        "pending_advisories": stats.get("pending", 0)
    }


def get_advisory_pipeline_status(stage: str = "ic") -> Dict:
    """
    Get current pipeline status for specific stage.
    READ-ONLY - uses lookup to never create runtime.
    """
    orchestrator = lookup_orchestrator(stage=stage)
    if orchestrator is None:
        return {
            "stage": stage,
            "initialized": False,
            "is_running": False,
            "thread_alive": False,
            "workers_active": 0,
            "queue": {"total": 0, "pending": 0, "completed": 0, "failed": 0},
            "generated_count": 0,
            "pending_advisories": 0
        }
    return orchestrator.get_status(stage=stage)


def start_background_generation(stage: str = "ic", max_items: Optional[int] = None) -> None:
    """
    Start background advisory generation for specific stage.
    MUTATING - creates runtime if absent (allowed - explicit initialization path).
    """
    
    orchestrator = get_orchestrator(stage=stage)
    orchestrator.start_worker(max_items)


def is_advisory_generation_active(stage: str = "ic") -> bool:
    """
    Check if advisory generation is active for specific stage.
    READ-ONLY - uses lookup to never create runtime.
    """
    orchestrator = lookup_orchestrator(stage=stage)
    if orchestrator is None:
        return False
    return orchestrator.is_generating()