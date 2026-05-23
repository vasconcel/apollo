"""
Protocol Calibration Runner for APOLLO.

Orchestrates a sequential EC→IC pilot screening on a subset of articles
using the same advisory engine, queue, cache, and worker infrastructure.

This is NOT a separate pipeline — it is a different orchestration policy
reusing all existing components.
"""

import time
import threading
from typing import List, Dict, Optional, Any

from .advisory_models import AdvisoryConfig, AdvisoryDecision
from .advisory_orchestrator import (
    AdvisoryWorkerOrchestrator,
    reset_orchestrator_for_stage,
    initialize_advisory_pipeline,
)
from .advisory_queue import reset_queue_for_stage, get_queue_stats
from .advisory_cache import get_advisory_cache, get_cache_stats
from .advisory_metrics import get_metrics, reset_metrics
from .calibration_artifact import build_calibration_artifact, save_calibration_artifact
from .protocol_diagnostics import run_diagnostics
from .telemetry_bus import get_telemetry_bus


CALIBRATION_STAGES = ("ec", "ic")


def _select_calibration_sample(articles: List, sample_size: int) -> List:
    """Select first N articles for calibration."""
    return articles[:sample_size]


def _extract_advisory_decisions(stage: str) -> List[Dict]:
    """Extract advisory decisions for a given stage from cache."""
    cache = get_advisory_cache()
    cached_keys = cache.list_cached(None)
    results = []
    for key in cached_keys:
        item = cache.get(key)
        if item and getattr(item, 'stage', None) == stage:
            results.append({
                "cache_key": key,
                "decision": getattr(item, 'decision', "UNKNOWN"),
                "confidence": getattr(item, 'confidence', 0.0),
                "triggered_criteria": getattr(item, 'triggered_criteria', []),
                "criterion_evaluations": getattr(item, 'criterion_evaluations', []),
                "hallucination_risk_score": getattr(item, 'hallucination_risk_score', 0.0),
                "grounding_strength": getattr(item, 'grounding_strength', 0.0),
            })
    return results


def _count_triggered_criteria(advisories: List[Dict]) -> Dict[str, int]:
    """Count how many times each criterion was triggered."""
    counts: Dict[str, int] = {}
    for adv in advisories:
        for criterion in adv.get("triggered_criteria", []):
            criterion_name = criterion if isinstance(criterion, str) else str(criterion)
            counts[criterion_name] = counts.get(criterion_name, 0) + 1
    return counts


def _count_never_triggered(
    all_criteria: List[str],
    triggered_counts: Dict[str, int],
) -> List[str]:
    """Return criteria that were never triggered."""
    return [c for c in all_criteria if triggered_counts.get(c, 0) == 0]


def _count_always_triggered(all_advisories: int, triggered_counts: Dict[str, int]) -> List[str]:
    """Return criteria triggered for every advisory."""
    return [c for c, count in triggered_counts.items() if count >= all_advisories]


def _compute_criteria_overlap(
    ec_advisories: List[Dict],
    ic_advisories: List[Dict],
) -> Dict:
    """Detect semantic overlap between EC and IC criteria activation."""
    ec_sets = [set(a.get("triggered_criteria", [])) for a in ec_advisories]
    ic_sets = [set(a.get("triggered_criteria", [])) for a in ic_advisories]
    overlap_count = sum(
        1 for ec_set, ic_set in zip(ec_sets, ic_sets) if ec_set & ic_set
    )
    return {
        "ec_ic_overlap_count": overlap_count,
        "ec_ic_overlap_rate": round(overlap_count / max(len(ec_advisories), 1), 4),
    }


