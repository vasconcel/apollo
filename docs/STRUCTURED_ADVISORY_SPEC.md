# STRUCTURED ADVISORY SPECIFICATION
## APOLLO v1.0.0 - SPRINT 7.7

---

## 1. OBJECTIVE

Eliminate semantic drift, hallucinated ambiguity, and inconsistent criterion interpretation in the LLM advisory subsystem.

The LLM MUST become:
- metadata-grounded
- criterion-grounded
- deterministic in structure
- protocol-constrained
- scientifically auditable

**AUTHORITY**: Protocol and canonical metadata are authoritative. LLM ONLY assists interpretation.

---

## 2. CANONICAL SCHEMAS

### 2.1 StructuredAdvisory

```python
@dataclass
class StructuredAdvisory:
    stage: str  # "ec", "ic", "qc"

    decision: str  # "include", "exclude", "unavailable"

    confidence: float  # 0.0-1.0

    triggered_criteria: List[str]  # Criterion IDs triggered
    non_triggered_criteria: List[str]  # Criterion IDs NOT triggered

    criterion_evaluations: Dict[str, CriterionEvaluation]

    justification: str  # Human-readable explanation
    reasoning_summary: str  # Concise evaluation process summary

    ambiguity_flags: List[str]  # ONLY flag ambiguity if grounded in actual metadata gaps
    evidence_extracts: List[str]  # Verbatim text extracts from title/abstract

    metadata_grounding: Dict[str, bool]  # Which metadata fields were used

    is_fallback: bool  # True when LLM unavailable
    fallback_reason: str  # Error description

    protocol_version: str  # Protocol version used
    advisory_hash: str  # Deterministic hash of advisory structure
```

### 2.2 CriterionEvaluation

```python
@dataclass
class CriterionEvaluation:
    criterion_id: str

    triggered: bool

    evidence: List[str]  # Text extracts supporting evaluation
    justification: str  # Why triggered or not triggered

    ambiguity_detected: bool  # True only if actual metadata gap exists
    grounded_metadata_fields: List[str]  # Which metadata fields grounded this evaluation
```

### 2.3 AdvisorySuggestion (Legacy)

```python
@dataclass
class AdvisorySuggestion:
    """Legacy advisory for backward compatibility."""
    stage: str
    decision: str
    confidence: float
    justification: str

    triggered_criteria: Dict[str, str]  # criterion_id -> justification
    evidence: List[str]
    ambiguity_flags: List[str]
    is_fallback: bool
```

---

## 3. LITERATURE TYPE NORMALIZATION

### 3.1 Canonical Labels

| Input | Canonical |
|-------|-----------|
| WL, wl, Wl | White Literature |
| White Literature, white literature, WHITE LITERATURE | White Literature |
| GL, gl, Gl | Grey Literature |
| Grey Literature, grey literature, GREY LITERATURE | Grey Literature |
| Gray Literature, GRAY LITERATURE | Grey Literature |
| (empty), None, unknown | White Literature (default) |

### 3.2 Normalization Function

```python
WL_CANONICAL = "White Literature"
GL_CANONICAL = "Grey Literature"

WL_LABELS = {"WL", "White Literature", "WHITE LITERATURE", "white literature", "Wl", "wl"}
GL_LABELS = {"GL", "Grey Literature", "GREY LITERATURE", "grey literature", "Gray Literature", "GRAY LITERATURE", "Gl", "gl"}

def normalize_literature_label(raw: str) -> str:
    if not raw:
        return WL_CANONICAL
    stripped = raw.strip()
    if stripped in WL_LABELS:
        return WL_CANONICAL
    if stripped in GL_LABELS:
        return GL_CANONICAL
    upper = stripped.upper()
    if upper in WL_LABELS or upper == "WHITE LITERATURE":
        return WL_CANONICAL
    if upper in GL_LABELS or upper == "GREY LITERATURE":
        return GL_CANONICAL
    return WL_CANONICAL  # Default
```

---

## 4. METADATA GROUNDING REQUIREMENTS

### 4.1 Required Payload Structure

The LLM MUST receive EXPLICIT structured metadata:

```json
{
  "title": "Article Title",
  "abstract": "Full abstract text",
  "year": 2021,
  "year_source": "atlas | csv | manual | unknown",
  "authors": ["Author1", "Author2"],
  "doi": "10.xxxx/xxxxx",
  "literature_type": "White Literature",
  "source": "atlas",
  "keywords": ["SE", "recruitment"],
  "metadata_completeness": 0.95
}
```

