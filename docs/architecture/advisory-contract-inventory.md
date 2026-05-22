# Advisory Contract Surface Inventory

## Surfaces Identified

| # | Surface | Location | Role | Consumes | Produces |
|---|---------|----------|------|----------|----------|
| S1 | `StructuredAdvisory` | `src/core/llm_assistant.py:160` | Parser output model | LLM JSON → normalized fields | Dict via `to_dict()` |
| S2 | `AdvisoryResult` | `src/advisory/advisory_models.py:766` | Canonical runtime model | Worker pipeline | Cache, UI, replay |
| S3 | `StageIsolationReport` | `src/advisory/stage_guard.py:44` | Validation output | StageGuard check | Validation result |
| S4 | `Cache validation` | `src/advisory/advisory_cache.py:84` | Structure validator | Any advisory | normalized dict |
| S5 | `Cache serialization` | `AdvisoryResult.to_dict/from_dict` | Persistence | AdvisoryResult | JSON on disk |
| S6 | `Worker plant` | `advisory_worker.py:812-846` | Generation plant | S1+S2 fields | AdvisoryResult |
| S7 | `EC view` | `ec_screening_view.py` | UI consumer | AdvisoryResult | HTML/st.markdown |
| S8 | `IC view` | `ic_screening_view.py` | UI consumer | AdvisoryResult | HTML/st.markdown |

---

## Field-by-Field Cross-Reference

### Fields present in BOTH StructuredAdvisory AND AdvisoryResult

| Field | S1 type | S2 type | Drift? |
|-------|---------|---------|--------|
| `confidence` | float (declared twice, 2nd=0.5 default) | float | Minor: S1 has duplicate declaration |
| `triggered_criteria` | `List[str]` | `List[str]` | Aligned |
| `justification` | `str` | `str` | Aligned |
| `is_fallback` | `bool` | `bool` | Aligned |
| `protocol_version` | `str` | `str` | Aligned |
| `grounding_evidence` | `List[str]` | `List[str]` | Aligned |
| `topic_relevance` | `Dict[str, float]` | `Optional[TopicRelevance]` | CONTAINER DRIFT: dict vs dataclass |

### Fields in StructuredAdvisory ONLY (S1 → no S2 counterpart)

| Field | S1 type | Consumed by? | Risk |
|-------|---------|-------------|------|
| `stage` | str | Cache validator (via getattr) | Low: getattr-guarded |
| `non_triggered_criteria` | `List[str]` | StageGuard, Cache validator | **CRITICAL**: S2 missing, runtime AttributeError |
| `reasoning_summary` | str | none | Low |
| `ambiguity_flags` | `List[str]` | none | Low |
| `evidence_extracts` | `List[str]` | none | Low |
| `uncertainty_reasoning` | str | none | Low |
| `domain_alignment_reasoning` | str | none | Low |
| `metadata_grounding` | `Dict` | none | Low |
| `fallback_reason` | str | none | Low |
| `advisory_hash` | str | none | Low |

### Fields in AdvisoryResult ONLY (S2 → no S1 counterpart)

| Field | S2 type | Consumed by? | Risk |
|-------|---------|-------------|------|
| `cache_key` | str | Cache (required) | Core |
| `decision` | `AdvisoryDecision` (enum) | Cache, UI, StageGuard | Core |
| `error` | `Optional[str]` | Cache, UI | Core |
| `is_placeholder` | bool | Cache | Low |
| `risk_classification` | `Optional[RiskClassification]` | UI | Core |
| `risk_reason` | str | UI | Core |
| `validation_queue` | `Optional[ValidationQueue]` | UI | Core |
| `requires_validation` | bool | UI | Core |
| `criterion_grounding` | `Dict[str, str]` | UI | Core |
| `grounding_strength` | float | UI, calibration | Core |
| `unsupported_claims_detected` | bool | calibration | Core |
| `hallucination_risk_score` | float | calibration | Core |
| `generated_at` | `Optional[str]` | Cache, UI | Core |
| `generation_duration_ms` | `Optional[float]` | telemetry | Low |
| `raw_confidence` | float | calibration | Core |
| `parser_confidence` | float | calibration | Low |
| `routing_confidence` | float | calibration | Low |
| `evidence_confidence` | float | calibration | Low |
| `decision_confidence` | float | calibration | Low |
| `calibration_provenance` | `Dict` | telemetry | Low |
| `evidence_span` | `List[str]` | UI, telemetry | MINOR: set as int in worker |
| `metadata_fields_used` | `List[str]` | UI | Low |
| `heuristic_contributions` | `Dict/List` | telemetry | Low |
| `prompt_hash` | str | telemetry | Low |
| `routing_rationale` | str | telemetry | Low |
| `stage_validation` | `Dict[str, Any]` (annotated) | Cache (get_status) | **DRIFT**: set as str in worker |
| `prefilter_applied` | bool | Cache, UI | Core |
| `prefilter_reason` | str | UI | Core |
| `model_used` | str | Cache | Low |

