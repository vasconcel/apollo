# APOLLO — Canonical Runtime Path

**Document Version**: 1.0.0
**Date**: 2026-05-12
**Status**: **AUTHORITATIVE** — This document defines the single canonical execution flow for APOLLO.

---

## 1. Execution Flow Diagram

```
                          ┌──────────────────┐
                          │     app.py        │
                          │  (Streamlit UI)   │
                          │  Entry Point     │
                          └────────┬─────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │         SIDEBAR              │
                    │   Navigation Radio           │
                    └──────────────┬──────────────┘
                                   │
          ┌────────────────────────┴────────────────────────┐
          │                                                 │
          ▼                                                 ▼
   "Protocol Configuration"                    "EC Screening"
  protocol_view.py:556                       ec_screening_view.py:487
  (REQUIRED — always first)                  (Stage 1: Exclusion)
          │                                          │
          │                                 ┌────────┴────────┐
          │                                 │ Stage Selector   │
          │                                 │ (EC → IC → QC)  │
          │                                 └────────┬────────┘
          │                                          │
          ▼                                          ▼
   "IC Screening"                        "QC Assessment"
   ic_screening_view.py:398             qc_assessment_view.py:391
   (Stage 2: Inclusion)                 (Stage 3: Quality)
          │                                 │
          │                                 │
          └─────────────┬───────────────────┘
                        │
                        ▼
              "Exports & Audit"
             export_view.py:194
             (Session + calibration + manifest)
                        │
                        ▼
              "Inter-Rater Calibration"
             calibration_view.py:154
             (Cohen's Kappa export)
```

### Stage Transition Rules

```
EC → IC → QC: Sequential funnel
  - EC: ALL articles reviewed
  - IC: Only EC-passed articles reviewed
  - QC: Only IC-passed articles reviewed
  - Skip: Article can be skipped, recovered later
  - Discuss: Article flagged for team discussion
```

---

## 2. Routing Ownership

| Route | Module | Status | Authority |
|-------|--------|--------|-----------|
| `/` | `app.py` | ACTIVE | Main entry point |
| Protocol Config | `protocol_view.py` | **AUTHORITATIVE** | REQUIRED before screening |
| EC Screening | `ec_screening_view.py` | **AUTHORITATIVE** | Canonical Stage 1 |
| IC Screening | `ic_screening_view.py` | **AUTHORITATIVE** | Canonical Stage 2 |
| QC Assessment | `qc_assessment_view.py` | **AUTHORITATIVE** | Canonical Stage 3 |
| Exports | `export_view.py` | **AUTHORITATIVE** | Canonical export |
| Calibration | `calibration_view.py` | **AUTHORITATIVE** | IRR export |
| Review Interface | `review_view.py` | **DEPRECATED** | Legacy HITL — see §4 |
| Eligibility Eval | `eligibility_view.py` | **ORPHANED** | Database-backed — not routed |
| Quality View | `quality_view.py` | **ORPHANED** | Database-backed — not routed |
| Overview | `overview_view.py` | **ORPHANED** | Database-backed — not routed |
| Planning | `planning_view.py` | **ORPHANED** | Database-backed — not routed |
| ATLAS Processor | `atlas_processor_view.py` | **ORPHANED** | Processing UI — not routed |

---

## 3. Session Ownership

### Canonical Session Pattern

**Authority**: `ScreeningSession` from `src/core/screening_session.py`

**Key Properties**:
- `session.articles`: List[ArticleReview]
- `session.stage`: str ("ec" | "ic" | "qc")
- `session.current_index`: int
- `session.ec_completed`, `session.ic_completed`, `session.qc_completed`: int
- `session.dynamic_protocol`: Dict (from `DynamicProtocol`)

**Session Methods**:
- `record_decision(decision, notes, llm_suggestion)` — records at current stage for current article
- `apply_decision(article_id, stage, decision, notes)` — records at specific stage for specific article
- `advance(skip)` — moves to next undecided article
- `get_current_article()` — returns current ArticleReview
- `save(output_dir)` — persists with hash integrity

