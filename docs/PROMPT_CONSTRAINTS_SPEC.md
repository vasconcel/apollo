# PROMPT CONSTRAINTS SPECIFICATION
## APOLLO v1.0.0 - SPRINT 7.7

---

## 1. PROTOCOL-AUTHORITATIVE PROMPTING

### 1.1 Authority Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTHORITY HIERARCHY                        │
├─────────────────────────────────────────────────────────────┤
│  1. Protocol (EC/IC/QC criteria definitions)               │
│  2. Canonical Metadata (ground truth from ingestion)        │
│  3. LLM Interpretation (advisory only - assists researcher) │
├─────────────────────────────────────────────────────────────┤
│  LLM is NOT the authority. LLM ONLY assists interpretation.  │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 System Prompt Template

```
SYSTEM CONTEXT:
You are a systematic review expert. PROTOCOL and CANONICAL METADATA are authoritative. You ONLY assist interpretation.
```

---

## 2. EC PROMPT CONSTRAINTS

### 2.1 Full EC Prompt Structure

```
SYSTEM CONTEXT:
You are a systematic review expert. PROTOCOL and CANONICAL METADATA are authoritative. You ONLY assist interpretation.

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
5. EC4 (publication year) must ONLY use year field — never infer from other metadata

EXCLUSION CRITERIA (protocol-authoritative):
- EC1: {description}
- EC2: {description}
- EC3: {description}
- EC4: {description}

WL CONTEXT: {lit_context}
EC criteria filter inappropriate sources BEFORE relevance assessment.

STRUCTURED OUTPUT REQUIRED:
Return ONLY valid JSON with this exact structure:

{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation using ONLY provided metadata",
  "reasoning_summary": "concise summary of evaluation process",
  "triggered_criteria": ["list of criterion IDs triggered"],
  "non_triggered_criteria": ["list of criterion IDs NOT triggered"],
  "criterion_evaluations": {
    "EC1": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "EC2": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "EC3": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "EC4": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false}
  },
  "ambiguity_flags": ["ONLY flag ambiguity if grounded in actual metadata gaps"],
  "evidence_extracts": ["verbatim text extracts from title/abstract"],
  "metadata_grounding": {
    "title_used": true,
    "year_used": {year_str != "NOT PROVIDED"},
    "abstract_used": true,
    "literature_type_used": true
  }
}

Return ONLY valid JSON.
```

---

## 3. IC PROMPT CONSTRAINTS

### 3.1 Full IC Prompt Structure

```
SYSTEM CONTEXT:
You are a systematic review expert. PROTOCOL and CANONICAL METADATA are authoritative.

METADATA GROUNDING:
- Title: {title}
- Literature Type: {literature_type}
- Year Source: {year_source}
- Metadata Completeness: {metadata_completeness}
- Abstract: {abstract[:600]}

ADVISORY CONSTRAINTS:
1. IC criteria assess RELEVANCE to research question
2. Articles passing EC are already deemed empirical and recent
3. Focus on SE Recruitment & Selection (R&S) relevance
4. NEVER fabricate ambiguity when metadata is complete

INCLUSION CRITERIA (protocol-authoritative):
- IC1: {description}
- IC2: {description}
- IC3: {description}

STRUCTURED OUTPUT REQUIRED:
Return ONLY valid JSON:

{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation",
  "reasoning_summary": "concise evaluation summary",
  "triggered_criteria": ["list of criterion IDs triggered"],
  "non_triggered_criteria": ["list of criterion IDs NOT triggered"],
  "criterion_evaluations": {
    "IC1": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "IC2": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "IC3": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false}
  },
  "ambiguity_flags": [],
  "evidence_extracts": ["text extracts from title/abstract"],
  "metadata_grounding": {"title_used": true, "abstract_used": true, "literature_type_used": true}
}

Return ONLY valid JSON.
```

---

## 4. QC PROMPT CONSTRAINTS

### 4.1 Full QC Prompt Structure (WL)

```
SYSTEM CONTEXT:
You are a systematic review expert. PROTOCOL and CANONICAL METADATA are authoritative.

METADATA GROUNDING:
- Title: {title}
- Literature Type: {literature_type}
- Abstract: {abstract[:600]}

QUALITY CRITERIA (protocol-authoritative):
- WL-Q1: Are the research aims and SE R&S context clearly stated?
- WL-Q2: Is the methodology adequately described and appropriate?
- WL-Q3: Are findings clearly supported by collected data?
- WL-Q4: Does the study adequately discuss limitations?

STRUCTURED OUTPUT REQUIRED:
Return ONLY valid JSON:

{
  "decision": "include" or "exclude",
  "confidence": 0.0-1.0,
  "justification": "2-3 sentence explanation",
  "reasoning_summary": "quality assessment summary",
  "triggered_criteria": ["criteria scores"],
  "non_triggered_criteria": [],
  "criterion_evaluations": {
    "WL-Q1": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "WL-Q2": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "WL-Q3": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false},
    "WL-Q4": {"triggered": false, "evidence": [], "justification": "", "ambiguity_detected": false}
  },
  "ambiguity_flags": [],
  "evidence_extracts": [],
  "metadata_grounding": {"title_used": true, "abstract_used": true}
}

Return ONLY valid JSON.
```

### 4.2 Full QC Prompt Structure (GL)

Same as WL but with GL criteria:
- GL-Q1: Is author's expertise or organizational context explicitly stated?
- GL-Q2: Is the source of experience transparent?
- GL-Q3: Are claims supported by operational artifacts?
- GL-Q4: Does the source provide insights beyond generic marketing?

---

## 5. FORBIDDEN PHRASES

### 5.1 Year-Related Forbidden Phrases

