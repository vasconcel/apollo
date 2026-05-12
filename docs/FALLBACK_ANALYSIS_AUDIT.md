# Fallback Analysis Audit

## Overview

This document audits fallback advisory responses and their detection in APOLLO.

---

## 1. Fallback Detection Sources

### 1.1 LLM Assistant Fallback

**Location**: `src/core/llm_assistant.py:368-382`

```python
def _fallback_suggestion(self, stage: str, error: Optional[str] = None) -> AdvisorySuggestion:
    """Return fallback suggestion when LLM unavailable."""
    return AdvisorySuggestion(
        stage=stage,
        decision="skip",
        confidence=0.0,
        justification=f"LLM unavailable: {error}" if error else "LLM not configured",
        triggered_criteria={},
        evidence=[],
        ambiguity_flags=["LLM not available"]
    )
```

**Trigger Conditions**:
1. No LLM client initialized
2. JSON parse error
3. HTTP/API errors (400, 404, model errors)
4. Generic exceptions

### 1.2 UI Fallback (Insufficient Metadata)

**Location**: `src/ui/modules/ec_screening_view.py:347-363`

```python
if not has_title or not has_abstract:
    return {
        "stage": "ec",
        "decision": "uncertain",
        "confidence": 0.3,
        "justification": "Insufficient metadata: " +
            ("title " if not has_title else "") +
            ("abstract " if not has_abstract else "") +
            "not available for reliable evaluation.",
        "triggered_criteria": {},
        "evidence": [],
        "ambiguity_flags": [
            "Title missing" if not has_title else "",
            "Abstract missing" if not has_abstract else "",
            "Reduce confidence — manual review recommended"
        ]
    }
```

---

## 2. Fallback Response Patterns

### 2.1 LLM Unavailable Fallback

```json
{
    "stage": "ec",
    "decision": "skip",
    "confidence": 0.0,
    "justification": "LLM unavailable: No LLM client initialized",
    "triggered_criteria": {},
    "evidence": [],
    "ambiguity_flags": ["LLM not available"]
}
```

**Detection**: `confidence == 0.0` AND `"LLM not available"` in `ambiguity_flags`

### 2.2 Insufficient Metadata Fallback

```json
{
    "stage": "ec",
    "decision": "uncertain",
    "confidence": 0.3,
    "justification": "Insufficient metadata: title abstract not available for reliable evaluation.",
    "triggered_criteria": {},
    "evidence": [],
    "ambiguity_flags": [
        "Title missing",
        "Abstract missing",
        "Reduce confidence — manual review recommended"
    ]
}
```

**Detection**: `decision == "uncertain"` AND `confidence == 0.3`

### 2.3 Year Source Unknown Pattern

**Problem**: When CSV files are uploaded without `year_source` field, the LLM receives:
```
Year: 2023 (source: unknown)
```

**This is NOT a fallback** - it's a metadata propagation issue. The actual year is present, but year_source is missing.

---

## 3. Fallback Markers

### 3.1 Current Markers

| Fallback Type | Decision | Confidence | Marker |
|---------------|----------|-----------|--------|
| LLM unavailable | `skip` | 0.0 | `"LLM not available"` in flags |
| JSON parse error | `skip` | 0.0 | `"JSON parse error"` in justification |
| HTTP error | `skip` | 0.0 | `"LLM API error"` in justification |
| Insufficient metadata | `uncertain` | 0.3 | `"Reduce confidence"` in flags |

### 3.2 Recommended Markers

Add explicit `is_fallback` field to AdvisorySuggestion:

```python
@dataclass
class AdvisorySuggestion:
    stage: str
    decision: str
    confidence: float
    justification: str
    triggered_criteria: Dict[str, str] = field(default_factory=dict)
    evidence: List[str] = field(default_factory=list)
    ambiguity_flags: List[str] = field(default_factory=list)
    is_fallback: bool = False  # ← ADD
    fallback_reason: Optional[str] = None  # ← ADD
```

