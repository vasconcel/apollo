# APOLLO — Orphan Module Audit

**Document Version**: 1.0.0
**Date**: 2026-05-12
**Status**: **DEPRECATION RECORD**

---

## 1. Module Classification

| Module | Classification | Routed By | Verdict |
|--------|----------------|-----------|--------|
| `llm_reasoning.py` | **DEPRECATED** | `eligibility_view.py`, `quality_view.py` (both orphaned) | Deprecated — replaced by `llm_assistant.py` |
| `database.py` | **ORPHANED (runtime)** | `eligibility_view.py`, `quality_view.py`, `overview_view.py`, `planning_view.py` (all orphaned) | Runtime path orphaned — not part of canonical path |
| `eligibility_view.py` | **ORPHANED** | None (`app.py` does not route it) | Deprecated UI module |
| `quality_view.py` | **ORPHANED** | None | Deprecated UI module |
| `overview_view.py` | **ORPHANED** | None | Deprecated UI module |
| `planning_view.py` | **ORPHANED** | None | Deprecated UI module |
| `atlas_processor_view.py` | **ORPHANED** | None | Deprecated UI module |
| `app/main.py` | **LEGACY** | Standalone | Separate legacy application |

---

## 2. Detailed Findings

### 2.1 `llm_reasoning.py` — DEPRECATED

**File**: `src/core/llm_reasoning.py` (381 lines)

**Usage Audit**:
```
grep "import.*llm_reasoning" src/ -> eligibility_view.py, quality_view.py
grep "from.*llm_reasoning" src/ -> same
```

**Called by**:
- `src/ui/modules/eligibility_view.py` (line 36): `from src.core.llm_reasoning import generate_ec_rationale, generate_ic_rationale, detect_ambiguity`
- `src/ui/modules/quality_view.py` (line 53): `from src.core.llm_reasoning import generate_qc_rationale`

**Neither of these views is routed by `app.py`**. They are completely orphaned from the routing layer.

**What it does**:
- Provides `generate_ec_rationale()`, `generate_ic_rationale()`, `generate_qc_rationale()` — LLM-powered rationale generation
- Provides `detect_ambiguity()` — ambiguity flag detection

**Why it's deprecated**:
- `llm_assistant.py` provides the same functionality (`suggest_ec`, `suggest_ic`, `suggest_qc`) in a cleaner, dataclass-based API
- `llm_assistant.py` is the **authoritative** LLM layer (as defined in CANONICAL_RUNTIME_PATH.md)
- `llm_reasoning.py` uses a different model (`llama-3.1-70b-versatile`) vs `llm_assistant.py` (`llama-3.3-70b-versatile`)
- `llm_reasoning.py` has no `__init__.py` exports
- Its functions duplicate `llm_assistant.py` functionality with different signatures

**Action**: DEPRECATED. Do not use. Will be removed in a future version.

---

### 2.2 `database.py` — ORPHANED (runtime path)

**File**: `src/core/database.py` (462 lines)

**Usage Audit**:
```
grep "import.*database" src/ ->
  overview_view.py (lines 9, 16)
  eligibility_view.py (lines 12, 35)
  quality_view.py (lines 15, 52)
  planning_view.py (lines 10, 16)
```

All consumers are **orphaned UI modules** not routed by `app.py`.

**What it provides**:
- SQLite-backed article storage
- Eligibility decision storage (EC/IC)
- Quality assessment storage
- Statistics queries
- Export methods

**Why it's orphaned**:
- The canonical path uses `ScreeningSession` for state management (JSON-based, file-persisted)
- `database.py` is a completely separate persistence layer
- No canonical module imports it
- Not referenced by any routed view

**Note**: This module may be useful for multi-user scenarios or persistent storage in future versions. For now, it is **orphaned but not deleted** to preserve potential future utility.

**Action**: ORPHANED. Not part of current canonical path. Kept for potential future use.

---

### 2.3 Orphaned UI Modules

| Module | Lines | Uses | Not Routed Because |
|--------|-------|------|-------------------|
| `eligibility_view.py` | 310 | `database.py`, `llm_reasoning.py` | Superseded by stage-specific screens |
| `quality_view.py` | 227 | `database.py`, `llm_reasoning.py` | Superseded by `qc_assessment_view.py` |
| `overview_view.py` | 145 | `database.py` | Dashboard-style view not in routing |
| `planning_view.py` | 83 | `database.py` | Planning view not in routing |
| `atlas_processor_view.py` | 339 | None | Standalone processing UI |

**Why they're orphaned**:
- `app.py` routes to: `protocol_view`, `ec_screening_view`, `ic_screening_view`, `qc_assessment_view`, `calibration_view`, `export_view`
- All other UI modules are loaded as sub-imports within routed views (e.g., `overview_view` imports `protocol_view` internally)
- These views were created during development but never integrated into the routing

**Action**: ORPHANED. Not deleted — may contain useful patterns or future features. Each module is marked with a deprecation comment.

---

## 3. Deprecation Instructions

### For `llm_reasoning.py`
```
DO NOT USE for new features.
Migrate to: src.core.llm_assistant.LLMAssistant
Canonical replacement methods:
  generate_ec_rationale -> llm.suggest_ec()
  generate_ic_rationale -> llm.suggest_ic()
  generate_qc_rationale -> llm.suggest_qc()
  detect_ambiguity -> check suggestion.ambiguity_flags
```

### For `database.py`
```
DO NOT USE for new features without architectural review.
This module is not part of the canonical ScreeningSession path.
Current canonical path: ScreeningSession (JSON-based, file-persisted).
Future use cases: multi-user sync, persistent storage.
```

### For orphaned UI modules
```
DO NOT ADD new features to orphaned UI modules.
The canonical UI path is defined in CANONICAL_RUNTIME_PATH.md.
If a feature is needed, implement it in the canonical path.
```

---

## 4. Import Evidence

```bash
# llm_reasoning.py consumers
grep -r "llm_reasoning" src/ --include="*.py"
# Result: ONLY eligibility_view.py and quality_view.py

# database.py consumers
grep -r "from src.core.database import" src/ --include="*.py"
# Result: ONLY overview_view.py, eligibility_view.py, quality_view.py, planning_view.py

# None of the above are routed by app.py
grep -E "eligibility_view|quality_view|overview_view|planning_view" app.py
# Result: NONE
```

---

## 5. Future Cleanup Plan

| Phase | Action | Target |
|-------|--------|--------|
| Future | Remove `llm_reasoning.py` | After migration of remaining consumers |
| Future | Remove orphaned UI modules | After confirmation no routing needed |
| Future | Re-evaluate `database.py` | If multi-user features needed |
| Future | Remove `app/main.py` | If legacy app is fully superseded |

**Note**: No module has been deleted in this sprint. All orphaned modules are marked with deprecation comments but remain in the codebase for reference and potential future use.

---

*This document is the authoritative orphan module audit record.*
