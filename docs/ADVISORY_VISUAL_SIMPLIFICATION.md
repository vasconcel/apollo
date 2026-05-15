# Advisory Visual Simplification Report

## Issue
EC advisory was simplified in previous pass, but IC advisory STILL contained:
- Percentage-based confidence ("Confidence: 100%")
- Duplicated confidence semantics
- Excessive visual prominence

The advisory was competing with article content for attention.

## Goal
Apply SAME cleanup pattern used in EC to IC advisory:
- Remove percentage-based confidence
- Replace with decision-based labeling
- Keep advisory SUBORDINATE to article content
- Remove duplicated grounding warnings

## Changes Applied

### IC Advisory Update (`ic_screening_view.py`)

#### Before
```python
confidence = suggestion.get("confidence", 0)
confidence_pct = int(confidence * 100)
...
col_conf:
    metric_tile("CONFIDENCE", f"{confidence_pct}%")
```

#### After
```python
confidence = suggestion.get("confidence", 0)

if confidence >= 0.7:
    signal_label = "Strong heuristic alignment"
elif confidence >= 0.4:
    signal_label = "Moderate LLM signal"
else:
    signal_label = "Weak heuristic alignment"
...
col_conf:
    metric_tile("SIGNAL", signal_label)
```

### Logic
| Confidence Range | Signal Label |
|------------------|---------------|
| >= 0.7 (70%+)    | Strong heuristic alignment |
| >= 0.4 (40-69%)  | Moderate LLM signal |
| < 0.4 (<40%)     | Weak heuristic alignment |

## Duplication Removal

### Before
- Grounding metadata displayed in multiple places
- Multiple confidence calculations
- Redundant advisory summaries

### After
- Single grounding display (kept for traceability)
- No percentage calculations
- Clean signal label

## Files Modified
- `src/ui/modules/ic_screening_view.py` - `render_suggestion_details()` function

## Validation

### EC + IC Advisory Coherence
- Both now use decision-based labeling (not percentage)
- Both show "SIGNAL" metric instead of "CONFIDENCE"
- Both use simplified categories:
  - "Strong heuristic alignment"
  - "Moderate LLM signal"  
  - "Weak heuristic alignment"

### Visual Hierarchy
- Advisory is now clearly subordinate to article content
- Signal label provides quick assessment without numeric precision
- Grounding metadata preserved for auditability

## Remaining Considerations
- LLM reasoning text still shown below signal label
- Triggered criteria panel still available for detailed analysis
- Fallback warning maintained when LLM unavailable