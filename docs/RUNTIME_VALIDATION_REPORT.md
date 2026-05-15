# Runtime Validation Report - APOLLO v2.0.0 Primal

## Executive Summary

This pass adds REAL runtime instrumentation to validate fixes. Distinguishes between:
- CODE CHANGE APPLIED
- RUNTIME VALIDATION CONFIRMED

## Separation of Claims

| Category | Count | Items |
|----------|-------|-------|
| VERIFIED | 0 | None - requires runtime |
| ASSUMED | 3 | Year fix works, author fix works, sidebar works |
| UNVERIFIED | 5 | All require runtime testing |
| CANNOT REPRODUCE | 1 | "Müllerller" - no test data |

---

## 1. Year Pipeline - ASSUMED

### Code Changes Applied
- ✅ Added `_get_year()` with NaN handling in article_metadata.py
- ✅ Added `extract_year()` regex fallback in screening_session.py
- ✅ Added debug logging throughout pipeline
- ✅ Added `normalize_metadata()` defensive function
- ✅ Added `year_source` tracking

### Runtime Validation Pending
- [ ] Console shows debug logs during file upload
- [ ] Year extracted via regex from title/abstract
- [ ] Year source shows "regex" (not "atlas" when no column)
- [ ] Year displays in UI (not "Unknown")

### Test Data Constraint
- Test file has NO Year column
- Cannot verify structured year extraction works

---

## 2. Author Normalization - CANNOT REPRODUCE

### Code Changes Applied
- ✅ Added pylatexenc integration
- ✅ Added startup logging for pylatexenc availability
- ✅ Added decode_author_string() debug logging
- ✅ Added author_normalization_source field

### Runtime Validation Pending
- [ ] Startup log shows LATEX_DECODER_AVAILABLE = True/False
- [ ] Debug logs show author processing
- [ ] No "Müllerller" duplication

### Cannot Reproduce
- Test file has NO Authors column
- Cannot validate "Müllerller" fix without test data

---

## 3. Sidebar Width - ASSUMED

### Code Changes Applied
- ✅ Enhanced CSS with BaseWeb selectors
- ✅ Added radiogroup targeting
- ✅ Added max-width enforcement
- ✅ Added SIDEBAR_DEBUG flag for visual validation

### Runtime Validation Pending
- [ ] Set SIDEBAR_DEBUG = True
- [ ] Verify outlines visible on labels/containers
- [ ] Verify labels full width

### Known Risk
- Streamlit/BaseWeb may override CSS with inline styles
- May need config adjustment or alternative component

---

## 4. Metadata Provenance - ASSUMED

### Code Changes Applied
- ✅ Added `normalize_metadata()` defensive function
- ✅ Applied to WL and GL ingestion paths
- ✅ Guaranteed all required fields present
- ✅ Added default values for missing fields

### Runtime Validation Pending
- [ ] Verify all articles have required fields
- [ ] No silent empty strings
- [ ] Year defaults to "Unknown" (not "")

---

## 5. Advisory Consistency - VERIFIED (Code)

### Code Analysis Verified
- [x] No confidence_pct in ec_screening_view.py
- [x] No confidence_pct in ic_screening_view.py
- [x] Signal-based labeling ("Strong heuristic alignment")
- [x] Only LLM prompt contains "CONFIDENCE" (not UI)

---

## User Action Required

To validate runtime behavior:

1. **Year Pipeline**
   ```bash
   # Run app and upload ATLAS file
   # Check console for debug output:
   # [YEAR DEBUG] ...
   # [INGEST WL 0] ...
   ```

2. **Author Normalization**
   ```bash
   # Check startup output for:
   # === AUTHOR DECODER INITIALIZATION ===
   # pylatexenc version: ...
   # LATEX_DECODER_AVAILABLE: True/False
   ```

3. **Sidebar**
   ```python
   # In styles.py, set:
   SIDEBAR_DEBUG = True
   # Then run app and inspect sidebar visually
   ```

4. **Metadata Provenance**
   ```python
   # In Python:
   for a in session.articles:
       print(a.metadata.keys())
   # Should contain all required fields
   ```

---

## Files Modified

| File | Changes |
|------|---------|
| src/core/article_metadata.py | Debug logging, year extraction, author decoding |
| src/core/screening_session.py | Debug logging, regex fallback, metadata normalization |
| src/ui/styles.py | Enhanced sidebar CSS, debug mode |

---

## Documentation Produced

1. YEAR_TRACE_MATRIX.md - Year pipeline instrumentation
2. AUTHOR_DECODING_VALIDATION.md - Author forensics
3. SIDEBAR_RUNTIME_VALIDATION.md - Sidebar DOM analysis
4. METADATA_PROVENANCE_AUDIT.md - Metadata hardening

---

## Final Assessment

**NO VERIFIED FIXES** - all require runtime validation.

The previous "FIXED" claims were INVALID. This report provides:
- Actual instrumentation for real validation
- Clear separation between code changes and runtime behavior
- Specific verification steps for user to execute