| Forbidden Phrase | Correct Alternative |
|------------------|---------------------|
| "year unknown" | `Year: {year} (source: {year_source})` |
| "publication year unclear" | `Year: {year} (source: {year_source})` |
| "cannot determine publication age" | `Year: {year} (source: {year_source})` |
| "year missing" when year exists | `Year: {year} (source: {year_source})` |
| "publication date not provided" when year provided | `Year: {year} (source: {year_source})` |

### 5.2 Metadata-Related Forbidden Phrases

| Forbidden Phrase | Correct Alternative |
|------------------|---------------------|
| "unclear metadata" when completeness > 0.8 | No ambiguity flagged |
| "incomplete information" when completeness is "high" | No ambiguity flagged |
| "insufficient data" when title and abstract exist | No ambiguity flagged |
| "metadata gap" when all fields populated | No ambiguity flagged |

### 5.3 Ambiguity-Related Forbidden Phrases

| Forbidden Phrase | Condition |
|------------------|-----------|
| "possibly excluded" | Unless protocol explicitly states "maybe" |
| "might be relevant" | Use "include" or "exclude" decision |
| "borderline case" | Use criterion evaluation with evidence |
| "unclear if triggered" | Must make definitive judgment |

### 5.4 Semantic Leakage Forbidden Phrases

| Forbidden Phrase | Reason |
|------------------|--------|
| "GL sources are older" | EC4 must only use year field |
| "WL implies recent research" | Year is explicit in metadata |
| "peer-review implies exclusion" | EC3 is about peer-review status, not quality |
| "literature type suggests age" | Year field is authoritative |

---

## 6. CRITERION ISOLATION RULES

### 6.1 EC1 Isolation

```
EC1: Not empirical SE research

ISOLATION RULES:
- Use ONLY title and abstract content
- Do NOT consider publication year
- Do NOT consider literature type
- Do NOT infer from authors
```

### 6.2 EC2 Isolation

```
EC2: Published before 2015

ISOLATION RULES:
- Use ONLY year field
- Do NOT infer from literature type
- Do NOT use abstract content
- Do NOT use title content
```

### 6.3 EC3 Isolation

```
EC3: Not peer-reviewed - WL sources must be peer-reviewed academic publications

ISOLATION RULES:
- For WL: Evaluate peer-review status from abstract
- For GL: EC3 NOT applicable (GL is definitionally non-peer-reviewed)
- Do NOT use year field for EC3 evaluation
```

### 6.4 EC4 Isolation

```
EC4: Duplicate publication

ISOLATION RULES:
- Use ONLY year field and title
- Do NOT use literature type
- Do NOT infer from abstract
- Do NOT use peer-review status
```

---

## 7. EVIDENCE EXTRACTION RULES

### 7.1 Allowed Evidence Sources

| Source | Allowed |
|--------|---------|
| Title | ✓ Always |
| Abstract | ✓ Always |
| Year | ✓ For EC2/EC4 |
| Authors | ✗ Not for criteria |
| DOI | ✗ Not for criteria |
| Keywords | ✗ Not for criteria |

### 7.2 Evidence Format

```json
{
  "evidence_extracts": [
    "software engineering recruitment study",
    "survey of hiring practices in tech companies",
    "empirical analysis of developer selection"
  ]
}
```

### 7.3 Verbatim Requirement

Evidence MUST be:
- Extracted from title or abstract
- Verbatim or close paraphrase
- Not invented or inferred

---

## 8. METADATA GROUNDING ENFORCEMENT

### 8.1 Grounding Display in Prompts

```
METADATA GROUNDING:
- Title: {title}
- Year: {year_str} (source: {year_source})
- Literature Type: {literature_type}
- Metadata Completeness: {metadata_completeness}
- Abstract: {abstract[:600]}
```

### 8.2 Grounding Verification in Output

```json
{
  "metadata_grounding": {
    "title_used": true,
    "year_used": true,
    "abstract_used": true,
    "literature_type_used": true
  }
}
```

### 8.3 Ambiguity Constraint

```
ADVISORY CONSTRAINTS:
1. NEVER say "year unknown" when year is NOT "NOT PROVIDED"
2. NEVER mark ambiguity when metadata_completeness indicates complete data
3. NEVER reinterpret canonical metadata values
4. Evaluate EACH criterion ISOLATED from others
5. EC4 (publication year) must ONLY use year field — never infer from other metadata
```

---

## 9. PROMPT INJECTION PREVENTION

### 9.1 Injection Risk Model

| Risk | Description | Mitigation |
|------|-------------|------------|
| Criterion injection | Malicious criterion in protocol | Protocol validated before use |
| Metadata injection | Fake metadata fields | Ingestion validates sources |
| Response injection | Malformed JSON from LLM | JSON parse with fallback |

### 9.2 Validation Layers

1. **Protocol validation**: Criteria must match schema
2. **Metadata validation**: Fields must match expected types
3. **JSON parsing**: Invalid JSON triggers fallback
4. **Schema validation**: Missing fields use defaults

---

## 10. PROMPT VERSIONING

### 10.1 Version Tracking

Each prompt is constrained by:
- `protocol_version`: Protocol version used
- `advisory_hash`: Hash of advisory structure

### 10.2 Audit Trail

```python
StructuredAdvisory(
    ...
    protocol_version="1.0",
    advisory_hash="a3f8b2c1d4e5"
)
```

---

## 11. SUMMARY

| Constraint Type | Count | Status |
|-----------------|-------|--------|
| System context | 1 | ✓ |
| Metadata grounding fields | 5 | ✓ |
| Advisory constraints | 5 | ✓ |
| Forbidden phrases | 15+ | ✓ |
| Criterion isolation rules | 4 | ✓ |
| Evidence extraction rules | 3 | ✓ |
| Grounding enforcement | 3 | ✓ |
| Injection prevention | 4 | ✓ |