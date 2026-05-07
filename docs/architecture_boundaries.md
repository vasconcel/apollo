# APOLLO Architecture Boundaries

## Overview

APOLLO is a deterministic screening engine for systematic literature review (SLR) in Software Engineering recruitment & selection (R&S) domain. This document defines the architectural boundaries and responsibilities of APOLLO and its future companion system HERMES.

## APOLLO Responsibilities

APOLLO handles the following within the SLR pipeline:

1. **Article Ingestion**
   - Load ATLAS Excel exports (WL and GL sheets)
   - Validate input schema before processing
   - Normalize column names and handle missing data

2. **EC/IC/QC Evaluation**
   - **Exclusion Criteria (EC)**: Apply EC1-EC4 rules
   - **Inclusion Criteria (IC)**: Apply IC1-IC3 rules  
   - **Quality Criteria (QC)**: Apply WL-Q1-Q4 or GL-Q1-Q4 scoring with threshold ≥2.0

3. **Selection and Export**
   - Generate single clean Excel export with deterministic column structure
   - WL sheet: Library, Global_ID, Local_ID, Title, Abstract, Keywords, CIs1, CEs1, Revisor 1, CIs2, CEs2, Revisor 2, Decision
   - GL sheet: Posicao, Title, URL, Source_File, Revisor 1 EC, Revisor 1 IC, Decision
   - WL Seeds for HERMES: Empty placeholder for future system

4. **Traceability Preparation**
   - Include stable identifiers (Global_ID, Local_ID)
   - Maintain decision chain (EC → IC → QC → final)
   - Prepare metadata for downstream systems

5. **Auditability and Reproducibility**
   - Deterministic processing (no randomness)
   - Protocol versioning
   - Audit logging (logs/apollo_run_*.json)
   - Regression test suite

## HERMES Responsibilities (Future System)

The future HERMES system will handle:

1. **Snowballing Execution**
   - Forward snowballing (find papers citing selected papers)
   - Backward snowballing (find references in selected papers)
   - Citation network analysis
   - Recursive article discovery

2. **Extended Search**
   - Cross-database crawling
   - Metadata enrichment
   - DOI resolution

3. **Citation Scoring**
   - Citation count aggregation
   - Network-based relevance scoring
   - Similarity metrics

## Why Snowballing is Intentionally Excluded from APOLLO

### 1. Determinism Requirements

APOLLO is designed as a **pure deterministic screening engine**:
- Same input + same protocol = same output, every time
- No nondeterministic behavior (no random sampling, no API calls)
- Reproducible scientific results

Snowballing introduces inherent nondeterminism:
- Citation databases change over time
- Network traversal order affects results
- Recursive discovery creates unbounded iteration
- Different runs may discover different papers

### 2. Bounded Context

APOLLO scope is **bounded evaluation**:
- Fixed input set → fixed output set
- Clear termination conditions (all articles processed)
- Predictable resource usage

Snowballing creates **unbounded exploration**:
- Each discovery can lead to more discoveries
- No natural termination point
- Resource usage grows exponentially

### 3. Pipeline Separation

```
┌─────────────┐    ┌─────────────┐
│   APOLLO    │───▶│   HERMES    │
│  (bounded)  │    │ (unbounded) │
└─────────────┘    └─────────────┘
     │                   │
     ▼                   ▼
Selection seeds    Citation expansion
for HERMES         by HERMES
```

APOLLO produces a **closed set** of selected papers as seeds. HERMES receives these seeds and performs the unbounded citation expansion.

### 4. Reproducibility Argument

For systematic literature reviews:
- **APOLLO selection is reproducible**: Same seeds, same criteria, same results
- **HERMES expansion is logged**: Each HERMES run can be audited by recording which citations were followed

This separation allows:
- Audit trail of which papers were selected by APOLLO
- Reproducible HERMES runs by fixing database snapshots
- Clear responsibility boundaries

## Protocol System

APOLLO supports configurable EC/IC/QC via protocol engine:

- **Default protocol**: Hardcoded logic matching original APOLLO behavior
- **Custom protocol**: JSON/YAML protocol files for user-defined criteria
- **Semantic parity**: `default_behavior == protocol(get_default_protocol())` with zero tolerance

Protocol benefits:
- Configurability without code changes
- Protocol versioning and checksum
- User-defined EC/IC/QC criteria
- Future protocol DSL support

## Input Validation

APOLLO enforces strict input validation:

- **WL required columns**: Library, Global_ID, Local_ID, Title, Abstract, Keywords
- **GL required columns**: Posicao, Title, URL, Source_File
- **Fail-fast**: Clear error messages on missing columns
- **No silent failures**: Schema validation before any processing

## Audit Logging

Each APOLLO run produces a deterministic log:

```
logs/apollo_run_<timestamp>.json
```

Contents:
- Protocol used (name, version, checksum)
- Input filename and row counts
- Duplicate detection counts
- EC/IC/QC statistics (passed/failed per criterion)
- Execution duration
- Determinism hash (input + protocol → output)
- Export checksum

**Strict rules**:
- No LLM reasoning leakage
- No article full text dumps
- No nondeterministic timestamps in reproducibility hash

## Dashboard Readiness

APOLLO produces metrics ready for dashboard consumption:

### Core Metrics
- Total articles processed
- WL included/excluded counts
- GL included/excluded counts
- QC score distribution
- EC/IC failure distribution
- Processing progress percentage
- Deterministic run hash
- Protocol version/checksum

### Research Metrics
- Inclusion rate
- Exclusion rate  
- Duplicate rate
- QC average score
- GL/WL ratio
- Top exclusion reasons

### Protocol Metrics
- Active protocol name and version
- Protocol checksum
- Criteria version
- Reproducibility verification status
- Protocol parity test status

## Integration Points with HERMES

APOLLO provides clean interfaces for HERMES:

1. **WL Seeds Export**: "WL Seeds for HERMES" sheet in Excel output
   - Contains selected WL papers as candidate seeds
   - Stable identifiers (Global_ID) for citation lookup
   - Currently empty (placeholder for future)

2. **Protocol Interface**: 
   - APOLLO criteria version exposed in audit logs
   - HERMES can query which EC/IC/QC criteria were applied

3. **Audit Trail**:
   - Each APOLLO run logged with determinism hash
   - HERMES runs can reference which APOLLO selection they extend

## Conclusion

APOLLO is a bounded, deterministic screening engine. Snowballing belongs to the unbounded exploration domain and is intentionally delegated to the future HERMES system. This separation ensures:
- Reproducible selection
- Clear audit boundaries
- Scalable architecture
- Future extensibility