# APOLLO — Runtime Execution Trace

**Document Version**: 1.0.0
**Date**: 2026-05-12
**Status**: **VERIFIED EXECUTION TRACE**

---

## 1. Canonical Execution Call Graph

```
app.py:main()
│
├── render_apollo_header()          [render-only: HTML/CSS]
│
├── render_sidebar()                [render-only: radio navigation]
│   └── Returns view name string
│
└── View Routing (canonical):
    │
    ├── "Protocol Configuration"
    │   └── protocol_view.py:render_protocol_dashboard()
    │       ├── Creates/manages DynamicProtocol in st.session_state.research_protocol
    │       ├── state: "research_protocol", "protocol_locked"
    │       └── Authority: dynamic_protocol.py
    │
    ├── "EC Screening"
    │   └── ec_screening_view.py:render_ec_screening()
    │       ├── Creates st.session_state.ec_session dict
    │       ├── render_upload_section() → load_atlas_papers()
    │       │   ├── pd.read_excel(..., sheet_name="White Literature")
    │       │   ├── pd.read_excel(..., sheet_name="Grey Literature")
    │       │   ├── normalize_wl_metadata() [article_metadata.py]
    │       │   ├── normalize_gl_metadata() [article_metadata.py]
    │       │   └── article_to_dict() [article_metadata.py]
    │       ├── render_screening_workspace()
    │       │   └── article dict iteration
    │       ├── render_ai_advisory_panel() → get_llm_ec_suggestion()
    │       │   └── LLMAssistant.suggest_ec() [llm_assistant.py]
    │       ├── render_decision_controls()
    │       │   └── STORES: st.session_state.ec_session["decisions"][idx]
    │       └── export_ec_results() → pd.DataFrame → .to_csv()
    │
    ├── "IC Screening"
    │   └── ic_screening_view.py:render_ic_screening()
    │       ├── Creates st.session_state.ic_session dict
    │       ├── render_upload_section() → load_papers()
    │       │   ├── pd.read_excel() or pd.read_csv()
    │       │   └── creates article dicts
    │       ├── render_screening_workspace()
    │       ├── render_ai_advisory_panel() → get_llm_ic_suggestion()
    │       │   └── LLMAssistant.suggest_ic() [llm_assistant.py]
    │       ├── render_decision_controls()
    │       │   └── STORES: st.session_state.ic_session["decisions"][idx]
    │       └── export_ic_results() → pd.DataFrame → .to_csv()
    │
    ├── "QC Assessment"
    │   └── qc_assessment_view.py:render_qc_assessment()
    │       ├── Creates st.session_state.qc_session dict
    │       ├── render_upload_section() → load_papers()
    │       │   ├── pd.read_csv() or pd.read_excel()
    │       │   └── creates article dicts
    │       ├── render_assessment_workspace()
    │       ├── render_wl_qc_framework() / render_gl_qc_framework()
    │       │   └── reads from st.session_state.research_protocol
    │       └── export_qc_results() → pd.DataFrame → .to_csv()
    │
    ├── "Inter-Rater Calibration"
    │   └── calibration_view.py:render_calibration_view()
    │       ├── load_session_json() → json.load()
    │       └── CalibrationEngine.compute_kappa_between_sessions()
    │           [calibration_engine.py]
    │
    └── "Exports & Audit"
        └── export_view.py:render_exports()
            ├── READS: st.session_state.ec_session (counts)
            ├── READS: st.session_state.ic_session (counts)
            ├── READS: st.session_state.qc_session (counts)
            ├── render_protocol_summary() → protocol.to_dict() [NO export]
            ├── render_export_protocol_section() → protocol_json.to_csv()
            └── render_audit_section() → audit_data.to_csv()
```

---

## 2. Session Mutation Map

### Canonical Workflow State (DICT-BASED — `st.session_state`)

| Key | Owner Module | Mutations | Type |
|------|-------------|-----------|------|
| `research_protocol` | `protocol_view.py` | `setdefault()`, `_apply_template()`, `lock()` | DynamicProtocol object |
| `protocol_locked` | `protocol_view.py` | Boolean flag | bool |
| `ec_session` | `ec_screening_view.py` | Articles load, decision dict update | Dict of dicts |
| `ic_session` | `ic_screening_view.py` | Articles load, decision dict update | Dict of dicts |
| `qc_session` | `qc_assessment_view.py` | Articles load, assessment dict update | Dict of dicts |
| `{ec,ic}_advice_{idx}` | `ec/ic_screening_view.py` | Cached LLM suggestions | Dict |

### Legacy Workflow State (`ScreeningSession` — NOT routed)

| Key | Owner Module | Status |
|-----|-------------|--------|
| `session` | `review_view.py` | NOT routed by app.py |
| `reviewer_state` | `review_view.py` | NOT routed |

### Session State Violations

