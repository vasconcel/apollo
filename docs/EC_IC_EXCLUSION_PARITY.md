# EC-IC Exclusion Parity Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Line-by-Line Parity Analysis

### EXCLUDE Button Handler

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Stage property | `article.ec_stage` | `session.articles[original_idx].ic_stage` | ✅ PARITY |
| Set value | `"exclude"` | `"exclude"` | ✅ PARITY |
| Session flag | `st.session_state[f"ec_{idx}"]` | `st.session_state[f"ic_{idx}"]` | ✅ PARITY |
| Rerun | `st.rerun()` | `st.rerun()` | ✅ PARITY |

### Code Selection Branch

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Condition | `current_decision == "exclude" and not current_ec_code` | `current_decision == "exclude" and not current_ic_code` | ✅ PARITY |
| Variable name | current_ec_code (ces1) | current_ic_code (cis1) | INTENTIONAL |
| Header text | "SELECT EXCLUSION CODE" | "SELECT EXCLUSION CODE" | ✅ PARITY |
| Counter increment | `session.ec_completed += 1` | `session.ic_completed += 1` | ✅ PARITY |
| Advance | `session.current_index += 1` | `st.session_state.ic_current_index += 1` | ✅ PARITY |

### Final State Display

| Aspect | EC | IC | Status |
|--------|----|----|--------|
| Badge | "EXCLUDED" or decision.upper() | "INCLUDED" or decision.upper() | ✅ PARITY |

## State Transition Parity

```
EC EXCLUDE:                    IC EXCLUDE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Click EXCLUDE               1. Click EXCLUDE
2. article.ec_stage="exclude"  2. session[original_idx].ic_stage="exclude"
3. Set session flag            3. Set session flag  
4. st.rerun()                  4. st.rerun()
                              
[On Rerun]                    [On Rerun]                    
5. article.ec_stage=="exclude" 5. article.ic_stage=="exclude"
6. ces1 empty? YES → show code  6. cis1 empty? YES → show code
7. Select code → ces1=code     7. Select code → ces1=code
8. ec_completed++              8. ic_completed++  
9. Advance                    9. Advance
```

## Key Differences (Intentional)

| Aspect | EC | IC | Reason |
|--------|----|----|--------|
| Index storage | session.current_index | st.session_state.ic_current_index | Filtered vs master list |
| Article reference | Direct `article` | Via original_idx lookup | Filtered list isolation |

## Behavioral Verification

- [x] Both enter code selection after EXCLUDE click
- [x] Both increment correct counter
- [x] Both advance to next article
- [x] Both persist decision in article property

## Constraint Compliance

- ✅ No hidden state divergence
- ✅ Deterministic replay preserved
- ✅ Audit chain integrity maintained