# Criteria Semantic Alignment Report

## Overview

This document audits the semantic alignment between criteria definitions and how the LLM interprets them, with focus on:
1. WL interpretation (whether "WL" is correctly understood)
2. EC3 ambiguity (peer-review criterion)
3. Model speculation patterns

---

## 1. EC Criteria Definitions

### 1.1 Current Definitions

**Location**: `src/core/criteria_registry.py`

```python
EC_DESCRIPTIONS: Dict[str, str] = {
    "EC1": "Not empirical software engineering research",
    "EC2": "Published before 2015",
    "EC3": "Not peer-reviewed (for WL)",
    "EC4": "Duplicate publication (by Global_ID)"
}
```

### 1.2 Dynamic Protocol Definitions

**Location**: `src/core/dynamic_protocol.py`

```python
ECProtocol:
    criteria: Dict[str, Criterion]  # Contains description field
```

**Default Template** (`ProtocolTemplate.SE_RS_BOOTSTRAP`):

```python
"ec": {
    "EC1": {"description": "Sources not written in English.", "enabled": True},
    "EC2": {"description": "Sources whose full text was unavailable...", "enabled": True},
    "EC3": {"description": "Short publications lacking sufficient methodological or experiential evidence...", "enabled": True},
    "EC4": {"description": "Sources published before 2015.", "enabled": True},
    "EC5": {"description": "Sources unrelated to Software Engineering...", "enabled": True},
    "EC6": {"description": "Duplicate studies.", "enabled": True},
}
```

**AUDIT FINDING**: Default template has DIFFERENT EC3 wording than criteria_registry!

---

## 2. EC3 Semantic Analysis

### 2.1 Current Wording: "Not peer-reviewed (for WL)"

**Problem**: This wording is semantically ambiguous:

1. **Interpretation A**: "Exclude papers that are NOT peer-reviewed"
   - This is the INTENDED meaning
   - WL = White Literature = peer-reviewed academic sources
   - If a "WL" source is not peer-reviewed, it fails EC3

2. **Interpretation B**: "EC3 only applies to WL"
   - The parenthetical "(for WL)" could mean this
   - GL sources are exempt from EC3

3. **Interpretation C**: "Papers that say they are WL but aren't peer-reviewed"
   - More nuanced interpretation
   - Could lead to over-exclusion

### 2.2 Evidence of Model Confusion

The LLM prompt includes:

```
Type: WL
Metadata Completeness: unknown  # ← Due to missing metadata

ACTIVE EC CRITERIA:
- EC3: Not peer-reviewed (for WL)
```

**Potential model reasoning**:
- Sees "WL" type
- Sees "Not peer-reviewed (for WL)"
- May interpret as: "Since this is WL, EC3 applies"
- May reason: "WL should be peer-reviewed, if it's not, exclude"
- OR: "WL is peer-reviewed by definition, so EC3 doesn't apply"

### 2.3 Recommended Fix

**Replace ambiguous wording with explicit exclusion criterion**:

```python
EC_DESCRIPTIONS: Dict[str, str] = {
    "EC1": "Not empirical software engineering research",
    "EC2": "Published before 2015",
    "EC3": "Not peer-reviewed - WL sources must be peer-reviewed academic publications",
    "EC4": "Duplicate publication (by Global_ID)"
}
```

---

## 3. Literature Type (WL) Semantic Analysis

### 3.1 WL Definition in APOLLO

| Literature Type | Definition | Source Type |
|----------------|------------|-------------|
| **WL** (White Literature) | Peer-reviewed academic publications | Journals, Conferences |
| **GL** (Grey Literature) | Non-peer-reviewed sources | Blogs, Reports, White Papers |

### 3.2 How LLM Receives WL Context

**Current prompt**:
```
Type: WL
```

**Missing context**: The LLM doesn't know what "WL" means unless told.

### 3.3 Recommended Addition

**Add explicit literature type context to prompts**:

