# APOLLO Screening Lifecycle

## Overview

This document describes the deterministic screening workflow from article import to final decision.

## Lifecycle Stages

### 1. Protocol Configuration

```
Researcher defines:
- EC criteria (Exclusion Criteria)
- IC criteria (Inclusion Criteria)  
- QC criteria (Quality Criteria)
- Protocol version
- Protocol state: DRAFT
```

**Invariant**: Protocol must be LOCKED before screening begins.

### 2. Article Import

```
Researcher imports:
- ATLAS export (RIS, BibTeX, EndNote)
- Article metadata extraction
- Article ID generation
```

**Constraint**: Articles are immutable once imported.

### 3. Advisory Generation (Per Article)

```
For each article:
1. LLM generates advisory (advisory_worker)
2. Advisory includes:
   - Decision (INCLUDE/EXCLUDE/UNKNOWN)
   - Confidence (0.0-1.0)
   - Triggered criteria
   - Justification
   - Grounding strength
   - Hallucination risk score
```

**Determinism**: Advisory is deterministic given same article + protocol + LLM.

### 4. Risk Classification (Per Article)

```
AdvisoryResult → RiskClassification:
- CRITICAL_REVIEW: confidence < 0.5 OR hallucination_risk > 0.7
- HIGH_RISK: confidence < 0.7 OR grounding_strength < 0.5
- MEDIUM_RISK: confidence < 0.85
- LOW_RISK: confidence >= 0.85 AND grounding >= 0.5
```

### 5. Queue Routing (Per Article)

```
RiskClassification + Deterministic Sampling → ValidationQueue:
- CRITICAL_REVIEW → PRIORITY_REVIEW (always)
- HIGH_RISK → PRIORITY_REVIEW (always)
- MEDIUM_RISK → PRIORITY_REVIEW (always)
- LOW_RISK + sampled → AUTO_ACCEPT_CANDIDATES (for validation)
- LOW_RISK + not sampled → AUTO_EXCLUDE_CANDIDATES (collapsed)
```

### 6. Review Workflow

```
Researcher selects:
- Review Mode: FOCUSED_RISK_REVIEW | SEQUENTIAL_REVIEW | CALIBRATION_REVIEW
- Queue Filter: CRITICAL_REVIEW | HIGH_RISK | MEDIUM_RISK | ...

For each article in filtered queue:
1. Display advisory card:
   - Decision
   - Confidence
   - Evidence Alignment
   - Evidence Reliability
   - Grounded criteria
   
2. Researcher actions:
   - Confirm (approve AI decision)
   - Override (human decision with reason)
   - Escalate (mark for manual review)
   
3. State transition:
   - Next article
   - Previous article
   - Queue filter change
   - Review mode change
```

### 7. Calibration Logging

```
On Override/Escalate:
1. Create CalibrationEvent:
   - article_id
   - protocol_version
   - stage (ec/ic/qc)
   - ai_decision
   - human_decision
   - disagreement (bool)
   - override_severity
   - override_reason
   - timestamp
   
2. Append to calibration log (append-only)
```

### 8. Export

```
Researcher exports:
- Screened articles with decisions
- Calibration summary
- Protocol version hash
- Session metadata
```

## Queue Priority Order

Based on operational priority:

1. **CRITICAL_REVIEW** - Highest priority, always visible
2. **HIGH_RISK** - Requires review, visible
3. **MEDIUM_RISK** - Should review, visible
4. **LOW_RISK_SAMPLED** - Validation sample, visible
5. **AUTO_LOW_RISK** - Collapsed by default, expandable for audit

## Session State

```
ScreeningSession:
- session_id (unique)
- current_index (safe bounds)
- articles (list)
- protocol_version
- stage (ec/ic/qc)
- ec_completed (count)
- ic_completed (count)
- qc_completed (count)
```

## Reproducibility Requirements

For same screening session reproducibility:
- Protocol version hash
- Article order (deterministic sort)
- Sampling seed (MD5-based)
- LLM model (fixed version)
- All calibration events logged