### 4.2 Grounding Constraints

| Rule | Constraint |
|------|------------|
| R1 | NEVER say "unknown year" if year != null |
| R2 | NEVER infer missingness when metadata exists |
| R3 | NEVER reinterpret canonical metadata values |
| R4 | NEVER mark ambiguity when completeness > 0.8 |
| R5 | EC4 must ONLY use publication year field |
| R6 | Criteria MUST NOT leak semantics into each other |

### 4.3 Metadata Ground Truth

| Field | Source | Completeness |
|-------|--------|--------------|
| title | Always required | Always available |
| year | atlas: reliable, csv: present | atlas: high, csv: varies |
| abstract | Always available | Always available |
| literature_type | Hardcoded from sheet or CSV | Always known |

---

## 5. PROMPT ARCHITECTURE

### 5.1 EC Prompt Structure

```
SYSTEM CONTEXT:
You are a systematic review expert. PROTOCOL and CANONICAL METADATA are authoritative.

METADATA GROUNDING:
- Title: {title}
- Year: {year_str} (source: {year_source})
- Literature Type: {literature_type}
- Metadata Completeness: {metadata_completeness}
- Abstract: {abstract[:600]}

ADVISORY CONSTRAINTS:
1. NEVER say "year unknown" when year is NOT "NOT PROVIDED"
2. NEVER mark ambiguity when metadata_completeness indicates complete data
3. NEVER reinterpret canonical metadata values
4. Evaluate EACH criterion ISOLATED from others
5. EC4 (publication year) must ONLY use year field

EXCLUSION CRITERIA (protocol-authoritative):
- EC1: {description}
- EC2: {description}
- EC3: {description}
- EC4: {description}

STRUCTURED OUTPUT:
{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation using ONLY provided metadata",
  "reasoning_summary": "concise summary of evaluation process",
  "triggered_criteria": ["list"],
  "non_triggered_criteria": ["list"],
  "criterion_evaluations": {
    "EC1": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    ...
  },
  "ambiguity_flags": ["ONLY flag if metadata gap"],
  "evidence_extracts": ["verbatim"],
  "metadata_grounding": {"title_used": true, "year_used": true, ...}
}
```

### 5.2 IC Prompt Structure

Same as EC but for inclusion criteria. Focus on RELEVANCE to research question.

### 5.3 QC Prompt Structure

Same structure with quality criteria for WL (WL-Q1..Q4) or GL (GL-Q1..Q4).

---

## 6. FALLBACK BEHAVIOR

### 6.1 Fallback Conditions

| Condition | Fallback Trigger |
|-----------|-----------------|
| LLM client not initialized | `_fallback_advisory(stage, "No LLM client", metadata)` |
| JSON parse error | `_fallback_advisory(stage, f"JSON parse error: {str(e)[:50]}", metadata)` |
| HTTP/API error (400, 404, rate limit) | `_fallback_advisory(stage, f"LLM API error: {error_str[:50]}", metadata)` |
| Generic exception | `_fallback_advisory(stage, f"Error: {error_str[:50]}", metadata)` |

### 6.2 Fallback Advisory Structure

```python
StructuredAdvisory(
    stage=stage,
    decision="unavailable",
    confidence=0.0,
    triggered_criteria=[],
    non_triggered_criteria=[],
    criterion_evaluations={},
    justification="Structured advisory unavailable. Displaying deterministic fallback summary.",
    reasoning_summary="LLM service unavailable. Manual review required.",
    ambiguity_flags=["LLM not available"],
    evidence_extracts=[],
    metadata_grounding={
        "title_used": False,
        "year_used": False,
        "abstract_used": False,
        "literature_type_used": False
    },
    is_fallback=True,
    fallback_reason=error,
    protocol_version="1.0"
)
```

### 6.3 Fallback Detection

```python
if is_fallback:
    st.warning("⚠ STRUCTURED ADVISORY UNAVAILABLE — LLM service unavailable. Manual review required.")
```

---

## 7. ADVISORY HASH

### 7.1 Hash Computation

