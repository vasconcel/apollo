"""
APOLLO Advisory Pipeline

Offline, persisted, precomputed advisory generation.

This module provides:
- advisory_models: Typed dataclasses for advisories
- advisory_cache: Centralized cache layer (read-only for UI)
- advisory_queue: Queue management and progress tracking
- advisory_worker: Background generation pipeline
- precompute_advisories: CLI entrypoint for preprocessing

Usage:

    # Precompute entire corpus (CLI)
    python -m src.advisory.precompute_advisories --source data/articles.json

    # Generate single advisory
    from src.advisory import generate_single_advisory
    advisory = generate_single_advisory(title, abstract)

    # Check advisory status (UI)
    from src.advisory import get_advisory_status, AdvisoryStatus
    status = get_advisory_status(title, abstract)
    if status == AdvisoryStatus.COMPLETED:
        # Show advisory
"""

from .advisory_models import (
    AdvisoryStatus,
    ALL_ADVISORY_STATUSES,
    is_known_status,
    AdvisoryDecision,
    AdvisoryResult,
    AdvisoryRequest,
    CriterionEvaluation,
    QueueItem,
    QueueState,
    AdvisoryConfig,
    ValidationRouting,
    AutonomyAssessment,
    TopicRelevance,
    calibrate_confidence,
    compute_risk_classification,
    compute_evidence_strength,
    compute_uncertainty_score,
    assess_autonomy,
    populate_risk_classification,
    compute_metadata_completeness,
)

from .advisory_cache import (
    get_advisory_cache,
    get_advisory,
    get_advisory_by_key,
    get_ec_advisory,
    get_ec_advisory_status,
    get_qc_advisory,
    get_qc_advisory_status,
    has_advisory,
    store_advisory,
    get_advisory_status,
    get_cache_stats,
    list_cached_advisories,
    validate_advisory_structure
)

from .advisory_queue import (
    get_advisory_queue,
    build_queue,
    get_queue_stats,
    reset_failed_advisories
)

from .prefilter import (
    PrefilterEngine,
    PrefilterResult,
    get_prefilter,
)

from .stage_guard import (
    validate_criteria_stage_isolation,
    strip_contaminated_criteria,
    quarantine_advisory,
    get_stage_prefixes,
    get_opposite_stage_prefixes,
)

from .advisory_worker import (
    AdvisoryWorker,
    run_worker,
    generate_single_advisory
)

from .advisory_orchestrator import (
    AdvisoryWorkerOrchestrator,
    get_orchestrator,
    initialize_advisory_pipeline,
    get_advisory_pipeline_status,
    start_background_generation,
    is_advisory_generation_active
)

from .advisory_scheduler import (
    AdvisoryScheduler,
    get_advisory_scheduler,
    set_active_stage,
    get_active_stage,
    should_process_stage,
    get_worker_state
)

from .telemetry_timeseries import (
    TimeSeriesStore,
    MetricSeries,
    get_timeseries_store,
    reset_timeseries_store,
)

from .telemetry_bus import (
    TelemetryBus,
    get_telemetry_bus,
    reset_telemetry_bus,
)

from .telemetry_clock import (
    LogicalClock,
    EventEnvelope,
    stamp_event,
    get_logical_clock,
    reset_logical_clock,
)

from .telemetry_reconciliation import (
    ReconciliationEngine,
    ReconciliationReport,
    ReconciliationStore,
    run_reconciliation,
)

from .telemetry_backpressure import (
    BackpressureController,
    BackpressureState,
    get_backpressure_controller,
    reset_backpressure_controller,
)

from .telemetry_consistency import (
    ConsistencyChecker,
    ConsistencyReport,
    run_consistency_check,
)

from .telemetry_aggregator import (
    aggregate_decision_distribution,
    aggregate_acceptance_rate,
    aggregate_confidence_distribution,
    aggregate_latency,
    aggregate_retry_rate,
    aggregate_429_rate,
    aggregate_all,
    aggregate_all_windows,
)

from .calibration_drift import (
    jensen_shannon_divergence,
    detect_decision_drift,
    detect_confidence_drift,
    detect_criteria_drift,
    detect_drift,
    IncrementalDriftTracker,
)

from .advisory_quality_score import (
    compute_confidence_calibration_score,
    compute_grounding_quality_score,
    compute_criterion_consistency_score,
    compute_hallucination_risk_score,
    compute_override_rate_score,
    compute_quality_score,
    LiveQualityTracker,
)

from .advisory_reliability import (
    compute_advisory_reliability,
    compute_reliability_components,
    compute_batch_reliability,
    check_escalation,
    ThresholdCalibrator,
    OperationalMetrics,
    get_threshold_calibrator,
    get_operational_metrics,
)

from .transient_failures import (
    is_transient_provider_error,
    is_terminal_failure,
    classify_failure,
    classify_failure_semantic,
    classify_failure_detailed,
)

from .replay_system import (
    ReplaySnapshot,
    ReplayStore,
    freeze_replay_snapshot,
    compute_replay_session_id,
    get_replay_store,
    reset_replay_store,
    TelemetryReplay,
)

from .ground_truth_comparator import (
    compute_confusion_matrix,
    compute_per_criterion_accuracy,
    compute_ground_truth_summary,
)

