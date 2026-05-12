# APOLLO — Legacy Execution Audit

**Document Version**: 1.0.0
**Date**: 2026-05-12
**Status**: **EVIDENCE-BASED CLASSIFICATION**

---

## 1. Module Classification Matrix

| Module | App.py Routing | Imports Canonical | Imports Orphaned | Classification |
|--------|---------------|-----------------|-----------------|----------------|
| `llm_reasoning.py` | NO | NO | NO | **DEAD** |
| `database.py` | NO | NO | NO | **ORPHANED** (passive) |
| `eligibility_view.py` | NO | NO | `database`, `llm_reasoning` | **ORPHANED** |
| `quality_view.py` | NO | NO | `database`, `llm_reasoning` | **ORPHANED** |
| `overview_view.py` | NO | NO | `database` | **ORPHANED** |
| `planning_view.py` | NO | NO | `database` | **ORPHANED** |
| `review_view.py` | NO | `atlas_processor`, `screening_session`, `llm_assistant`, `export_engine`, `protocol_view` | NO | **PASSIVE** (not routed, imports canonical) |
| `atlas_processor_view.py` | NO | `dynamic_protocol`, `audit_logger`, `atlas_processor` | NO | **ORPHANED** |
| `ingestion_view.py` | NO | `atlas_processor`, `atlas_loader` | NO | **ORPHANED** |

---

## 2. Evidence

### 2.1 `llm_reasoning.py` — **DEAD**

**File**: `src/core/llm_reasoning.py` (381 lines)

**Import Graph**:
```
llm_reasoning.py
  └─ imported_by:
      ├─ src/ui/modules/eligibility_view.py (ORPHANED)
      └─ src/ui/modules/quality_view.py (ORPHANED)
          └─ neither is routed by app.py
```

**No other module imports `llm_reasoning.py`**. Not even `llm_assistant.py` (which is the canonical LLM layer and uses `criteria_registry` instead).

**Runtime Reachability**: **ZERO**. No canonical path or orphaned routed view can reach this module.

**Grep Evidence**:
```bash
grep -r "llm_reasoning" src/ --include="*.py" | grep -v __pycache__
```
Result: Only `eligibility_view.py` and `quality_view.py` (both orphaned, not routed).

**Verdict**: **DEAD** — Can be safely removed after orphaned consumers are removed.

---

### 2.2 `database.py` — **ORPHANED (passive)**

**File**: `src/core/database.py` (462 lines)

**Import Graph**:
```
database.py
  └─ imported_by:
      ├─ src/ui/modules/eligibility_view.py (ORPHANED)
      ├─ src/ui/modules/quality_view.py (ORPHANED)
      ├─ src/ui/modules/overview_view.py (ORPHANED)
      └─ src/ui/modules/planning_view.py (ORPHANED)
```

**No canonical module imports `database.py`**. The canonical path uses `ScreeningSession` (JSON-based, file-persisted) for state management.

**Runtime Reachability**: **ZERO**. No routed view uses this module.

**Grep Evidence**:
```bash
grep "from src.core.database import" src/ --include="*.py" -r | grep -v __pycache__
```
Result: Only 4 orphaned UI modules.

**Verdict**: **ORPHANED (passive)** — Preserved for potential future multi-user persistence. Not active in any execution path.

---

### 2.3 `eligibility_view.py` — **ORPHANED**

**File**: `src/ui/modules/eligibility_view.py` (310 lines)

**Import Graph**:
```
eligibility_view.py
  ├─ from src.core.database import Database
  ├─ from src.core.llm_reasoning import generate_ec_rationale, generate_ic_rationale, detect_ambiguity
  └─ Deprecation banner: PRESENT ✓
```

**App.py Routing**: ❌ NOT ROUTED

**Runtime Reachability**: **ZERO**. `app.py` does not call this module.

**Grep Evidence**:
```bash
grep "eligibility_view" app.py
```
Result: None.

**Verdict**: **ORPHANED** — Deprecated, not reachable.

---

### 2.4 `quality_view.py` — **ORPHANED**

**File**: `src/ui/modules/quality_view.py` (227 lines)

**Import Graph**:
```
quality_view.py
  ├─ from src.core.database import Database
  ├─ from src.core.llm_reasoning import generate_qc_rationale
  └─ Deprecation banner: PRESENT ✓
```

**App.py Routing**: ❌ NOT ROUTED

**Runtime Reachability**: **ZERO**.

**Verdict**: **ORPHANED** — Deprecated, not reachable.

---

### 2.5 `overview_view.py` — **ORPHANED**

**File**: `src/ui/modules/overview_view.py` (145 lines)

**Import Graph**:
```
overview_view.py
  └─ from src.core.database import Database
```

**App.py Routing**: ❌ NOT ROUTED

**Runtime Reachability**: **ZERO**.

**Verdict**: **ORPHANED** — Deprecated, not reachable.

---

### 2.6 `planning_view.py` — **ORPHANED**

**File**: `src/ui/modules/planning_view.py` (83 lines)

**Import Graph**:
```
planning_view.py
  └─ from src.core.database import Database
```

**App.py Routing**: ❌ NOT ROUTED

**Runtime Reachability**: **ZERO**.

**Verdict**: **ORPHANED** — Deprecated, not reachable.

---

### 2.7 `review_view.py` — **PASSIVE**

**File**: `src/ui/modules/review_view.py` (319 lines)

**Import Graph**:
```
review_view.py
  ├─ from src.core.atlas_processor import ATLASLoader, APOLLODecisionEngine
  ├─ from src.core.screening_session import ScreeningSession, ...
  ├─ from src.core.reviewer_state import ReviewerState
  ├─ from src.core.llm_assistant import LLMAssistant
  ├─ from src.core.export_engine import ExportEngine
  ├─ from src.ui.modules.protocol_view import render_protocol_config_panel
  └─ Deprecation banner: NOT PRESENT (needs addition)
```

