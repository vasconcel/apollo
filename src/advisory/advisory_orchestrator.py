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


class AdvisoryWorkerOrchestrator:
    """
    Manages background advisory worker lifecycle.
    
    Key features:
    - Automatic queue creation
    - Background thread execution
    - Progress persistence
    - Session integration
    """
    
    def __init__(self, config: Optional[AdvisoryConfig] = None, stage: str = "ic"):
        self.config = config or AdvisoryConfig()
        self._stage = stage
        self._worker: Optional[AdvisoryWorker] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._start_lock = threading.Lock()
        print(f"[ORCHESTRATOR INIT] Stage: {stage}")
    
    def initialize_queue(self, articles: List, protocol_version: str = "1.0", stage: str = "ic") -> Dict:
        """
        Initialize advisory queue from articles.

        Called automatically after session creation/upload.
        """
        print(f"[ORCHESTRATOR] Getting queue for stage: {stage}")
        queue = get_advisory_queue(self.config, stage=stage)
        print(f"[ORCHESTRATOR] Queue retrieved: {id(queue)}")

        # CRITICAL FIX: Always rebuild queue to ensure cache keys match current articles
        # The previous early return caused stale queue items to persist while UI shows different articles
        print(f"[ORCHESTRATOR] Clearing existing queue for stage: {stage}")
        queue.clear()

        print(f"[ORCHESTRATOR] Building queue for stage: {stage}")

        state = queue.build_from_articles(
            articles,
            protocol_version=protocol_version,
            stage=stage,
            skip_existing=True
        )

        print(f"[ORCHESTRATOR] Queue built with {state.total} items for stage {stage}")
        return queue.get_stats()
    
    def start_worker(self, max_items: Optional[int] = None) -> None:
        """
        Start background worker thread.

        Runs independently from Streamlit reruns.
        """
        print(f"[LIFECYCLE] start_worker called for stage: {self._stage}")
        
        with self._start_lock:
            if self._is_running and self._worker_thread and self._worker_thread.is_alive():
                print(f"[LIFECYCLE] Worker already active: advisory-worker-{self._stage}")
                print(f"[LIFECYCLE] Prevented duplicate worker spawn for: {self._stage}")
                return

            print(f"[ORCHESTRATOR] Starting worker for stage: {self._stage}")
            self._worker = AdvisoryWorker(self.config)
            self._is_running = True

            def run_worker_loop():
                try:
                    self._worker.process_all(max_items, stage=self._stage)
                except Exception as e:
                    print(f"Advisory worker error: {e}")
                finally:
                    self._is_running = False
                    print(f"[WORKER STOP] Stage: {self._stage}")

            self._worker_thread = threading.Thread(
                target=run_worker_loop,
                daemon=True,
                name=f"advisory-worker-{self._stage}"
            )
            self._worker_thread.start()
            print(f"[WORKER START] Stage: {self._stage} | Thread: {self._worker_thread.name}")
    
    def stop_worker(self) -> None:
        """Stop background worker."""
        self._is_running = False
    
    def get_status(self, stage: str = "ic") -> Dict:
        """Get worker status for specific stage."""
        print(f"[ORCHESTRATOR STATUS] Stage: {stage}")
        queue_stats = get_advisory_queue(self.config, stage=stage).get_stats()
        cache_stats = get_cache_stats()
        
        return {
            "is_running": self._is_running,
            "thread_alive": self._worker_thread.is_alive() if self._worker_thread else False,
            "queue": queue_stats,
            "cache": cache_stats,
            "generated_count": queue_stats.get("completed", 0),
            "pending_count": queue_stats.get("pending", 0),
            "failed_count": queue_stats.get("failed", 0)
        }
    
    def is_generating(self) -> bool:
        """Check if worker is actively processing."""
        return self._is_running and (
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

    print(f"[LOOKUP ORCHESTRATOR] Stage: {stage}")

    global _global_orchestrator_ec, _global_orchestrator_ic, _global_orchestrator_qc

    stage_lower = stage.lower()
    if stage_lower == "ec":
        if _global_orchestrator_ec is None:
            print(f"[LOOKUP ORCHESTRATOR] Stage: ec | MISSING")
            return None
        print(f"[LOOKUP ORCHESTRATOR] Stage: ec | FOUND")
        return _global_orchestrator_ec
    elif stage_lower == "ic":
        if _global_orchestrator_ic is None:
            print(f"[LOOKUP ORCHESTRATOR] Stage: ic | MISSING")
            return None
        print(f"[LOOKUP ORCHESTRATOR] Stage: ic | FOUND")
        return _global_orchestrator_ic
    else:
        if _global_orchestrator_qc is None:
            print(f"[LOOKUP ORCHESTRATOR] Stage: qc | MISSING")
            return None
        print(f"[LOOKUP ORCHESTRATOR] Stage: qc | FOUND")
        return _global_orchestrator_qc


def get_orchestrator(config: Optional[AdvisoryConfig] = None, stage: str = "ic") -> AdvisoryWorkerOrchestrator:
    """Get stage-scoped orchestrator instance - CREATES if absent."""
    global _global_orchestrator_ec, _global_orchestrator_ic, _global_orchestrator_qc

    stage_lower = stage.lower()
    if stage_lower == "ec":
        if _global_orchestrator_ec is None:
            print(f"[ORCHESTRATOR CREATE] Stage: ec")
            _global_orchestrator_ec = AdvisoryWorkerOrchestrator(config, stage="ec")
        else:
            print(f"[ORCHESTRATOR REUSE] Stage: ec")
        return _global_orchestrator_ec
    elif stage_lower == "ic":
        if _global_orchestrator_ic is None:
            print(f"[ORCHESTRATOR CREATE] Stage: ic")
            _global_orchestrator_ic = AdvisoryWorkerOrchestrator(config, stage="ic")
        else:
            print(f"[ORCHESTRATOR REUSE] Stage: ic")
        return _global_orchestrator_ic
    else:
        if _global_orchestrator_qc is None:
            print(f"[ORCHESTRATOR CREATE] Stage: qc")
            _global_orchestrator_qc = AdvisoryWorkerOrchestrator(config, stage="qc")
        else:
            print(f"[ORCHESTRATOR REUSE] Stage: qc")
        return _global_orchestrator_qc


def reset_orchestrator_for_stage(stage: str = "ic"):
    """Reset orchestrator for specific stage."""
    global _global_orchestrator_ec, _global_orchestrator_ic, _global_orchestrator_qc
    stage_lower = stage.lower()
    if stage_lower == "ec":
        _global_orchestrator_ec = None
        print(f"[ORCHESTRATOR RESET] Stage: ec")
    elif stage_lower == "ic":
        _global_orchestrator_ic = None
        print(f"[ORCHESTRATOR RESET] Stage: ic")
    else:
        _global_orchestrator_qc = None
        print(f"[ORCHESTRATOR RESET] Stage: qc")


def initialize_advisory_pipeline(
    articles: List,
    protocol_version: str = "1.0",
    stage: str = "ic",
    auto_start: bool = True,
    max_items: Optional[int] = None
) -> Dict:
    """
    Initialize advisory pipeline after session creation.

    This is the main entry point called after upload.

    Steps:
    1. Build queue from articles (with stage)
    2. Start background worker (if auto_start=True)
    3. Return status for UI display
    """
    print(f"[PIPELINE CREATE] Stage: {stage}")
    orchestrator = get_orchestrator(stage=stage)

    try:
        from src.advisory.advisory_scheduler import set_active_stage, get_advisory_scheduler
        set_active_stage(stage)
        scheduler_status = get_advisory_scheduler().get_status()
        print(f"[PIPELINE] Scheduler updated: active={scheduler_status['active_stage']}")
    except ImportError:
        pass

    print(f"[PIPELINE] Initializing for stage: {stage}")

    stats = orchestrator.initialize_queue(articles, protocol_version, stage=stage)

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
    print(f"[PIPELINE STATUS] Stage: {stage}")
    orchestrator = lookup_orchestrator(stage=stage)
    if orchestrator is None:
        print(f"[PIPELINE STATUS] Stage: {stage} | NOT INITIALIZED")
        return {
            "stage": stage,
            "initialized": False,
            "is_running": False,
            "thread_alive": False,
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
    print(f"[BACKGROUND START] Stage: {stage}")
    orchestrator = get_orchestrator(stage=stage)
    orchestrator.start_worker(max_items)


def is_advisory_generation_active(stage: str = "ic") -> bool:
    """
    Check if advisory generation is active for specific stage.
    READ-ONLY - uses lookup to never create runtime.
    """
    orchestrator = lookup_orchestrator(stage=stage)
    if orchestrator is None:
        print(f"[IS ACTIVE CHECK] Stage: {stage} | NOT INITIALIZED")
        return False
    return orchestrator.is_generating()