def generate_calibration_report(
    sample_size: int,
    ec_advisories: List[Dict],
    ic_advisories: List[Dict],
    config: AdvisoryConfig,
) -> Dict:
    """Build the calibration report from EC and IC results."""
    total = max(len(ec_advisories), len(ic_advisories), sample_size)

    ec_accepts = sum(1 for a in ec_advisories if a["decision"] == AdvisoryDecision.INCLUDE.value)
    ec_rejects = sum(1 for a in ec_advisories if a["decision"] == AdvisoryDecision.EXCLUDE.value)
    ec_ambiguous = total - ec_accepts - ec_rejects

    ic_accepts = sum(1 for a in ic_advisories if a["decision"] == AdvisoryDecision.INCLUDE.value)
    ic_rejects = sum(1 for a in ic_advisories if a["decision"] == AdvisoryDecision.EXCLUDE.value)
    ic_ambiguous = total - ic_accepts - ic_rejects

    ec_triggered = _count_triggered_criteria(ec_advisories)
    ic_triggered = _count_triggered_criteria(ic_advisories)

    ec_mean_conf = (
        round(sum(a["confidence"] for a in ec_advisories) / len(ec_advisories), 4)
        if ec_advisories else 0.0
    )
    ic_mean_conf = (
        round(sum(a["confidence"] for a in ic_advisories) / len(ic_advisories), 4)
        if ic_advisories else 0.0
    )

    low_grounding_ec = sum(1 for a in ec_advisories if a["grounding_strength"] < 0.5)
    low_grounding_ic = sum(1 for a in ic_advisories if a["grounding_strength"] < 0.5)

    high_ambiguity_ec = sum(1 for a in ec_advisories if a["hallucination_risk_score"] > 0.5)
    high_ambiguity_ic = sum(1 for a in ic_advisories if a["hallucination_risk_score"] > 0.5)

    overlap = _compute_criteria_overlap(ec_advisories, ic_advisories)

    # Recommendation logic
    high_ambiguity_total = high_ambiguity_ec + high_ambiguity_ic
    low_grounding_total = low_grounding_ec + low_grounding_ic
    criteria_issues = len(
        _count_never_triggered(list(ec_triggered.keys()) + list(ic_triggered.keys()), {})
    ) if (ec_triggered or ic_triggered) else 0

    if high_ambiguity_total > total * 0.3 or low_grounding_total > total * 0.5:
        recommendation = "protocol_requires_refinement"
        recommendation_label = "Protocol requires refinement — high ambiguity or low grounding detected"
    elif criteria_issues > 3 or overlap["ec_ic_overlap_rate"] > 0.5:
        recommendation = "criteria_underspecified"
        recommendation_label = "Criteria underspecified — overlap or never-triggered criteria detected"
    else:
        recommendation = "protocol_stable"
        recommendation_label = "Protocol stable — criteria well-specified for this sample"

    return {
        "sample_size": sample_size,
        "total_processed": total,
        "ec": {
            "total": len(ec_advisories),
            "accepts": ec_accepts,
            "rejects": ec_rejects,
            "ambiguous": ec_ambiguous,
            "mean_confidence": ec_mean_conf,
            "low_grounding": low_grounding_ec,
            "high_ambiguity": high_ambiguity_ec,
        },
        "ic": {
            "total": len(ic_advisories),
            "accepts": ic_accepts,
            "rejects": ic_rejects,
            "ambiguous": ic_ambiguous,
            "mean_confidence": ic_mean_conf,
            "low_grounding": low_grounding_ic,
            "high_ambiguity": high_ambiguity_ic,
        },
        "criteria": {
            "most_triggered_ec": sorted(ec_triggered.items(), key=lambda x: -x[1])[:5],
            "most_triggered_ic": sorted(ic_triggered.items(), key=lambda x: -x[1])[:5],
            "never_triggered_ec": ec_triggered,
            "never_triggered_ic": ic_triggered,
        },
        "overlap": overlap,
        "recommendation": recommendation,
        "recommendation_label": recommendation_label,
    }


