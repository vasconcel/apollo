# Author Decoding Validation - Runtime Forensics

## Instrumentation Added

### 1. Startup Logging
Added to `article_metadata.py`:
- pylatexenc version
- latex_to_unicode import status
- LATEX_DECODER_AVAILABLE boolean

### 2. decode_author_string() Debug
Added logging:
- Raw input (repr)
- pylatexenc decoded output (if applicable)
- Fallback output (if pylatexenc fails)
- Final returned value

### 3. normalize_wl_metadata() Debug
Added logging:
- Raw authors from column
- Decoded authors after pylatexenc

### 4. Metadata Provenance
Added `author_normalization_source` field:
- Values: "pylatexenc", "raw", "unknown"

## Forensic Decoding Table

| Input | Expected Output | Decoder | Validated |
|-------|-----------------|---------|-----------|
| `M{\"u}ller` | Müller | pylatexenc | UNVERIFIED |
| `Garc{\\'i}a` | García | pylatexenc | UNVERIFIED |
| `Fran{\\c{c}}ois` | François | pylatexenc | UNVERIFIED |
| `Muller` | Muller | None (no LaTeX) | UNVERIFIED |
| Empty string | "" | - | UNVERIFIED |
| "nan" | "" | - | UNVERIFIED |

## Code Analysis Findings

### pylatexenc Import Status
```python
try:
    from pylatexenc import latex_to_unicode
    LATEX_DECODER_AVAILABLE = True
except ImportError:
    LATEX_DECODER_AVAILABLE = False
```

**Issue**: In Python 3.14 with pylatexenc 2.10, `latex_to_unicode` may not be directly importable from `pylatexenc` package root.

**Impact**: LATEX_DECODER_AVAILABLE may be False, falling back to raw string return.

### Test Data Constraint
- Test file has NO Authors column
- Cannot reproduce "Müllerller" corruption
- Need user data with actual Author field

## Validation Required

User must:
1. Run app - observe startup logging for pylatexenc status
2. Upload file with Author column containing LaTeX encoding
3. Verify debug logs show:
   - Raw input
   - Decoded output
   - author_normalization_source in metadata
4. Verify no "Müllerller" duplication

## Code Change vs Runtime Validation

| Item | Code Change | Runtime Validation |
|------|-------------|-------------------|
| Startup logging | ✅ Added | ❌ Pending |
| decode_author_string logging | ✅ Added | ❌ Pending |
| author_normalization_source field | ✅ Added | ❌ Pending |
| pylatexenc import fix | ⚠️ May need fix | ❌ Pending |

## Possible pylatexenc Fix

If import fails, alternative import paths to try:
```python
from pylatexenc.latex2unicode import latex_to_unicode
from pylatexenc.latexencode import unicode_to_latex
```

Need to verify which works in pylatexenc 2.10.