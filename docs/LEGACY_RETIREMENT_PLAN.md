# LEGACY RETIREMENT PLAN — Sprint 2 Phase 7

**Purpose**: Actionable remediation plan for all identified violations, prioritized by risk, with removal criteria and safety checks.

**Evidence standard**: Every item references the audit doc + specific violation that proves the fix is needed.

---

## 1. PHASE 7 SUMMARY

| Priority | Item | Risk | Effort | Type |
|---|---|---|---|---|
| P0 | Fix `str(protocol_dict)` → `json.dumps()` in export_view.py:67 | CRITICAL | LOW | BUG FIX |
| P0 | Wire ScreeningSession to views (replace dict sessions) | HIGH | HIGH | ARCHITECTURAL REFACTOR |
| P1 | Delegate DataFrame ops to canonical ingestion | HIGH | MEDIUM | ARCHITECTURAL REFACTOR |
| P1 | Fix QC scores `str(dict)` in qc_assessment_view.py:374 | MEDIUM | LOW | BUG FIX |
| P1 | Wire export_engine to export_view | MEDIUM | MEDIUM | ARCHITECTURAL REFACTOR |
| P2 | Add deprecation banners to orphaned views | LOW | LOW | DISPLAY FIX |
| P2 | Add metadata normalization to IC/QC views | MEDIUM | MEDIUM | DATA INTEGRITY |
| P3 | Delete llm_reasoning.py (after orphaned consumers removed) | LOW | LOW | DEAD CODE REMOVAL |
| P3 | Delete orphaned UI views after canonical equivalent confirmed | LOW | MEDIUM | LEGACY REMOVAL |

---

## 2. P0 — CRITICAL BUG FIX

### 2.1 Fix str(protocol_dict) in export_view.py:67

**File**: `src/ui/modules/export_view.py:66-67`
**Violation**: `str(protocol_dict)` produces non-standard JSON
**Reference**: EXPORT_PIPELINE_VERIFICATION.md §2
**Evidence**: `dynamic_protocol.py:413` uses correct canonical pattern

**Fix**:
```python
import json  # already imported at top
protocol_dict = protocol.to_dict()
protocol_json = json.dumps(protocol_dict, sort_keys=True, ensure_ascii=False)
```

**Verification**:
1. Export protocol JSON from export view
2. Verify with `json.loads()` — must parse without error
3. Verify `True`/`False` (not Python `True`/`False`)
4. Run `test_architectural_integrity.py::TestProtocolDeterminism` — must pass

**Safety**: LOW RISK — only changes export format, no protocol logic modified
**Rollback**: Change back to `str()` in one line

---

### 2.2 Wire ScreeningSession to Views

**Files**: `ec_screening_view.py`, `ic_screening_view.py`, `qc_assessment_view.py`
**Violation**: Dict sessions bypass canonical ScreeningSession authority
**Reference**: SESSION_AUTHORITY_AUDIT.md §2-4, RUNTIME_EXECUTION_TRACE.md §4
**Evidence**: 0 `ScreeningSession()` constructor calls from any UI module

**Fix** — replace in each view:
```python
# OLD (dict session)
if "ec_session" not in st.session_state:
    st.session_state.ec_session = {"articles": [], "decisions": {}, ...}

# NEW (canonical session)
if "apollo_session" not in st.session_state:
    st.session_state.apollo_session = ScreeningSession(
        session_id=str(uuid.uuid4())[:8],
        created_at=datetime.now().isoformat(),
        protocol_version=protocol.protocol_version,
        researcher_id="researcher_1"
    )

# OLD: session = st.session_state.ec_session
# NEW: session = st.session_state.apollo_session
```

**Key methods to call**:
- `session.add_articles(article_records)` — replaces inline DataFrame parsing
- `session.record_decision("include"|"exclude"|"skip", notes)` — replaces dict mutation
- `session.save()` — enables session persistence
- `session.take_snapshot()` — preserves protocol hash per decision

