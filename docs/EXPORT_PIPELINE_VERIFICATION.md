# EXPORT PIPELINE VERIFICATION — Sprint 2 Phase 5

**Purpose**: Verify the export pipeline end-to-end, confirm QC scores as str(dict), assess PRISMA Excel export capability, and document all export paths.

**Evidence standard**: Every violation must cite file:line with exact code excerpt.

---

## 1. EXECUTIVE SUMMARY

| Export Path | Format | Canonical? | Status |
|---|---|---|---|
| `export_view.py:66-82` | Protocol JSON | YES (but broken) | **VIOLATION** — `str(dict)` not valid JSON |
| `export_view.py:88-158` | PRISMA counts | N/A — UI display only | **VIOLATION** — No structured Excel export |
| `export_view.py:189-193` | Audit log JSON | PARTIAL | WEAK — protocol metadata only, no decision audit |
| `qc_assessment_view.py:374` | QC CSV | NO | **VIOLATION** — QC scores as `str(dict)` |
| `export_engine.py:79-135` | Decisions Excel | YES | UNREACHABLE — never called from UI |
| `export_engine.py:151-162` | Session JSON | YES | UNREACHABLE — never called from UI |
| `export_engine.py:164-198` | Audit log | YES | UNREACHABLE — never called from UI |
| `export_engine.py:200-226` | Manifest | YES | UNREACHABLE — never called from UI |

**All canonical export methods exist in `export_engine.py` but are completely unreachable from the UI**. The UI produces broken/partial exports instead.

---

## 2. EXPORT_VIEW.PY — BROKEN PROTOCOL EXPORT

**File**: `src/ui/modules/export_view.py:66-82`

**Violation**: `str(protocol_dict)` instead of `json.dumps()`.

**Evidence** (lines 66-67):
```python
protocol_dict = protocol.to_dict()
protocol_json = str(protocol_dict)
```

**Problem**: Python's `str()` on a dict produces Python repr, not valid JSON:
- `True`/`False` instead of `true`/`false`
- `'single quotes'` instead of `"double quotes"`
- Possible unescaped Unicode characters
- Single quotes around keys that are not valid JSON

**Correct code** (from `src/core/dynamic_protocol.py:413`):
```python
# dynamic_protocol.py:413 — canonical correct usage
content = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
```

**Impact**: Protocol JSON file downloaded from `export_view` is **NOT parseable by standard JSON parsers**. Reproducibility guarantee is broken at the export boundary.

---

## 3. QC SCORES EXPORTED AS str(dict)

**File**: `src/ui/modules/qc_assessment_view.py:374`

**Violation**: QC scores exported as string representation of dict.

**Evidence** (lines 358-386):
```python
def export_qc_results(session: Dict):
    """Export QC assessment results."""
    import pandas as pd

    articles = session["articles"]
    assessments = session["assessments"]

    results = []
    for i, article in enumerate(articles):
        assessment = assessments.get(i, {})
        decision = assessment.get("qc_decision", "pending")
        results.append({
            "Title": article["title"],
            "Literature_Type": article["literature_type"],
            "QC_Decision": decision.upper(),
            "QC_Score": assessment.get("qc_total", 0),
            "QC_Scores": str(assessment.get("qc_scores", {})),  # ← VIOLATION
            "Abstract": article.get("abstract", "")
        })
```

**Example output** (`QC_Scores` column):
```
"{'WL1': 0.5, 'WL2': 1.0, 'WL3': 0.5}"
```

This is a **string**, not a structured data field. Cannot filter, sort, or analyze QC scores per criterion in spreadsheet software. Must be parsed with `eval()` or `ast.literal_eval()` to recover the dict.

**Contrast with canonical pattern** (`export_engine.py:88-116`):
```python
for article in session.articles:
    meta = article.metadata
    # ... extracts individual fields, writes as separate columns
```

**Impact**: QC criterion-level scores are not analyzable post-export. Researchers must manually parse Python dict strings to analyze quality patterns.

---

## 4. NO STRUCTURED PRISMA EXCEL EXPORT

**File**: `src/ui/modules/export_view.py` (full file, 194 lines)

**Violation**: No `pd.ExcelWriter` anywhere in the file. No structured Excel export for PRISMA flow diagram.

**Evidence**: Full file search — zero `pd.ExcelWriter`, zero `to_excel()`, zero structured sheet generation.

**What `export_view` DOES produce**:
1. Protocol JSON download (broken — `str(dict)`)
2. PRISMA counts displayed as ASCII art (lines 138-158) and HTML metric tiles
3. Audit log JSON (just protocol metadata — not decision-level audit)

**What researchers NEED for PRISMA**:
- Structured Excel with columns: Title, Authors, Year, DOI, Decision, Stage, Notes, Rationale
- WL sheet + GL sheet + Summary sheet
- PRISMA flow diagram counts in machine-readable format

**Contrast with canonical pattern** (`export_engine.py:79-135`):
```python
with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    if wl_data:
        pd.DataFrame(wl_data).to_excel(writer, sheet_name="WL", index=False)
    if gl_data:
        pd.DataFrame(gl_data).to_excel(writer, sheet_name="GL", index=False)
    pd.DataFrame(columns=[]).to_excel(writer, sheet_name="WL Seeds for HERMES", index=False)
```

This method exists, is complete, and is **never called**.

---

## 5. EXPORT ENGINE — UNREACHABLE CANONICAL CODE

**File**: `src/core/export_engine.py`

All canonical export methods are **fully implemented** but unreachable from UI:

### 5.1 export_decisions_excel (lines 79-135)

**Fully implemented**. Produces WL/GL sheets with proper column structure. Extracts metadata fields individually (not as `str(dict)`). Uses `openpyxl` engine.

