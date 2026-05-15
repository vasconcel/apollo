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
    AdvisoryDecision,
    AdvisoryResult,
    AdvisoryRequest,
    CriterionEvaluation,
    QueueItem,
    QueueState,
    AdvisoryConfig
)

from .advisory_cache import (
    get_advisory_cache,
    get_advisory,
    get_advisory_by_key,
    get_ec_advisory,
    get_ec_advisory_status,
    has_advisory,
    store_advisory,
    get_advisory_status,
    get_cache_stats,
    list_cached_advisories
)

from .advisory_queue import (
    get_advisory_queue,
    build_queue,
    get_queue_stats,
    reset_failed_advisories
)

from .advisory_worker import (
    AdvisoryWorker,
    run_worker,
    generate_single_advisory
)

__all__ = [
    # Models
    "AdvisoryStatus",
    "AdvisoryDecision",
    "AdvisoryResult",
    "AdvisoryRequest",
    "CriterionEvaluation",
    "QueueItem",
    "QueueState",
    "AdvisoryConfig",
    
    # Cache
    "get_advisory_cache",
    "get_advisory",
    "get_advisory_by_key",
    "has_advisory",
    "store_advisory",
    "get_advisory_status",
    "get_cache_stats",
    "list_cached_advisories",
    
    # Queue
    "get_advisory_queue",
    "build_queue",
    "get_queue_stats",
    "reset_failed_advisories",
    
    # Worker
    "AdvisoryWorker",
    "run_worker",
    "generate_single_advisory"
]