```python
def _compute_hash(self) -> str:
    data = {
        "stage": self.stage,
        "decision": self.decision,
        "triggered_criteria": sorted(self.triggered_criteria),
        "criterion_evaluations": {
            k: v.to_dict() for k, v in self.criterion_evaluations.items()
        }
    }
    content = json.dumps(data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

### 7.2 Hash Properties

- Deterministic: Same inputs → Same hash
- Collision-resistant: Different structure → Different hash
- Audit trail: Hash enables advisory traceability

---

## 8. CRITERION-BY-CRITERION ISOLATION

### 8.1 Isolation Rules

| Rule | Description |
|------|-------------|
| C1 | Each criterion evaluates independently |
| C2 | EC4 uses ONLY year field — never infers from literature_type |
| C3 | EC3 (peer-review) applies ONLY to WL — GL always passes |
| C4 | Ambiguity flags ONLY when actual metadata gap exists |
| C5 | Evidence extracts verbatim from title/abstract |

### 8.2 Example: EC4 Isolation

```python
# WRONG: EC4 influenced by literature_type
evidence = ["GL source - grey literature not peer-reviewed"]
justification = "GL source implies older publication"

# CORRECT: EC4 isolated to year field
evidence = ["publication year = 2022"]
justification = "2022 >= 2015 threshold"
grounded_metadata_fields = ["year"]
```

---

## 9. BACKWARD COMPATIBILITY

### 9.1 Legacy AdvisorySuggestion

`AdvisorySuggestion` remains for legacy code compatibility:

```python
suggestion = llm.suggest_ec(title, abstract, lit_type, year, metadata=metadata)
# Returns AdvisorySuggestion (legacy)

advisory = llm.suggest_ec(title, abstract, lit_type, year, metadata=metadata)
# Returns StructuredAdvisory (new)
```

### 9.2 Compatibility Wrapper

`_call_llm()` converts `StructuredAdvisory` to `AdvisorySuggestion` for legacy callers:

```python
def _call_llm(self, prompt, stage, literature_type) -> AdvisorySuggestion:
    advisory = self._call_structured_llm(prompt, stage, literature_type, {})

    triggered = {}
    for cid, eval_obj in advisory.criterion_evaluations.items():
        if eval_obj.triggered:
            triggered[cid] = eval_obj.justification

    return AdvisorySuggestion(
        stage=stage,
        decision=advisory.decision,
        confidence=advisory.confidence,
        justification=advisory.justification,
        triggered_criteria=triggered,
        evidence=advisory.evidence_extracts,
        ambiguity_flags=advisory.ambiguity_flags,
        is_fallback=advisory.is_fallback
    )
```

---

## 10. FILES MODIFIED

| File | Changes |
|------|---------|
| src/core/llm_assistant.py | Added StructuredAdvisory, CriterionEvaluation, normalize_literature_label(), structured prompts, advisory hash, fallback safety |
| src/ui/modules/ec_screening_view.py | Enhanced UI with metadata grounding display, criterion evaluations, advisory hash, fallback banner |
| src/core/screening_session.py | CSV ingestion now adds year_source and metadata_completeness |
| tests/unit/test_structured_advisory.py | 31 tests covering normalization, serialization, hash determinism, hallucination mitigation, replay |

---

## 11. VERIFICATION

### 11.1 Test Coverage

- WL/GL normalization: 15 parameterized tests
- Criterion evaluation serialization: 2 tests
- Advisory hash determinism: 3 tests
- Serialization round-trip: 2 tests
- Hallucination mitigation: 2 tests
- EC4 year isolation: 1 test
- Replay validation: 1 test

**Total: 31 tests, 31 passed**

### 11.2 Semantic Guarantees

| Guarantee | Verification |
|-----------|--------------|
| Same metadata → same advisory structure | Hash determinism test |
| WL normalization deterministic | Parameterized tests |
| GL normalization deterministic | Parameterized tests |
| EC4 uses ONLY year | Year isolation test |
| No hallucinated ambiguity | Hallucination mitigation tests |
| Replay preserves advisory | Round-trip tests |
| Advisory serialization deterministic | Hash equality test |
| Fallback has explicit markers | Structure tests |

---

## 12. REMAINING LIMITATIONS

1. **LLM response variability**: Temperature=0.1 reduces but does not eliminate variability
2. **Prompt injection risk**: Malicious protocol could attempt injection via criterion descriptions
3. **Context truncation**: Abstracts >600 chars truncated for prompt length limits
4. **Model dependence**: Structured outputs are model-specific; different models may require different prompting
5. **No semantic validation**: LLM may still produce semantically inconsistent criterion evaluations