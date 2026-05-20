# APOLLO Evaluation Protocol

## Purpose

This document provides a standardized protocol for conducting controlled empirical evaluations of APOLLO.

## Prerequisites

Before conducting evaluation:

1. **Protocol Configuration**
   - Define EC, IC, QC criteria
   - Lock protocol version
   - Record protocol hash

2. **Dataset Preparation**
   - Import articles from source
   - Verify dataset integrity
   - Record dataset hash

3. **System Configuration**
   - Select LLM model
   - Set temperature (recommended: 0.1)
   - Configure advisory pipeline

## Evaluation Conditions

### Condition 1: Manual-Only (Baseline)

**Description**: Reviewers screen articles without AI assistance.

**Procedure**:
1. Load articles
2. Display article metadata + abstract
3. Reviewer makes INCLUDE/EXCLUDE decision
4. Record decision timestamp

**Purpose**: Establish baseline performance.

### Condition 2: Advisory-Assisted

**Description**: Reviewers screen with AI advisory visible.

**Procedure**:
1. Load articles with pre-computed advisories
2. Display article + advisory
3. Reviewer can approve or override
4. Record decision, override reason if applicable

**Purpose**: Measure advisory utility.

### Condition 3: Risk-Based (Full APOLLO)

**Description**: Full APOLLO workflow with queue prioritization.

**Procedure**:
1. Configure risk thresholds
2. Enable queue filtering
3. Review articles by priority
4. Use calibration tracking

**Purpose**: Measure end-to-end workflow.

## Required Metrics

### Primary Metrics

1. **Agreement Rate**
   - Proportion of reviewer decisions matching AI advisory
   - Formula: (agreements / total) × 100%

2. **Workload Reduction**
   - Proportion of articles auto-screened
   - Formula: (auto-accepted / total) × 100%

3. **Override Rate**
   - Proportion of reviewer decisions overriding AI
   - Formula: (overrides / total) × 100%

### Secondary Metrics

4. **False Exclusion Estimate**
   - Articles AI excluded but human included

5. **False Inclusion Estimate**
   - Articles AI included but human excluded

6. **Escalation Rate**
   - Proportion of articles escalated for manual review

7. **Throughput**
   - Articles reviewed per minute

8. **Override Severity Distribution**
   - LOW/MEDIUM/HIGH/CRITICAL breakdown

## Data Collection

### Required Data Points

Per review decision, record:
- Article ID
- Protocol version
- Stage (EC/IC/QC)
- AI advisory decision
- AI confidence score
- Human decision
- Disagreement (Y/N)
- Override severity (if applicable)
- Override reason (if applicable)
- Review time (seconds)
- Risk classification
- Validation queue

### Export Format

Export to CSV with columns:
```
article_id, protocol_version, stage, advisory_decision, 
advisory_confidence, human_decision, disagreement, 
override_severity, override_reason, risk_classification,
validation_queue, elapsed_time_seconds, reviewer_id, timestamp
```

## Sample Size Guidelines

Minimum recommended:

| Metric | Minimum |
|--------|---------|
| Total articles | 500 |
| High-risk articles | 50 |
| Low-risk articles | 100 |
| Reviewers | 2 (for inter-rater reliability) |

## Analysis Requirements

1. Calculate 95% confidence intervals
2. Report effect sizes where applicable
3. Conduct subgroup analysis by risk level
4. Compare across conditions

## Reporting Checklist

- [ ] Protocol version and hash
- [ ] Dataset characteristics
- [ ] LLM model and version
- [ ] Sample size
- [ ] All primary metrics with CI
- [ ] Secondary metrics
- [ ] Limitations acknowledged
- [ ] Reproducibility artifacts (hashes)