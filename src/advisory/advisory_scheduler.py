"""
APOLLO Stage-Aware Advisory Scheduler

Implements deterministic stage-aware advisory prioritization:
- Tracks active researcher stage (EC/IC/QC)
- Controls worker priority based on active stage
- Supports pause/resume without queue loss
- Preserves deterministic behavior and isolation guarantees
"""

from typing import Optional, Dict, Literal
from dataclasses import dataclass, field
from datetime import datetime
import threading

WorkerState = Literal["RUNNING", "PAUSED", "IDLE"]

STAGE_PRIORITY = {
    "ec": 1,
    "ic": 2,
    "qc": 3
}

VALID_STAGES = ("ec", "ic", "qc")


@dataclass
class SchedulerState:
    active_stage: str = "ec"
    worker_states: Dict[str, WorkerState] = field(default_factory=lambda: {
        "ec": "IDLE", 
        "ic": "IDLE", 
        "qc": "IDLE"
    })
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    priority_hint: str = "ec"


class AdvisoryScheduler:
    """
    Centralized scheduler for stage-aware advisory generation.
    
    Key principles:
    - Deterministic: same active stage → same worker behavior
    - Isolated: stage-specific workers remain independent
    - Resumable: pause/resume preserves queue position
    - Observable: all state transitions logged
    """
    
    def __init__(self):
        self._state = SchedulerState()
        self._lock = threading.RLock()
        self._initialized = False
        print(f"[SCHEDULER INIT] Priority order: ec > ic > qc")
    
    @property
    def active_stage(self) -> str:
        with self._lock:
            return self._state.active_stage
    
    @property
    def worker_state(self) -> Dict[str, WorkerState]:
        with self._lock:
            return dict(self._state.worker_states)
    
    def get_worker_priority(self, stage: str) -> int:
        """Get numeric priority for a stage. Lower = higher priority."""
        if stage not in VALID_STAGES:
            return 999
        return STAGE_PRIORITY.get(stage, 999)
    
    def should_process_stage(self, stage: str) -> bool:
        """
        Determine if a stage should be processed based on active stage.
        
        Priority rules:
        - Active stage gets highest priority
        - Other stages are paused/yield
        - This is deterministic based on active_stage
        """
        with self._lock:
            active = self._state.active_stage
            
            if stage == active:
                return True
            
            active_priority = self.get_worker_priority(active)
            stage_priority = self.get_worker_priority(stage)
            
            should_process = stage_priority <= active_priority
            
            if not should_process:
                print(f"[SCHEDULER] Stage '{stage}' yields to active stage '{active}'")
            
            return should_process
    
    def set_active_stage(self, stage: str) -> None:
        """
        Update active researcher stage.
        
        This is called when researcher navigates to a different screen.
        Must be deterministic - same stage input → same state output.
        """
        if stage not in VALID_STAGES:
            print(f"[SCHEDULER WARN] Invalid stage: {stage}")
            return
        
        with self._lock:
            old_stage = self._state.active_stage
            
            if old_stage != stage:
                self._state.active_stage = stage
                self._state.last_updated = datetime.utcnow().isoformat()
                self._state.priority_hint = stage
                
                print(f"[SCHEDULER] Active stage changed: {old_stage} -> {stage}")
                print(f"[SCHEDULER] Priority hint: {stage}")
                
                self._update_worker_states(stage)
    
    def _update_worker_states(self, active_stage: str) -> None:
        """Update worker states based on new active stage."""
        for stage in VALID_STAGES:
            if stage == active_stage:
                new_state: WorkerState = "RUNNING"
            else:
                new_state = "PAUSED"
            
            old_state = self._state.worker_states.get(stage, "IDLE")
            
            if old_state != new_state:
                print(f"[SCHEDULER] Worker state: {stage}: {old_state} -> {new_state}")
                self._state.worker_states[stage] = new_state
    
    def get_worker_state(self, stage: str) -> WorkerState:
        """Get current state of a specific stage worker."""
        with self._lock:
            return self._state.worker_states.get(stage, "IDLE")
    
    def pause_worker(self, stage: str) -> None:
        """Explicitly pause a stage's worker."""
        if stage not in VALID_STAGES:
            return
        
        with self._lock:
            if self._state.worker_states[stage] != "PAUSED":
                self._state.worker_states[stage] = "PAUSED"
                print(f"[WORKER PAUSE] Stage: {stage}")
    
    def resume_worker(self, stage: str) -> None:
        """Explicitly resume a stage's worker."""
        if stage not in VALID_STAGES:
            return
        
        with self._lock:
            if self._state.worker_states[stage] != "RUNNING":
                if self._state.active_stage == stage:
                    self._state.worker_states[stage] = "RUNNING"
                    print(f"[WORKER RESUME] Stage: {stage} (active)")
                else:
                    self._state.worker_states[stage] = "PAUSED"
                    print(f"[WORKER RESUME] Stage: {stage} (pending - waiting for active)")
    
    def get_status(self) -> Dict:
        """Get scheduler status for observability."""
        with self._lock:
            return {
                "active_stage": self._state.active_stage,
                "priority_hint": self._state.priority_hint,
                "worker_states": dict(self._state.worker_states),
                "last_updated": self._state.last_updated,
                "priority_order": STAGE_PRIORITY
            }
    
    def get_stage_priority_order(self) -> list:
        """Get stages in priority order (highest to lowest)."""
        return sorted(STAGE_PRIORITY.keys(), key=lambda x: STAGE_PRIORITY[x])


_global_scheduler: Optional[AdvisoryScheduler] = None


def get_advisory_scheduler() -> AdvisoryScheduler:
    """Get global scheduler instance."""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = AdvisoryScheduler()
    return _global_scheduler


def set_active_stage(stage: str) -> None:
    """Set the active researcher stage (convenience function)."""
    scheduler = get_advisory_scheduler()
    scheduler.set_active_stage(stage)


def get_active_stage() -> str:
    """Get the current active researcher stage."""
    return get_advisory_scheduler().active_stage


def should_process_stage(stage: str) -> bool:
    """Check if a stage should be processed based on active stage."""
    return get_advisory_scheduler().should_process_stage(stage)


def get_worker_state(stage: str) -> WorkerState:
    """Get current state of a stage's worker."""
    return get_advisory_scheduler().get_worker_state(stage)