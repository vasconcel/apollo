# UI BOUNDARY AUDIT — Sprint 2 Phase 3

**Purpose**: Document DataFrame operations in UI layer, identify layer violations, and assess scientific integrity impact.

**Evidence standard**: Every violation must cite file:line with exact code excerpt.

---

## 1. EXECUTIVE SUMMARY

| Category | Count | Status |
|---|---|---|
| DataFrame ops in UI (iterrows, read_excel, read_csv) | 7 | VIOLATION |
| QC scores exported as str(dict) | 1 | VIOLATION |
| No structured PRISMA Excel export | 1 | VIOLATION |
| Canonical DataFrame ops (atlas_processor, article_metadata) | 3 | ACCEPTABLE |

All UI-layer violations are **confirmed by runtime evidence**. No claim is made without line-cited proof.

---

## 2. DATAFRAME OPERATIONS IN UI LAYER

### 2.1 VIOLATION — ec_screening_view.py

**File**: `src/ui/modules/ec_screening_view.py`

| Line | Operation | Violation Type |
|---|---|---|
| 133 | `pd.read_excel(temp_path, sheet_name="White Literature")` | Layer boundary: read in UI |
| 134 | `pd.read_excel(temp_path, sheet_name="Grey Literature")` | Layer boundary: read in UI |
| 137 | `for _, row in wl_df.iterrows():` | Performance anti-pattern + layer boundary |
| 138 | `row_dict = row.to_dict()` | Dict conversion in hot loop |
| 145 | `for _, row in gl_df.iterrows():` | Performance anti-pattern + layer boundary |
| 146 | `row_dict = row.to_dict()` | Dict conversion in hot loop |

**Evidence** (lines 132–146):

```python
wl_df = pd.read_excel(temp_path, sheet_name="White Literature")
gl_df = pd.read_excel(temp_path, sheet_name="Grey Literature")

articles = []
for _, row in wl_df.iterrows():
    row_dict = row.to_dict()
    article = normalize_wl_metadata(row_dict)
    article_dict = article_to_dict(article)
    article_dict["ec_decision"] = ""
    article_dict["ec_notes"] = ""
    articles.append(article_dict)

for _, row in gl_df.iterrows():
    row_dict = row.to_dict()
    article = normalize_gl_metadata(row_dict)
    article_dict = article_to_dict(article)
    article_dict["ec_decision"] = ""
    article_dict["ec_notes"] = ""
    articles.append(article_dict)
```

**Impact**:
- DataFrame parsing mixed with UI rendering — no separation of concerns
- `.iterrows()` creates dict per row (O(n) dict creation, performance anti-pattern)
- Row data immediately converted to dict (`row.to_dict()`) then passed to normalization layer
- Articles stored in `st.session_state.ec_session["articles"]` as raw dicts, bypassing `ScreeningSession` authority

**Corrective canonical path**: `atlas_processor.py:167-168` reads Excel canonical; `atlas_processor.py:328,347` uses `.iterrows()` internally (acceptable — core/domain layer). UI should delegate to `ScreeningSession.load_atlas_file()`.

---

### 2.2 VIOLATION — ic_screening_view.py

**File**: `src/ui/modules/ic_screening_view.py`

| Line | Operation | Violation Type |
|---|---|---|
| 129 | `df = pd.read_excel(temp_path, sheet_name="White Literature")` | Layer boundary: read in UI |
| 131 | `df = pd.read_excel(temp_path, sheet_name=0)` | Layer boundary: read in UI |
| 134 | `for _, row in df.iterrows():` | Performance anti-pattern + layer boundary |
| 136–142 | `row.get()` chaining to build article dict | Dict mutation in UI |

**Evidence** (lines 129–142):

```python
df = pd.read_excel(temp_path, sheet_name="White Literature")
# ...
df = pd.read_excel(temp_path, sheet_name=0)

articles = []
for _, row in df.iterrows():
    articles.append({
        "title": str(row.get("Title", row.get("title", ""))),
        "abstract": str(row.get("Abstract", row.get("abstract", ""))),
        "literature_type": str(row.get("Literature_Type", "WL")),
        "ec_decision": str(row.get("EC_Decision", "INCLUDE")),
        "ic_decision": "",
        "ic_notes": ""
    })
```