class CalibrationRunner:
    """
    Orchestrates a sequential EC→IC calibration run on a sample subset.

    Reuses the existing queue, cache, and worker infrastructure.
    Does NOT create separate pipelines or fork orchestration logic.
    """

    def __init__(
        self,
        articles: List,
        config: Optional[AdvisoryConfig] = None,
        protocol=None,
        protocol_version: str = "1.0",
    ):
        self.articles = articles
        self.config = config or AdvisoryConfig()
        self.protocol = protocol
        self.protocol_version = protocol_version
        self.sample_size = self.config.calibration_sample_size
        self.all_criteria: List[str] = []

        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._status = "idle"
        self._current_stage: Optional[str] = None
        self._report: Optional[Dict] = None
        self._artifact_path: Optional[str] = None
        self._error: Optional[str] = None

        self._snapshot: Dict = self._build_snapshot()

    def _build_snapshot(self) -> Dict:
        """Build a frozen snapshot of current runtime state."""
        from .advisory_orchestrator import get_advisory_pipeline_status as _gaps
        ec_status = _gaps("ec")
        ic_status = _gaps("ic")
        return {
            "status": self._status,
            "current_stage": self._current_stage,
            "sample_size": self.sample_size,
            "ec_total": ec_status.get("queue", {}).get("total", 0),
            "ec_completed": ec_status.get("queue", {}).get("completed", 0),
            "ic_total": ic_status.get("queue", {}).get("total", 0),
            "ic_completed": ic_status.get("queue", {}).get("completed", 0),
            "ec_running": ec_status.get("is_running", False),
            "ic_running": ic_status.get("is_running", False),
            "timestamp": time.time(),
        }

    @property
    def status(self) -> str:
        return self._status

    @property
    def current_stage(self) -> Optional[str]:
        return self._current_stage

    @property
    def report(self) -> Optional[Dict]:
        return self._report

    @property
    def artifact_path(self) -> Optional[str]:
        return self._artifact_path

    def stop(self) -> None:
        """Signal graceful stop and wait for thread to finish."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=10.0)

    @property
    def calibration_progress(self) -> Dict:
        """Get frozen snapshot of progress (safe for UI across reruns)."""
        if self._status == "running":
            self._snapshot = self._build_snapshot()
        result = dict(self._snapshot)
        result["status"] = self._status
        return result

    def _run_stage(self, stage: str, sample: List) -> bool:
        """Run a single screening stage on the calibration sample."""
        bus = get_telemetry_bus()
        if self._stop_event.is_set():
            self._error = f"Calibration stopped before {stage.upper()}"
            bus.record_info(f"calibration_stage_stopped stage={stage} reason=user_stop", component="calibration", stage=stage)
            return False

        self._current_stage = stage
        bus.record_info(f"calibration_stage_start stage={stage} sample_size={len(sample)}", component="calibration", stage=stage, sample_size=str(len(sample)))
        reset_queue_for_stage(stage, force=True)
        reset_orchestrator_for_stage(stage, force=True)

        try:
            result = initialize_advisory_pipeline(
                articles=sample,
                protocol_version=self.protocol_version,
                stage=stage,
                auto_start=True,
                protocol=self.protocol,
            )
            ok = result.get("queue_initialized", False)
            if ok:
                bus.record_info(f"calibration_stage_initialized stage={stage}", component="calibration", stage=stage)
            else:
                bus.record_info(f"calibration_stage_failed stage={stage} reason=init_failed", component="calibration", stage=stage)
            return ok
        except Exception as e:
            self._error = f"Failed to initialize {stage.upper()}: {e}"
            bus.record_info(f"calibration_stage_error stage={stage} reason={e!s}", component="calibration", stage=stage)
            return False

    def _wait_for_completion(self, stage: str, timeout: float = 600.0) -> bool:
        """Wait for worker to finish processing the stage."""
        from .advisory_orchestrator import lookup_orchestrator, is_advisory_generation_active
        from .advisory_queue import get_queue_stats, lookup_queue

        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._stop_event.is_set():
                self._error = f"Calibration stopped during {stage.upper()}"
                return False
            if not is_advisory_generation_active(stage):
                queue = lookup_queue(stage)
                if queue is None:
                    return False
                stats = queue.get_stats()
                if stats.get("pending", 0) == 0:
                    return True
            if self._stop_event.wait(timeout=0.5):
                self._error = f"Calibration stopped during {stage.upper()}"
                return False
        self._error = f"Timeout waiting for {stage.upper()} to complete"
        return False

    def run(self) -> Dict:
        """
        Execute the full EC→IC calibration sequence.

        Returns:
            Calibration report dict.
        """
        bus = get_telemetry_bus()
        self._status = "running"
        overall_start = time.time()
        bus.record_info(f"calibration_start sample_size={self.sample_size} total_articles={len(self.articles)}", component="calibration", sample_size=str(self.sample_size))

        sample = _select_calibration_sample(self.articles, self.sample_size)
        if not sample:
            self._status = "error"
            self._error = "No articles for calibration sample"
            bus.record_info("calibration_failed reason=no_sample", component="calibration")
            return {"status": "error", "error": self._error}

        # EC stage
        ec_start = time.time()
        if self._stop_event.is_set():
            self._status = "stopped"
            bus.record_info("calibration_stopped reason=user_stop_before_ec", component="calibration")
            return {"status": "stopped", "error": self._error}

        if not self._run_stage("ec", sample):
            self._status = "error"
            bus.record_info(f"calibration_failed reason=ec_stage_failed error={self._error!s}", component="calibration")
            return {"status": "error", "error": self._error}

        if not self._wait_for_completion("ec"):
            self._status = "error" if self._error else "stopped"
            bus.record_info(f"calibration_failed reason=ec_wait_failed error={self._error!s}", component="calibration")
            return {"status": self._status, "error": self._error}
        ec_duration = time.time() - ec_start
        bus.record_info(f"calibration_stage_complete stage=ec duration_s={ec_duration:.1f}", component="calibration", stage="ec")

        # IC stage
        if self._stop_event.is_set():
            self._status = "stopped"
            bus.record_info("calibration_stopped reason=user_stop_before_ic", component="calibration")
            return {"status": "stopped", "error": "Calibration stopped before IC"}

        ic_start = time.time()
        if not self._run_stage("ic", sample):
            self._status = "error"
            bus.record_info(f"calibration_failed reason=ic_stage_failed error={self._error!s}", component="calibration")
            return {"status": "error", "error": self._error}

        if not self._wait_for_completion("ic"):
            self._status = "error"
            bus.record_info(f"calibration_failed reason=ic_wait_failed error={self._error!s}", component="calibration")
            return {"status": "error", "error": self._error}
        ic_duration = time.time() - ic_start
        bus.record_info(f"calibration_stage_complete stage=ic duration_s={ic_duration:.1f}", component="calibration", stage="ic")

        total_duration = time.time() - overall_start

        # Generate report
        ec_advisories = _extract_advisory_decisions("ec")
        ic_advisories = _extract_advisory_decisions("ic")

        self._report = generate_calibration_report(
            sample_size=self.sample_size,
            ec_advisories=ec_advisories,
            ic_advisories=ic_advisories,
            config=self.config,
        )

        # Run diagnostics
        overlap = self._report.get("overlap", {})
        diagnostics = run_diagnostics(
            ec_advisories=ec_advisories,
            ic_advisories=ic_advisories,
            all_criteria=self.all_criteria,
            overlap=overlap,
            config=self.config,
        )

        # Build and save calibration artifact
        artifact = build_calibration_artifact(
            report=self._report,
            runner=self,
            config=self.config,
            ec_advisories=ec_advisories,
            ic_advisories=ic_advisories,
            duration_seconds=total_duration,
            ec_duration=ec_duration,
            ic_duration=ic_duration,
        )
        artifact["diagnostics"] = diagnostics

        # Populate diagnostic-driven recommendation reasons
        high_severity = [d for d in diagnostics if d.get("severity") == "high"]
        medium_severity = [d for d in diagnostics if d.get("severity") == "medium"]
        if high_severity:
            artifact["recommendation"]["reasons"] = [
                d["description"] for d in high_severity
            ]
        elif medium_severity:
            artifact["recommendation"]["reasons"] = [
                d["description"] for d in medium_severity[:3]
            ]

        self._artifact_path = save_calibration_artifact(artifact)
        self._report["artifact_path"] = self._artifact_path
        self._report["diagnostics_count"] = len(diagnostics)
        self._report["diagnostics"] = diagnostics

        self._status = "completed"
        bus.record_info(f"calibration_completed duration_s={total_duration:.1f} artifact={self._artifact_path}", component="calibration")
        return self._report

    def run_async(self) -> Optional[threading.Thread]:
        """Launch calibration in a background thread.

        Idempotent: if already running or completed, does nothing
        and returns the existing thread or None.

        Returns:
            The background thread if started, None if already running/completed.
        """
        with self._lock:
            if self._status == "running":
                return self._thread
            if self._status == "completed":
                return None
            if self._thread is not None and self._thread.is_alive():
                return self._thread
            self._stop_event.clear()
            self._status = "running"
            self._thread = threading.Thread(target=self.run, daemon=True)
            self._thread.start()
            get_telemetry_bus().record_info("calibration_async_start", component="calibration")
            return self._thread
