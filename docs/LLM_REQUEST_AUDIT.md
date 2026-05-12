# LLM Request Audit

## Overview

This document audits all LLM request assembly points, identifying where metadata is constructed and where degradation occurs.

---

## 1. Groq Request Builders

### 1.1 Main Request Builder

**Location**: `src/core/llm_assistant.py` → `_call_llm()`

```python
def _call_llm(
    self,
    prompt: str,
    stage: str,
    literature_type: str
) -> AdvisorySuggestion:
    """Call LLM and parse response with robust error handling."""
    if not self._client:
        return self._fallback_suggestion(stage, "No LLM client initialized")
    
    try:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are a systematic review expert..."},
                {"role": "user", "content": prompt}  # ← Final prompt
            ],
            temperature=0.1,
            max_tokens=800
        )
```

**AUDIT FINDING**: System prompt is generic and doesn't include scientific context.

---

## 2. Prompt Assembly Functions

### 2.1 EC Suggestion Prompt

**Location**: `src/core/llm_assistant.py` → `suggest_ec()`

```python
def suggest_ec(
    self,
    title: str,
    abstract: str,
    literature_type: str = "WL",
    year: Optional[int] = None,
    protocol_criteria: Optional[Dict[str, str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AdvisorySuggestion:
    
    year_source = metadata.get("year_source", "unknown") if metadata else "unknown"
    metadata_completeness = metadata.get("metadata_completeness", "unknown") if metadata else "unknown"
    
    prompt = f"""You are an expert systematic review assistant. Analyze this article for EXCLUSION CRITERIA (EC).

Article Title: {title}
Year: {year or 'Unknown'} (source: {year_source})  # ← Depends on metadata
Type: {literature_type}
Metadata Completeness: {metadata_completeness}       # ← Depends on metadata
Abstract: {abstract[:800] if abstract else 'No abstract available'}

ACTIVE EC CRITERIA:
{chr(10).join([f"- {k}: {v}" for k, v in criteria.items()])}

Task: Determine if article should be EXCLUDED. Provide JSON only:
...
"""
```

**AUDIT FINDING**: 
- ✓ `year_source` included if metadata passed
- ✓ `metadata_completeness` included if metadata passed
- ⚠ `year` expects int but may receive string

### 2.2 IC Suggestion Prompt

**Location**: `src/core/llm_assistant.py` → `suggest_ic()`

```python
def suggest_ic(
    self,
    title: str,
    abstract: str,
    literature_type: str = "WL",
    protocol_criteria: Optional[Dict[str, str]] = None
) -> AdvisorySuggestion:
    # ❌ NO year parameter
    # ❌ NO metadata parameter
    # ❌ NO year_source in prompt
    # ❌ NO metadata_completeness in prompt
    
    prompt = f"""You are an expert systematic review assistant. Analyze this article for INCLUSION CRITERIA (IC).

Article Title: {title}
Type: {literature_type}
Abstract: {abstract[:800] if abstract else 'No abstract available'}

ACTIVE IC CRITERIA:
...
"""
```

**AUDIT FINDING**: 
- ❌ IC prompt is MISSING year and provenance entirely
- ❌ This is a separate issue from EC

### 2.3 QC Suggestion Prompt

**Location**: `src/core/llm_assistant.py` → `suggest_qc()`

```python
def suggest_qc(
    self,
    title: str,
    abstract: str,
    literature_type: str = "WL",
    protocol_criteria: Optional[Dict[str, str]] = None
) -> AdvisorySuggestion:
    # ❌ NO year parameter
    # ❌ NO metadata parameter
    # ❌ NO literature_type context for WL vs GL difference
    
    prompt = f"""You are an expert systematic review assistant. Analyze this article's QUALITY.

Article Title: {title}
Type: {literature_type}  # ✓ Passes WL/GL
Abstract: {abstract[:800] if abstract else 'No abstract available'}

ACTIVE {literature_type} QUALITY CRITERIA:
...
"""
```

**AUDIT FINDING**:
- ⚠ Literature type passed but no explanation of WL vs GL significance
- ❌ Missing provenance context

---

## 3. Serialization Helpers

### 3.1 AdvisorySuggestion Serialization

```python
@dataclass
class AdvisorySuggestion:
    stage: str
    decision: str
    confidence: float
    justification: str
    triggered_criteria: Dict[str, str]
    evidence: List[str]
    ambiguity_flags: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "stage": self.stage,
            "decision": self.decision,
            "confidence": self.confidence,
            "justification": self.justification,
            "triggered_criteria": self.triggered_criteria,
            "evidence": self.evidence,
            "ambiguity_flags": self.ambiguity_flags
        }
```

**AUDIT FINDING**: ✓ Correctly serializes all fields.

---

## 4. AI Analysis Request Payloads

### 4.1 EC Screening View

**Location**: `src/ui/modules/ec_screening_view.py` → `get_llm_ec_suggestion()`

```python
def get_llm_ec_suggestion(article):
    # ... extraction ...
    
    if isinstance(article, ArticleReview):
        title = article.title
        abstract = article.abstract
        literature_type = article.get_literature_type()
        year = article.metadata.get("year", "")  # ← STRING not INT
        metadata = article.metadata
    
    # ❌ BROKEN: metadata extracted but not passed
    suggestion = llm.suggest_ec(
        title=title,
        abstract=abstract,
        literature_type=literature_type,
        protocol_criteria=protocol_criteria
    )
```