| Issue | Module | Severity |
|--------|--------|----------|
| Three independent dict sessions (`ec_session`, `ic_session`, `qc_session`) — NO unified `ScreeningSession` | ec/ic/qc_screening_view | HIGH |
| `export_view.py` reads from dict sessions but doesn't own them | export_view | MEDIUM |
| Each screening view creates its own session independently | ec/ic/qc_screening_view | HIGH |
| No single authoritative session owner across stages | ALL screening views | HIGH |

---

## 3. Metadata Transformation Map

### EC Screening Load (atlas_processor.py → ec_screening_view.py)

```
ATLAS Excel WL/GL sheets
  ↓
pd.read_excel() [ec_screening_view.py:133-134]
  ↓
row.to_dict() [ec_screening_view.py:138, 146]
  ↓
normalize_wl_metadata(row_dict) [article_metadata.py:200-238]
  ├─ title: from row (TITLE_ALIASES)
  ├─ abstract: from row (ABSTRACT_ALIASES)
  ├─ authors: from row (AUTHORS_ALIASES)
  ├─ year: int(row[YEAR_ALIASES]) [article_metadata.py:189-197]
  ├─ literature_type: "WL" or "GL"
  ├─ provenance: from row (PROVENANCE_ALIASES)
  └─ raw_data: dict(row)
  ↓
article_to_dict(article) [article_metadata.py:272-299]
  ├─ year: article.year_str (string "[NOT AVAILABLE]" if missing)
  ├─ completeness: article.metadata_completeness
  ├─ authors: string (may be empty)
  └─ returns plain dict (NO provenance flags like year_source)
  ↓
st.session_state.ec_session["articles"] [ec_screening_view.py:143, 151]
```

**METADATA BYPASS DETECTED**:
- `normalize_wl_metadata()` does NOT populate `year_source` provenance flag
- `article_to_dict()` returns plain dict with `year` as string, `completeness` as computed field
- **Provenance flags (`year_source`, `metadata_completeness`, `literature_provenance`) are NOT propagated** in this path
- This path BYPASSES the `ArticleRecord.metadata` lineage that was fixed in `atlas_processor.py`

---

## 4. Criteria Evaluation Map

### EC Screening Criteria (EC Evaluation)

```
User clicks INCLUDE/EXCLUDE button
  ↓
No automatic criteria evaluation
  ↓
Researcher makes decision manually
  ↓
LLM advisory (OPTIONAL):
  get_llm_ec_suggestion(article) [ec_screening_view.py:332]
    → LLMAssistant.suggest_ec() [llm_assistant.py]
      → criteria: EC_DESCRIPTIONS from criteria_registry [llm_assistant.py:9]
      → prompt includes year, year_source, metadata_completeness [llm_assistant.py:155-156]
      → model: llama-3.3-70b-versatile [llm_assistant.py:72]
```

### IC Screening Criteria (IC Evaluation)

```
User clicks INCLUDE/EXCLUDE button
  ↓
No automatic criteria evaluation
  ↓
Researcher makes decision manually
  ↓
LLM advisory (OPTIONAL):
  get_llm_ic_suggestion(article) [ic_screening_view.py:280]
    → LLMAssistant.suggest_ic() [llm_assistant.py]
      → criteria: IC_DESCRIPTIONS from criteria_registry [llm_assistant.py:11]
```

### QC Assessment

```
User uses sliders for QC criteria
  ↓
Researcher adjusts scores manually (0.0, 0.5, 1.0)
  ↓
THRESHOLD CHECK (client-side):
  if qc_total < threshold: display "below threshold" warning [qc_assessment_view.py:295]
  NO automatic exclusion — researcher decides
```

### Criteria Centralization Verification

```
criteria_registry.py: SE_KEYWORDS, RECRUITMENT_KEYWORDS, EMPIRICAL_KEYWORDS, INDUSTRY_KEYWORDS
  ├─ atlas_processor.py (CRITERIA classes): USES criteria_registry ✓
  ├─ protocol_engine.py (_default_* methods): USES criteria_registry ✓
  └─ llm_assistant.py (prompt building): USES criteria_registry ✓
```

**VERIFIED**: All canonical criteria evaluation uses `criteria_registry` as single source.

---

## 5. Export Transformation Map

### EC Export (`ec_screening_view.py:456-487`)

```
st.session_state.ec_session["articles"] + ["decisions"]
  ↓
FOR each article (index-based):
  - Title: article["title"]
  - Literature_Type: article["literature_type"]
  - EC_Decision: decisions[idx]["decision"].upper()
  - EC_Notes: decisions[idx]["notes"]
  - Abstract: article["abstract"]
  ↓
pd.DataFrame(results) [ec_screening_view.py:474]
  ↓
.to_csv() → st.download_button()
```

### IC Export (`ic_screening_view.py:366-398`)

```
st.session_state.ic_session["articles"] + ["decisions"]
  ↓
Columns: Title, Literature_Type, EC_Decision, IC_Decision, IC_Notes, Abstract
  ↓
pd.DataFrame → .to_csv()
```

### QC Export (`qc_assessment_view.py:358-391`)

