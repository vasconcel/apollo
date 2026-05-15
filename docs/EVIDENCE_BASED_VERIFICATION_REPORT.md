# APOLLO v1.0.0 Evidence-Based Verification Report

**Date**: 2026-05-14
**Purpose**: Verify all prior claims with direct repository evidence

---

## Phase 1 — Test Claims Validation

### Claim: "66 tests collected, 63 passing, 3 failing"

**EVIDENCE**:
```
$ python -m pytest tests/unit/test_design_system_ux.py tests/unit/test_structured_advisory.py tests/unit/test_visual_logic.py -v

======================== 1 failed, 65 passed in 0.66s =========================
```

**FINDING**: **PARTIALLY VERIFIED**

- Tests collected: 66 (from test output)
- Tests passing: 65 (from test output)
- Tests failing: 1 (test_workflow_components_importable)
- Collection errors: 4 (test_protocol_layer.py calls sys.exit(0))

The prior claim of "3 failing" is **OVERSTATED** - only 1 actually fails.

---

## Phase 2 — Reproducibility Claims Validation

### Claim: "Session checksum deterministic"

**EVIDENCE**:
```
Run 1: 6eb307fe681e6acc...
Run 2: 6eb307fe681e6acc...
Run 3: 6eb307fe681e6acc...
```

**FINDING**: **VERIFIED** ✅

### Claim: "Bundle checksums present in session.json"

**EVIDENCE**:
```python
with open(bundle.session_json) as f:
    data = json.load(f)
print(f'session_checksum in JSON: {"session_checksum" in data}')
# Output: session_checksum in JSON: False
```

**FINDING**: **CONTRADICTED** ❌

The session_checksum is NOT written to session.json during bundle creation.

### Claim: "Replay is deterministic"

**EVIDENCE**:
```
Replay checksums: ['30f202eee5416588', '02b6bb061d10fa95', 'eb30344ee9f33e17']
All identical: False
```

**FINDING**: **CONTRADICTED** ❌

Replay is NON-DETERMINISTIC - different checksums on each replay.

### Root Cause Analysis

**Audit chain NOT restored during replay**:
```python
# Evidence:
Original audit events: 1
Replayed audit events: 0

# Cause: session.json does NOT include audit_chain
# _to_dict_full() doesn't include _audit_chain
```

**FINDING**: **CONTRADICTED** ❌

The audit chain is exported to `audit_log.json` but NOT to `session.json`. Replay cannot restore audit events because they're not in the session data.

---

## Phase 3 — LLM Claims Validation

### Claim: "Year propagates to prompts"

**EVIDENCE**:
```python
prompt = llm._build_ec_prompt(...)
print('Year: 2023 (source: atlas)' in prompt)
# Output: True
```

**FINDING**: **VERIFIED** ✅

### Claim: "Metadata completeness propagates to EC prompts"

**EVIDENCE**:
```python
print('complete' in prompt.lower())
# Output: False
```

**FINDING**: **CONTRADICTED** ❌

metadata_completeness is NOT included in EC prompts (only in IC prompts at line 539).

### Claim: "Metadata completeness propagates to IC prompts"

**EVIDENCE**:
```python
# Line 539 in llm_assistant.py:
- Metadata Completeness: {metadata_completeness}
```

**FINDING**: **VERIFIED** ✅ (for IC only)

### Claim: "WL/GL normalization operational"

**EVIDENCE**:
```
normalize_literature_label('wl') -> 'White Literature'
normalize_literature_label('GL') -> 'Grey Literature'
normalize_literature_label('Gray') -> 'Grey Literature'
```

**FINDING**: **VERIFIED** ✅

### Claim: "Fallback detection operational"

**EVIDENCE**:
```
is_fallback: True
decision: unavailable
confidence: 0.0
fallback_reason: No LLM client
```

**FINDING**: **VERIFIED** ✅

### Claim: "Advisory separation enforced"

**EVIDENCE**:
```python
# ec_screening_view.py line 167-168:
if incl_clicked:
    session.record_decision("include", notes="")
    # NOT: session.record_decision(llm_suggestion.decision)
```

**FINDING**: **VERIFIED** ✅

LLM suggestions are displayed but NOT auto-applied.

---

## Phase 4 — Workflow Claims Validation

### Claim: "QC stage integrated in workflow"

**EVIDENCE**:
```python
# app.py lines 99-107 - Sidebar options:
options = [
    "Protocol Configuration",
    "EC Screening",
    "IC Screening",
    "Inter-Rater Calibration",
    "Exports & Audit"
]

# NO "QC Screening" option
```

**FINDING**: **CONTRADICTED** ❌

There is NO QC Screening view. QC is defined in code but NOT accessible via UI.

