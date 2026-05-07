# APOLLO UX Friction Report

## Document Version: 1.0.0
## Date: 2026-05-07

---

## 1. Executive Summary

This report analyzes UX friction points identified during simulated MLR (Systematic Literature Review) workflow execution.

**Overall Assessment**: APOLLO has coherent workflow logic but several UX friction points that could cause reviewer fatigue or confusion.

---

## 2. Identified UX Friction Points

### 2.1 Stage Indicator Visibility (HIGH PRIORITY)

**Issue**: Current stage visible only in sidebar, not prominently in main review area.

**Impact**:
- Researcher may lose context during long review sessions
- Easy to forget which stage (EC/IC/QC) currently reviewing

**Current Behavior**:
```
Sidebar shows:
- Stage: EC
- Protocol: 1.0
```

**Recommendation**: Add large stage indicator in main area header.

---

### 2.2 Blocked Article Indication (HIGH PRIORITY)

**Issue**: When a paper is excluded at EC and cannot proceed to IC, no clear indication.

**Impact**:
- Researcher may be confused why "Next" doesn't advance
- May think system is broken

**Current Behavior**:
- `can_proceed_to_stage()` returns False
- But no visual indicator in UI

**Recommendation**: Show explicit "Cannot proceed: EC excluded" message.

---

### 2.3 Notes Field Placement (MEDIUM PRIORITY)

**Issue**: Notes textarea appears only AFTER clicking decision button.

**Impact**:
- Awkward flow: click → wait for re-render → type notes → decision
- Researcher may skip notes to avoid extra click

**Current Flow**:
```
1. Click "Include"
2. UI refreshes
3. Notes textarea appears
4. Type notes (optional)
```

**Recommendation**: Show notes field alongside buttons, not after.

---

### 2.4 Empty Abstract Handling (MEDIUM PRIORITY)

**Issue**: No special visual handling for papers with empty abstracts (common in GL).

**Impact**:
- Researcher may not notice empty abstract
- May waste time trying to find information

**Current Behavior**:
- Shows "No abstract available" but not prominent

**Recommendation**: Add visual warning (yellow banner) for empty abstracts.

---

### 2.5 Per-Stage Progress (LOW PRIORITY)

**Issue**: No pending count shown per stage.

**Impact**:
- Researcher doesn't know how many IC reviews remain
- Cannot plan review session

**Current Behavior**:
```
Progress: 3/5
```

**Missing**:
```
EC completed: 5/5
IC pending: 3  (papers that passed EC)
QC pending: 2   (papers that passed IC)
```

**Recommendation**: Add stage-specific pending counts.

---

### 2.6 Decision History (LOW PRIORITY)

**Issue**: No quick view of recent decisions.

**Impact**:
- Cannot detect decision pattern drift
- Hard to spot inconsistencies

**Current Behavior**:
- Must navigate to specific article
- No "last 5 decisions" summary

**Recommendation**: Add recent decisions panel.

---

### 2.7 Disagreement Flag (LOW PRIORITY)

**Issue**: No way to mark items for team discussion (separate from NEEDS_DISCUSSION decision).

**Impact**:
- Must complete full decision to flag
- No "review with team" quick option

**Current Behavior**:
- Only NEEDS_DISCUSSION decision option
- Requires full review completion

**Recommendation**: Add quick "Flag for discussion" button.

---

### 2.8 Keyboard Shortcuts Visibility (LOW PRIORITY)

**Issue**: Shortcuts documented but not visible in button labels.

**Impact**:
- New users don't know shortcuts
- Slower initial adoption

**Current Behavior**:
```
Buttons show: "Include", "Exclude"
Shortcuts shown in sidebar only
```

**Recommendation**: Add shortcut hints (e.g., "Include (I)") to buttons.

---

## 3. Cognitive Load Assessment

### 3.1 Decision Fatigue Points

| Point | Trigger | Mitigation |
|-------|---------|-------------|
| Stage switch | Moving EC→IC→QC | Clear stage indicator |
| Abstract re-read | Multiple passes | Auto-populate LLM summary |
| Exclusion reason | Must remember | Add quick tags |

### 3.2 Information Hierarchy

**Current**: Title → Abstract → Metadata → Suggestion → Decision

**Issues**:
- Abstract is long (scroll required)
- Suggestion competes with abstract
- Decision buttons at bottom

**Recommendation**: Compact abstract view initially, expand on click.

---

## 4. Usability Recommendations

### 4.1 Must Fix (for production)

1. **Stage indicator in main area**
2. **Blocked article message**
3. **Notes field visible with buttons**

### 4.2 Should Fix

4. **Empty abstract warning**
5. **Per-stage pending count**

### 4.3 Nice to Have

6. **Recent decisions summary**
7. **Quick discussion flag**
8. **Shortcut hints in buttons**

---

## 5. Summary

| Category | Count | Severity |
|----------|-------|----------|
| High Priority | 3 | Affects workflow |
| Medium Priority | 3 | Causes friction |
| Low Priority | 3 | Nice to have |

**Workflow Coherence**: PASS
- EC exclusion correctly blocks IC
- IC exclusion correctly blocks QC
- Session persistence works

**Recommendation**: Fix High Priority items before production use.

---

## 6. Appendix: Regression Test Results

```
Overall: PASS
- Schema: PASS
- EC4: PASS  
- GL Policy: PASS
- Determinism: PASS
```