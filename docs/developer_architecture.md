# APOLLO Developer Architecture Guide

## For Developers - Understanding APOLLO's Design

---

## 1. Bounded Contexts

APOLLO is intentionally bounded to a single responsibility:

```
┌─────────────────────────────────────────────────────────────────┐
│                     APOLLO BOUNDED CONTEXT                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  INPUT          PROCESS              OUTPUT                    │
│  ATLAS Excel → EC/IC/QC → Excel Export + Audit                │
│     │               │                   │                      │
│     │               │                   │                      │
│  Schema        Deterministic        Schema                     │
│  Validation    Evaluation          Validation                  │
│                                                                 │
│  Boundaries:                                                 │
│  - No snowballing (future HERMES)                             │
│  - No citation analysis                                       │
│  - No ML in decisions                                         │
│  - No database persistence                                    │
│  - No multiple reviewers                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Clear Boundaries

| Inside APOLLO | Outside APOLLO (Future HERMES) |
|---------------|-------------------------------|
| EC/IC/QC evaluation | Snowballing |
| Input schema validation | Citation network analysis |
| Protocol system | Recursive discovery |
| Audit logging | Cross-database crawling |
| Export generation | Citation scoring |

---

## 2. Pipeline Flow

### Main Pipeline (White Literature)

```python
wl_df → ATLASLoader.validate() → process_wl_articles()
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Exclusion       │
                           │ Criteria        │──▶ EC1, EC2, EC3, EC4
                           │ (EC1-EC4)       │
                           └────────┬────────┘
                                    │
                         decision == "include"
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Inclusion       │
                           │ Criteria        │──▶ IC1, IC2, IC3
                           │ (IC1-IC3)       │
                           └────────┬────────┘
                                    │
                         decision == "include"
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Quality         │
                           │ Criteria        │──▶ WL-Q1 to WL-Q4
                           │ (WL-Q1-Q4)      │
                           └────────┬────────┘
                                    │
                           total >= 2.0
                                    │
                                    ▼
                               Final Decision
```

### Simplified Pipeline (Grey Literature)

```python
gl_df → ATLASLoader.validate() → process_gl_articles()
                                    │
                                    ▼
                           ┌─────────────────┐
                           │ Exclusion      │
                           │ Criteria       │──▶ EC1, EC2 only
                           │ (EC1-EC2)      │
                           └────────┬────────┘
                                    │
                         decision == "include"
                                    │
                                    ▼
                           IC = "SKIPPED"
                           QC = "SKIPPED"
                           Final = "EXCLUDE"
```

---

## 3. Protocol Engine Architecture

### Design Goals

1. **Backwards Compatibility**: Default behavior unchanged when no protocol
2. **Determinism**: Same protocol + same input = same output
3. **No Schema Drift**: Export columns unchanged
4. **Extensibility**: Users can define custom EC/IC/QC criteria

### Protocol Structure

```python
@dataclass
class ProtocolRule:
    rule_id: str
    rule_type: str  # "rule" or "semantic"
    field: str
    operator: str   # "contains_any", "=", "<", etc.
    value: Any
    action: str     # "exclude", "exclude_if_none_found", etc.
```

### Key Operators

| Operator | Behavior |
|----------|-----------|
| `contains_any` | True if any keyword found |
| `contains_all` | True if all keywords found |
| `=` | Exact match |
| `!=` | Not equal |
| `<`, `>`, `<=`, `>=` | Numeric comparison |
| `length_lt` | String length less than |
| `length_gt` | String length greater than |
| `is_duplicate` | Pre-computed duplicate flag |

### Key Actions

| Action | Behavior |
|--------|----------|
| `exclude` | Exclude if rule matches |
| `exclude_if_none_found` | Exclude if keyword NOT found (EC1 semantics) |
| `exclude_if_duplicate` | Exclude if is_duplicate flag is true |

### Protocol Parity

```python
# MUST always hold
default_behavior == protocol(get_default_protocol())
```

Any protocol evaluation must produce identical results to the default hardcoded logic.

---

## 4. Audit Logging Design

### Philosophy

- **Minimal**: Log only what's needed for reproducibility
- **No Leakage**: Never log LLM reasoning or full article text
- **Deterministic**: Hash includes input + protocol + output stats

### Audit Log Structure

```python
@dataclass
class ProcessingStats:
    wl_total: int
    wl_included: int
    wl_excluded: int
    gl_total: int
    gl_included: int
    gl_excluded: int
    duplicates_detected: int
    
    ec1_failures: int
    ec2_failures: int
    ec3_failures: int
    ec4_failures: int
    
    qc_scores_4: int
    qc_scores_3: int
    qc_scores_2: int
    qc_scores_below: int
```

### Log File Location

```
logs/apollo_run_<timestamp>.json
```

### Determinism Hash

```python
def _compute_determinism_hash(input_file, protocol_info, stats):
    hash_input = f"{input_file}|{protocol.checksum}|{stats.wl_included}|..."
    return sha256(hash_input).hexdigest()[:16]
```

---

## 5. Deterministic Design Principles

### Why APOLLO Avoids Mutable State

1. **Reproducibility**: Same input → same output every time
2. **Testability**: Easy to verify behavior
3. **Parallelization**: No state to corrupt
4. **Debugging**: Clear cause-and-effect

### Global_ID: The Critical Key

```python
# EC4 uses Global_ID as the duplicate detection key
# This is deterministic because:
# 1. Global_ID is an input property, not generated
# 2. Same Global_IDs always map to same duplicate detection
# 3. Order-independent: duplicates found via set operations

