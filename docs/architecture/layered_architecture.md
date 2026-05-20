# APOLLO Layered Architecture

## Overview

APOLLO follows a strictly layered architecture to ensure:
- Maintainability
- Testability
- Reproducibility
- Scientific defensibility

## Architectural Layers

### 1. Protocol Layer (`src/core/dynamic_protocol.py`, `src/core/protocol_service.py`)

**Responsibility**: Protocol definition, validation, and state management.

**Components**:
- Protocol definitions (EC, IC, QC criteria)
- Protocol state machine (DRAFT → LOCKED)
- Protocol hashing for reproducibility
- Protocol version tracking

**Boundary**: 
- Inputs: Protocol configuration
- Outputs: Validated protocol for screening

### 2. Advisory Layer (`src/advisory/advisory_worker.py`, `src/advisory/advisory_models.py`)

**Responsibility**: AI advisory generation and validation.

**Components**:
- LLM advisory generation (advisory_worker.py)
- Advisory models (advisory_models.py)
- Grounding validation (validate_grounding)
- Hallucination detection (compute_hallucination_risk)
- Confidence scoring

**Boundary**:
- Inputs: Article, protocol criteria, metadata
- Outputs: AdvisoryResult with decision, confidence, grounding

**Constraint**: Advisory is ADVISORY ONLY - cannot finalize decisions.

### 3. Risk Layer (`src/advisory/queue_manager.py`)

**Responsibility**: Risk classification and queue routing.

**Components**:
- RiskClassification enum (LOW_RISK, MEDIUM_RISK, HIGH_RISK, CRITICAL_REVIEW)
- ValidationQueue routing (AUTO_ACCEPT, AUTO_EXCLUDE, PRIORITY_REVIEW)
- Deterministic sampling (MD5 hash-based)
- Queue filtering

**Boundary**:
- Inputs: AdvisoryResult, article metadata
- Outputs: ValidationQueue assignment, risk classification

### 4. Calibration Layer (`src/advisory/calibration_tracker.py`, `src/core/calibration_engine.py`)

**Responsibility**: Disagreement tracking and agreement metrics.

**Components**:
- CalibrationEvent logging
- Agreement rate computation
- Override severity tracking
- False inclusion/exclusion estimation

**Boundary**:
- Inputs: Human decision, AI decision, metadata
- Outputs: Calibration summary metrics

### 5. Workflow Layer (`src/core/workflow.py`, `src/core/screening_session.py`)

**Responsibility**: Session state, navigation, review modes.

**Components**:
- ScreeningSession management
- Current index tracking
- Review mode (FOCUSED_RISK_REVIEW, SEQUENTIAL_REVIEW, CALIBRATION_REVIEW)
- Queue transitions

**Boundary**:
- Inputs: User actions (next, prev, queue filter)
- Outputs: Updated session state

### 6. Audit Layer (`src/core/audit_logger.py`, `src/core/reproducibility_engine.py`)

**Responsibility**: Append-only logging, deterministic traces.

**Components**:
- Audit event logging
- Reproducibility tracking
- Session lineage
- Provenance tracking

**Boundary**:
- Inputs: All system events
- Outputs: Immutable audit log

### 7. UI Layer (`src/ui/modules/`, `src/ui/components.py`)

**Responsibility**: Rendering only - declarative display.

**Components**:
- EC screening view
- IC screening view
- Calibration view
- Theme and styling

**Boundary**:
- Inputs: Session state, articles, advisories
- Outputs: Streamlit components

**Constraint**: No business logic, no protocol logic, no risk logic.

## Data Flow

```
Protocol (LOCKED)
    ↓
Article + Criteria → Advisory Layer → AdvisoryResult
    ↓
Risk Layer → RiskClassification + ValidationQueue
    ↓
Workflow Layer (queue filter, navigation)
    ↓
UI Layer (render advisory card, queue summary)
    ↓
User Review (Approve/Override/Escalate)
    ↓
Calibration Layer (log disagreement)
    ↓
Audit Layer (append-only log)
```

## Layer Dependencies

- UI → Workflow → Risk → Advisory → Protocol
- Calibration → Advisory
- Audit → All layers (observational)

## Testability

Each layer should be testable independently:
- Protocol: Unit test protocol locking
- Advisory: Unit test grounding validation
- Risk: Unit test risk classification
- Calibration: Unit test event logging
- Workflow: Integration test navigation
- Audit: Unit test log appending
- UI: Visual/regression test only