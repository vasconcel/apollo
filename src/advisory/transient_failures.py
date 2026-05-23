"""
Transient vs terminal failure classification for APOLLO.

Deterministic classification of runtime errors to determine whether
a failure should:
- Remain inside retry/backoff flow (TRANSIENT)
- Escalate to pipeline reset (TERMINAL)
- Escalate but not reset (UNKNOWN)

Transient provider failures must NEVER invalidate:
- queue state
- orchestrator lifecycle
- worker ownership
- calibration execution state

Provider instability is NOT a pipeline failure.

Failure Taxonomy (Part 6):
  - provider_failure: 429, rate limit, cooldown, upstream errors
  - parsing_failure: JSON decode, schema mismatch, missing fields
  - validation_failure: invariant violation, stage guard violation
  - timeout_failure: connection timeout, deadline exceeded, total retry timeout
  - circuit_breaker_failure: provider in cooldown, unavailable
  - queue_failure: corrupted WAL, corrupted snapshot, data-plane isolation
"""
from typing import Optional


# Patterns matching transient provider failures
_TRANSIENT_PATTERNS = (
    "429",
    "rate limit",
    "rate_limit",
    "too many requests",
    "connection timeout",
    "connect timeout",
    "connection refused",
    "connection reset",
    "temporarily unavailable",
    "service unavailable",
    "server error",
    "5xx",
    "502",
    "503",
    "504",
    "gateway timeout",
    "upstream",
    "deadline exceeded",
    "context deadline",
    "i/o timeout",
    "dns lookup",
    "name resolution",
    "temporary failure",
    "throttl",
    "capacity exceeded",
    "quota exceeded",
    "retryable",
    "retry later",
    "try again",
    "backoff",
    "cooldown",
    "PROVIDER_COOLDOWN",
    "Provider .* in COOLDOWN",
    "Concurrency slot timeout",
    "Rate limit timeout",
    "LLM_UNAVAILABLE",
    "network is unreachable",
    "no route to host",
    "connection aborted",
)

# Patterns matching terminal (non-retryable) pipeline failures
_TERMINAL_PATTERNS = (
    "corrupted queue",
    "corrupted snapshot",
    "invalid protocol",
    "invariant violation",
    "data-plane",
    "DATA-PLANE ISOLATION VIOLATION",
    "unrecoverable",
    "fatal",
    "stage mismatch",
    "Queue contains invalid",
)

# Patterns for semantic failure categories
_PARSING_PATTERNS = (
    "JSONDecodeError",
    "INVALID_JSON",
    "MISSING_FIELDS",
    "INVALID_STATUS",
    "EMPTY_RESPONSE",
    "SCHEMA_MISMATCH",
    "PARSE_ERROR",
    "parse_error",
    "normalize_suggestion_response",
    "to_dict() failed",
    "Expected value",
    "Extra data",
    "Unterminated string",
    "Expecting value",
)

_VALIDATION_PATTERNS = (
    "invariant violation",
    "stage guard",
    "QUARANTINED",
    "contaminated",
    "stage_validation",
    "cannot process item with stage",
)

_TIMEOUT_PATTERNS = (
    "deadline exceeded",
    "context deadline",
    "i/o timeout",
    "connection timeout",
    "timeout",
    "Timed out",
    "Retry total timeout exceeded",
    "Concurrency slot timeout",
    "Rate limit timeout",
    "PROCESSING_TIMEOUT",
)

_CIRCUIT_BREAKER_PATTERNS = (
    " is UNAVAILABLE",
    " in COOLDOWN",
    "circuit breaker",
    "Provider .* is UNAVAILABLE",
    "Provider .* in COOLDOWN",
)

_QUEUE_PATTERNS = (
    "corrupted queue",
    "corrupted snapshot",
    "WAL replay",
    "malformed_wal",
    "DATA-PLANE ISOLATION VIOLATION",
)


def is_transient_provider_error(error_str: Optional[str]) -> bool:
    """Check if an error string represents a transient provider failure.

    Transient failures can be retried and must not trigger pipeline resets.

    Args:
        error_str: Error message from exception or advisory.

    Returns:
        True if the error is transient, False otherwise.
    """
    if not error_str:
        return False
    lower = error_str.lower()
    for pattern in _TRANSIENT_PATTERNS:
        if pattern.lower() in lower:
            return True
    return False


def is_terminal_failure(error_str: Optional[str]) -> bool:
    """Check if an error string represents a terminal pipeline failure.

    Terminal failures require pipeline reset and cannot be retried.

    Args:
        error_str: Error message from exception or advisory.

    Returns:
        True if the error is terminal, False otherwise.
    """
    if not error_str:
        return False
    lower = error_str.lower()
    for pattern in _TERMINAL_PATTERNS:
        if pattern.lower() in lower:
            return True
    return False


def classify_failure(error_str: Optional[str]) -> str:
    """Classify a failure as transient, terminal, or unknown.

    Args:
        error_str: Error message to classify.

    Returns:
        "transient", "terminal", or "unknown".
    """
    if error_str is None:
        return "unknown"
    if is_transient_provider_error(error_str):
        return "transient"
    if is_terminal_failure(error_str):
        return "terminal"
    return "unknown"


def classify_failure_semantic(error_str: Optional[str]) -> str:
    """Classify a failure into a semantic category.

    Returns one of:
      - provider_failure
      - parsing_failure
      - validation_failure
      - timeout_failure
      - circuit_breaker_failure
      - queue_failure
      - unknown

    Deterministic: same input -> same category.
    """
    if not error_str:
        return "unknown"

    lower = error_str.lower()
    error_upper = error_str.upper()

    # Check circuit breaker first (these are explicit state checks)
    for pattern in _CIRCUIT_BREAKER_PATTERNS:
        if pattern.lower() in lower or pattern.upper() in error_upper:
            return "circuit_breaker_failure"

    # Check validation failures
    for pattern in _VALIDATION_PATTERNS:
        if pattern.lower() in lower:
            return "validation_failure"

    # Check timeout failures
    for pattern in _TIMEOUT_PATTERNS:
        if pattern.lower() in lower:
            return "timeout_failure"

    # Check queue failures
    for pattern in _QUEUE_PATTERNS:
        if pattern.lower() in lower:
            return "queue_failure"

    # Check parsing failures
    for pattern in _PARSING_PATTERNS:
        if pattern.lower() in lower:
            return "parsing_failure"

    # Check provider failures (after circuit breaker, timeout)
    for pattern in _TRANSIENT_PATTERNS:
        if pattern.lower() in lower:
            return "provider_failure"

    return "unknown"


def classify_failure_detailed(error_str: Optional[str]) -> dict:
    """Full failure classification with all categories.

    Args:
        error_str: Error message to classify.

    Returns:
        Dict with failure_class, failure_category, is_transient, is_terminal.
    """
    category = classify_failure_semantic(error_str)
    fclass = classify_failure(error_str)
    return {
        "failure_class": fclass,
        "failure_category": category,
        "is_transient": fclass == "transient",
        "is_terminal": fclass == "terminal",
    }