---

## Drift Analysis

### CRITICAL DRIFT #1 — `non_triggered_criteria` (S1 → S2 gap)
- `StructuredAdvisory` has it (from LLM parser)
- `AdvisoryResult` does NOT have it
- `stage_guard.validate_criteria_stage_isolation()` expects it as a parameter
- `advisory_worker.py:863` accesses `advisory.non_triggered_criteria` → **AttributeError**
- `advisory_cache.py:106` guards with `getattr(advisory, 'non_triggered_criteria', [])` — defensive but masking the gap

### CRITICAL DRIFT #2 — `validate_criteria_stage_isolation` return type misuse
- Function returns `StageIsolationReport` (a dataclass object)
- Worker code treats return value as list: `if stage_violations:` (truthy check on object) then `quarantine_advisory(advisory, stage_violations)` (passes object as string param)
- `quarantine_advisory(advisory, stage, reason)` → called with 2 instead of 3 positional args

### DRIFT #3 — `stage_validation` type annotation vs usage
- `AdvisoryResult.stage_validation: Dict[str, Any]` annotated as dict
- Worker sets it to string values: `"passed"` or `"QUARANTINED: ..."`
- Cache reads it as `str(stage_val)` — works but violates annotation

### DRIFT #4 — `evidence_span` type mismatch
- Annotated as `List[str]` but worker sets `evidence_span=len(evidence_snippets)` (int)
- This will cause `to_dict()` to serialize an int, but `from_dict` reads it as-is

### DRIFT #5 — `topic_relevance` container mismatch
- S1 uses `Dict[str, float]` with 4 keys
- S2 uses `Optional[TopicRelevance]` dataclass with 3 fields
- Worker bridges them manually (lines 796-800)

### MINOR — `quarantine_advisory` docstring/usage contract
- Defined as `(advisory, stage, reason)` — 3 positional params
- Called as `(advisory, stage_violations)` — 2 params, `stage_violations` is `StageIsolationReport`
- `stage_violations` gets passed as `stage`, `reason` not provided → TypeError

---

## Classification Summary

| Category | Count | Fields |
|----------|-------|--------|
| Canonical (must survive cache) | 22 | cache_key, protocol_version, decision, confidence, triggered_criteria, criterion_evaluations, justification, error, is_fallback, is_placeholder, risk_classification, risk_reason, validation_queue, requires_validation, grounding_evidence, criterion_grounding, grounding_strength, unsupported_claims_detected, hallucination_risk_score, generated_at, prefilter_applied, prefilter_reason |
| Optional (safe to omit) | 4 | generated_duration_ms, topic_relevance, model_used, prompt_hash |
| Runtime-only (not serialized) | 2 | generation_duration_ms (in to_dict), generated_at (serialized) |
| UI-only (derived) | 3 | evidence_span, metadata_fields_used, heuristic_contributions |
| Validation-critical | 3 | triggered_criteria, non_triggered_criteria, criterion_evaluations |
| Replay-critical | 18 | all canonical + cache_key + protocol_version |

---

## Identified Fixes Required

1. **Add `non_triggered_criteria: List[str]` to `AdvisoryResult`** — closes S1→S2 gap, fixes runtime AttributeError
2. **Fix `stage_validation` annotation** — change to `str` (not `Dict`) to match actual usage
3. **Fix `evidence_span` type** — change to `int` to match worker assignment
4. **Fix `validate_criteria_stage_isolation` call site** — extract `StageIsolationReport` properly, use `.contaminated_criteria` for quarantine
5. **Fix `quarantine_advisory` call** — pass `(advisory, stage, reason)` correctly
6. **Fix `stage_guard.py:validate_criteria_stage_isolation` return type** — document that it returns `StageIsolationReport`, not list
