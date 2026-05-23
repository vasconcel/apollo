"""
Advisory worker pipeline for APOLLO.

This module provides:
- Background advisory generation
- Rate limiting and throttling
- Retry logic with exponential backoff
- Progress tracking and persistence
- Full observability and failure diagnostics

This is the ONLY module that should invoke LLM generation.
UI modules must NEVER call LLM directly.
"""

import os
import sys
import time
import random
import json
import re
import traceback
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading


VALID_STAGES = frozenset({"ec", "ic", "qc"})

from .advisory_models import safe_enum_value


def normalize_stage(stage: Any) -> str:
    """Centralized stage normalization - SINGLE SOURCE OF TRUTH."""
    if stage is None:
        return "ic"
    stage_str = str(stage).strip().lower()
    if stage_str not in VALID_STAGES:
        raise ValueError(f"Unsupported stage: '{stage}'. Must be one of: {', '.join(sorted(VALID_STAGES))}")
    return stage_str

def safe_preview(value: Any, limit: int = 500) -> str:
    """
    Safe debug serialization for arbitrary objects.
    NEVER raises - always returns a string.
    """
    if value is None:
        return "(None)"
    try:
        if isinstance(value, str):
            return value[:limit] if len(value) > limit else value
        if isinstance(value, dict):
            return json.dumps(value, default=str)[:limit]
        if isinstance(value, list):
            return json.dumps(value, default=str)[:limit]
        result = json.dumps(value, default=str, ensure_ascii=False)
        return result[:limit] if len(result) > limit else result
    except Exception:
        try:
            return str(value)[:limit]
        except Exception:
            return f"<unserializable: {type(value).__name__}>"


from .advisory_models import (
    AdvisoryResult,
    AdvisoryConfig,
    AdvisoryRequest,
    AdvisoryDecision,
    CriterionEvaluation,
    QueueItem,
    AdvisoryStatus,
    validate_grounding,
    compute_hallucination_risk,
    calibrate_confidence,
    compute_metadata_completeness,
    compute_evidence_strength,
    compute_uncertainty_score,
    assess_autonomy,
    TopicRelevance,
    populate_risk_classification,
    compute_calibration_provenance,
)
from .advisory_queue import get_advisory_queue
from .advisory_cache import get_advisory_cache, store_advisory
from .advisory_metrics import get_metrics
from .telemetry_bus import get_telemetry_bus


class AdvisoryFailureType(str, Enum):
    """Taxonomy of advisory generation failures."""
    INVALID_JSON = "INVALID_JSON"
    MISSING_FIELDS = "MISSING_FIELDS"
    INVALID_STATUS = "INVALID_STATUS"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    MARKDOWN_WRAPPED = "MARKDOWN_WRAPPED"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    RATE_LIMIT = "RATE_LIMIT"
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    PARSE_ERROR = "PARSE_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class AdvisoryParseResult:
    """Result of advisory parsing with full diagnostics."""
    success: bool
    failure_type: Optional[AdvisoryFailureType] = None
    failure_reason: str = ""
    raw_response: str = ""
    normalized_response: Dict[str, Any] = field(default_factory=dict)
    cache_key: str = ""
    article_id: str = ""
    protocol_version: str = "1.0"
    stage: str = "IC"
    timestamp: str = ""
    model_used: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


def _get_advisory_failure_log_path() -> Path:
    """Get path for advisory failure logs."""
    base_path = Path("data/logs/advisory_failures")
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path


def _persist_failure_artifact(parse_result: AdvisoryParseResult):
    """Persist failure artifact to disk for debugging."""
    try:
        log_path = _get_advisory_failure_log_path()
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"failure_{parse_result.article_id}_{timestamp}.json"
        filepath = log_path / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(parse_result.to_dict(), f, indent=2, ensure_ascii=False)

        print(f"  [PERSISTED] Failure artifact: {filepath.name}")
    except Exception as e:
        print(f"  [WARNING] Failed to persist failure artifact: {e}")


def _log_advisory_debug(parse_result: AdvisoryParseResult):
    """Log structured advisory debug information via telemetry."""
    status = "completed" if parse_result.success else "failed"
    get_telemetry_bus().record_info(
        f"advisory_generated article_id={parse_result.article_id} "
        f"stage={parse_result.stage} status={status} "
        f"model={parse_result.model_used or 'unknown'} "
        f"failure={safe_enum_value(parse_result.failure_type, 'none')}",
        component="worker",
        article_id=str(parse_result.article_id),
        stage=parse_result.stage,
        status=status,
    )


def normalize_suggestion_response(suggestion: Any) -> tuple[Dict[str, Any], Optional[AdvisoryFailureType], str]:
    """
    Normalize LLM response to ensure consistent dict structure.
    Handles all edge cases: raw string, markdown JSON, dict, malformed JSON.
    Returns: (normalized_dict, failure_type, failure_reason)
    """
    if suggestion is None:
        return _empty_suggestion_dict(), AdvisoryFailureType.EMPTY_RESPONSE, "Empty suggestion object"

    if isinstance(suggestion, dict):
        if not suggestion:
            return _empty_suggestion_dict(), AdvisoryFailureType.EMPTY_RESPONSE, "Empty dict suggestion"
        validation_result = _validate_response_schema(suggestion)
        return suggestion, validation_result[0], validation_result[1]

    if isinstance(suggestion, str):
        return _parse_string_response_with_diagnostics(suggestion)

    try:
        result = suggestion.to_dict()
        validation_result = _validate_response_schema(result)
        return result, validation_result[0], validation_result[1]
    except (AttributeError, TypeError) as e:
        return _empty_suggestion_dict(), AdvisoryFailureType.PARSE_ERROR, f"to_dict() failed: {str(e)}"


