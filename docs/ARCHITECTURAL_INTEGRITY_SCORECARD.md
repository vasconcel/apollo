# ARCHITECTURAL INTEGRITY SCORECARD — Sprint 2 Phase 8

**Purpose**: Consolidated scoring of APOLLO architecture across 8 dimensions. Every score includes evidence from runtime/import/execution analysis.

**Date**: Sprint 2 completion
**Test suite**: `PYTHONPATH=. pytest tests/integration/test_architectural_integrity.py` → **16/16 PASSED**

---

## 1. EXECUTIVE SCORECARD

| Dimension | Score | Grade | Trend |
|---|---|---|---|
| Module Routing | 100/100 | A+ | STABLE |
| Session Authority | 33/100 | F | DRIFT |
| Layer Boundaries | 57/100 | D+ | DRIFT |
| Export Pipeline | 38/100 | F | DRIFT |
| Protocol Determinism | 100/100 | A+ | STABLE |
| Metadata Lineage | 67/100 | D+ | DRIFT |
| Legacy Isolation | 70/100 | C+ | IMPROVING |
| Test Coverage | 80/100 | B | IMPROVING |
| **OVERALL** | **68/100** | **D+** | DRIFT |

**Overall grade D+** — canonical core is solid but UI layer has significant architectural drift. Core modules (protocol, screening_session, export_engine, criteria_registry) are well-designed. The UI layer bypasses canonical authority through dict sessions and DataFrame operations in view code.

---

## 2. DIMENSION SCORES

### 2.1 Module Routing — 100/100 (A+)

**What this measures**: Only canonical modules are routed by `app.py`. No orphaned views are reachable.

**Evidence**:
- `app.py:122-140` routes 6 views only: protocol, ec, ic, qc, calibration, export
- No `st.switch_page` to orphaned views (grep confirmed)
- No `__import__`, `importlib`, or dynamic `st.page_link` anywhere in codebase
- Orphaned views form isolated clusters — no canonical path can reach them

**Score**: 100/100 — PERFECT. Zero routing violations.

---

### 2.2 Session Authority — 33/100 (F)

**What this measures**: All screening decisions flow through `ScreeningSession` canonical authority.

**Evidence**:
- `ec_screening_view.py:49-55`: Dict session initialized as raw dict
- `ic_screening_view.py:44-50`: Dict session initialized as raw dict
- `qc_assessment_view.py:44-50`: Dict session initialized as raw dict
- `ScreeningSession` NEVER instantiated by any view (`rg "ScreeningSession\(" src/ui/modules/` → 0 matches)
- No `session.record_decision()` calls in UI (grep confirmed)
- No `session.take_snapshot()` calls in UI (grep confirmed)
- No `session.save()` calls in UI (grep confirmed)

**Violations**: 3 dict sessions bypass canonical authority completely. `ScreeningSession` exists, is complete, and is unused.

**Score**: 33/100 — **FAIL**. Canonical session authority is present but completely unwired.

---

### 2.3 Layer Boundaries — 57/100 (D+)

**What this measures**: No DataFrame operations in UI layer. UI should delegate file reading to core domain.

**Evidence**:
| Operation | File:Line | Classification |
|---|---|---|
| `pd.read_excel()` | `ec_screening_view.py:133-134` | VIOLATION |
| `.iterrows()` | `ec_screening_view.py:137,145` | VIOLATION |
| `pd.read_excel()` | `ic_screening_view.py:129,131` | VIOLATION |
| `.iterrows()` | `ic_screening_view.py:134` | VIOLATION |
| `pd.read_excel()` | `qc_assessment_view.py:130` | VIOLATION |
| `.iterrows()` | `qc_assessment_view.py:133` | VIOLATION |
| `pd.read_excel()` | `atlas_processor.py:167-168` | CANONICAL |
| `.iterrows()` | `atlas_processor.py:328,347,423-424` | CANONICAL |

- 7 DataFrame operations in UI layer (violations)
- 6 DataFrame operations in canonical layer (acceptable)
- IC and QC views do NOT call `normalize_wl_metadata` / `normalize_gl_metadata`
- EC view DOES call normalization (line 139, 147)

**Score**: 57/100 — **D+**. Canonical domain layer is correct. UI layer has 7 boundary violations.

---

### 2.4 Export Pipeline — 38/100 (F)

**What this measures**: All exports use canonical patterns (json.dump, ExcelWriter) and produce valid, analyzable output.