duplicate_ids = set(df['Global_ID'].value_counts()[df['Global_ID'].value_counts() > 1].index)
```

### Why Keyword-Based Evaluation

- **Deterministic**: Same keywords → same decisions
- **Transparent**: Exact rules visible in code
- **Auditable**: Can trace each decision to keywords
- **No Randomness**: No LLM non-determinism in decisions

---

## 6. Protocol Parity: Why It Matters

### The Golden Rule

```
default_behavior == protocol(get_default_protocol())
```

### Why Parity Matters

1. **User Trust**: Users can choose between default and custom protocols
2. **Verification**: Easy to verify custom protocols are correct
3. **Migration**: Can switch protocols without changing results
4. **Testing**: Simple to test protocol vs default

### How Parity is Verified

```python
# test_protocol_parity.py runs all test cases twice:
# 1. With default behavior (no protocol)
# 2. With get_default_protocol()

# Compares every decision, score, and final outcome
# If ANY difference found → test FAILS
```

---

## 7. Where NOT to Extend the System

### Anti-Patterns to Avoid

#### ❌ Do Not Add Snowballing to APOLLO

```
APOLLO scope: Bounded screening
HERMES scope: Unbounded exploration

Adding snowballing to APOLLO would:
- Break deterministic guarantees
- Create non-terminating processes
- Violate bounded context
- Introduce randomness via citation databases
```

**Correct Approach**: Export seeds to "WL Seeds for HERMES" sheet, let HERMES handle expansion.

#### ❌ Do Not Add ML to Decisions

```
APOLLO: Keyword-based, deterministic
ML: Probabilistic, potentially non-deterministic

Adding ML would:
- Break reproducibility guarantees
- Make decisions non-auditable
- Introduce model dependency
- Violate deterministic design
```

**Correct Approach**: Keep ML out of APOLLO decisions. Use keyword-based evaluation only.

#### ❌ Do Not Add Multiple Reviewer Support

```
APOLLO: Single-reviewer simulation (Revisor 1 = "APOLLO")
Future: Manual post-processing for consensus

Adding multi-reviewer would:
- Add complex state management
- Break simple deterministic model
- Add consensus resolution logic
```

**Correct Approach**: Let APOLLO screen, then manually resolve conflicts if needed.

#### ❌ Do Not Add Database Persistence

```
APOLLO: Stateless processing
Purpose: Simple, reproducible, auditable

Adding database would:
- Add state management complexity
- Break simple deployment model
- Add infrastructure dependencies
```

**Correct Approach**: Each run is stateless. Re-process from input file each time.

#### ❌ Do Not Add Web API

```
APOLLO: CLI + Streamlit UI
Future: Separate project

Adding API would:
- Add infrastructure complexity
- Create state management issues
- Break simple deployment
```

**Correct Approach**: Keep APOLLO as standalone tool. Create separate project for API if needed.

---

## 8. Key Files and Their Responsibilities

### Core Files

| File | Responsibility |
|------|----------------|
| `atlas_processor.py` | Main pipeline, EC/IC/QC classes, export |
| `protocol_engine.py` | Protocol parsing, rule evaluation |
| `audit_logger.py` | Deterministic run logging |
| `database.py` | SQLite for UI state (not APOLLO core) |
| `quality.py` | QC scoring logic |
| `workflow.py` | Stage definitions |
| `logger.py` | Application logging |
| `llm_reasoning.py` | Internal reasoning (not exported) |

### Test Files

| File | Purpose |
|------|---------|
| `test_apollo_regression.py` | Regression tests |
| `test_protocol_parity.py` | Protocol parity verification |
| `test_protocol_layer.py` | Protocol integration test |

### Entry Points

| File | Usage |
|------|-------|
| `scripts/process_atlas.py` | CLI entrypoint |
| `app.py` | Streamlit UI entrypoint |

---

## 9. Extension Points (Safe to Extend)

### Within APOLLO Scope

These areas are safe to extend within APOLLO's bounded context:

1. **Custom Protocols**: Add new EC/IC/QC rules via JSON/YAML
2. **QC Criteria**: Add new quality questions
3. **Audit Fields**: Add more processing stats
4. **Documentation**: Expand guides
5. **Tests**: More test coverage
6. **Input Validation**: Additional checks
7. **Output Formats**: Additional export formats

### Example: Adding Custom Protocol

```python
from src.core.protocol_engine import ProtocolEngine, load_protocol

# Load custom protocol
custom = load_protocol("my_custom_protocol.yaml")

# Use it
engine = APOLLODecisionEngine(protocol=custom)
results = engine.process_wl_articles(df)
```

---

## Summary: Architectural Principles

1. **Bounded**: Clear scope, explicit exclusions
2. **Deterministic**: Same input + same protocol = same output
3. **Stateless**: No persistent state between runs
4. **Auditable**: Complete logging, no hidden decisions
5. **Transparent**: Keyword-based, no ML in decisions
6. **Reproducible**: Determinism hash, checksums, audit logs
7. **Protocol-Based**: Extensible without code changes
8. **Parity-Verified**: Protocol always matches default

---

*Document Version: 1.0.0*  
*For APOLLO 1.0.0 Developers*  
*This guide explains architecture decisions and extension points*