### Legacy Session Patterns (DEPRECATED)

| Pattern | Location | Problem |
|---------|----------|---------|
| `ec_session` dict | `ec_screening_view.py:49` | UI-owned workflow state, no persistence, no protocol linkage |
| `ic_session` dict | `ic_screening_view.py:44` | Same |
| `qc_session` dict | `qc_assessment_view.py:44` | Same |
| `ScreeningSession` | `review_view.py:266` | Deprecated interface (review_view.py) |

**Migration Required**: Phase 4 of the Execution Consolidation Sprint addresses this.

---

## 4. Metadata Ownership

### Canonical Metadata Path

**Authority**: `ArticleRecord` from `src/core/atlas_processor.py`

```python
@dataclass
class ArticleRecord:
    title, abstract, keywords, authors, year  # Core fields
    literature_type: str  # "WL" or "GL"
    ec_decision, ic_decision, qc_score, final_decision  # Decisions
    metadata: Dict[str, Any]  # Full row + provenance flags
```

**Provenance Fields in `metadata`**:
- `year_source`: "structured" | "regex" | "missing"
- `metadata_completeness`: "complete" | "partial" | "minimal"
- `literature_provenance`: "WL" | "GL"

### Metadata Flow

```
ATLAS Excel → ATLASLoader → ArticleRecord.metadata (preserved)
                                    │
                                    ▼
                            ArticleReview.metadata (propagated)
                                    │
                                    ▼
                            UI renders via metadata dict
```

### Metadata Bypasses (PHASE 3 addresses)

- `ec_screening_view.py` uses `normalize_wl_metadata()` → creates `NormalizedArticle` → converts to `article_dict`
  - This BYPASSES `ArticleRecord.metadata` lineage
  - Provenance flags (`year_source`, `metadata_completeness`) are NOT preserved in the dict
  - `year` field is lost (stored as string in `NormalizedArticle.year_str`)
  - `authors` and other ATLAS fields may be stripped

- Same pattern in `ic_screening_view.py` and `qc_assessment_view.py`

---

## 5. Criteria Ownership

### Canonical Registry

**Authority**: Keyword sets defined in:
1. `src/core/atlas_processor.py:ExclusionCriteria` (lines 193-227)
2. `src/core/atlas_processor.py:InclusionCriteria` (lines 230-254)
3. `src/core/atlas_processor.py:QualityCriteria` (lines 257-300)
4. `src/core/protocol_engine.py` (duplicates via `_default_*` methods)
5. `src/core/llm_assistant.py` (hardcoded in prompts)

### Keyword Duplication (PHASE 5 addresses)

| Keyword Set | Location 1 | Location 2 | Status |
|-------------|-----------|-----------|--------|
| SE keywords | `atlas_processor:213` | `protocol_engine:308` | DUPLICATED |
| Recruitment keywords | `atlas_processor:241` | `protocol_engine:258` | DUPLICATED |
| Empirical keywords | `atlas_processor:242` | `protocol_engine:262` | DUPLICATED |
| Industry keywords | `atlas_processor:243` | `protocol_engine:266` | DUPLICATED |
| QC scoring keywords | `atlas_processor:291-299` | `protocol_engine:364-436` | DUPLICATED |

---

## 6. LLM Orchestration

### Canonical LLM Layer

**Authority**: `LLMAssistant` from `src/core/llm_assistant.py`

- Model: `llama-3.3-70b-versatile` (Groq) or `gpt-4o-mini` (OpenAI)
- Role: **ADVISORY ONLY** — researcher makes final decisions
- Methods: `suggest_ec()`, `suggest_ic()`, `suggest_qc()`
- Fallback: Returns `AdvisorySuggestion` with `confidence=0.0` if unavailable

### Legacy LLM Layers