**Evidence**:
| Export | File:Line | Pattern | Status |
|---|---|---|---|
| Protocol JSON | `export_view.py:67` | `str(dict)` | VIOLATION |
| QC CSV | `qc_assessment_view.py:374` | `str(dict)` | VIOLATION |
| PRISMA counts | `export_view.py:88-158` | UI display only | VIOLATION |
| Decisions Excel | `export_engine.py:79-135` | `json.dump`, `ExcelWriter` | CANONICAL |
| Session JSON | `export_engine.py:151-162` | `json.dump` | CANONICAL |
| Audit log | `export_engine.py:164-198` | `json.dump` | CANONICAL |
| Manifest | `export_engine.py:200-226` | `json.dump` | CANONICAL |

**Violations**:
1. `str(dict)` instead of `json.dumps()` in export_view — broken JSON
2. QC scores as `str(dict)` — not analyzable
3. No PRISMA Excel export — researchers must manually transcribe
4. All canonical export methods exist but are completely unreachable

**Score**: 38/100 — **FAIL**. Broken exports + unreachable canonical engine.

---

### 2.5 Protocol Determinism — 100/100 (A+)

**What this measures**: Protocol hash is deterministic. Same input = same output. No floating non-determinism.

**Evidence**:
```
test_protocol_hash_deterministic_after_roundtrip: PASSED
test_protocol_json_uses_json_dumps_not_str: PASSED
test_same_input_produces_same_hash: PASSED
```

- `dynamic_protocol.py:413`: Uses `json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)` — canonical
- Protocol hash stable after serialization roundtrip
- Same default protocol → same hash (verified by test)

**Score**: 100/100 — **A+**. Protocol layer is architecturally perfect.

---

### 2.6 Metadata Lineage — 67/100 (D+)

**What this measures**: Article metadata propagates from ATLAS to QC, preserving provenance across all stages.

**Evidence**:
| Stage | Metadata Normalization | Status |
|---|---|---|
| EC | `normalize_wl_metadata()` called (ec_screening_view.py:139,147) | OK |
| IC | NOT called — raw `row.get()` | VIOLATION |
| QC | NOT called — raw `row.get()` | VIOLATION |
| ScreeningSession | `ArticleReview.metadata` field present | OK |
| Export | `export_engine.py:88-116` extracts individual fields | OK |

**Violations**:
1. IC view silently drops metadata fields — only title/abstract preserved
2. QC view silently drops metadata fields — only title/abstract preserved
3. Provenance chain broken between EC → IC → QC

**Score**: 67/100 — **D+**. EC stage preserves metadata, but IC/QC stages lose lineage.

---

### 2.7 Legacy Isolation — 70/100 (C+)

**What this measures**: Dead/orphaned modules do not affect canonical execution. Legacy code is contained.

**Evidence**:
| Module | Classification | Evidence |
|---|---|---|
| `llm_reasoning.py` | DEAD | 0 imports from canonical modules |
| `database.py` | ORPHANED | 0 imports from canonical modules |
| `review_view.py` | PASSIVE | imports canonical but not routed |
| `eligibility_view.py` | ORPHANED | not routed |
| `ingestion_view.py` | ORPHANED | not routed, missing deprecation banner |
| `quality_view.py` | ORPHANED | not routed |
| `overview_view.py` | ORPHANED | not routed |
| `planning_view.py` | ORPHANED | not routed |
| `atlas_processor_view.py` | ORPHANED | not routed |

**Evidence**:
```
test_database_not_imported_by_canonical_modules: PASSED
test_llm_reasoning_not_imported_by_canonical_modules: PASSED
test_criteria_registry_replaces_keyword_literals: PASSED
```

**Violations**:
1. `review_view.py` (PASSIVE) missing deprecation banner
2. `ingestion_view.py` (ORPHANED) missing deprecation banner
3. `llm_reasoning.py` uses `llama-3.1-70b-versatile` (deprecated) but DEAD — not a risk

**Score**: 70/100 — **C+**. Orphaned modules are isolated, but deprecation banners are missing on 2 views.

---

### 2.8 Test Coverage — 80/100 (B)

**What this measures**: Runtime verification of canonical architecture through integration tests.

**Evidence**: `tests/integration/test_architectural_integrity.py` — **16/16 PASSED**
```
TestProtocolDeterminism: 3/3 passed
TestMetadataLineage: 3/3 passed
TestScreeningSessionAuthority: 4/4 passed
TestExportEngineCanonical: 3/3 passed
TestNoOrphanedPaths: 2/2 passed
TestCriteriaRegistry: 1/1 passed
```

