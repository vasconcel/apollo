# ADVISORY GROUNDING REPORT
## APOLLO v1.0.0 - SPRINT 7.7

---

## 1. METADATA GROUNDING ARCHITECTURE

### 1.1 Grounding Layers

```
┌─────────────────────────────────────────────────────────────┐
│                   LLM ADVISORY SUBSYSTEM                     │
├─────────────────────────────────────────────────────────────┤
│  METADATA GROUNDING LAYER                                    │
│  ├── Title: Always used                                      │
│  ├── Abstract: Always used (truncated to 600 chars)           │
│  ├── Year: Used when present, "NOT PROVIDED" when absent     │
│  ├── Literature Type: Canonical normalization applied        │
│  └── Metadata Completeness: Determines ambiguity flags        │
├─────────────────────────────────────────────────────────────┤
│  PROTOCOL CONSTRAINT LAYER                                   │
│  ├── Criteria definitions: Protocol-authoritative            │
│  ├── Criterion isolation: No semantic leakage                │
│  └── Evaluation structure: Strict JSON schema                │
├─────────────────────────────────────────────────────────────┤
│  FALLBACK SAFETY LAYER                                        │
│  ├── Explicit fallback markers                               │
│  ├── Deterministic fallback advisory                         │
│  └── Visual distinction from real advisory                  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Grounding Fields

| Field | Source | When Used | Truncation |
|-------|--------|-----------|------------|
| title | Article title | Always | No |
| abstract | Article abstract | Always | 600 chars |
| year | metadata.year | When != null | N/A |
| year_source | metadata.year_source | Always | N/A |
| literature_type | metadata.literature_type | Always | N/A |
| metadata_completeness | metadata.metadata_completeness | Always | N/A |
| authors | metadata.authors | When available | No |
| doi | metadata.doi | When available | N/A |
| keywords | metadata.keywords | When available | N/A |

---

## 2. METADATA PROPAGATION FIXES

### 2.1 CSV Ingestion Fix (screening_session.py:292-305)

**Before:**
```python
metadata = {
    "year": str(row_dict.get("Year", "")),
    "authors": str(row_dict.get("Authors", "")),
    "literature_type": lit_type,
    "title": str(row_dict.get("Title", "")),
    "abstract": str(row_dict.get("Abstract", "")),
    "global_id": str(row_dict.get("global_id", str(uuid.uuid4())[:8])),
}
```

**After:**
```python
metadata = {
    "year": str(row_dict.get("Year", "")),
    "authors": str(row_dict.get("Authors", "")),
    "literature_type": normalize_literature_type(lit_type),
    "title": str(row_dict.get("Title", "")),
    "abstract": str(row_dict.get("Abstract", "")),
    "global_id": str(row_dict.get("global_id", str(uuid.uuid4())[:8])),
    "year_source": "csv",  # FIXED: was missing
    "metadata_completeness": compute_csv_metadata_completeness(row_dict)  # FIXED: was missing
}
```

**Root Cause**: CSV ingestion did not populate `year_source` and `metadata_completeness` fields, causing LLM to see "unknown" for both.

### 2.2 ATLAS Ingestion (Already Fixed)

ATLAS Excel ingestion correctly populates both fields:
```python
metadata = {
    ...
    "year_source": "atlas",  # ✓ Correct
    "metadata_completeness": article.metadata_completeness  # ✓ Correct
}
```

---

## 3. YEAR SOURCE GROUNDING

### 3.1 Year Source Values

| Source | Description | Reliability |
|--------|-------------|-------------|
| atlas | ATLAS Excel file | High - validated export |
| csv | CSV ingestion | Variable - depends on upload |
| manual | Manually entered | Depends on researcher |
| unknown | Not provided | N/A |

### 3.2 Year Grounding in Prompts

```
Year: {year_str} (source: {year_source})
```

- When year exists: `Year: 2021 (source: atlas)`
- When year missing: `Year: NOT PROVIDED (source: unknown)`

### 3.3 Forbidden Phrases

| Forbidden | Correct |
|-----------|--------|
| "year unknown" when year exists | `Year: 2021 (source: atlas)` |
| "publication year unclear" when year provided | `Year: 2021 (source: csv)` |
| "cannot determine age" when year field populated | `Year: 2021 (source: atlas)` |

---

## 4. METADATA COMPLETENESS GROUNDING

### 4.1 Completeness Calculation (CSV)

```python
def compute_csv_metadata_completeness(row: dict) -> str:
    has_title = bool(row.get("Title"))
    has_year = bool(row.get("Year"))
    has_authors = bool(row.get("Authors"))
    has_abstract = bool(row.get("Abstract") and len(str(row.get("Abstract", ""))) > 50)

    count = sum([has_title, has_year, has_authors, has_abstract])
    total = 4

    if count == total:
        return "high"
    elif count >= 3:
        return "medium"
    elif count >= 2:
        return "low"
    else:
        return "minimal"