from .research_export import (
    export_calibration_runs_csv,
    export_advisories_csv,
    export_calibration_json,
    export_ec_ic_summary_json,
    export_drift_report_json,
    export_quality_metrics_json,
    export_full_calibration_export,
    export_advisories_csv_string,
)

__all__ = [
    # Models
    "AdvisoryStatus",
    "ALL_ADVISORY_STATUSES",
    "is_known_status",
    "AdvisoryDecision",
    "AdvisoryResult",
    "AdvisoryRequest",
    "CriterionEvaluation",
    "QueueItem",
    "QueueState",
    "AdvisoryConfig",
    "ValidationRouting",
    "AutonomyAssessment",
    "TopicRelevance",
    
    # Cache
    "get_advisory_cache",
    "get_advisory",
    "get_advisory_by_key",
    "get_ec_advisory",
    "get_ec_advisory_status",
    "get_qc_advisory",
    "get_qc_advisory_status",
    "has_advisory",
    "store_advisory",
    "get_advisory_status",
    "get_cache_stats",
    "list_cached_advisories",
    "validate_advisory_structure",
    
    # Queue
    "get_advisory_queue",
    "build_queue",
    "get_queue_stats",
    "reset_failed_advisories",
    
    # Worker
    "AdvisoryWorker",
    "run_worker",
    "generate_single_advisory",
    
    # Orchestrator
    "AdvisoryWorkerOrchestrator",
    "get_orchestrator",
    "initialize_advisory_pipeline",
    "get_advisory_pipeline_status",
    "start_background_generation",
    "is_advisory_generation_active",
    
    # Scheduler
    "AdvisoryScheduler",
    "get_advisory_scheduler",
    "set_active_stage",
    "get_active_stage",
    "should_process_stage",
    "get_worker_state",

    # Prefilter
    "PrefilterEngine",
    "PrefilterResult",
    "get_prefilter",

    # Stage Guard
    "validate_criteria_stage_isolation",
    "strip_contaminated_criteria",
    "quarantine_advisory",
    "get_stage_prefixes",
    "get_opposite_stage_prefixes",

    # Confidence & Autonomy
    "calibrate_confidence",
    "compute_risk_classification",
    "compute_evidence_strength",
    "compute_uncertainty_score",
    "assess_autonomy",
    "populate_risk_classification",
    "compute_metadata_completeness",

    # Telemetry Timeseries
    "TimeSeriesStore",
    "MetricSeries",
    "get_timeseries_store",
    "reset_timeseries_store",

    # Telemetry Aggregator
    "aggregate_decision_distribution",
    "aggregate_acceptance_rate",
    "aggregate_confidence_distribution",
    "aggregate_latency",
    "aggregate_retry_rate",
    "aggregate_429_rate",
    "aggregate_all",
    "aggregate_all_windows",

    # Telemetry Bus
    "TelemetryBus",
    "get_telemetry_bus",
    "reset_telemetry_bus",

    # Telemetry Clock
    "LogicalClock",
    "EventEnvelope",
    "stamp_event",
    "get_logical_clock",
    "reset_logical_clock",

    # Telemetry Reconciliation
    "ReconciliationEngine",
    "ReconciliationReport",
    "ReconciliationStore",
    "run_reconciliation",

    # Telemetry Backpressure
    "BackpressureController",
    "BackpressureState",
    "get_backpressure_controller",
    "reset_backpressure_controller",

    # Telemetry Consistency
    "ConsistencyChecker",
    "ConsistencyReport",
    "run_consistency_check",

    # Calibration Drift
    "jensen_shannon_divergence",
    "detect_decision_drift",
    "detect_confidence_drift",
    "detect_criteria_drift",
    "detect_drift",
    "IncrementalDriftTracker",

    # Advisory Quality Score
    "compute_confidence_calibration_score",
    "compute_grounding_quality_score",
    "compute_criterion_consistency_score",
    "compute_hallucination_risk_score",
    "compute_override_rate_score",
    "compute_quality_score",
    "LiveQualityTracker",

    # Replay System
    "ReplaySnapshot",
    "ReplayStore",
    "freeze_replay_snapshot",
    "compute_replay_session_id",
    "get_replay_store",
    "reset_replay_store",
    "TelemetryReplay",

    # Ground Truth Comparator
    "compute_confusion_matrix",
    "compute_per_criterion_accuracy",
    "compute_ground_truth_summary",

    # Transient Failures
    "is_transient_provider_error",
    "is_terminal_failure",
    "classify_failure",
    "classify_failure_semantic",
    "classify_failure_detailed",

    # Reliability
    "compute_advisory_reliability",
    "compute_reliability_components",
    "compute_batch_reliability",
    "check_escalation",
    "ThresholdCalibrator",
    "OperationalMetrics",
    "get_threshold_calibrator",
    "get_operational_metrics",

    # Research Export
    "export_calibration_runs_csv",
    "export_advisories_csv",
    "export_calibration_json",
    "export_ec_ic_summary_json",
    "export_drift_report_json",
    "export_quality_metrics_json",
    "export_full_calibration_export",
    "export_advisories_csv_string",
]