---

## Phase 5 — Scientific Claims Validation

### Claim: "Reproducible screening"

**EVIDENCE**:
- Session checksum deterministic: **VERIFIED** ✅
- Bundle reproducibility: **PARTIALLY VERIFIED** (checksums missing)
- Replay determinism: **CONTRADICTED** ❌

**FINDING**: **PARTIALLY VERIFIED**

### Claim: "Auditable decisions"

**EVIDENCE**:
- Audit chain created on each decision: **VERIFIED** ✅ (line 423 in screening_session.py)
- Audit chain verification: **VERIFIED** ✅
- Audit chain NOT included in replay: **CONTRADICTED** ❌

**FINDING**: **PARTIALLY VERIFIED**

### Claim: "Protocol traceability"

**EVIDENCE**:
```python
# Protocol locking (ec_screening_view.py line 39-42):
if protocol.state == ProtocolState.DRAFT.value:
    protocol.state = ProtocolState.LOCKED.value
    protocol.lock()
```

**FINDING**: **VERIFIED** ✅

### Claim: "HITL enforcement"

**EVIDENCE**:
```python
# Explicit researcher decision required:
session.record_decision("include", notes="")  # Researcher action
# NOT: session.record_decision(llm.decision)  # NOT auto-applied
```

**FINDING**: **VERIFIED** ✅

### Claim: "Deterministic replay"

**EVIDENCE**:
```
Replay checksums differ between runs: True
Audit chain NOT restored: True
```

**FINDING**: **CONTRADICTED** ❌

---

## Summary of Overstated Claims

| Claim | Actual Status | Evidence |
|-------|---------------|----------|
| 3 tests failing | 1 test failing | 65 pass, 1 fail |
| Bundle session_checksum present | NOT present | False in JSON |
| Replay deterministic | NON-DETERMINISTIC | Different hashes |
| Audit chain restored in replay | NOT restored | 0 events |
| Metadata completeness in EC prompt | NOT in EC | False in output |
| QC stage integrated | NOT integrated | No UI route |

---

## Claims Fully Verified

| Claim | Evidence |
|-------|----------|
| Session checksum deterministic | Same hash 3x |
| Audit chain verification works | Valid=True |
| Tamper detection works | is_clean=True |
| WL/GL normalization | All variants work |
| Fallback detection | is_fallback=True |
| Advisory separation | No auto-apply |
| Protocol locking | Implemented |

---

## Remaining Unknowns

1. **QC real functionality**: Only stub implementation, actual quality scoring not implemented
2. **Real API behavior**: Only fallback tested, no real API calls verified
3. **QC integration path**: No QC Screening view exists

---

## Residual Methodological Risks

| Risk | Severity | Evidence |
|------|----------|----------|
| Audit chain not in replay | HIGH | session.json missing audit_chain |
| QC stage incomplete | MEDIUM | No UI integration |
| EC prompts missing metadata_completeness | MEDIUM | Parameter unused in EC |
| Non-deterministic replay | HIGH | Different hashes |

---

## Residual Reproducibility Risks

| Risk | Severity | Evidence |
|------|----------|----------|
| Replay produces different state | HIGH | Checksums differ |
| Audit events lost on replay | HIGH | Not in session.json |
| Bundle missing session_checksum | MEDIUM | False in JSON |

---

## Residual Operational Risks

| Risk | Severity | Evidence |
|------|----------|----------|
| Test collection broken (sys.exit) | MEDIUM | test_protocol_layer.py |
| QC not accessible in UI | HIGH | No route |
| Missing module tests | LOW | 15 test files |

---

## Final Assessment

### Overstated Claims (5)

1. Test failure count (3 vs 1)
2. Bundle session_checksum present
3. Replay deterministic  
4. Audit chain restored in replay
5. Metadata completeness in EC prompts

### Fully Verified Claims (7)

1. Session checksum deterministic
2. Audit chain verification
3. WL/GL normalization
4. Fallback detection
5. Advisory separation
6. Protocol locking
7. Audit chain creation

### Contradicted Claims (5)

1. Bundle session checksums
2. Replay determinism
3. Audit chain restoration
4. QC integration
5. EC metadata_completeness

---

**CONCLUSION**: The prior reports contain **significant overstatements** regarding reproducibility, replay determinism, and QC integration. The system has critical issues that prevent true reproducibility:

1. **Audit chain not persisted** in session.json
2. **Replay is non-deterministic** 
3. **QC stage not accessible** via UI
4. **EC prompts missing** metadata_completeness

**RECOMMENDATION**: Do NOT use for production reproducibility until:
- Audit chain added to session.json
- Replay made deterministic  
- QC UI integrated
- EC prompts include metadata_completeness