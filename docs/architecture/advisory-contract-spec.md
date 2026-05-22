# Canonical Advisory Contract Specification

## Schema Authority

`AdvisoryResult` is the **SOLE canonical advisory artifact**. All other surfaces
(`StructuredAdvisory`, cache, UI, stage guards, serializer) are secondary and
must conform to `AdvisoryResult`.

`StructuredAdvisory` is a **parser-output transient** — its fields are consumed
at generation time and normalized into `AdvisoryResult`. After normalization,
`StructuredAdvisory` has no further role.

---

## Canonical Field Registry

### Required Fields (must survive cache roundtrip, must be present at generation)

| Field | Type | Serialization | Validation | Replay-sensitive |
|-------|------|--------------|------------|-----------------|
| `cache_key` | str | `"cache_key"` | non-empty | YES |
| `protocol_version` | str | `"protocol_version"` | non-empty | YES |
| `decision` | AdvisoryDecision | `"decision"` enum value | known enum | YES |
| `confidence` | float | `"confidence"` | 0.0–1.0 | YES |
| `triggered_criteria` | List[str] | `"triggered_criteria"` | str list | YES |
| `non_triggered_criteria` | List[str] | `"non_triggered_criteria"` | str list | YES |
| `criterion_evaluations` | List[CriterionEvaluation] | `"criterion_evaluations"` structured | list of objects | YES |
| `justification` | str | `"justification"` | always str | YES |
| `error` | Optional[str] | `"error"` | None or non-empty | YES |
| `is_fallback` | bool | `"is_fallback"` | bool | YES |
| `is_placeholder` | bool | `"is_placeholder"` | bool | YES |

### Replay-Visible Fields (serialized, deterministic across runs)

| Field | Type | Owner | Notes |
|-------|------|-------|-------|
| `risk_classification` | RiskClassification enum | computed by `populate_risk_classification` | deterministic from inputs |
| `risk_reason` | str | computed | deterministic from inputs |
| `validation_queue` | ValidationQueue enum | computed | deterministic from inputs |
| `requires_validation` | bool | computed | deterministic from inputs |
| `grounding_evidence` | List[str] | computed by `validate_grounding` | deterministic |
| `criterion_grounding` | Dict[str, str] | computed by `validate_grounding` | deterministic |
| `grounding_strength` | float | computed | deterministic |
| `unsupported_claims_detected` | bool | computed | deterministic |
| `hallucination_risk_score` | float | computed | deterministic |
| `generated_at` | Optional[str] | system | Timestamp varies per run |
| `generation_duration_ms` | Optional[float] | system | Varies per run |
| `topic_relevance` | Optional[TopicRelevance] | computed | deterministic from inputs |
| `raw_confidence` | float | from LLM response | deterministic |
| `parser_confidence` | float | from LLM response | deterministic |
| `routing_confidence` | float | from LLM response | deterministic |
| `evidence_confidence` | float | from grounding | deterministic |
| `decision_confidence` | float | calibrated | deterministic |
| `calibration_provenance` | Dict | computed | deterministic |
| `prefilter_applied` | bool | from prefilter | deterministic |
| `prefilter_reason` | str | from prefilter | deterministic |
| `model_used` | str | from worker | deterministic |
| `stage_validation` | str | from stage guard | deterministic |

### Runtime-Only Fields (not replay-deterministic)

| Field | Type | Owner | Notes |
|-------|------|-------|-------|
| `evidence_span` | int | computed | Derived, not replayed |
| `metadata_fields_used` | List[str] | from worker | deterministic from inputs |
| `heuristic_contributions` | Dict | from worker | deterministic from inputs |
| `prompt_hash` | str | from LLM | deterministic |
| `routing_rationale` | str | built in worker | deterministic |

---

## Ownership Boundaries

| Responsibility | Owner |
|--------------|-------|
| Parsing LLM JSON → StructuredAdvisory | `llm_assistant.py` |
| StructuredAdvisory → AdvisoryResult | `advisory_worker.py` |
| Confidence calibration | `advisory_models.py:calibrate_confidence()` |
| Grounding validation | `advisory_models.py:validate_grounding()` |
| Stage isolation validation | `stage_guard.py:validate_criteria_stage_isolation()` |
| Cache persistence | `advisory_cache.py:AdvisoryCache` |
| UI consumption | `ec_screening_view.py` / `ic_screening_view.py` |

---

## Serialization Contract

### `to_dict()` guarantees
- Every canonical field maps to a JSON-safe value
- Enum types serialize via `.value`
- `None` fields serialize as JSON `null` (not omitted)
- Lists and dicts always produce empty containers, never `None`

### `from_dict()` guarantees
- Missing fields use deterministic defaults (never raise KeyError)
- Unknown fields silently ignored
- Enum deserialization failsafe → fallback to `UNAVAILABLE`
- `criterion_evaluations` dict deserializes each item defensively

---

## Validation Semantics

### StageGuard contract
INPUT: `(triggered_criteria, non_triggered_criteria, criterion_evaluations, stage)`
OUTPUT: `StageIsolationReport`
- `passed: bool` — true if no contamination
- `contaminated_criteria: List[str]` — list of violating criterion IDs
- `quarantined: bool` — true if contamination detected
- NEVER raises

### Cache validator contract
INPUT: any object
OUTPUT: `(bool, str, Optional[Dict])`
- `bool` = is valid AdvisoryResult instance
- `str` = error message (empty if valid)
- `Dict` = normalized form (None if invalid)

---

## Backward Compatibility Rules

1. Never remove a field from `AdvisoryResult` — mark deprecated instead
2. Never change a field's serialization key in `to_dict()` without adding the old key in `from_dict()` or providing a migration path
3. New fields must have safe defaults in `from_dict()` via `.get(key, default)`
4. Cache entries with missing fields must deserialize without error
5. Unknown fields in cached JSON must not cause deserialization errors

---

## Prohibited Behaviors

- Silent normalization of malformed advisories (must fail explicitly)
- Auto-healing of validation failures
- Suppressing errors by catching and ignoring
- Probabilistic validation
- Implicit type coercion of canonical fields
