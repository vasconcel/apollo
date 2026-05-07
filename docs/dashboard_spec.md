# APOLLO Dashboard Specification

## Overview

This document defines the dashboard specifications for APOLLO. The dashboard will display key metrics from APOLLO processing runs, enabling users to understand selection outcomes, protocol details, and system status.

**IMPORTANT**: This is a design specification only. ML/AI features are NOT implemented in current APOLLO version - they are defined as future hooks.

## Dashboard Layout

### Header Section
- APOLLO logo/title
- Current version
- Protocol version in use
- Last run timestamp

### Core Metrics Panel

#### Processing Overview
| Metric | Description |
|--------|-------------|
| Total Articles | Sum of WL + GL articles in input |
| WL Processed | Number of White Literature articles processed |
| GL Processed | Number of Grey Literature articles processed |
| Remaining | Articles not yet processed (for batch processing) |
| Processing Progress % | (Processed / Total) * 100 |

#### Selection Results
| Metric | Description |
|--------|-------------|
| WL Included | Number of WL articles passing EC → IC → QC |
| WL Excluded | Number of WL articles failing any stage |
| GL Included | Number of GL articles passing EC |
| GL Excluded | Number of GL articles failing EC |

#### QC Distribution (WL only)
| Score Range | Count |
|-------------|-------|
| 4.0/4 (Full) | Number of articles with QC score 4.0 |
| 3.0-3.5 | Number of articles with QC score 3.0-3.5 |
| 2.0-2.5 | Number of articles with QC score 2.0-2.5 |
| < 2.0 | Number of articles below QC threshold |
| N/A | Articles not reaching QC stage |

#### EC/IC Failure Distribution
| Criterion | WL Count | GL Count |
|-----------|----------|----------|
| EC1 (No SE context) | N | N |
| EC2 (Pre-2015) | N | N |
| EC3 (No abstract) | N | N/A |
| EC4 (Duplicate) | N | N/A |
| IC1 (No R&S) | N | N/A |
| IC2 (No empirical) | N | N/A |

### Research Metrics Panel

#### Key Ratios
| Metric | Formula | Display |
|--------|---------|---------|
| Inclusion Rate | (WL Included + GL Included) / Total | X% |
| Exclusion Rate | (WL Excluded + GL Excluded) / Total | X% |
| Duplicate Rate | EC4 Count / Total WL | X% |
| QC Average | Sum(WL QC Scores) / WL Included | X.X |
| GL/WL Ratio | GL Processed / WL Processed | X:1 |

#### Top Exclusion Reasons
- List top 5 EC/IC failure reasons with counts
- Sort by frequency descending

### Protocol/Model Metrics Panel

#### Current Protocol
| Field | Description |
|-------|-------------|
| Protocol Name | e.g., "Default APOLLO Protocol" or custom name |
| Protocol Version | e.g., "1.0" |
| Protocol Checksum | SHA256 hash of protocol definition |
| EC Criteria Count | Number of EC rules |
| IC Criteria Count | Number of IC rules |
| QC Criteria Count | Number of QC rules |
| QC Threshold | Current threshold (default 2.0) |

#### Reproducibility
| Field | Description |
|-------|-------------|
| Determinism Hash | SHA256(input + protocol → output) |
| Last Run ID | Unique run identifier |
| Reproducibility Status | PASS/FAIL |
| Parity Test Status | PASS/FAIL (tests default == protocol) |

### (DESIGN ONLY) Future ML Metrics Panel

**WARNING**: These metrics are NOT implemented in current version. This section defines future hooks.

#### Confidence Estimation (Future)
| Metric | Description |
|--------|-------------|
| EC Confidence | Estimated confidence in EC decision |
| IC Confidence | Estimated confidence in IC decision |
| QC Confidence | Estimated confidence in QC score |

#### Agreement Metrics (Future)
| Metric | Description |
|--------|-------------|
| Agreement Score | Inter-rater agreement (if multiple reviewers) |
| Disagreement Alerts | Cases where criteria decisions conflict |

#### Precision/Recall (Future)
| Metric | Description |
|--------|-------------|
| Estimated Precision | Predicted precision of selection |
| Estimated Recall | Predicted recall of relevant papers |

#### Human Override (Future)
| Metric | Description |
|--------|-------------|
| Override Count | Number of manual decision overrides |
| Override Rate | Override Count / Total decisions |

## Implementation Notes

### Data Sources
- Core metrics from `APOLLODecisionEngine.process_wl_articles()` and `process_gl_articles()`
- Protocol metrics from `get_default_protocol()` and audit logs
- QC distribution computed from `QualityCriteria.evaluate()` results

### Dashboard Updates
- Real-time update during batch processing
- Static display for completed runs
- Historical trends (future enhancement)

### Design Principles
1. **No randomness**: All displayed metrics are deterministic
2. **Clear provenance**: Each metric shows source (EC/IC/QC/log)
3. **Fail-fast**: Invalid states clearly indicated (red/warning)
4. **Audit-ready**: All metrics can be traced to input + protocol

### Future Integration Points
- HERMES status indicator (when HERMES is active)
- Snowballing progress (future HERMES integration)
- Citation network metrics (future)

## Example Dashboard JSON Output

```json
{
  "header": {
    "version": "1.0.0",
    "protocol": "Default APOLLO Protocol",
    "last_run": "2024-01-15T10:30:00Z"
  },
  "core_metrics": {
    "total_articles": 31,
    "wl_processed": 21,
    "gl_processed": 10,
    "wl_included": 9,
    "wl_excluded": 12,
    "gl_included": 0,
    "gl_excluded": 10
  },
  "qc_distribution": {
    "full_4": 3,
    "good_3": 4,
    "marginal_2": 2,
    "below_threshold": 12
  },
  "ec_ic_failures": {
    "EC1": 5,
    "EC2": 2,
    "EC3": 3,
    "EC4": 2,
    "IC1": 4,
    "IC2": 2
  },
  "research_metrics": {
    "inclusion_rate": 0.29,
    "exclusion_rate": 0.71,
    "duplicate_rate": 0.095,
    "qc_average": 2.8,
    "gl_wl_ratio": 0.476
  },
  "protocol": {
    "name": "Default APOLLO Protocol",
    "version": "1.0",
    "checksum": "a1b2c3d4...",
    "ec_count": 4,
    "ic_count": 3,
    "qc_count": 4,
    "threshold": 2.0
  },
  "reproducibility": {
    "hash": "e5f6g7h8...",
    "run_id": "run_20240115_103000",
    "status": "PASS"
  }
}
```

## Conclusion

This dashboard specification provides comprehensive visibility into APOLLO processing while maintaining deterministic, reproducible metrics. The ML/AI metrics section defines future hooks without implementing them in the current version.