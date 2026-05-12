# LLM Semantic Alignment Report

## Overview

This document verifies that the fixes implemented correctly align LLM advisory reasoning with APOLLO's scientific methodology.

---

## Semantic Issues Identified

### Issue 1: "WL" Interpretation

**Problem**: The LLM received just "WL" or "GL" without understanding what these mean.

**Root Cause**: Literature type was passed but not defined.

**Fix Applied**: Added explicit definitions to prompts:

```
Type: WL - White Literature - peer-reviewed academic publications (journals, conferences)
Type: GL - Grey Literature - non-peer-reviewed sources (blogs, reports, white papers)
```

**Verification**:
- Before: LLM may interpret "WL" as just a label
- After: LLM understands WL = peer-reviewed, GL = non-peer-reviewed

---

### Issue 2: EC3 Ambiguity

**Problem**: "Not peer-reviewed (for WL)" was semantically ambiguous.

**Root Cause**: Parenthetical "(for WL)" could be interpreted as:
1. "This criterion applies only to WL" (correct but unclear)
2. "Papers claiming to be WL that aren't peer-reviewed" (correct but vague)
3. "Exclude non-peer-reviewed sources" (correct intent)

**Fix Applied**:
```
EC3: "Not peer-reviewed - WL sources must be peer-reviewed academic publications"
```

**Verification**:
- Before: Model confused about EC3 applicability
- After: Model understands WL must be peer-reviewed; if not, EC3 triggered

---

### Issue 3: Year Source Interpretation

**Problem**: Year source "unknown" led to speculation.

**Root Cause**: Metadata not passed, year_source defaulted to "unknown".

**Fix Applied**: Pass metadata containing year_source to LLM functions.

**Verification**:
- Before: `Year: Unknown (source: unknown)` → Model speculates publication date
- After: `Year: 2023 (source: atlas)` → Model knows year is reliable

---

### Issue 4: Metadata Completeness Impact

**Problem**: Unknown completeness led to negative bias.

**Root Cause**: Metadata not passed, completeness defaulted to "unknown".

**Fix Applied**: Pass metadata containing metadata_completeness to LLM functions.

**Verification**:
- Before: `Metadata Completeness: unknown` → Model assumes low quality
- After: `Metadata Completeness: complete` → Model has accurate context

---

## Alignment Matrix

| Semantic Concept | LLM Understanding Before | LLM Understanding After | Alignment Status |
|-----------------|--------------------------|--------------------------|------------------|
| WL = Peer-reviewed | Unclear | Explicit "White Literature - peer-reviewed" | ✓ Aligned |
| GL = Non-peer-reviewed | Unclear | Explicit "Grey Literature - non-peer-reviewed" | ✓ Aligned |
| EC3 excludes non-peer-reviewed WL | Confused by "(for WL)" | Clear "WL must be peer-reviewed" | ✓ Aligned |
| Year source indicates reliability | N/A (was unknown) | "atlas" = reliable source | ✓ Aligned |
| Metadata completeness | N/A (was unknown) | Accurate completeness level | ✓ Aligned |

---

## Advisory Reasoning Examples

### Example 1: Peer-Reviewed WL Article

**Article**: Conference paper on SE recruitment published in IEEE Transactions

**Expected LLM Reasoning**:
```
EC3 NOT triggered - Article is from IEEE, clearly peer-reviewed
No evidence of non-peer-review in title or abstract
Peer-reviewed venue confirms EC3 compliance
```

**Before Fix**:
- Year: Unknown (source: unknown)
- Type: WL
- EC3: "Not peer-reviewed (for WL)"
- Reasoning may be confused about EC3 applicability

**After Fix**:
- Year: 2023 (source: atlas)
- Type: WL - peer-reviewed academic publications
- EC3: "Not peer-reviewed - WL must be peer-reviewed"
- Reasoning: "IEEE Transactions is peer-reviewed → EC3 not triggered"

---

### Example 2: Non-Peer-Reviewed Source Marked as WL

**Article**: Blog post shared in ATLAS export with literature_type="WL"

**Expected LLM Reasoning**:
```
EC3 TRIGGERED - Despite being marked WL, this is a blog post
Evidence: "blog", "personal experience", lack of journal/conference markers
Article claims to be WL but lacks peer-review characteristics
```

**Before Fix**:
- Model may not understand that WL should be peer-reviewed
- EC3 interpretation unclear due to ambiguous wording

