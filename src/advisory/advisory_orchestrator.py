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
    
    def __init__(self, config: Optional[AdvisoryConfig] = None):
        self.config = config or AdvisoryConfig()
        self._worker: Optional[AdvisoryWorker] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._start_lock = threading.Lock()
    
    def initialize_queue(self, articles: List, protocol_version: str = "1.0") -> Dict:
        """
        Initialize advisory queue from articles.
        
        Called automatically after session creation/upload.
        """
        queue = get_advisory_queue(self.config)
        
        existing = queue.get_stats()
        if existing.get("total", 0) > 0:
            return existing
        
        state = queue.build_from_articles(
            articles,
            protocol_version=protocol_version,
            skip_existing=True
        )
        
        return queue.get_stats()
    
    def start_worker(self, max_items: Optional[int] = None) -> None:
        """
        Start background worker thread.
        
        Runs independently from Streamlit reruns.
        """
        with self._start_lock:
            if self._is_running and self._worker_thread and self._worker_thread.is_alive():
                return
            
            self._worker = AdvisoryWorker(self.config)
            self._is_running = True
            
            def run_worker_loop():
                try:
                    self._worker.process_all(max_items)
                except Exception as e:
                    print(f"Advisory worker error: {e}")
                finally:
                    self._is_running = False
            
            self._worker_thread = threading.Thread(
                target=run_worker_loop,
                daemon=True,
                name="advisory-worker"
            )
            self._worker_thread.start()
    
    def stop_worker(self) -> None:
        """Stop background worker."""
        self._is_running = False
    
    def get_status(self) -> Dict:
        """Get worker status."""
        queue_stats = get_advisory_queue(self.config).get_stats()
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


_global_orchestrator: Optional[AdvisoryWorkerOrchestrator] = None


def get_orchestrator(config: Optional[AdvisoryConfig] = None) -> AdvisoryWorkerOrchestrator:
    """Get global orchestrator instance."""
    global _global_orchestrator
    if _global_orchestrator is None:
        _global_orchestrator = AdvisoryWorkerOrchestrator(config)
    return _global_orchestrator


def initialize_advisory_pipeline(
    articles: List,
    protocol_version: str = "1.0",
    auto_start: bool = True,
    max_items: Optional[int] = None
) -> Dict:
    """
    Initialize advisory pipeline after session creation.
    
    This is the main entry point called after upload.
    
    Steps:
    1. Build queue from articles
    2. Start background worker (if auto_start=True)
    3. Return status for UI display
    """
    orchestrator = get_orchestrator()
    
    stats = orchestrator.initialize_queue(articles, protocol_version)
    
    if auto_start:
        orchestrator.start_worker(max_items)
    
    return {
        "queue_initialized": True,
        "worker_started": auto_start,
        "total_articles": stats.get("total", 0),
        "pending_advisories": stats.get("pending", 0)
    }


def get_advisory_pipeline_status() -> Dict:
    """Get current pipeline status."""
    orchestrator = get_orchestrator()
    return orchestrator.get_status()


def start_background_generation(max_items: Optional[int] = None) -> None:
    """Start background advisory generation."""
    orchestrator = get_orchestrator()
    orchestrator.start_worker(max_items)


def is_advisory_generation_active() -> bool:
    """Check if advisory generation is active."""
    orchestrator = get_orchestrator()
    return orchestrator.is_generating()