**AUDIT FINDING**: Metadata not passed to LLM.

### 4.2 IC Screening View

**Location**: `src/ui/modules/ic_screening_view.py` → Similar pattern

```python
def get_llm_ic_suggestion(article):
    suggestion = llm.suggest_ic(
        title=title,
        abstract=abstract,
        literature_type=literature_type,
        protocol_criteria=protocol_criteria
    )
    # ❌ No year, no metadata at all
```

### 4.3 Review View

**Location**: `src/ui/modules/review_view.py`

```python
suggestion = llm.suggest(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    stage=stage,
    metadata=metadata  # ✓ This one DOES pass metadata
)
```

**AUDIT FINDING**: The `suggest()` method (unified entry point) DOES pass metadata.

---

## 5. Legacy Dict Access Patterns

### 5.1 article.get() Usage

**Location**: `src/ui/modules/ec_screening_view.py:337-342`

```python
else:
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    literature_type = article.get("literature_type", "WL")
    year = article.get("year")
    metadata = article
```

**AUDIT FINDING**: Legacy dict fallback exists for backward compatibility.

### 5.2 metadata.get() with "unknown" Fallback

**Found in multiple locations**:

```python
# LLM assistant
year_source = metadata.get("year_source", "unknown") if metadata else "unknown"
metadata_completeness = metadata.get("metadata_completeness", "unknown") if metadata else "unknown"

# UI rendering
completeness = metadata.get("metadata_completeness", "unknown")

# Design system
year_source = metadata.get("year_source", "unknown")
```

**AUDIT FINDING**: Consistent use of "unknown" as fallback, but this creates bad context for LLM.

---

## 6. Metadata Field Verification

### 6.1 What Exists in Canonical ArticleReview

| Field | In metadata? | Passed to LLM? | In Prompt? |
|-------|-------------|-----------------|------------|
| `title` | ✓ | ✓ | ✓ |
| `abstract` | ✓ | ✓ | ✓ |
| `literature_type` | ✓ | ✓ | ✓ |
| `year` | ✓ | ⚠ String | ✓ |
| `year_source` | ✓ | ❌ | ❌ |
| `metadata_completeness` | ✓ | ❌ | ❌ |
| `authors` | ✓ | ❌ | ❌ |
| `doi` | ✓ | ❌ | ❌ |
| `source` | ✓ | ❌ | ❌ |

---

## 7. Before vs After Payload Comparison

### 7.1 BEFORE (Broken - Current)

```json
{
  "messages": [
    {"role": "system", "content": "You are a systematic review expert..."},
    {"role": "user", "content": "You are an expert systematic review assistant. Analyze this article for EXCLUSION CRITERIA (EC).\n\nArticle Title: Software Engineering Recruitment Practices\nYear: Unknown (source: unknown)\nType: WL\nMetadata Completeness: unknown\nAbstract: This study investigates... [800 chars]\n\nACTIVE EC CRITERIA:\n- EC1: Not empirical SE research\n- EC2: Published before 2015\n- EC3: Not peer-reviewed (for WL)\n- EC4: Duplicate publication\n..."}
  ]
}
```

### 7.2 AFTER (Fixed)

```json
{
  "messages": [
    {"role": "system", "content": "You are a systematic review expert..."},
    {"role": "user", "content": "You are an expert systematic review assistant. Analyze this article for EXCLUSION CRITERIA (EC).\n\nArticle Title: Software Engineering Recruitment Practices\nYear: 2023 (source: atlas)\nType: WL\nMetadata Completeness: complete\nAbstract: This study investigates... [800 chars]\n\nACTIVE EC CRITERIA:\n- EC1: Not empirical SE research\n- EC2: Published before 2015\n- EC3: Not peer-reviewed (WL is peer-reviewed academic sources - exclude non-peer-reviewed)\n- EC4: Duplicate publication\n..."}
  ]
}
```

---

## 8. Summary of Issues

| Issue | Location | Severity | Impact |
|-------|----------|----------|--------|
| metadata not passed to suggest_ec | ec_screening_view.py:367 | CRITICAL | year_source="unknown" |
| metadata not passed to suggest_ic | ic_screening_view.py:292 | CRITICAL | No year info at all |
| suggest_ic missing year param | llm_assistant.py:181 | HIGH | IC prompt lacks year |
| year is string not int | ec_screening_view.py:335 | MEDIUM | Type mismatch |
| EC3 wording ambiguous | criteria_registry.py:50 | MEDIUM | Model confusion |
| suggest_ic no metadata param | llm_assistant.py:181 | HIGH | No provenance context |
| Generic system prompt | llm_assistant.py:292 | LOW | Lacks scientific framing |

---

## Recommendations

1. **Pass metadata in all LLM calls** - Add `metadata=metadata` parameter
2. **Add year_source to IC prompts** - Extend suggest_ic signature
3. **Clarify EC3 wording** - Rewrite to eliminate ambiguity
4. **Add payload logging** - Log final prompt before inference for debugging
5. **Standardize year type** - Ensure year is passed as int or handle string conversion
