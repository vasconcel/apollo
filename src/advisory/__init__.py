"""
APOLLO Advisory Pipeline

Offline, persisted, precomputed advisory generation.

This module provides:
- advisory_models: Typed dataclasses for advisories
- advisory_cache: Centralized cache layer (read-only for UI)
- advisory_queue: Queue management and progress tracking
- advisory_worker: Background generation pipeline
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

from .provider_controller import (
    ProviderState,
    ProviderController,
    get_provider_controller,
    reset_provider_controller,
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

    # Provider Controller
    "ProviderState",
    "ProviderController",
    "get_provider_controller",
    "reset_provider_controller",
]
