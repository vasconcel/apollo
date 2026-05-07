# APOLLO Migration Plan - Human-in-the-Loop Refactoring

## Document Version: 1.0.0
## Date: 2026-05-07

---

## 1. Executive Summary

This document describes the migration from APOLLO's deterministic automatic screening engine to a human-in-the-loop (HITL) scientific screening environment. The key change is that LLM suggestions become advisory while researchers make explicit final decisions.

### Key Changes

| Before | After |
|--------|-------|
| Automatic decisions | Researcher makes final decisions |
| LLM decides | LLM suggests, researcher chooses |
| No explicit decisions | Researcher chooses: Include/Exclude/Skip/Needs Discussion |
| Single-pass flow | Staged workflow (EC → IC → QC) |
| Basic export | Full audit trail + calibration exports |

---

## 2. Architecture Changes

### New Modules

```
src/core/
├── screening_session.py    # Session management
├── reviewer_state.py       # Per-researcher state tracking
├── decision_engine.py      # Human-in-the-loop orchestration
├── llm_assistant.py        # Advisory LLM suggestions
├── calibration_engine.py  # Inter-rater reliability
└── export_engine.py       # Auditable exports

src/ui/modules/
└── review_view.py          # Streamlit review interface
```

### Module Responsibilities

| Module | Responsibility |
|--------|----------------|
| screening_session.py | Manage review sessions, track progress |
| reviewer_state.py | Track individual researcher decisions |
| decision_engine.py | Orchestrate workflow, integrate LLM suggestions |
| llm_assistant.py | Generate advisory suggestions |
| calibration_engine.py | Generate Kappa-ready exports |
| export_engine.py | Full audit trail exports |
| review_view.py | Streamlit review UI |

### Data Flow Changes

```
ATLAS File → Load → Session Created → Researcher Reviews
                                      ↓
                              LLM Advisory Suggestion
                                      ↓
                        Researcher Makes Final Decision
                                      ↓
                     EC Stage → IC Stage → QC Stage → Export
```

---

## 3. New Workflow: Staged Human Screening

### Stage 1: EC (Exclusion Criteria)

1. Researcher sees Title + Abstract + metadata
2. LLM provides exclusion suggestion + justification
3. Researcher chooses:
   - **Include** → Move to IC stage
   - **Exclude** → Record exclusion, move to next
   - **Skip** → Skip article
   - **Needs Discussion** → Mark for discussion

### Stage 2: IC (Inclusion Criteria)

1. Same pattern as EC
2. Focus on relevance to SE R&S

### Stage 3: QC (Quality Assessment)

1. Same pattern as EC/IC
2. Focus on study quality

### Decision Options

| Option | Meaning |
|--------|---------|
| Include | Article passes this stage |
| Exclude | Article excluded at this stage |
| Skip | Skip for later review |
| Needs Discussion | Mark for team discussion |

---

## 4. UI Flow Description

### Main Screen

1. **Sidebar**:
   - Session info (ID, stage, progress)
   - Quick stats (included/excluded/discussion counts)

2. **Main Area**:
   - Article card (title, abstract, metadata)
   - LLM suggestion panel (decision, confidence, justification)
   - Decision buttons (Include/Exclude/Skip/Needs Discussion)
   - Notes textarea

3. **Navigation**:
   - Stage selector (EC/IC/QC)
   - Progress indicator

### Export Options

- **Excel**: Legacy format (for compatibility)
- **Session JSON**: Full session with LLM suggestions
- **Audit Log**: Decision trail with hashes
- **Calibration**: 2x2 matrix for Cohen's Kappa

---

## 5. Backward Compatibility

### Preserved

- `export_apollo_selection_criteria()` function signature
- Output Excel format (WL, GL, WL Seeds for HERMES sheets)
- Protocol engine integration
- Regression test compatibility

### New API

```python
# New: Human-in-the-loop workflow
from src.core.screening_session import create_session
from src.core.decision_engine import HumanDecisionEngine
from src.core.export_engine import create_export

# Legacy: Still works
from src.core.atlas_processor import export_apollo_selection_criteria
```

---

## 6. Migration Timeline

### Phase 1: Core Modules (Completed)
- [x] screening_session.py
- [x] reviewer_state.py
- [x] decision_engine.py
- [x] llm_assistant.py
- [x] calibration_engine.py
- [x] export_engine.py

### Phase 2: Integration (Completed)
- [x] Refactor atlas_processor.py
- [x] Add create_screening_session() function
- [x] Preserve process_atlas_file() for regression

### Phase 3: UI (Completed)
- [x] review_view.py Streamlit interface
- [x] Update app.py to include new view

### Phase 4: Testing (Pending)
- [ ] Run existing regression tests
- [ ] Validate backward compatibility

---

## 7. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM unavailable | Medium | Manual review fallback |
| Session state loss | High | Auto-save on each decision |
| Export format changes | Low | Legacy export preserved |
| Protocol mismatch | Medium | Version tracking |

---

## 8. Reproducibility Impact

### What's Preserved

- Protocol checksums
- Audit logging
- Deterministic hash
- Protocol version tracking

### What's New

- Per-researcher decision tracking
- LLM suggestion logging
- Calibration-ready exports
- Full decision audit trail

---

## 9. Protocol Version Traceability

Each session records:
- Protocol version used
- Input file checksum
- All decisions with timestamps
- LLM suggestions (advisory only)

Export manifest includes:
- Export timestamp
- Protocol version
- Input file checksum
- Total articles processed

---

## 10. Testing Strategy

### Existing Tests (Preserve)

```bash
python tests/test_apollo_regression.py
python tests/test_protocol_parity.py
python tests/test_protocol_layer.py
```

### New Tests

```bash
# Session management
tests/test_screening_session.py

# Human decision workflow
tests/test_reviewer_state.py

# LLM suggestions
tests/test_llm_assistant.py

# Calibration exports
tests/test_calibration_engine.py
```

---

## 11. Configuration

### Environment Variables

| Variable | Purpose |
|----------|---------|
| GROQ_API_KEY | LLM suggestions |
| OPENAI_API_KEY | LLM suggestions fallback |

### Optional Components

- LLM: If unavailable, researcher reviews manually
- Calibration: If single researcher, sequential pairs
- Export: All exports optional

---

## 12. Rollback Plan

### If Issues Found

1. Use legacy `process_atlas_file()` function
2. Keep existing regression tests passing
3. Maintain backward compatibility mode

### Known Limitations

- No multi-user sync (single session at a time)
- No cloud/database (local-first)
- No authentication (single researcher)

---

## Summary

The migration introduces:

1. ✅ **Human-in-the-loop**: Researcher makes final decisions
2. ✅ **Staged workflow**: EC → IC → QC
3. ✅ **LLM suggestions**: Advisory, not final
4. ✅ **Audit trail**: Full decision tracking
5. ✅ **Calibration ready**: Kappa exports
6. ✅ **Backward compatible**: Legacy mode preserved

The key principle: **Researcher is the final decision-maker, not the LLM.**