**Verification**:
1. Run a screening session through EC → IC → QC
2. Verify `session.save()` produces valid JSON (json.loadable)
3. Verify `session_hash` present in saved JSON
4. Verify `ScreeningSession.load()` restores state correctly
5. Run `test_architectural_integrity.py::TestScreeningSessionAuthority` — must pass

**Safety**: HIGH RISK — changes session management. Requires integration test coverage before deployment.
**Rollback**: Restore dict sessions in each view file

---

## 3. P1 — HIGH-PRIORITY ARCHITECTURAL REFACTOR

### 3.1 Delegate DataFrame Ops to Canonical Ingestion

**Files**: `ec_screening_view.py:133-151`, `ic_screening_view.py:129-142`, `qc_assessment_view.py:130-146`
**Violation**: UI reads Excel + iterrows directly
**Reference**: UI_BOUNDARY_AUDIT.md §2
**Evidence**: `atlas_processor.py:167-168` canonical read exists

**Fix pattern**:
```python
# OLD (UI layer)
wl_df = pd.read_excel(temp_path, sheet_name="White Literature")
for _, row in wl_df.iterrows():
    row_dict = row.to_dict()
    article = normalize_wl_metadata(row_dict)
    ...

# NEW (delegate to ScreeningSession.ingest())
session.ingest_from_upload(uploaded_file)  # canonical ingestion
```

**Action**: Implement `ScreeningSession.ingest_from_upload(uploaded_file)` that:
1. Writes uploaded_file to temp path
2. Calls `atlas_processor.process_atlas_file()` (canonical DataFrame ops)
3. Returns `List[ArticleReview]` objects
4. Deletes temp file

**Verification**:
1. Upload same ATLAS file in EC/IC/QC stages
2. Verify articles have consistent metadata across stages
3. Verify no `pd.read_excel()` in UI modules post-refactor (grep check)

---

### 3.2 Fix QC Scores str(dict) in qc_assessment_view.py:374

**File**: `src/ui/modules/qc_assessment_view.py:374`
**Violation**: `str(assessment.get("qc_scores", {}))` — QC scores as Python repr string
**Reference**: EXPORT_PIPELINE_VERIFICATION.md §3

**Fix**:
```python
# OLD
"QC_Scores": str(assessment.get("qc_scores", {}))

# NEW — individual criterion columns
qc_scores = assessment.get("qc_scores", {})
for criterion_id, score in qc_scores.items():
    results.append({
        "Title": article["title"],
        "QC_Score_Total": assessment.get("qc_total", 0),
        f"QC_{criterion_id}": score,  # individual column per criterion
        ...
    })
# OR: export as JSON string (valid)
"QC_Scores": json.dumps(assessment.get("qc_scores", {}))
```

**Verification**:
1. Run QC assessment, export results
2. Verify QC_Scores column is valid JSON parseable
3. Run `test_architectural_integrity.py::TestExportEngineCanonical` — must pass

---

### 3.3 Wire export_engine to export_view

**File**: `src/ui/modules/export_view.py`
**Violation**: Canonical export methods unreachable from UI
**Reference**: EXPORT_PIPELINE_VERIFICATION.md §5
**Evidence**: `export_engine.py` has zero imports from UI modules

**Fix**:
```python
# Add to export_view.py
from src.core.export_engine import ExportEngine

def render_export_section():
    session = st.session_state.apollo_session

    if st.button("Export Full Session (Excel)"):
        engine = ExportEngine(protocol_version=session.protocol_version)
        with tempfile.TemporaryDirectory() as tmpdir:
            # Convert dict sessions to canonical if needed
            excel_path = engine.export_decisions_excel(session, ...)
            # etc.
```

**Verification**:
1. Click "Export Full Session" button
2. Verify Excel file has WL + GL sheets
3. Verify JSON exports are json.loadable
4. Verify manifest includes input_checksum

---

## 4. P2 — MEDIUM-PRIORITY FIXES

### 4.1 Add Deprecation Banners

**Files**:
- `review_view.py` — PASSIVE (missing banner)
- `ingestion_view.py` — ORPHANED (missing banner)
- `quality_view.py` — verify banner exists
- `overview_view.py` — verify banner exists
- `planning_view.py` — verify banner exists
- `atlas_processor_view.py` — verify banner exists