```

### 4.2 Completeness in Prompts

```
Metadata Completeness: high
```

### 4.3 Ambiguity Constraints

| Completeness | Allowed Ambiguity |
|--------------|-------------------|
| high | NONE - ambiguity_detected must be False |
| medium | Only if actual metadata gap exists |
| low | Flag if title or abstract missing |
| minimal | Flag multiple missing fields |

---

## 5. LITERATURE TYPE GROUNDING

### 5.1 Canonical Labels

| Raw Value | Canonical | Context |
|-----------|-----------|---------|
| WL | White Literature | Peer-reviewed academic |
| White Literature | White Literature | Peer-reviewed academic |
| GL | Grey Literature | Non-peer-reviewed |
| Grey Literature | Grey Literature | Non-peer-reviewed |

### 5.2 Literature Context in Prompts

```
WL CONTEXT: PEER-REVIEWED academic sources (journals, conferences)
GL CONTEXT: NON-PEER-REVIEWED sources (blogs, reports, white papers)
```

### 5.3 EC3 Grounding

```
EC3: Not peer-reviewed - WL sources must be peer-reviewed academic publications

WL articles: EC3 evaluates peer-review status
GL articles: EC3 is NOT applicable (GL is definitionally non-peer-reviewed)
```

---

## 6. EVIDENCE EXTRACTION GROUNDING

### 6.1 Extraction Rules

1. Extract ONLY from title and abstract
2. Use verbatim text when possible
3. Mark metadata field used for extraction
4. No invented or inferred evidence

### 6.2 Example Evidence Extracts

```python
evidence_extracts = [
    "software engineering recruitment",
    "human resources for IT positions",
    "survey of hiring practices in tech companies"
]
```

### 6.3 Grounded Metadata Fields

```python
criterion_evaluation.grounded_metadata_fields = ["title", "abstract"]
```

---

## 7. GROUNDING VERIFICATION

### 7.1 Verification Tests

| Test | Description | Status |
|------|-------------|--------|
| test_year_not_hallucinated_when_provided | Year field used, not marked unknown | ✓ PASS |
| test_no_ambiguity_when_metadata_complete | High completeness → no ambiguity flags | ✓ PASS |
| test_ec4_must_not_infer_from_literature_type | EC4 uses year only, not lit_type | ✓ PASS |

### 7.2 Ground Truth Sources

| Source | Type | Trust Level |
|--------|------|-------------|
| ATLAS Excel | Structured export | High |
| CSV upload | User-provided | Variable |
| Manual entry | Researcher input | Variable |

---

## 8. SEMANTIC DRIFT MITIGATION

### 8.1 Drift Sources Identified

1. **Year hallucination**: "unknown year" when year exists → Fixed by year_source field
2. **Ambiguity fabrication**: False ambiguity flags → Fixed by metadata_completeness grounding
3. **Semantic leakage**: Criteria influencing each other → Fixed by criterion isolation prompts
4. **Metadata reinterpretation**: LLM ignoring canonical values → Fixed by explicit normalization

### 8.2 Mitigation Evidence

| Drift Type | Before | After |
|------------|--------|-------|
| Year hallucination | `Year: Unknown (source: unknown)` | `Year: 2021 (source: atlas)` |
| Ambiguity fabrication | `ambiguity_flags: ["year unclear"]` | `ambiguity_detected: False` |
| Semantic leakage | EC4 influenced by literature_type | EC4 uses year field only |
| Metadata reinterpretation | `literature_type: "unknown"` | `literature_type: "White Literature"` |

---

## 9. ADVISORY HASH TRACEABILITY

### 9.1 Hash Components

```python
data = {
    "stage": self.stage,
    "decision": self.decision,
    "triggered_criteria": sorted(self.triggered_criteria),
    "criterion_evaluations": {
        k: v.to_dict() for k, v in self.criterion_evaluations.items()
    }
}
```

### 9.2 Hash Properties

- **Deterministic**: Same advisory structure → Same hash
- **Unique**: Different structure → Different hash
- **Audit trail**: Hash enables post-hoc verification

### 9.3 UI Display

```
advisory: a3f8b2c1d4e5
```

---

## 10. SUMMARY

| Aspect | Status |
|--------|--------|
| Metadata fields populated | ✓ Complete |
| Year source grounded | ✓ Complete |
| Completeness computed | ✓ Complete |
| Literature type normalized | ✓ Complete |
| Evidence extraction verified | ✓ Complete |
| Grounding visualization in UI | ✓ Complete |
| Advisory hash traceability | ✓ Complete |
| Fallback explicit markers | ✓ Complete |