DECISION_NORMALIZATION_MAP = {
    "exclude": "EXCLUDE",
    "reject": "EXCLUDE",
    "rejected": "EXCLUDE",
    "no": "EXCLUDE",
    "out": "EXCLUDE",
    "include": "INCLUDE",
    "accept": "INCLUDE",
    "accepted": "INCLUDE",
    "yes": "INCLUDE",
    "in": "INCLUDE",
    "skip": "SKIP",
    "skipped": "SKIP",
    "uncertain": "UNCERTAIN",
    "unclear": "UNCERTAIN",
    "cannot determine": "UNCERTAIN",
    "cannot_determine": "UNCERTAIN",
    "insufficient evidence": "INSUFFICIENT_EVIDENCE",
    "insufficient_evidence": "INSUFFICIENT_EVIDENCE",
    "review": "UNAVAILABLE",
    "unavailable": "UNAVAILABLE",
}


def normalize_decision(decision_value: Any) -> str:
    """Normalize decision value to canonical enum string."""
    if decision_value is None:
        return "UNAVAILABLE"

    decision_str = str(decision_value).strip().lower()

    if decision_str in DECISION_NORMALIZATION_MAP:
        return DECISION_NORMALIZATION_MAP[decision_str]

    upper = decision_str.upper()
    if upper in VALID_DECISIONS:
        return upper

    return "UNAVAILABLE"


VALID_DECISIONS = frozenset({"INCLUDE", "EXCLUDE", "SKIP", "UNCERTAIN", "INSUFFICIENT_EVIDENCE", "CANNOT_DETERMINE", "UNAVAILABLE"})


def _validate_response_schema(response: Dict[str, Any]) -> tuple[Optional[AdvisoryFailureType], str]:
    """Validate response has required schema fields."""
    required_fields = ["decision", "confidence"]
    missing = [f for f in required_fields if f not in response]

    if missing:
        return AdvisoryFailureType.MISSING_FIELDS, f"Missing fields: {missing}"

    normalized_decision = normalize_decision(response.get("decision"))

    if normalized_decision not in VALID_DECISIONS:
        return AdvisoryFailureType.INVALID_STATUS, f"Invalid decision value: {response.get('decision')}"

    try:
        conf = float(response.get("confidence", 0))
        if not (0.0 <= conf <= 1.0):
            return AdvisoryFailureType.SCHEMA_MISMATCH, f"Confidence out of range: {conf}"
    except (ValueError, TypeError):
        return AdvisoryFailureType.SCHEMA_MISMATCH, "Confidence not a valid number"

    return None, ""


def _parse_string_response_with_diagnostics(content: str) -> tuple[Dict[str, Any], Optional[AdvisoryFailureType], str]:
    """Parse string response with robust fallback and diagnostics."""
    if not content or not content.strip():
        return _empty_suggestion_dict(), AdvisoryFailureType.EMPTY_RESPONSE, "Empty string response"

    original_content = content
    content = content.strip()

    is_markdown_wrapped = content.startswith("```") or content.startswith("```json")
    if is_markdown_wrapped:
        content_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
        if content_match:
            content = content_match.group(1).strip()

    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        json_str = json_match.group(0)
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                validation_result = _validate_response_schema(parsed)
                return parsed, validation_result[0], validation_result[1]
        except json.JSONDecodeError as e:
            pass

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            validation_result = _validate_response_schema(parsed)
            return parsed, validation_result[0], validation_result[1]
    except json.JSONDecodeError as e:
        failure_reason = f"JSON parse failed: {str(e)[:100]}"
        if is_markdown_wrapped:
            return _empty_suggestion_dict(), AdvisoryFailureType.MARKDOWN_WRAPPED, failure_reason
        return _empty_suggestion_dict(), AdvisoryFailureType.INVALID_JSON, failure_reason

    return {
        "decision": "UNAVAILABLE",
        "confidence": 0.0,
        "justification": f"Non-JSON response: {safe_preview(content, 100)}",
        "criterion_evaluations": {},
        "triggered_criteria": [],
        "raw_response": safe_preview(original_content, 500)
    }, AdvisoryFailureType.INVALID_JSON, "Could not parse as JSON"


def _empty_suggestion_dict() -> Dict[str, Any]:
    """Return empty suggestion structure."""
    return {
        "decision": "UNAVAILABLE",
        "confidence": 0.0,
        "justification": "Advisory generation failed",
        "criterion_evaluations": {},
        "triggered_criteria": [],
        "error": "Failed to parse LLM response"
    }