```
st.session_state.qc_session["articles"] + ["assessments"]
  ↓
Columns: Title, Literature_Type, QC_Decision, QC_Score, QC_Scores, Abstract
  ↓
QC_Scores: str(dictionary) — NOT structured export
  ↓
pd.DataFrame → .to_csv()
```

### Export Schema Violations

| Issue | Location | Severity |
|-------|----------|----------|
| QC_Scores exported as `str(dict)` — cannot be parsed | `qc_assessment_view.py:374` | HIGH |
| No structured Excel export (PRISMA format) in screening views | ALL screening views | MEDIUM |
| export_view reads dict sessions but produces NO structured export | `export_view.py:20-194` | HIGH |
| No metadata completeness in exports | ALL screening views | MEDIUM |
| No year_source provenance in exports | ALL screening views | MEDIUM |

---

## 6. Execution Mode Classification

### CANONICAL EXECUTION (app.py routed — ACTIVE)

| Module | Lines | Execution Path | Status |
|--------|-------|---------------|--------|
| `app.py` | 144 | Entry point, routing | ACTIVE |
| `protocol_view.py` | 556 | Protocol configuration | ACTIVE |
| `ec_screening_view.py` | 487 | EC screening (dict session) | ACTIVE |
| `ic_screening_view.py` | 398 | IC screening (dict session) | ACTIVE |
| `qc_assessment_view.py` | 391 | QC assessment (dict session) | ACTIVE |
| `calibration_view.py` | 154 | IRR calibration | ACTIVE |
| `export_view.py` | 194 | Export/audit (reads dict sessions) | ACTIVE |
| `article_metadata.py` | 428 | Metadata normalization | ACTIVE |
| `dynamic_protocol.py` | 644 | Protocol management | ACTIVE |
| `criteria_registry.py` | ~280 | Keyword registry | ACTIVE |
| `llm_assistant.py` | 354 | LLM advisory | ACTIVE |

### DEPRECATED EXECUTION (app.py NOT routed — PASSIVE)

| Module | Status | Called By |
|--------|--------|-----------|
| `review_view.py` | NOT routed — DEPRECATED | None (app.py never calls it) |
| `screening_session.py` | Passive — metadata fixes applied | `review_view.py` (deprecated), `atlas_processor.py` (canonical) |
| `reviewer_state.py` | Passive | `review_view.py` (deprecated) |
| `export_engine.py` | Passive | `review_view.py` (deprecated) |

### ORPHANED EXECUTION (app.py NOT routed — NO PATH)

| Module | Status | Called By |
|--------|--------|-----------|
| `llm_reasoning.py` | ORPHANED — NO execution path | `eligibility_view.py`, `quality_view.py` (both orphaned) |
| `database.py` | ORPHANED — NO execution path | `eligibility_view.py`, `quality_view.py`, `overview_view.py`, `planning_view.py` (all orphaned) |
| `eligibility_view.py` | ORPHANED | None |
| `quality_view.py` | ORPHANED | None |
| `overview_view.py` | ORPHANED | None |
| `planning_view.py` | ORPHANED | None |
| `atlas_processor_view.py` | ORPHANED | None |
| `ingestion_view.py` | ORPHANED | None |

### LEGACY EXECUTION (Separate app)

| Module | Status | Called By |
|--------|--------|-----------|
| `app/main.py` | LEGACY — Separate application | Standalone execution only |

---

## 7. Runtime Findings Summary

### CONFIRMED CANONICAL:
- `criteria_registry.py` is single source of all keywords
- `llm_assistant.py` is the authoritative LLM layer
- `protocol_view.py` manages protocol lock
- `calibration_view.py` uses `CalibrationEngine`
- Six views are routed by `app.py`

### CONFIRMED VIOLATIONS:

1. **Dict-based sessions vs `ScreeningSession`**: Each screening stage uses `st.session_state.{ec,ic,qc}_session` dicts. `ScreeningSession` (the canonical model) is NOT used in the canonical path.

2. **Metadata lineage bypass**: EC/IC/QC screening views read ATLAS directly with `normalize_wl_metadata()` and bypass `ArticleRecord.metadata` provenance flags. `year_source`, `metadata_completeness`, `literature_provenance` are NOT preserved in the canonical screening path.

3. **DataFrame operations in UI**: All three screening views (`ec/ic/qc_screening_view`) contain `pd.read_excel()`, `.iterrows()`, `.to_dict()` directly in the UI layer.

4. **QC scores as string**: `qc_assessment_view` exports `QC_Scores` as `str(dict)` — cannot be parsed back.

5. **No structured Excel export**: The canonical path only produces CSV exports. `export_view.py` reads dict sessions but produces no structured PRISMA Excel export.

6. **`export_view.py` has no real export logic**: It reads session counts for PRISMA display but has no equivalent of `ExportEngine.export_decisions_excel()`.

---

*Trace generated from static analysis and runtime import graph.*
*Verify by running: `python tests/integration/test_canonical_path.py`*