| Module | Model | Status |
|--------|-------|--------|
| `llm_assistant.py` | llama-3.3-70b-versatile | **AUTHORITATIVE** |
| `decision_engine.py` | llama-3.1-70b-versatile | LEGACY (internal only) |
| `llm_reasoning.py` | llama-3.1-70b-versatile | **ORPHANED** |
| `app/main.py` | llama-3.1-70b-versatile | LEGACY (separate app) |

---

## 7. Export Schema Ownership

### Canonical Export

**Authority**: `ExportEngine` from `src/core/export_engine.py`

| Export Type | Format | Schema |
|-------------|--------|--------|
| Decisions | Excel | WL sheet: Library, Global_ID, Local_ID, Title, Abstract, Keywords, CIs1, CEs1, Revisor 1, CIs2, CEs2, Revisor 2, Decision |
| Decisions | Excel | GL sheet: Posicao, Title, URL, Source_File, Revisor 1 EC, Revisor 1 IC, Decision |
| Session | JSON | Full session with articles, decisions, protocol |
| Audit | JSON | All decisions with hashes |
| Manifest | JSON | Protocol version, input checksum, session ID |
| Calibration | Excel | Pairs with Cohen's Kappa matrix |
| Calibration | JSON | 2x2 contingency matrix |

### Legacy Export

`atlas_processor.py:export_to_excel()` — uses different column names:
- WL: `CEs1` instead of `ec_decision`, `CIs1` instead of `ic_decision`
- These are for PRISMA compatibility, but the naming differs from `export_engine.py`

---

## 8. Deprecated Paths

### review_view.py — DEPRECATED

**File**: `src/ui/modules/review_view.py` (319 lines)
**Status**: DEPRECATED — Not routed by `app.py`

This module was created during the HITL migration but was superseded by the stage-specific screening views. It contains a complete review interface that combines EC/IC/QC in a single screen, but:
- It is NOT imported by `app.py`
- It has a different session model than the ScreeningSession (it uses `st.session_state.session`)
- It contains a **RUNTIME BUG** (fixed: `apply_decision()` method was missing)

**Migration**: Features from `review_view.py` should NOT be back-ported to the canonical path. The stage-specific approach (PATH A) is the authoritative workflow.

**TODO**: Remove `review_view.py` from codebase after Phase 4 consolidation.

---

## 9. Orphaned Modules

| Module | Classification | Evidence |
|--------|----------------|----------|
| `llm_reasoning.py` | **ORPHANED** | Used only by `eligibility_view.py` and `quality_view.py` — neither is routed |
| `eligibility_view.py` | **ORPHANED** | Not in `app.py` routing. Uses `database.py` + `llm_reasoning.py` |
| `quality_view.py` | **ORPHANED** | Not in `app.py` routing. Uses `database.py` + `llm_reasoning.py` |
| `overview_view.py` | **ORPHANED** | Not in `app.py` routing. Uses `database.py` |
| `planning_view.py` | **ORPHANED** | Not in `app.py` routing. Uses `database.py` |
| `atlas_processor_view.py` | **ORPHANED** | Not in `app.py` routing. Standalone processing UI |
| `database.py` | **ORPHANED (runtime)** | Only used by orphaned views above. Not part of canonical path |

**Note**: `app/main.py` is a separate legacy application (in Portuguese, with direct DataFrame manipulation) and is NOT part of the APOLLO canonical path.

---

## 10. Backward Compatibility

The following are preserved for compatibility but are NOT part of the canonical path:

| Component | Preservation Reason |
|-----------|---------------------|
| `atlas_processor.py:APOLLODecisionEngine` | CLI entry point (`scripts/process_atlas.py`) |
| `process_atlas_file()` | Deterministic batch processing |
| `export_to_excel()` | PRISMA column compatibility |
| `protocol_engine.py:get_default_protocol()` | Protocol parity reference |
| `app/main.py` | Legacy standalone app (separate project) |

---

*This document is the authoritative source for APOLLO's execution path. Update when architecture changes.*
