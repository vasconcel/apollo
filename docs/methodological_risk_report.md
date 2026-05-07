# APOLLO Methodological Risk Report

## Document Version: 1.0.0
## Date: 2026-05-07

---

## 1. Executive Summary

This report analyzes methodological risks in APOLLO's human-in-the-loop screening workflow.

**Overall Assessment**: APOLLO maintains scientific defensibility with researcher authority over AI suggestions. Key risks are documentable but manageable.

---

## 2. Scientific Defensibility Verification

### 2.1 AI Override Detection

**Requirement**: When researcher overrides AI suggestion, must be logged for audit.

**Implementation**:
```python
@dataclass
class DecisionRecord:
    ai_suggestion: Optional[str] = None
    ai_confidence: Optional[float] = None
    
    @property
    def did_override_ai(self) -> bool:
        if not self.ai_suggestion:
            return False
        return self.decision != self.ai_suggestion
```

**Status**: IMPLEMENTED

---

### 2.2 Human Decision Authority

**Requirement**: Final decisions must be human-authored.

**Implementation**:
- `is_human_decision` property checks researcher_id present
- AI suggestions stored separately in `ai_suggestions` list

**Status**: IMPLEMENTED

---

### 2.3 Protocol Traceability

**Requirement**: Every decision traceable to protocol version.

**Implementation**:
```python
class ReviewerState:
    protocol_version: str = "1.0"
    protocol_snapshot: str = ""
    input_checksum: str = ""
```

**Status**: IMPLEMENTED

---

## 3. Methodological Risks

### 3.1 Risk: Reviewer Drift

**Definition**: Researcher inconsistently applies criteria over time.

**Likelihood**: MEDIUM

**Mitigation**:
- Notes field for justification
- Recent decisions view (planned)
- Calibration export for inter-reviewer reliability

**Status**: PARTIALLY MITIGATED

---

### 3.2 Risk: Confirmation Bias

**Definition**: Researcher blindly accepts AI suggestion.

**Likelihood**: MEDIUM

**Mitigation**:
- AI suggestion labeled "ADVISORY"
- Override logged separately
- Justification field provided

**Status**: MITIGATED

---

### 3.3 Risk: Stage Skipping

**Definition**: Researcher skips EC/IC/QC stage accidentally.

**Likelihood**: LOW

**Mitigation**:
- Workflow enforces stage progression
- `can_proceed_to_stage()` blocks invalid transitions

**Status**: MITIGATED

---

### 3.4 Risk: GL Empty Abstract

**Definition**: Grey literature with no abstract cannot be assessed.

**Likelihood**: HIGH (for GL)

**Current Handling**:
- EC can still evaluate (title-based)
- IC cannot evaluate (no abstract)
- QC skipped when IC not assessable

**Status**: DOCUMENTED - Researcher must make judgment call

---

### 3.5 Risk: Inconsistent EC→IC→QC Decisions

**Definition**: Researcher applies different standards to similar papers.

**Likelihood**: MEDIUM

**Mitigation**:
- Validation highlights IC decisions without EC pass
- Export includes decision history
- Calibration matrix for comparison

**Status**: PARTIALLY MITIGATED

---

## 4. Audit Completeness

### 4.1 Required Audit Fields

| Field | Status | Implementation |
|-------|--------|----------------|
| Timestamp | YES | ISO datetime |
| Decision hash | YES | SHA256 |
| Researcher ID | YES | researcher_id field |
| Stage | YES | stage field |
| AI suggestion | YES | Separate list |
| AI confidence | YES | ai_confidence field |
| Notes | YES | notes field |
| Protocol version | YES | protocol_version |
| Override flag | YES | did_override_ai |

**Status**: COMPLETE

---

### 4.2 Export Formats

| Format | Purpose | Status |
|--------|---------|--------|
| Excel | Legacy compatibility | IMPLEMENTED |
| Session JSON | Full state | IMPLEMENTED |
| Audit Log | Decision trail | IMPLEMENTED |
| Calibration CSV | Kappa analysis | IMPLEMENTED |
| Disagreement | Override tracking | IMPLEMENTED |

**Status**: COMPLETE

---

## 5. Reproducibility Verification

### 5.1 Session Persistence

**Test**: Save session → Load session → Verify state

```
Result: SUCCESS
- Session ID preserved
- Articles preserved
- Decisions preserved
- Hash integrity verified
```

**Status**: PASS

---

### 5.2 Determinism

**Test**: Same input → Same output (twice)

```
Result: PASS
- Output identical
- Hashes match
```

**Status**: PASS

---

## 6. Calibration Readiness

### 6.1 Required Formats

For inter-rater reliability (Cohen's Kappa), need:

| Format | Field | Status |
|--------|-------|--------|
| Article ID | article_id | YES |
| Stage | stage | YES |
| Reviewer 1 Decision | decision | YES |
| Reviewer 2 Decision | decision | YES (via export) |
| Timestamp | timestamp | YES |

**Status**: READY

---

### 6.2 Disagreement Tracking

Current tracking:
- `did_override_ai` property logs researcher vs AI
- Disagreement export captures override cases
- Human decision vs AI suggestion logged

**Status**: PARTIALLY READY (single reviewer mode)

---

## 7. Risk Matrix

| Risk | Likelihood | Impact | Mitigation | Status |
|------|-----------|--------|------------|--------|
| Reviewer Drift | Medium | High | Notes + Audit | Mitigated |
| Confirmation Bias | Medium | Medium | Override Log | Mitigated |
| Stage Skipping | Low | High | Workflow Enforced | Mitigated |
| GL Empty Abstract | High | Low | Documented | OK |
| Inconsistent Decisions | Medium | Medium | Export + Validation | Partially Mitigated |
| Session Loss | Low | High | Auto-save + Recovery | Mitigated |

---

## 8. Recommendations

### 8.1 Immediate

1. Add stage indicator prominently in UI
2. Log all AI overrides explicitly in export
3. Document GL empty abstract policy

### 8.2 Future

1. Inter-reviewer workflow (for Kappa)
2. Real-time decision drift detection
3. Automated consistency checks

---

## 9. Conclusion

APOLLO is **methodologically sound** for human-in-the-loop screening:

- ✅ Human makes final decisions
- ✅ AI suggestions advisory only  
- ✅ All decisions auditable
- ✅ Protocol version preserved
- ✅ Session recoverable
- ✅ Export formats ready for calibration

**Primary Risks**:
- GL empty abstracts (documented)
- Reviewer drift (notes + audit help)
- Confirmation bias (override tracking helps)

**Recommendation**: Production use acceptable with documented workflow.

---

## 10. Appendix: Regression Tests

```
APOLLO REGRESSION REPORT
- Schema: PASS
- EC4: PASS (Global_ID based)
- GL Policy: PASS (explicit SKIPPED)  
- Determinism: PASS

OVERALL: PASS
```