**After Fix**:
- Model knows "WL = peer-reviewed academic publications"
- Clear EC3 criterion: "WL sources must be peer-reviewed"
- Reasoning: "This is a blog, not peer-reviewed → EC3 triggered"

---

### Example 3: IC Relevance Assessment

**Article**: Industry report on developer hiring practices (GL)

**Expected LLM Reasoning**:
```
IC1 TRIGGERED - Explicitly addresses SE recruitment
IC2 NOT triggered - No empirical methodology described
IC3 NOT triggered - Industry context present but not primary focus

Overall: INCLUDE for relevance (IC1), but note GL QC framework applies
```

**Before Fix**:
- Model has no IC context about article's EC passage
- No awareness that IC follows EC filtering

**After Fix**:
- IC prompt includes: "Articles that passed EC are already deemed empirical and recent"
- Context helps model focus on relevance, not re-filtering

---

## Validation Test Cases

### TC1: WL Peer-Reviewed Article

| Field | Value |
|-------|-------|
| literature_type | WL |
| year | 2023 |
| year_source | atlas |
| metadata_completeness | complete |
| venue | IEEE Software |

**Expected**: EC3 NOT triggered
**Reasoning**: Peer-reviewed venue confirmed

### TC2: WL Blog Post

| Field | Value |
|-------|-------|
| literature_type | WL |
| year | 2023 |
| year_source | manual |
| metadata_completeness | partial |
| venue | personal blog |

**Expected**: EC3 TRIGGERED
**Reasoning**: Blog post not peer-reviewed despite WL label

### TC3: GL Industry Report

| Field | Value |
|-------|-------|
| literature_type | GL |
| year | 2023 |
| year_source | atlas |
| metadata_completeness | complete |

**Expected**: EC3 NOT triggered (EC3 applies to WL only)
**Reasoning**: GL is non-peer-reviewed by definition; EC3 irrelevant

### TC4: Pre-2015 Article

| Field | Value |
|-------|-------|
| literature_type | WL |
| year | 2012 |
| year_source | doi |
| metadata_completeness | complete |

**Expected**: EC2 TRIGGERED
**Reasoning**: Published 2012 < 2015 threshold

---

## Confidence Score Calibration

### Expected Confidence Ranges

| Scenario | Expected Confidence | Rationale |
|----------|-------------------|-----------|
| WL peer-reviewed venue, clear evidence | 0.8-0.95 | Strong positive signal |
| WL peer-reviewed venue, some ambiguity | 0.6-0.8 | Positive but uncertain |
| WL non-peer-reviewed, clear evidence | 0.8-0.95 | Strong negative signal |
| GL with clear relevance | 0.7-0.9 | Positive signal |
| GL with industry context | 0.5-0.7 | Moderate relevance |

### Confidence Modifier: Year Source

| Year Source | Effect on Confidence |
|-------------|---------------------|
| atlas | Neutral - reliable source |
| doi | Neutral - registry verified |
| manual | Slight reduction - manual entry |

### Confidence Modifier: Metadata Completeness

| Completeness | Effect on Confidence |
|--------------|---------------------|
| complete | Neutral |
| partial | Slight reduction |
| minimal | Moderate reduction |

---

## Recommendations for Ongoing Alignment

### 1. Regular Prompt Review

Schedule quarterly review of:
- Criteria wording for ambiguity
- Literature type definitions
- Year/completeness handling

### 2. Logging and Monitoring

Enable `APOLLO_LLM_LOGGING=1` to:
- Capture sample prompts
- Verify metadata propagation
- Identify reasoning patterns

### 3. Human Calibration

Compare LLM suggestions against human decisions:
- Track agreement rates by literature type
- Identify systematic biases
- Adjust prompts based on findings

### 4. Protocol-Versioned Prompts

Consider versioned prompt templates that:
- Match DynamicProtocol versions
- Include protocol hash in audit
- Enable reproducibility verification

---

## Summary

The fixes implemented address all identified semantic alignment issues:

1. ✓ WL/GL are now explicitly defined in prompts
2. ✓ EC3 wording is unambiguous
3. ✓ Year source context is preserved
4. ✓ Metadata completeness is communicated
5. ✓ IC context includes EC passage awareness

**Result**: LLM advisory reasoning should now accurately reflect APOLLO's scientific methodology.