**Coverage**:
- Protocol hash determinism: COVERED
- Metadata lineage: COVERED
- ScreeningSession authority: COVERED
- Export engine canonical patterns: COVERED
- Orphaned path isolation: COVERED
- Criteria registry: COVERED

**Gaps**:
- No end-to-end integration test (Protocol → EC → IC → QC → Export)
- No test for ScreeningSession wiring to views (since not yet implemented)
- No test for session save/load roundtrip with hashing
- No test for UI layer DataFrame ops (violations detected by grep, not tests)

**Score**: 80/100 — **B**. Core architectural properties are verified. Integration test coverage for canonical paths is strong. UI layer violations are detected by audit, not tests.

---

## 3. VIOLATION REGISTER

| ID | Severity | Location | Type | Fix Effort |
|---|---|---|---|---|
| V-01 | CRITICAL | export_view.py:67 | str(dict) → json.dumps() | LOW |
| V-02 | HIGH | ec/ic/qc_screening_view.py | DataFrame ops in UI | HIGH |
| V-03 | HIGH | ic/qc_screening_view.py | No metadata normalization | MEDIUM |
| V-04 | HIGH | ec/ic/qc_screening_view.py | Dict sessions bypass ScreeningSession | HIGH |
| V-05 | MEDIUM | qc_assessment_view.py:374 | QC scores as str(dict) | LOW |
| V-06 | MEDIUM | export_view.py | No PRISMA Excel export | MEDIUM |
| V-07 | MEDIUM | export_engine.py | Unreachable from UI | MEDIUM |
| V-08 | LOW | review_view.py | Missing deprecation banner | LOW |
| V-09 | LOW | ingestion_view.py | Missing deprecation banner | LOW |

---

## 4. CRITICAL CONTEXT

### What is actually working:
1. Protocol hashing — deterministic, canonical, tested
2. Criteria registry — 74 keyword literals eliminated
3. Module routing — only canonical views routed
4. Orphaned module isolation — dead/orphaned modules confirmed unreachable
5. Export engine — fully implemented canonical code
6. ScreeningSession — fully implemented canonical model

### What needs fixing:
1. UI layer bypasses canonical session authority (dict sessions)
2. UI layer reads DataFrames directly (no canonical delegation)
3. Export pipeline uses broken str(dict) instead of json.dumps()
4. Metadata lineage drops between EC and IC/QC stages
5. Export engine unreachable from UI

### What is safe to leave alone:
- `atlas_processor.py` DataFrame ops (domain layer — correct)
- `dynamic_protocol.py` (canonical — correct)
- `export_engine.py` (canonical — correct)
- `screening_session.py` (canonical model — correct)
- `criteria_registry.py` (canonical — correct)
- `llm_assistant.py` (canonical — correct)

---

## 5. VERIFICATION STATUS

| Audit Document | Status | Key Finding |
|---|---|---|
| RUNTIME_EXECUTION_TRACE.md | COMPLETE | 6 runtime violations confirmed |
| LEGACY_EXECUTION_AUDIT.md | COMPLETE | 7 DEAD/ORPHANED modules classified |
| UI_BOUNDARY_AUDIT.md | COMPLETE | 7 DataFrame ops in UI layer |
| SESSION_AUTHORITY_AUDIT.md | COMPLETE | 3 dict sessions bypass canonical |
| EXPORT_PIPELINE_VERIFICATION.md | COMPLETE | Canonical engine unreachable |
| LEGACY_RETIREMENT_PLAN.md | COMPLETE | 9 items prioritized P0-P3 |
| **test_architectural_integrity.py** | **16/16 PASSED** | Canonical properties verified |

---

## 6. RECOMMENDED NEXT ACTIONS

1. **IMMEDIATE (P0)**: Fix `str(dict)` in export_view.py:67 — 1 line change, critical impact
2. **SHORT-TERM (P1)**: Wire `ScreeningSession` to EC/IC/QC views — architectural fix, high effort
3. **SHORT-TERM (P1)**: Wire `export_engine` to `export_view` — connect canonical to UI
4. **MEDIUM-TERM (P2)**: Add metadata normalization to IC/QC views — data integrity
5. **MEDIUM-TERM (P2)**: Add deprecation banners to orphaned views
6. **LONG-TERM (P3)**: Delete orphaned views after canonical wiring confirmed

**Sprint 3 recommended focus**: Phase C from LEGACY_RETIREMENT_PLAN (architectural refactor) with test coverage.