def safe_extract_criterion_evaluations(suggestion_dict: Dict[str, Any]) -> tuple:
    """
    Safely extract criterion evaluations from suggestion dict.
    Returns tuple of (criterion_evaluations_list, triggered_criteria)
    NEVER raises exception.
    """
    criterion_evaluations = []
    triggered_criteria = []

    try:
        eval_data = suggestion_dict.get("criterion_evaluations")
    except Exception:
        return [], []

    if eval_data is None:
        return [], []

    try:
        if isinstance(eval_data, dict):
            for cid, eval_obj in eval_data.items():
                if isinstance(eval_obj, dict):
                    criterion_evaluations.append(CriterionEvaluation(
                        criterion_id=eval_obj.get("criterion_id", cid),
                        criterion_name=eval_obj.get("criterion_name", cid),
                        satisfied=eval_obj.get("triggered", eval_obj.get("satisfied", False)),
                        evidence=eval_obj.get("evidence", []),
                        confidence=eval_obj.get("confidence", 0.0)
                    ))
                    if eval_obj.get("triggered", eval_obj.get("satisfied", False)):
                        triggered_criteria.append(cid)

        elif isinstance(eval_data, list):
            for item in eval_data:
                if isinstance(item, dict):
                    cid = item.get("criterion_id", item.get("criterion", ""))
                    criterion_evaluations.append(CriterionEvaluation(
                        criterion_id=cid,
                        criterion_name=cid,
                        satisfied=item.get("triggered", item.get("satisfied", False)),
                        evidence=item.get("evidence", []),
                        confidence=item.get("confidence", 0.0)
                    ))
                    if item.get("triggered", item.get("satisfied", False)):
                        triggered_criteria.append(cid)
    except Exception:
        pass

    return criterion_evaluations, triggered_criteria