```python
LITERATURE_TYPE_CONTEXT = {
    "WL": "White Literature - peer-reviewed academic sources (journals, conferences)",
    "GL": "Grey Literature - non-peer-reviewed sources (blogs, reports, white papers)"
}

prompt = f"""...
Type: {literature_type} - {LITERATURE_TYPE_CONTEXT.get(literature_type, '')}
..."""
```

---

## 4. Model Speculation Patterns

### 4.1 Where Speculation Occurs

The LLM may speculate when:

1. **Year is "unknown"**: May assume recent publication
2. **Metadata is incomplete**: May assume low quality
3. **Abstract is short**: May assume lacks rigor
4. **Keywords missing**: May assume narrow scope

### 4.2 Year Speculation Issue

**Current broken state** (year_source="unknown"):
```
Year: Unknown (source: unknown)
```

**Model may reason**:
- "Year is unknown, this is suspicious"
- "Unknown year might mean before 2015, trigger EC2"
- "Should I assume it's recent or old?"

**Correct state**:
```
Year: 2023 (source: atlas)
```

**Model reasoning**:
- "Year 2023 is recent"
- "Does not trigger EC2 (before 2015)"
- "Modern study, likely peer-reviewed"

### 4.3 Metadata Completeness Impact

**Current broken state** (completeness="unknown"):
```
Metadata Completeness: unknown
```

**Model may reason**:
- "Metadata is incomplete, this is a red flag"
- "Low quality source, should be excluded"
- "May lack peer-review information"

**Correct state**:
```
Metadata Completeness: complete
```

**Model reasoning**:
- "Full metadata available"
- "This is a well-documented source"
- "Likely peer-reviewed academic publication"

---

## 5. Criteria Ambiguity Matrix

| Criterion | Current Wording | Ambiguity | Risk | Recommended Fix |
|-----------|----------------|-----------|------|----------------|
| EC1 | "Not empirical SE research" | Low | Low | OK |
| EC2 | "Published before 2015" | Low | MEDIUM | Add threshold explanation |
| EC3 | "Not peer-reviewed (for WL)" | HIGH | HIGH | Rewrite to be explicit |
| EC4 | "Duplicate publication" | Low | LOW | OK |

---

## 6. Prompt Context Completeness

### 6.1 What LLM Currently Receives (EC)

```python
prompt = f"""
Article Title: {title}
Year: {year or 'Unknown'} (source: {year_source})  # ← year_source often "unknown"
Type: {literature_type}  # ← Just "WL" or "GL", no definition
Metadata Completeness: {metadata_completeness}  # ← Often "unknown"
Abstract: {abstract[:800]}

ACTIVE EC CRITERIA:
- EC1: {criteria['EC1']}
- EC2: {criteria['EC2']}
- EC3: {criteria['EC3']}
- EC4: {criteria['EC4']}
"""
```

### 6.2 What LLM Should Receive

```python
LITERATURE_TYPE_CONTEXT = {
    "WL": "White Literature - peer-reviewed academic publications (journals, conferences)",
    "GL": "Grey Literature - non-peer-reviewed sources (blogs, reports, white papers, industry reports)"
}

prompt = f"""
Article Title: {title}
Year: {year or 'Unknown'} (source: {year_source})  # ← Always accurate with fix
Type: {literature_type} - {LITERATURE_TYPE_CONTEXT.get(literature_type, '')}
Metadata Completeness: {metadata_completeness}  # ← Always accurate with fix
Abstract: {abstract[:800]}

IMPORTANT CONTEXT:
- WL sources are PEER-REVIEWED by definition
- GL sources are NOT peer-reviewed
- EC3 excludes non-peer-reviewed WL sources only
- Year source indicates data reliability

ACTIVE EC CRITERIA:
- EC1: {criteria['EC1']}
- EC2: {criteria['EC2']}
- EC3: {criteria['EC3']}  ← Rewrite this
- EC4: {criteria['EC4']}
"""
```

