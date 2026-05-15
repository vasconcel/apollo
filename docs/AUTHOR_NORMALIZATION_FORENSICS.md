# Author Normalization Forensics

## Runtime Observations

### Test File Analysis
Tested with: `ATLAS_Master_Initial_Search.xlsx`

**Finding**: Spreadsheet has NO Authors column.
```
Available columns: ['Library', 'Global_ID', 'Local_ID', 'Title', 'Abstract', 'Keywords']
```

### Cannot Reproduce "Müllerller" Issue

The test data does not contain an Authors column, so I cannot reproduce the "Müllerller" corruption pattern reported by the user.

## Hypotheses Tested

### Hypothesis 1: Double pylatexenc processing
- **Tested**: Search for multiple `decode_author_string()` calls
- **Result**: Function called exactly once per article in normalization layer (lines 296, 337 in article_metadata.py)
- **Status**: Ruled out - no double-call found

### Hypothesis 2: Manual replacement chain still active
- **Tested**: Search for `.replace()` chains in author processing
- **Result**: No manual replacements found in author processing code
- **Status**: Ruled out in code

### Hypothesis 3: pylatexenc import failure
- **Tested**: Check pylatexenc import
- **Result**: `latex_to_unicode` import fails (not available in pylatexenc 2.10)
- **Status**: `LATEX_DECODER_AVAILABLE = False` - function returns string unchanged
- **Impact**: If user's file has LaTeX-encoded authors, they won't be decoded

### Hypothesis 4: Venue normalization touching authors
- **Tested**: Search for normalize_venue_name usage with authors
- **Result**: Only applied to "source" field, not authors
- **Status**: Ruled out

### Hypothesis 5: UI layer post-processing
- **Tested**: Search for author processing in UI code
- **Result**: UI only reads metadata.get("authors"), no transformation
- **Status**: Ruled out

## Current State

1. **decode_author_string()** correctly uses pylatexenc when available
2. When pylatexenc unavailable, returns string unchanged
3. No double-processing found in code path

## Possible Causes for "Müllerller" (Unverified)

1. **User's ATLAS file has Authors column** (test file doesn't)
2. **pylatexenc actually works** and there's a bug in how it handles certain inputs
3. **Some other pre-processing** specific to user's data environment
4. **Import path issue** - different pylatexenc version behaves differently

## Validation Required

User must provide sample data with actual Author field to verify:
1. Whether pylatexenc is importing correctly
2. Whether "Müllerller" can be reproduced
3. What the raw author string looks like before processing

## Code Confidence

- **Year fix**: High confidence (added explicit regex fallback)
- **Author fix**: Cannot verify without test data with Author column