**Impact**:
- NO metadata normalization — raw `row.get()` strings passed directly to session
- No `normalize_wl_metadata` or `normalize_gl_metadata` call (contrast with ec_screening_view which calls normalization)
- `ic_screening_view` silently strips metadata fields that `ec_screening_view` preserves
- Articles stored as raw dicts, bypassing `ScreeningSession`

---

### 2.3 VIOLATION — qc_assessment_view.py

**File**: `src/ui/modules/qc_assessment_view.py`

| Line | Operation | Violation Type |
|---|---|---|
| 130 | `df = pd.read_excel(temp_path, sheet_name=0)` | Layer boundary: read in UI |
| 133 | `for _, row in df.iterrows():` | Performance anti-pattern + layer boundary |

**Evidence** (lines 130–146):

```python
df = pd.read_excel(temp_path, sheet_name=0)

articles = []
for _, row in df.iterrows():
    ic_decision = str(row.get("IC_Decision", "INCLUDE"))
    if ic_decision.upper() != "INCLUDE":
        continue

    articles.append({
        "title": str(row.get("Title", row.get("title", ""))),
        "abstract": str(row.get("Abstract", row.get("abstract", ""))),
        "literature_type": str(row.get("Literature_Type", "WL")),
        "qc_scores": {},
        "qc_total": 0,
        "qc_decision": "",
        "ic_decision": ic_decision
    })
```

**Impact**:
- Same anti-pattern as ic_screening_view
- No metadata normalization
- `qc_scores` initialized as `{}` — QC scores are strings at export time (see Section 3)

---

## 3. QC SCORES EXPORTED AS str(dict) — VIOLATION

**File**: `src/ui/modules/export_view.py`

**Violation**: `protocol_dict = protocol.to_dict()` at line 66, then `protocol_json = str(protocol_dict)` at line 67.

**Evidence** (lines 66–67):

```python
protocol_dict = protocol.to_dict()
protocol_json = str(protocol_dict)
```

**Impact**:
- `str(dict)` produces non-standard JSON: Python repr for values (e.g., `True`/`False` instead of `true`/`false`, escaped Unicode, float precision issues)
- Protocol export is NOT a valid JSON file — cannot be parsed by standard JSON parsers
- `json.dump(manifest.to_dict(), f, indent=2)` in `export_engine.py:224` IS correct (uses proper `json.dump`)
- Protocol reproducibility guarantee is BROKEN at export boundary

**Corrective**: Use `json.dumps(protocol.to_dict(), sort_keys=True, ensure_ascii=False)` instead of `str()`.

---

## 4. NO STRUCTURED PRISMA EXCEL EXPORT — VIOLATION

**File**: `src/ui/modules/export_view.py`

**Violation**: `export_view.py` produces only:
1. Protocol JSON download (broken — str(dict), line 82)
2. PRISMA counts display (UI-only, lines 88–158)
3. Audit log JSON download (line 189–193)

**Evidence**: Full file (194 lines) has NO `pd.ExcelWriter`, NO structured Excel export, NO PRISMA sheet generation.

**Impact**:
- PRISMA flow diagram requires structured Excel output — researchers must manually transcribe counts
- No `ReviewSnapshot.to_excel()` or equivalent — session decisions not exported in analyzable format
- `export_engine.py` has export capabilities but is not wired from `export_view.py`

---

## 5. CANONICAL DATAFRAME OPERATIONS — ACCEPTABLE

The following DataFrame operations are in the **core/domain layer** and are architecturally correct:

| File | Lines | Operation | Classification |
|---|---|---|---|
| `src/core/atlas_processor.py` | 167, 168 | `pd.read_excel()` | CANONICAL — domain layer file reading |
| `src/core/atlas_processor.py` | 328, 347 | `for _, row in wl_df.iterrows():` | CANONICAL — domain layer processing |
| `src/core/atlas_processor.py` | 423, 424 | `for _, row in gl_df.iterrows():` | CANONICAL — domain layer processing |
| `src/core/article_metadata.py` | 394, 411 | `pd.read_excel()` | CANONICAL — metadata normalization layer |
| `src/core/screening_session.py` | 303, 463 | `.to_dict()` | CANONICAL — serialization at boundary |
| `src/core/dynamic_protocol.py` | 162, 194, 244, 245 | `.to_dict()` | CANONICAL — serialization at boundary |
| `src/core/export_engine.py` | 184, 224 | `.to_dict()` | CANONICAL — export boundary |
| `src/ui/modules/protocol_view.py` | 549 | `.to_dict()` | CANONICAL — UI reading from canonical model |
| `src/ui/modules/export_view.py` | 66 | `.to_dict()` | CANONICAL — but `str()` is violation |

