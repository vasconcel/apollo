# Reality Alignment Report - APOLLO v2.0.0 Primal

## Executive Summary

This report corrects the previous invalid conclusions and provides ACTUAL runtime-validated findings.

## Key Corrections

### 1. YEAR PIPELINE - ROOT CAUSE FOUND

**Previous Report**: Claimed fix applied, year working
**Reality**: 
- Test file has NO Year column
- No structured year exists in source data
- Regex fallback was NOT being called in ingestion

**Actual Fix**: Added `extract_year()` regex fallback to `screening_session.py` for:
- WL Excel ingestion
- GL Excel ingestion  
- CSV ingestion

**Validation Status**: CODE CHANGE APPLIED, RUNTIME VALIDATION PENDING

---

### 2. AUTHOR DECODING - CANNOT REPRODUCE

**Previous Report**: Claimed pylatexenc integrated, corruption fixed
**Reality**:
- Test file has NO Authors column
- Cannot reproduce "Müllerller" with available data
- pylatexenc import may fail silently (`latex_to_unicode` not available in v2.10)

**Validation Status**: CODE CHANGE PENDING CONFIRMATION, RUNTIME VALIDATION IMPOSSIBLE WITHOUT TEST DATA

---

### 3. SIDEBAR WIDTH - ENHANCED CSS APPLIED

**Previous Report**: Claimed fix applied
**Reality**: 
- Previous CSS targeting was incomplete
- Did not target BaseWeb radio internals
- Did not target [role="radiogroup"]

**Actual Fix**: Added more aggressive CSS targeting:
- `[data-baseweb="radio"]` 
- `[role="radiogroup"]`
- Inner divs with `max-width: 100%`

**Validation Status**: CODE CHANGE APPLIED, RUNTIME VALIDATION PENDING

---

## What Was Actually Changed

| Issue | Code Change | Runtime Validation |
|-------|-------------|-------------------|
| Year pipeline | Added `extract_year()` fallback | NEEDS USER TEST |
| Author decoding | No change possible without test data | IMPOSSIBLE |
| Sidebar width | Enhanced CSS selectors | NEEDS USER TEST |

## Separation of Claims

| Claim Type | Status |
|------------|--------|
| CODE CHANGE APPLIED | ✅ Verified - changes made to files |
| RUNTIME VALIDATION CONFIRMED | ❌ Cannot confirm without user testing |

## Files Modified

1. `src/core/screening_session.py` - Added year regex fallback
2. `src/ui/styles.py` - Enhanced sidebar CSS selectors

## User Action Required

To validate these fixes:

1. **Year**: Upload ATLAS file with data - verify year shows correctly
2. **Sidebar**: Run app - verify navigation fills width
3. **Author**: Provide sample with Author column to debug "Müllerller"

## Conclusion

The previous reports contained INVALID SUCCESS DECLARATIONS. This report provides:
- Actual root causes identified through code analysis
- Runtime constraints discovered (test file missing columns)
- Enhanced fixes based on deeper DOM analysis
- Clear separation between code changes and validation status