---

## 4. Fallback Detection Logic

### 4.1 Detection Function

```python
def is_fallback_advisory(suggestion: Dict) -> bool:
    """Detect if advisory is a fallback (not real inference)."""
    # Explicit fallback flag
    if suggestion.get('is_fallback', False):
        return True

    # Confidence-based detection
    if suggestion.get('confidence', 1.0) == 0.0:
        return True

    # Ambiguity flag detection
    flags = suggestion.get('ambiguity_flags', [])
    fallback_indicators = [
        'LLM not available',
        'LLM unavailable',
        'JSON parse error',
        'API error',
        'Reduce confidence'
    ]
    if any(indicator in ' '.join(flags) for indicator in fallback_indicators):
        return True

    return False
```

### 4.2 UI Handling

```python
def render_suggestion_details(suggestion: Dict):
    if is_fallback_advisory(suggestion):
        st.warning("⚠ AI analysis unavailable - this is a fallback response")

    # ... rest of rendering
```

---

## 5. "Unknown Publication Year" Investigation

### 5.1 Sources of "Unknown" Text

| Source | Location | Issue |
|--------|----------|-------|
| LLM prompt | `llm_assistant.py:158` | `f"Year: {year or 'Unknown'}"` |
| Fallback | `ec_screening_view.py:347-363` | `"Insufficient metadata"` message |
| CSV ingestion | `screening_session.py:268-275` | Missing `year_source` field |

### 5.2 Year Display Analysis

**Code in LLM prompt** (`llm_assistant.py`):
```python
prompt = f"""...
Year: {year or 'Unknown'} (source: {year_source})
..."""
```

**What happens**:
- If `year = None` → displays "Unknown"
- If `year = 2023` → displays "2023"
- If `year_source = "unknown"` → displays "source: unknown"

### 5.3 Root Cause: CSV Metadata Missing Fields

**CSV ingestion** creates metadata WITHOUT `year_source`:
```python
metadata = {
    "year": str(row_dict.get("Year", "")),  # ✓ Year might exist
    # ❌ year_source is MISSING
    # ❌ metadata_completeness is MISSING
}
```

**LLM receives**:
```python
year_source = metadata.get("year_source", "unknown")  # → "unknown"
```

**Result**: Even when year exists, "source: unknown" is displayed.

---

## 6. Fallback Visibility

### 6.1 Current State

Fallthrough responses are NOT clearly marked in the UI. A user might see:
```
Decision: SKIP
Confidence: 0%
Justification: LLM unavailable: No LLM client initialized
```

And not realize this is a fallback, not real AI analysis.

### 6.2 Recommended UI Changes

```python
def render_suggestion_details(suggestion: Dict):
    is_fallback = is_fallback_advisory(suggestion)

    if is_fallback:
        st.error("⚠ AI ADVISORY UNAVAILABLE")
        st.caption("Showing fallback response - real inference was not performed")
    else:
        # Normal rendering
```

---

## 7. Issues Summary

| Issue | Severity | Impact | Fix |
|-------|----------|--------|-----|
| Fallback not clearly marked | HIGH | User confusion | Add `is_fallback` flag |
| CSV missing year_source | CRITICAL | "source: unknown" | Add field in CSV ingestion |
| CSV missing metadata_completeness | CRITICAL | "completeness: unknown" | Add field in CSV ingestion |
| Year display shows "Unknown" | MEDIUM | User confusion | Ensure year always provided |

---

## 8. Files Requiring Changes

| File | Change |
|------|--------|
| `src/core/llm_assistant.py` | Add `is_fallback` and `fallback_reason` fields |
| `src/ui/modules/ec_screening_view.py` | Clear fallback indicator in UI |
| `src/ui/modules/ic_screening_view.py` | Clear fallback indicator in UI |
| `src/core/screening_session.py` | Add `year_source` and `metadata_completeness` to CSV |