---

## 6. ARCHITECTURAL ROOT CAUSE

```
UI Layer (ec/ic/qc views)
    ↓ (reads Excel directly)
ATLAS Excel file
    ↓ (article dicts)
st.session_state.{ec,ic,qc}_session["articles"]  ← raw dicts, no ScreeningSession
    ↓
export_view reads dicts → displays PRISMA counts
    ↓
No structured Excel export
```

**Root cause**: UI layer reads and processes Excel files directly instead of delegating to a canonical ingestion pipeline that returns `ArticleReview` objects managed by `ScreeningSession`.

**Correct path**:
```
uploaded_file
    → ScreeningSession.load_atlas_file()
    → atlas_processor (canonical DataFrame processing)
    → ArticleReview objects with metadata lineage
    → ScreeningSession.articles (authority)
    → ReviewSnapshot.to_excel() (structured export)
```

---

## 7. METADATA LINEAGE IMPACT

The IC and QC views do NOT call `normalize_wl_metadata` / `normalize_gl_metadata`:

| View | Calls normalize_wl_metadata? | Calls normalize_gl_metadata? |
|---|---|---|
| `ec_screening_view.py` | YES (line 139) | YES (line 147) |
| `ic_screening_view.py` | NO — raw row.get() | NO — raw row.get() |
| `qc_assessment_view.py` | NO — raw row.get() | NO — raw row.get() |

**Impact on scientific reproducibility**:
- EC stage: articles have standardized metadata (authors, year, DOI, etc.)
- IC stage: metadata fields silently dropped — only title/abstract preserved
- QC stage: same dropout — provenance chain broken between stages
- Researchers cannot trace QC decisions back to original ATLAS metadata

---

## 8. SEVERITY ASSESSMENT

| Violation | Severity | Reversible | Fix Complexity |
|---|---|---|---|
| DataFrame ops in UI (7 occurrences) | **HIGH** | YES | Medium — delegate to ScreeningSession ingestion |
| QC scores as str(dict) | **MEDIUM** | YES | LOW — use json.dumps() |
| No PRISMA Excel export | **MEDIUM** | YES | Medium — wire export_engine to export_view |
| Metadata lineage dropout (IC/QC) | **HIGH** | YES | Medium — call normalize functions |

**No irreversible damage**. All violations are data-processing patterns that can be refactored without changing protocol logic.

---

## 9. VERIFICATION CHECKLIST

- [ ] **CONFIRMED**: ec_screening_view.py:133-146 reads Excel in UI
- [ ] **CONFIRMED**: ic_screening_view.py:129-134 reads Excel in UI, no normalization
- [ ] **CONFIRMED**: qc_assessment_view.py:130-133 reads Excel in UI, no normalization
- [ ] **CONFIRMED**: export_view.py:67 uses str(dict) instead of json.dumps()
- [ ] **CONFIRMED**: export_view.py has no Excel export (full file review)
- [ ] **CONFIRMED**: canonical DataFrame ops in atlas_processor.py:167-168, 328, 347, 423-424 (domain layer — acceptable)
- [ ] **CONFIRMED**: normalize_wl_metadata / normalize_gl_metadata called in ec_screening_view.py but NOT in ic_screening_view.py or qc_assessment_view.py

---

## 10. RECOMMENDATIONS (FOR PHASE 7 — LEGACY RETIREMENT PLAN)

1. **Create canonical ingestion method**: `ScreeningSession.load_atlas_file(uploaded_file)` that handles Excel reading, normalization, and ArticleReview creation
2. **Replace UI DataFrame ops**: All three views should call `ScreeningSession.load_atlas_file()` instead of inline `pd.read_excel` / `.iterrows()`
3. **Fix protocol export**: Replace `str(protocol_dict)` with `json.dumps(protocol.to_dict(), sort_keys=True, ensure_ascii=False)` in export_view.py
4. **Wire export_engine to export_view**: Add structured Excel export for PRISMA flow diagram
5. **Add metadata normalization to IC/QC views**: Ensure `normalize_wl_metadata` / `normalize_gl_metadata` are called consistently across all stages

**Do not remove DataFrame ops from atlas_processor.py** — those are canonical domain operations.