**Reference**: LEGACY_EXECUTION_AUDIT.md §4.2
**Evidence**: grep for "deprecated\|DEPRECATED\|legacy\|LEGACY"

**Fix pattern** (if missing):
```python
def render_xxx_view():
    st.warning("⚠️ DEPRECATED MODULE — This view is not routed and will be removed in a future release. Use the canonical workflow views instead.")
    ...
```

**Verification**: grep check after implementation

---

### 4.2 Add Metadata Normalization to IC/QC Views

**Files**: `ic_screening_view.py`, `qc_assessment_view.py`
**Violation**: No `normalize_wl_metadata` / `normalize_gl_metadata` call
**Reference**: UI_BOUNDARY_AUDIT.md §7
**Evidence**: ec_screening_view.py calls normalization; ic/qc views do not

**Fix** — after P0 (ScreeningSession wiring):
```python
# In ScreeningSession.ingest_from_upload()
article = normalize_wl_metadata(row_dict)  # called canonical
session.add_articles([...])  # ArticleReview with full metadata
```

**Verification**: After ScreeningSession wiring, verify IC/QC articles have metadata lineage fields (year, authors, DOI, etc.)

---

## 5. P3 — LEGACY REMOVAL

### 5.1 Delete llm_reasoning.py

**File**: `src/core/llm_reasoning.py`
**Classification**: DEAD — no imports from any canonical module
**Reference**: LEGACY_EXECUTION_AUDIT.md §3.2

**Prerequisite** (MUST be done first):
1. Delete `src/ui/modules/eligibility_view.py` — primary consumer
2. Delete `src/ui/modules/quality_view.py` — secondary consumer
3. Verify zero imports of `llm_reasoning` (grep)

**Verification**:
```bash
rg "llm_reasoning" src/  # must return 0 matches
```
```python
PYTHONPATH=. python -c "from src.core.llm_reasoning import *"  # must fail ImportError after deletion
```

**Safety**: Verify `llm_assistant.py` (canonical) works for all LLM features before deletion
**Rollback**: Restore file from git

---

### 5.2 Delete Orphaned UI Views (Post-Wiring)

After canonical paths are verified functional:

1. **Delete** `src/ui/modules/ingestion_view.py` — ORPHANED, never routed
2. **Delete** `src/ui/modules/eligibility_view.py` — ORPHANED, primary llm_reasoning consumer
3. **Delete** `src/ui/modules/quality_view.py` — ORPHANED, secondary llm_reasoning consumer
4. **Delete** `src/ui/modules/overview_view.py` — ORPHANED, never routed
5. **Delete** `src/ui/modules/planning_view.py` — ORPHANED, never routed
6. **Delete** `src/ui/modules/atlas_processor_view.py` — ORPHANED, never routed
7. **Delete** `src/ui/modules/review_view.py` — PASSIVE, never routed

**Verification**:
1. Run `app.py` — verify only 6 routes (protocol, ec, ic, qc, calibration, export)
2. Verify no `__import__` or `importlib` dynamic loading
3. Run full test suite
4. Run integration tests

---

### 5.3 Delete database.py (Optional)

**File**: `src/core/database.py`
**Classification**: ORPHANED — imported only by orphaned UI modules
**Reference**: LEGACY_EXECUTION_AUDIT.md §3.3

**Action**: DELETE after orphaned consumers removed (Step 5.1-5.2).

**Preservation rationale** (from LEGACY_EXECUTION_AUDIT.md):
- May be needed for future multi-user persistence
- Not imported by any canonical module
- If multi-user feature is added, `database.py` provides schema foundation

**Decision criteria**: If no multi-user feature planned within 6 months, delete.

---

## 6. REMOVAL ORDER (EXECUTION SEQUENCE)

### Phase A — Safe fixes (no architectural risk)
1. Fix `str(dict)` → `json.dumps()` in export_view.py
2. Fix QC scores `str(dict)` in qc_assessment_view.py
3. Add deprecation banners to orphaned views
4. Verify/confirm all deprecation banners