---

## 7. Summary of Semantic Issues

| Issue | Root Cause | Impact | Fix |
|-------|-----------|--------|-----|
| "WL" not defined | Missing context in prompt | Model may not understand WL=peer-reviewed | Add literature type definition |
| EC3 ambiguous | "(for WL)" parenthetical | Model confusion on applicability | Rewrite to explicit exclusion |
| Year="unknown" | metadata not passed | Model speculation on publication date | Pass metadata to LLM |
| Completeness="unknown" | metadata not passed | Model assumes low quality | Pass metadata to LLM |

---

## 8. Recommended Changes

### 8.1 Fix 1: Pass Metadata to LLM (CRITICAL)

```python
# ec_screening_view.py line 367
suggestion = llm.suggest_ec(
    title=title,
    abstract=abstract,
    literature_type=literature_type,
    protocol_criteria=protocol_criteria,
    metadata=metadata  # ← ADD THIS
)
```

### 8.2 Fix 2: Add Literature Type Context

```python
# llm_assistant.py - Add constant
LITERATURE_TYPE_CONTEXT = {
    "WL": "White Literature - peer-reviewed academic publications",
    "GL": "Grey Literature - non-peer-reviewed sources"
}

# In prompt construction
prompt = f"""...
Type: {literature_type} - {LITERATURE_TYPE_CONTEXT.get(literature_type, '')}
..."""
```

### 8.3 Fix 3: Rewrite EC3

```python
# criteria_registry.py
EC_DESCRIPTIONS: Dict[str, str] = {
    "EC1": "Not empirical software engineering research",
    "EC2": "Published before 2015",
    "EC3": "Not peer-reviewed - WL sources must be peer-reviewed academic publications",
    "EC4": "Duplicate publication (by Global_ID)"
}
```

### 8.4 Fix 4: Add Year Source Context

```python
prompt = f"""...
Year: {year or 'Unknown'} (source: {year_source})

Year Source Legend:
- 'atlas': Extracted from ATLAS export metadata
- 'doi': Extracted from DOI registration
- 'manual': Manually entered by researcher
..."""
```

---

## 9. Before vs After Comparison

### 9.1 EC3 Interpretation

**BEFORE (Broken)**:
```
Model receives: "Type: WL" + "EC3: Not peer-reviewed (for WL)"
Model thinks: "EC3 applies to WL, but WL is peer-reviewed... confused"
Possible output: "EC3 triggered because... unclear reasoning"
```

**AFTER (Fixed)**:
```
Model receives: "Type: WL - White Literature - peer-reviewed academic publications"
           + "EC3: Not peer-reviewed - WL sources must be peer-reviewed"
Model thinks: "This is WL which is peer-reviewed by definition. If it fails EC3, 
              it means the source claims to be WL but isn't actually peer-reviewed"
Output: "EC3 not triggered - source is confirmed peer-reviewed journal article"
```

### 9.2 Year Context

**BEFORE (Broken)**:
```
Model receives: "Year: Unknown (source: unknown)"
Model thinks: "Year is unknown - might be before 2015, trigger EC2"
Possible output: "EC2 triggered - publication date unclear"
```

**AFTER (Fixed)**:
```
Model receives: "Year: 2023 (source: atlas)"
Model thinks: "2023 is recent, well within the study period"
Output: "EC2 not triggered - published in 2023"
```

---

## 10. Testing Recommendations

After implementing fixes:

1. **Test WL article without peer-review claim**
   - Verify EC3 is triggered correctly
   - Verify reasoning mentions "not peer-reviewed"

2. **Test WL article with peer-review claim**
   - Verify EC3 is NOT triggered
   - Verify reasoning mentions "peer-reviewed"

3. **Test year_source propagation**
   - Verify year_source appears in prompt
   - Verify model uses year_source for EC2 decisions

4. **Test metadata_completeness impact**
   - Verify model uses completeness in confidence scoring