**Status**: UNREACHABLE — not imported by `export_view.py`.

### 5.2 export_session_json (lines 151-162)

**Fully implemented**. Uses `json.dump()` (correct, not `str()`). Includes full session state.

**Status**: UNREACHABLE — not imported by `export_view.py`.

### 5.3 export_audit_log (lines 164-198)

**Fully implemented**. Produces decision-level audit entries with SHA256 hashes.

**Status**: UNREACHABLE — not imported by `export_view.py`.

### 5.4 export_manifest (lines 200-226)

**Fully implemented**. Records input file checksum, article counts, protocol version, session metadata. Uses `json.dump()` (correct).

**Status**: UNREACHABLE — not imported by `export_view.py`.

### 5.5 export_all (lines 228-255)

**Fully implemented**. Orchestrates all exports (Excel + JSON + Audit + Manifest) to timestamped files. Uses `json.dump()` throughout.

**Status**: UNREACHABLE — not imported by `export_view.py`.

---

## 6. CALIBRATION VIEW — JSON LOADING (ACCEPTABLE)

**File**: `src/ui/modules/calibration_view.py:21-32`

The calibration view reads session JSON files for IRR computation:

```python
def load_session_json(uploaded_file):
    try:
        data = json.load(uploaded_file)
        if "session_id" not in data or "articles" not in data:
            st.error(f"Invalid Session File: {uploaded_file.name}")
            return None
        return data
    except Exception as e:
        st.error(f"Error parsing JSON: {str(e)}")
        return None
```

**Status**: ACCEPTABLE — uses `json.load()` (correct), not `str()`. However, it expects `ScreeningSession`-style JSON (with `session_id`, `articles`), but the UI produces dict sessions that don't match this schema.

**Impact**: Calibration expects `export_engine.py` output format, but `export_view.py` never produces it. Calibration is effectively non-functional — it cannot load any session data produced by the current export pipeline.

---

## 7. EXPORT PIPELINE DISCONNECTION MAP

```
┌─────────────────────────────────────────────────────────┐
│ UI Layer                                                 │
│  export_view.py                                         │
│   ├─ Protocol JSON (broken — str(dict)) → BROKEN       │
│   ├─ PRISMA counts (UI display) → NOT EXPORTED          │
│   └─ Audit log (partial) → NOT DECISION-LEVEL           │
│  qc_assessment_view.py                                  │
│   └─ QC CSV (broken — str(dict) for scores) → BROKEN    │
└────────────────────────────────────┬────────────────────┘
                                     │ NEVER CALLED
┌────────────────────────────────────▼────────────────────┐
│ Core Layer (UNREACHABLE)                                │
│  export_engine.py                                       │
│   ├─ export_decisions_excel() → CANONICAL              │
│   ├─ export_session_json() → CANONICAL                  │
│   ├─ export_audit_log() → CANONICAL                     │
│   ├─ export_manifest() → CANONICAL                      │
│   └─ export_all() → CANONICAL                           │
└─────────────────────────────────────────────────────────┘
```

---

## 8. VERIFICATION CHECKLIST

- [ ] **CONFIRMED**: `export_view.py:67` uses `str(dict)` instead of `json.dumps()`
- [ ] **CONFIRMED**: `qc_assessment_view.py:374` exports QC scores as `str(dict)`
- [ ] **CONFIRMED**: `export_view.py` has no `pd.ExcelWriter` (full file review)
- [ ] **CONFIRMED**: `export_engine.py` methods are canonical and fully implemented
- [ ] **CONFIRMED**: `export_engine` is not imported by any UI module
- [ ] **CONFIRMED**: `calibration_view.py:24` uses `json.load()` (correct)
- [ ] **CONFIRMED**: `calibration_view` expects `ScreeningSession` JSON format, which the current export pipeline cannot produce
- [ ] **CONFIRMED**: `dynamic_protocol.py:413` uses `json.dumps()` (canonical correct pattern)

---

## 9. SCIENTIFIC INTEGRITY IMPACT

| Issue | Impact |
|---|---|
| Protocol JSON as `str(dict)` | Protocol cannot be parsed for reproducibility verification |
| QC scores as `str(dict)` | QC criterion-level analysis impossible post-export |
| No PRISMA Excel export | Researchers must manually transcribe counts to PRISMA diagram |
| Export engine unreachable | All canonical export methods exist but cannot be triggered |
| Calibration expects canonical format | IRR analysis non-functional — session exports don't match expected schema |

---

## 10. ROOT CAUSE

**Two parallel export systems**:
1. **Broken UI exports** (`export_view.py`, `qc_assessment_view.py`) — produce non-standard output
2. **Canonical export engine** (`export_engine.py`) — fully functional but never wired

The canonical `export_engine.py` was built as a separate module but was never connected to the UI layer. The UI exports are a stopgap that became the de facto path.

---

## 11. RECOMMENDATIONS (FOR PHASE 7 — LEGACY RETIREMENT PLAN)

1. **Wire `export_engine` to `export_view`**: Import and call canonical methods from `export_view`
2. **Fix protocol export**: Replace `str(protocol_dict)` with `json.dumps(protocol.to_dict(), sort_keys=True, ensure_ascii=False)`
3. **Fix QC CSV export**: Replace `str(assessment.get("qc_scores", {}))` with individual criterion columns
4. **Add PRISMA Excel export**: Call `export_engine.export_decisions_excel()` with dict session → canonical session conversion
5. **Fix calibration schema**: Ensure session exports match what `calibration_view.py` expects
6. **Preserve `export_engine.py`**: It is canonical code that needs to be wired, not rewritten
7. **DO NOT delete broken exports**: They serve as a reference for what NOT to do

**The broken exports are the legacy pattern to retire**. `export_engine.py` is the canonical target.