### Phase B — Verification before architectural changes
5. Run integration tests (`test_architectural_integrity.py`)
6. Verify all 16 tests pass
7. Create additional integration tests for canonical path wiring

### Phase C — Architectural refactor (high risk — requires test coverage)
8. Implement `ScreeningSession.ingest_from_upload()`
9. Wire `ScreeningSession` to EC/IC/QC views (replace dict sessions)
10. Wire `export_engine` to `export_view`
11. Add metadata normalization to IC/QC views

### Phase D — Verification of canonical path
12. Run full integration test suite
13. Run manual end-to-end screening session test
14. Verify session save/load roundtrip
15. Verify export outputs are valid JSON/Excel

### Phase E — Legacy cleanup (after Phase D verified)
16. Delete orphaned UI views (Step 5.2)
17. Delete `llm_reasoning.py` (after consumers removed)
18. Decision: delete or preserve `database.py`

---

## 7. VERIFICATION CHECKLIST

### Pre-Phase A
- [ ] Review LEGACY_RETIREMENT_PLAN.md with team
- [ ] Confirm priority ranking is accepted
- [ ] Confirm rollback procedures are documented

### Phase A
- [ ] Fix str(dict) in export_view.py:67 — verify with json.loads()
- [ ] Fix QC scores str(dict) in qc_assessment_view.py:374 — verify export
- [ ] Add deprecation banner to review_view.py
- [ ] Add deprecation banner to ingestion_view.py
- [ ] Verify deprecation banners on quality_view.py, overview_view.py, planning_view.py, atlas_processor_view.py

### Phase B
- [ ] Run `pytest tests/integration/test_architectural_integrity.py` — 16/16 pass
- [ ] Create integration tests for ScreeningSession wiring
- [ ] Run all existing tests

### Phase C
- [ ] Implement `ScreeningSession.ingest_from_upload()`
- [ ] Replace `st.session_state.ec_session` dict with `st.session_state.apollo_session: ScreeningSession`
- [ ] Replace `st.session_state.ic_session` dict with `st.session_state.apollo_session: ScreeningSession`
- [ ] Replace `st.session_state.qc_session` dict with `st.session_state.apollo_session: ScreeningSession`
- [ ] Wire `export_engine` to `export_view`
- [ ] Verify metadata normalization in all views

### Phase D
- [ ] Run full integration test suite — all pass
- [ ] Manual end-to-end: Protocol → EC → IC → QC → Export
- [ ] Session save/load roundtrip — verify hash stable
- [ ] Export Excel — verify WL/GL sheets
- [ ] Export JSON — verify json.loadable
- [ ] Export manifest — verify input_checksum present

### Phase E
- [ ] Delete orphaned UI views
- [ ] Verify zero orphaned module imports (grep)
- [ ] Delete llm_reasoning.py
- [ ] Decision: database.py (delete or preserve)
- [ ] Final grep: no orphaned paths, no dict sessions, no str(dict) exports

---

## 8. ROLLBACK PROCEDURES

| Change | Rollback Procedure |
|---|---|
| Fix str(dict) | Revert one line in export_view.py |
| Wire ScreeningSession | Restore three dict session inits in ec/ic/qc views |
| Wire export_engine | Remove import and method calls in export_view |
| Delete orphaned view | `git restore src/ui/modules/<deleted>.py` |
| Delete llm_reasoning.py | `git restore src/core/llm_reasoning.py` |

---

## 9. OPEN QUESTIONS

1. **Is `database.py` intended for future multi-user feature?** If yes, preserve with clear comment. If no, delete.
2. **Is there a canonical path for saving/restoring dict sessions across page refreshes?** Currently no — `ScreeningSession` has save/load but dict sessions do not.
3. **Should `calibration_view.py` remain as-is?** It imports `CalibrationEngine` (canonical) and reads JSON files. But it expects `ScreeningSession`-format JSON which dict sessions cannot produce. After ScreeningSession wiring, calibration should work correctly.
4. **Is `atlas_processor_view.py` ever intended to be routed?** If so, it needs canonical wiring. If not, it should be deleted with other orphaned views.