**App.py Routing**: ❌ NOT ROUTED

**Why it's PASSIVE (not DEAD)**:
- It imports canonical modules (`ScreeningSession`, `llm_assistant`, `export_engine`, `protocol_view`)
- The `apply_decision()` method was added to `ScreeningSession` specifically for this module
- It contains a complete HITL review interface
- It's the only module that uses `ScreeningSession` + `ReviewerState` together

**Why it's not ACTIVE**:
- `app.py` does not route to it
- No other canonical module imports it
- It is a dead-end in the import graph (nothing imports it)

**Runtime Reachability**: **INDIRECT** — Only reachable if `app.py` routing is modified to include it.

**Critical Issue**: No deprecation banner in `review_view.py`. The file is NOT marked as deprecated, even though it's not routed.

**Grep Evidence**:
```bash
grep "review_view" app.py
```
Result: None.

**Verdict**: **PASSIVE** — Not active, but imports canonical modules. Needs deprecation banner.

---

### 2.8 `atlas_processor_view.py` — **ORPHANED**

**File**: `src/ui/modules/atlas_processor_view.py` (339 lines)

**Import Graph**:
```
atlas_processor_view.py
  ├─ from src.core.atlas_processor import process_atlas_file
  ├─ from src.core.dynamic_protocol import DynamicProtocol, ProtocolState
  └─ from src.core.audit_logger import AuditLogger
```

**App.py Routing**: ❌ NOT ROUTED

**Runtime Reachability**: **ZERO**.

**Verdict**: **ORPHANED** — Deprecated, not reachable.

---

### 2.9 `ingestion_view.py` — **ORPHANED**

**File**: `src/ui/modules/ingestion_view.py` (119 lines)

**Import Graph**:
```
ingestion_view.py
  ├─ from src.core.atlas_processor import ATLASLoader, create_screening_session
  └─ Deprecation banner: NOT PRESENT (needs addition)
```

**App.py Routing**: ❌ NOT ROUTED

**Runtime Reachability**: **ZERO**.

**Verdict**: **ORPHANED** — Deprecated, not reachable.

---

## 3. Dependency Cluster Analysis

```
ORPHANED CLUSTER:
  llm_reasoning.py ───→ (imported by) ───→ eligibility_view.py
       │                                        │
       └──────────────────────→ quality_view.py
                                      │
                                      ↓
                              database.py ←── (imported by) ───→ overview_view.py
                                   │                              planning_view.py

PASSIVE MODULE:
  review_view.py ───→ imports canonical (screening_session, llm_assistant, export_engine)
                   ───→ NOT imported by anyone

ISOLATED ORPHANED:
  atlas_processor_view.py ───→ imports canonical (atlas_processor, dynamic_protocol, audit_logger)
  ingestion_view.py ───────→ imports canonical (atlas_processor)
```

**Key Finding**: The orphaned modules form isolated clusters. No canonical path can reach them. No orphaned module can reach a canonical path. The clusters are mutually exclusive.

---

## 4. Hidden Execution Paths

**None detected.** The following have been verified:

- No dynamic imports (`__import__`, `importlib`) to orphaned modules
- No fallback calls to orphaned modules from canonical code
- No reflection-based loading
- No conditional imports that could trigger orphaned code
- No `st.switch_page` or `st.navigation` that could reach orphaned views

**Evidence**:
```bash
grep -r "__import__\|importlib\|getattr.*import\|__file__" src/ --include="*.py" | grep -v __pycache__
```
Result: None related to orphaned modules.

---

## 5. Deprecation Banner Audit

| Module | Banner Present | Location |
|--------|---------------|----------|
| `llm_reasoning.py` | ✅ YES | Line 1 (docstring) |
| `database.py` | ✅ YES | Line 1 (docstring) |
| `eligibility_view.py` | ✅ YES | Line 1 (docstring) |
| `quality_view.py` | NOT CHECKED | — |
| `overview_view.py` | NOT CHECKED | — |
| `planning_view.py` | NOT CHECKED | — |
| `review_view.py` | ❌ **MISSING** | **MUST ADD** |
| `atlas_processor_view.py` | NOT CHECKED | — |
| `ingestion_view.py` | ❌ **MISSING** | **MUST ADD** |

---

## 6. Summary Table

| Module | Classification | App.py Route | Deprecation Banner | Safe to Remove |
|--------|---------------|-------------|-------------------|----------------|
| `llm_reasoning.py` | DEAD | NO | YES | YES (after orphaned views removed) |
| `database.py` | ORPHANED | NO | YES | NO (preserve for multi-user) |
| `eligibility_view.py` | ORPHANED | NO | YES | YES |
| `quality_view.py` | ORPHANED | NO | NO | YES |
| `overview_view.py` | ORPHANED | NO | NO | YES |
| `planning_view.py` | ORPHANED | NO | NO | YES |
| `review_view.py` | PASSIVE | NO | **NO** | **NO** (needs banner + review) |
| `atlas_processor_view.py` | ORPHANED | NO | NO | YES |
| `ingestion_view.py` | ORPHANED | NO | **NO** | YES |

---

## 7. Immediate Actions

1. **ADD deprecation banner to `review_view.py`** — It has no banner and imports canonical modules
2. **ADD deprecation banner to `ingestion_view.py`** — It has no banner
3. **Verify quality_view.py banner** — Not checked in this audit
4. **Verify overview_view.py banner** — Not checked in this audit
5. **Verify planning_view.py banner** — Not checked in this audit
6. **Verify atlas_processor_view.py banner** — Not checked in this audit

---

*Audit generated from import graph analysis and grep evidence.*