class AdvisoryWorker:
    """
    Advisory generation worker.
    
    Processes queue items and generates advisories with:
    - Rate limiting
    - Exponential backoff
    - Retry logic
    - Progress persistence
    - Heartbeat tracking
    
    Protocol criteria are loaded from the protocol object passed at init
    or via set_protocol(). This eliminates the previous dependency on
    Streamlit UI modules for criteria retrieval.
    """
    
    def __init__(self, config: Optional[AdvisoryConfig] = None, protocol=None):
        self.config = config or AdvisoryConfig()
        self._llm = None
        self._protocol_criteria: Optional[Dict] = None
        self._protocol = protocol
        self._heartbeat_lock = threading.Lock()
        self._last_progress_at: float = 0.0
        self._last_provider_attempt_at: float = 0.0
        self._last_success_at: float = 0.0
    
    def _update_heartbeat(self, field: str):
        """Update a heartbeat timestamp under lock."""
        with self._heartbeat_lock:
            now = time.monotonic()
            if field == "progress":
                self._last_progress_at = now
            elif field == "provider_attempt":
                self._last_provider_attempt_at = now
            elif field == "success":
                self._last_success_at = now
                self._last_progress_at = now
    
    def get_heartbeat_stats(self) -> Dict:
        """Get frozen heartbeat timestamps for telemetry."""
        with self._heartbeat_lock:
            return {
                "last_progress_at": self._last_progress_at,
                "last_provider_attempt_at": self._last_provider_attempt_at,
                "last_success_at": self._last_success_at,
            }
    
    def set_protocol(self, protocol) -> None:
        """Set the protocol object for criteria retrieval."""
        self._protocol = protocol
        self._protocol_criteria = None
    
    @property
    def llm(self):
        """Lazy load LLM assistant."""
        if self._llm is None:
            try:
                from src.core.llm_assistant import get_llm_assistant
                self._llm = get_llm_assistant()
            except ImportError as e:
                print(f"Warning: LLM assistant not available: {e}")
                self._llm = None
        return self._llm
    
    PROCESSING_TIMEOUT_SECONDS = 120

    def process_item(
        self,
        item: QueueItem,
        queue: Optional["AdvisoryQueue"] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> AdvisoryResult:
        """
        Process a single queue item.

        Args:
            item: Queue item to process
            queue: Queue instance (preferred). If None, fetched from global registry.

        This is the main entry point for worker processing.
        GUARANTEES terminal state transition (COMPLETED or FAILED).
        """
        worker_stage = getattr(self, '_stage', 'ic')
        item_stage = getattr(item, 'stage', 'ic')

        print(f"[WORKER ITEM] WorkerStage: {worker_stage} | ItemStage: {item_stage} | Article: {item.article_id}")

        if worker_stage != item_stage:
            print(f"[DATA-PLANE VIOLATION] Worker stage={worker_stage} != Item stage={item_stage}")
            raise RuntimeError(f"DATA-PLANE ISOLATION VIOLATION: Worker stage '{worker_stage}' cannot process item with stage '{item_stage}'")

        stage = item_stage
        print(f"[QUEUE] Stage: {stage} | Article: {item.article_id}")

        if queue is None:
            from .advisory_queue import get_advisory_queue
            queue = get_advisory_queue(self.config, stage=stage)
        start_time = time.time()

        # Note: item is already in PROCESSING state via acquire_next() in process_all()
        print(f"[STATE] PROCESSING (acquired): {item.article_id} (stage={stage})")

        request = AdvisoryRequest(
            cache_key=item.cache_key,
            protocol_version=item.protocol_version,
            title=getattr(item, 'title', '') or '',
            abstract=getattr(item, 'abstract', '') or '',
            literature_type="WL",
            metadata={"article_id": item.article_id, "stage": stage}
        )

        try:
            bus = get_telemetry_bus()
            bus.record_item_started(stage, item.cache_key)

            advisory = self._generate_with_retry(request, stage, stop_event=stop_event)
            store_advisory(advisory, stage=stage)
            if stage.lower() == "qc":
                print(f"[QC CACHE STORE] Stage: qc | CacheKey: {item.cache_key[:16]}... | Decision: {safe_enum_value(advisory.decision)}")
            else:
                print(f"[CACHE STORE] Stage: {stage} | CacheKey: {item.cache_key[:16]}...")

            elapsed = time.time() - start_time
            bus.record_latency(stage, elapsed * 1000)
            bus.record_decision(stage, safe_enum_value(advisory.decision))
            bus.record_confidence(stage, advisory.confidence)
            bus.record_acceptance(stage, advisory.decision not in (
                AdvisoryDecision.EXCLUDE, AdvisoryDecision.SKIP, AdvisoryDecision.UNAVAILABLE
            ))
            if advisory.error:
                queue.mark_failed(item, advisory.error)
                bus.record_item_failed(stage, item.cache_key, advisory.error)
                print(f"[STATE] PROCESSING -> FAILED: {item.article_id} ({elapsed:.1f}s) Error: {advisory.error[:50]}")
            else:
                queue.mark_completed(item)
                bus.record_item_completed(stage, item.cache_key, safe_enum_value(advisory.decision))
                print(f"[STATE] PROCESSING -> COMPLETED: {item.article_id} ({elapsed:.1f}s) Decision: {safe_enum_value(advisory.decision)}")

            return advisory

        except Exception as e:
            elapsed = time.time() - start_time
            error_msg = f"Worker exception: {str(e)[:100]}"
            print(f"[STATE] PROCESSING -> FAILED: {item.article_id} ({elapsed:.1f}s) Exception: {error_msg}")

            failed_advisory = AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=AdvisoryDecision.UNAVAILABLE,
                confidence=0.0,
                justification=f"Worker exception: {str(e)}",
                error=error_msg,
                generated_at=datetime.now(timezone.utc).isoformat()
            )
            store_advisory(failed_advisory, stage=stage)
            queue.mark_failed(item, error_msg)

            return failed_advisory

        finally:
            elapsed = time.time() - start_time
            if elapsed > self.PROCESSING_TIMEOUT_SECONDS:
                print(f"[WATCHDOG] {item.article_id} processing exceeded {elapsed:.1f}s timeout")
    
    def _generate_with_retry(
        self,
        request: AdvisoryRequest,
        stage: str = "ic",
        stop_event: Optional[threading.Event] = None,
    ) -> AdvisoryResult:
        """Generate advisory via the LLM Gateway.

        Routes through the centralized governance layer which handles
        concurrency, rate limiting, circuit breaking, deduplication,
        and deterministic retry.

        Falls back to legacy retry if gateway is unavailable.
        """
        from .llm_gateway import get_llm_gateway, compute_article_hash

        def provider_call():
            """Inner callable: the actual LLM invocation (what gets retried)."""
            return self._generate_advisory(request, stage)

        try:
            self._update_heartbeat("provider_attempt")
            gateway = get_llm_gateway(self.config)
            article_hash = compute_article_hash(
                request.title, request.abstract, request.protocol_version
            )
            fp_key = None
            try:
                from .llm_gateway import compute_request_fingerprint
                stage_key = stage or getattr(request, 'stage', 'ic')
                fp_key = compute_request_fingerprint(
                    request.protocol_version, article_hash, stage_key
                )
            except Exception:
                pass

            result = gateway.generate_advisory(
                request=request,
                execute_fn=provider_call,
                provider="default",
                fingerprint=fp_key,
                cancel_event=stop_event,
            )
            self._update_heartbeat("success")
            self._update_heartbeat("progress")
            return result

        except Exception as e:
            print(f"[GATEWAY] Error: {e}, falling back to legacy retry")
            return self._legacy_generate_with_retry(request, stage, stop_event=stop_event)

    def _legacy_generate_with_retry(
        self,
        request: AdvisoryRequest,
        stage: str = "ic",
        stop_event: Optional[threading.Event] = None,
    ) -> AdvisoryResult:
        """Legacy retry logic (fallback if gateway is unavailable)."""
        bus = get_telemetry_bus()
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            if stop_event and stop_event.is_set():
                print(f"[LEGACY RETRY] Stop event set, aborting retry for {request.cache_key[:16]}...")
                break
            try:
                advisory = self._generate_advisory(request, stage)
                if advisory.error and "429" in advisory.error:
                    bus.record_429("groq")
                    if attempt < self.config.max_retries:
                        bus.record_retry(stage)
                        backoff = self._calculate_backoff(attempt)
                        print(f"Rate limited, retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.config.max_retries + 1})")
                        self._interruptible_sleep(backoff, stop_event)
                        continue
                return advisory
            except Exception as e:
                last_error = str(e)
                if attempt < self.config.max_retries:
                    bus.record_retry(stage)
                    backoff = self._calculate_backoff(attempt)
                    print(f"Error: {last_error}, retrying in {backoff:.1f}s")
                    self._interruptible_sleep(backoff, stop_event)
                else:
                    break
        return AdvisoryResult.create_failed(
            reason=last_error or "Max retries exceeded",
            cache_key=request.cache_key,
            protocol_version=request.protocol_version
        )
    
    def _generate_advisory(self, request: AdvisoryRequest, stage: str = "ic") -> AdvisoryResult:
        """Generate advisory from LLM with full observability."""
        start_time = time.time()
        article_id = request.metadata.get("article_id", "unknown") if request.metadata else "unknown"
        stage = stage or request.metadata.get("stage", "ic")
        stage_upper = stage.upper()

        if not self.llm:
            parse_result = AdvisoryParseResult(
                success=False,
                failure_type=AdvisoryFailureType.LLM_UNAVAILABLE,
                failure_reason="LLM assistant not initialized",
                raw_response="",
                normalized_response={},
                cache_key=request.cache_key,
                article_id=article_id,
                protocol_version=request.protocol_version,
                stage=stage,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            _log_advisory_debug(parse_result)
            _persist_failure_artifact(parse_result)

            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=AdvisoryDecision.UNAVAILABLE,
                confidence=0.0,
                justification="LLM not available",
                error="LLM_UNAVAILABLE: LLM assistant not initialized",
                generated_at=datetime.now(timezone.utc).isoformat(),
                hallucination_risk_score=1.0,
                grounding_strength=0.0,
                unsupported_claims_detected=True
            )

        if not self.llm.is_available():
            parse_result = AdvisoryParseResult(
                success=False,
                failure_type=AdvisoryFailureType.LLM_UNAVAILABLE,
                failure_reason="LLM service unavailable",
                raw_response="",
                normalized_response={},
                cache_key=request.cache_key,
                article_id=article_id,
                protocol_version=request.protocol_version,
                stage=stage,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            _log_advisory_debug(parse_result)
            _persist_failure_artifact(parse_result)

            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=AdvisoryDecision.UNAVAILABLE,
                confidence=0.0,
                justification="LLM service unavailable",
                error="LLM_UNAVAILABLE: LLM not available",
                generated_at=datetime.now(timezone.utc).isoformat(),
                hallucination_risk_score=1.0,
                grounding_strength=0.0,
                unsupported_claims_detected=True
            )

        if self._protocol_criteria is None:
            self._protocol_criteria = self._load_protocol_criteria()

        title = request.title
        abstract = request.abstract
        literature_type = request.literature_type
        metadata = request.metadata

        stage_lower = normalize_stage(stage)
        print(f"[WORKER] Stage: {stage_lower}")

        raw_response = ""
        model_used = "llama-3.3-70b-versatile"

        prefilter_result = None
        try:
            from .prefilter import get_prefilter
            prefilter_result = get_prefilter(stage=stage_lower).check(title, abstract)
        except Exception:
            pass

        if prefilter_result and prefilter_result.is_reject:
            print(f"[PREFILTER] Rejected {article_id}: {prefilter_result.reason_key}")
            decision_str = prefilter_result.decision
            try:
                decision = AdvisoryDecision(decision_str)
            except ValueError:
                decision = AdvisoryDecision.EXCLUDE
            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=decision,
                confidence=prefilter_result.confidence,
                justification=prefilter_result.reason,
                generated_at=datetime.now(timezone.utc).isoformat(),
                generation_duration_ms=prefilter_result.elapsed_ms,
                grounding_evidence=[],
                grounding_strength=1.0,
                hallucination_risk_score=0.0,
                prefilter_applied=True,
                prefilter_reason=prefilter_result.reason_key,
                model_used="prefilter",
            )

        prompt_hash = ""
        try:
            if hasattr(self.llm, '_last_prompt_hash'):
                prompt_hash = self.llm._last_prompt_hash
        except Exception:
            pass

        try:
            if stage_lower == "ec":
                from src.core.llm_assistant import LLMAssistant
                if hasattr(self.llm, 'suggest_ec'):
                    suggestion = self.llm.suggest_ec(
                        title=title,
                        abstract=abstract,
                        literature_type=literature_type,
                        protocol_criteria=self._protocol_criteria,
                        metadata=metadata
                    )
                else:
                    suggestion = self.llm.suggest(
                        title=title,
                        abstract=abstract,
                        literature_type=literature_type,
                        stage="ec",
                        protocol_criteria=self._protocol_criteria,
                        metadata=metadata
                    )
            elif stage_lower == "ic":
                from src.core.llm_assistant import LLMAssistant
                if hasattr(self.llm, 'suggest_ic'):
                    suggestion = self.llm.suggest_ic(
                        title=title,
                        abstract=abstract,
                        literature_type=literature_type,
                        protocol_criteria=self._protocol_criteria,
                        metadata=metadata
                    )
                else:
                    suggestion = self.llm.suggest(
                        title=title,
                        abstract=abstract,
                        literature_type=literature_type,
                        stage="ic",
                        protocol_criteria=self._protocol_criteria,
                        metadata=metadata
                    )
            elif stage_lower == "qc":
                print(f"[QC ADVISORY GENERATION] Article: {article_id}")
                if hasattr(self.llm, 'suggest_qc'):
                    suggestion = self.llm.suggest_qc(
                        title=title,
                        abstract=abstract,
                        literature_type=literature_type,
                        protocol_criteria=self._load_protocol_criteria_qc(),
                        metadata=metadata
                    )
                else:
                    suggestion = self.llm.suggest(
                        title=title,
                        abstract=abstract,
                        literature_type=literature_type,
                        stage="qc",
                        metadata=metadata
                    )
            else:
                raise ValueError(f"Unsupported stage for advisory generation: {stage}. Must be 'ec', 'ic', or 'qc'.")

            try:
                raw_response = safe_preview(suggestion, 1000)
            except Exception as e:
                raw_response = f"<serialization_failed: {e}>"

            suggestion_dict, failure_type, failure_reason = normalize_suggestion_response(suggestion)

            normalized_decision = normalize_decision(suggestion_dict.get("decision", "UNAVAILABLE"))
            is_success = failure_type is None and normalized_decision != "UNAVAILABLE"

            parse_result = AdvisoryParseResult(
                success=is_success,
                failure_type=failure_type,
                failure_reason=failure_reason,
                raw_response=raw_response,
                normalized_response=suggestion_dict,
                cache_key=request.cache_key,
                article_id=article_id,
                protocol_version=request.protocol_version,
                stage=stage,
                timestamp=datetime.now(timezone.utc).isoformat(),
                model_used=model_used
            )
            _log_advisory_debug(parse_result)

            if not is_success:
                _persist_failure_artifact(parse_result)

            criterion_evaluations, triggered_criteria = safe_extract_criterion_evaluations(suggestion_dict)

            decision_str = normalize_decision(suggestion_dict.get("decision", "UNAVAILABLE"))
            try:
                decision = AdvisoryDecision(decision_str)
            except ValueError:
                decision = AdvisoryDecision.UNAVAILABLE

            duration_ms = (time.time() - start_time) * 1000

            parse_error = suggestion_dict.get("error")
            if failure_type:
                parse_error = f"{safe_enum_value(failure_type)}: {failure_reason}" if failure_reason else safe_enum_value(failure_type)

            error_msg = parse_error or (f"FAILED: {safe_enum_value(failure_type)}" if failure_type else None)

            justification = suggestion_dict.get("justification", "")
            grounding_strength, evidence_snippets, criterion_grounding, unsupported_detected = validate_grounding(
                justification=justification,
                title=title,
                abstract=abstract or "",
                criterion_evaluations=criterion_evaluations,
                metadata=metadata
            )

            raw_confidence = suggestion_dict.get("confidence", 0.0)

            metadata_completeness = 0.0
            if metadata:
                fields_present = sum(1 for v in metadata.values() if v)
                metadata_completeness = min(fields_present / 10.0, 1.0)

            has_evidence = bool(evidence_snippets) or bool(criterion_grounding)
            has_triggered_criteria = bool(triggered_criteria)

            calibrated_confidence = calibrate_confidence(
                base_confidence=raw_confidence,
                metadata_completeness=metadata_completeness,
                grounding_strength=grounding_strength,
                has_evidence=has_evidence,
                has_triggered_criteria=has_triggered_criteria
            )

            if calibrated_confidence < 0.5 and decision == AdvisoryDecision.INCLUDE:
                decision = AdvisoryDecision.UNCERTAIN

            hallucination_risk = compute_hallucination_risk(
                is_fallback=False,
                grounding_strength=grounding_strength,
                unsupported_claims=unsupported_detected,
                confidence=calibrated_confidence,
                metadata_completeness=metadata_completeness,
                error=error_msg
            )

            topic_relevance = TopicRelevance(
                domain_relevance_score=suggestion_dict.get("domain_relevance_score", 0.0),
                topical_alignment=suggestion_dict.get("topical_alignment", 0.0),
                rq_alignment_strength=suggestion_dict.get("rq_alignment_strength", 0.0)
            )

            calibration_provenance = compute_calibration_provenance(
                raw_confidence=raw_confidence,
                final_confidence=calibrated_confidence,
                grounding_strength=grounding_strength,
                metadata_completeness=metadata_completeness,
                has_evidence=has_evidence,
                has_triggered_criteria=has_triggered_criteria,
                decision=safe_enum_value(decision) if decision else "",
            )

            advisory = AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=decision,
                confidence=calibrated_confidence,
                raw_confidence=raw_confidence,
                parser_confidence=raw_confidence,
                routing_confidence=raw_confidence,
                evidence_confidence=grounding_strength,
                decision_confidence=calibrated_confidence,
                calibration_provenance=calibration_provenance,
                triggered_criteria=triggered_criteria,
                criterion_evaluations=criterion_evaluations,
                justification=justification,
                error=error_msg,
                generated_at=datetime.now(timezone.utc).isoformat(),
                generation_duration_ms=duration_ms,
                grounding_evidence=evidence_snippets,
                criterion_grounding=criterion_grounding,
                grounding_strength=grounding_strength,
                unsupported_claims_detected=unsupported_detected,
                hallucination_risk_score=hallucination_risk,
                topic_relevance=topic_relevance,
                evidence_span=len(evidence_snippets) if evidence_snippets else 0,
                metadata_fields_used={
                    k: True for k in (metadata or {}) if metadata.get(k)
                },
                heuristic_contributions=[],
                prompt_hash=prompt_hash,
                routing_rationale=f"stage={stage_lower}, decision={safe_enum_value(decision)}, confidence={calibrated_confidence:.2f}",
                stage_validation="passed",
                prefilter_applied=False,
                prefilter_reason="",
                model_used=model_used,
            )

            ambiguity_detected = decision in (
                AdvisoryDecision.UNCERTAIN,
                AdvisoryDecision.INSUFFICIENT_EVIDENCE,
                AdvisoryDecision.CANNOT_DETERMINE,
            ) or hallucination_risk > 0.5

            populate_risk_classification(
                advisory=advisory,
                metadata_completeness=metadata_completeness,
                criterion_grounding_score=grounding_strength,
                ambiguity_detected=ambiguity_detected,
            )

            try:
                from .stage_guard import validate_criteria_stage_isolation, quarantine_advisory
                isolation_report = validate_criteria_stage_isolation(
                    advisory.triggered_criteria or [],
                    advisory.non_triggered_criteria or [],
                    advisory.criterion_evaluations or [],
                    stage_lower
                )
                if not isolation_report.passed:
                    advisory = quarantine_advisory(
                        advisory,
                        isolation_report.stage,
                        "; ".join(isolation_report.contaminated_criteria)
                    )
                    advisory.stage_validation = (
                        f"QUARANTINED: {'; '.join(isolation_report.contaminated_criteria)}"
                    )
                    print(f"[STAGE_GUARD] Quarantined {article_id}: {isolation_report.contaminated_criteria}")
                else:
                    advisory.stage_validation = "passed"
            except Exception as e:
                print(f"[STAGE_GUARD] Validation error for {article_id}: {e}")

            try:
                from .advisory_models import check_methodological_safeguards, check_criterion_hallucination
                safeguards = check_methodological_safeguards(advisory)
                if safeguards:
                    print(f"[SAFEGUARD] Warnings for {article_id}: {safeguards}")
                criterion_warnings = check_criterion_hallucination(
                    triggered_criteria, justification, title, abstract or ""
                )
                if criterion_warnings:
                    print(f"[SAFEGUARD] Criterion warnings for {article_id}: {criterion_warnings}")
            except Exception as e:
                print(f"[SAFEGUARD] Check error for {article_id}: {e}")

            duration_ms = (time.time() - start_time) * 1000
            get_metrics().record_worker_latency(duration_ms)
            return advisory

        except Exception as e:
            tb = traceback.format_exc()
            parse_result = AdvisoryParseResult(
                success=False,
                failure_type=AdvisoryFailureType.UNKNOWN,
                failure_reason=f"Exception: {str(e)}",
                raw_response=safe_preview(raw_response, 500) if raw_response else "",
                normalized_response={},
                cache_key=request.cache_key,
                article_id=article_id,
                protocol_version=request.protocol_version,
                stage=stage,
                timestamp=datetime.now(timezone.utc).isoformat(),
                model_used=model_used
            )
            _log_advisory_debug(parse_result)
            _persist_failure_artifact(parse_result)

            return AdvisoryResult(
                cache_key=request.cache_key,
                protocol_version=request.protocol_version,
                decision=AdvisoryDecision.UNAVAILABLE,
                confidence=0.0,
                justification=f"Generation failed: {str(e)}",
                error=f"UNKNOWN: {str(e)}",
                generated_at=datetime.now(timezone.utc).isoformat(),
                hallucination_risk_score=1.0,
                grounding_strength=0.0,
                unsupported_claims_detected=True
            )
    
    @staticmethod
    def _interruptible_sleep(duration: float, cancel_event: Optional[threading.Event] = None):
        """Sleep for `duration` seconds, waking early if cancel_event is set."""
        if cancel_event is None:
            time.sleep(duration)
            return
        deadline = time.time() + duration
        while time.time() < deadline:
            if cancel_event.is_set():
                return
            remaining = deadline - time.time()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.1))

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter."""
        base_backoff = self.config.backoff_base ** attempt
        capped_backoff = min(base_backoff, self.config.backoff_max)
        
        jitter_range = capped_backoff * self.config.jitter
        jitter = random.uniform(-jitter_range, jitter_range)
        
        return max(0.1, capped_backoff + jitter)
    
    def _load_protocol_criteria(self) -> Dict[str, str]:
        """Load IC protocol criteria via protocol query service."""
        try:
            from src.core.protocol_query_service import get_ic_criteria
            return get_ic_criteria(self._protocol)
        except ImportError:
            return {}
    
    def _load_protocol_criteria_qc(self) -> Dict[str, str]:
        """Load QC protocol criteria via protocol query service - MUST be independent from IC."""
        try:
            from src.core.protocol_query_service import get_qc_criteria
            return get_qc_criteria(self._protocol)
        except ImportError:
            return {
                "QC1": "Quality assessment criteria",
                "QC2": "Methodological rigor assessment"
            }
    
    def process_all(self, max_items: Optional[int] = None, stage: str = "ic", stop_event: Optional[threading.Event] = None) -> Dict:
        """
        Process all pending queue items.

        Args:
            max_items: Maximum items to process (None for all)
            stage: Advisory stage for queue access
            stop_event: Optional event to signal early termination

        Returns:
            Processing summary
        """
        bus = get_telemetry_bus()
        print(f"[WORKER PROCESS_ALL] Stage: {stage}")
        self._stage = stage
        metrics = get_metrics()
        
        try:
            from src.advisory.advisory_scheduler import get_advisory_scheduler, should_process_stage
            
            scheduler = get_advisory_scheduler()
            scheduler_status = scheduler.get_status()
            print(f"[WORKER PRIORITY] Active stage: {scheduler_status['active_stage']} | Worker states: {scheduler_status['worker_states']}")
            
            if not should_process_stage(stage):
                print(f"[WORKER PRIORITY] Stage '{stage}' paused - active stage is '{scheduler_status['active_stage']}'")
                return {
                    "processed": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "remaining": 0,
                    "status": "PAUSED",
                    "active_stage": scheduler_status['active_stage']
                }
        except ImportError:
            pass
        
        queue = get_advisory_queue(self.config, stage=stage)
        
        processed = 0
        succeeded = 0
        failed = 0
        
        while True:
            if stop_event and stop_event.is_set():
                print(f"[WORKER STOP] Stop event signaled for stage: {stage}")
                metrics.worker_stop_count += 1
                break

            item = queue.acquire_next()
            if item is None:
                metrics.worker_idle_cycles += 1
                break
            
            if max_items is not None and processed >= max_items:
                break
            
            try:
                from src.advisory.advisory_scheduler import should_process_stage, get_advisory_scheduler
                if not should_process_stage(stage):
                    print(f"[WORKER PRIORITY CHECK] Stage '{stage}' no longer active - pausing")
                    break
            except ImportError:
                pass
            
            print(f"Processing: {item.article_id} ({item.cache_key[:8]}...)")
            
            result = self.process_item(item, queue=queue, stop_event=stop_event)
            processed += 1
            
            if result.error:
                failed += 1
                metrics.worker_failure_count += 1
                print(f"  Failed: {result.error}")
            else:
                succeeded += 1
                metrics.worker_generation_count += 1
                from src.advisory.advisory_reliability import get_operational_metrics, get_threshold_calibrator
                ops = get_operational_metrics()
                ops.record_processed(latency_ms=getattr(result, 'generation_duration_ms', 0.0) or 0.0)
                ops.record_queue_depth(queue.get_stats().get("pending", 0))
                print(f"  Success: {safe_enum_value(result.decision)} ({result.confidence:.2f})")
            
            if processed < (max_items or float('inf')):
                sleep_time = self.config.sleep_seconds
                self._interruptible_sleep(sleep_time, stop_event)
        
        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "remaining": queue.state.pending,
            "status": "COMPLETED" if processed > 0 else "IDLE"
        }
    
    def process_single(
        self,
        title: str,
        abstract: str,
        protocol_version: str = "1.0"
    ) -> AdvisoryResult:
        """
        Process a single article (standalone, not from queue).
        
        Useful for testing or on-demand generation.
        """
        cache = get_advisory_cache(self.config)
        cache_key = cache.compute_cache_key(title, abstract, protocol_version)
        
        if cache.has(cache_key, protocol_version):
            return cache.get(cache_key, protocol_version)
        
        request = AdvisoryRequest(
            cache_key=cache_key,
            protocol_version=protocol_version,
            title=title,
            abstract=abstract,
            literature_type="WL"
        )
        
        advisory = self._generate_with_retry(request)
        store_advisory(advisory)
        
        return advisory


def run_worker(
    max_items: Optional[int] = None,
    config: Optional[AdvisoryConfig] = None
) -> Dict:
    """
    Run advisory worker.
    
    Entry point for CLI: python advisory_worker.py
    """
    worker = AdvisoryWorker(config)
    return worker.process_all(max_items)


def generate_single_advisory(
    title: str,
    abstract: str,
    protocol_version: str = "1.0"
) -> AdvisoryResult:
    """
    Generate advisory for single article.
    
    Entry point for on-demand generation.
    """
    worker = AdvisoryWorker()
    return worker.process_single(title, abstract, protocol_version)


if __name__ == "__main__":
    max_items = None
    if len(sys.argv) > 1:
        try:
            max_items = int(sys.argv[1])
        except ValueError:
            pass
    
    print("=" * 60)
    print("APOLLO Advisory Worker")
    print("=" * 60)
    
    result = run_worker(max_items)
    
    print("=" * 60)
    print(f"Processing complete:")
    print(f"  Processed: {result['processed']}")
    print(f"  Succeeded: {result['succeeded']}")
    print(f"  Failed: {result['failed']}")
    print(f"  Remaining: {result['remaining']}")
    print("=" * 60)