# APOLLO Mutation Sensitivity Surfaces

## Purpose

This document maps all deterministic invariant surfaces in APOLLO's session core.
Each surface represents a class of plausible deterministic regression that the
replay oracle and governance layers must detect.

This is a SCIENTIFIC SENSITIVITY INSTRUMENT, not a scoring system.
Mutation detection rate is NOT a quality metric.

## Invariant Surface Map

### 1. Serialization Surface

**Location:** `session_persistence_service.py` — `to_dict()`, `to_dict_full()`, `build_article_dicts()`

**Deterministic invariant:** Field ordering and inclusion in serialization dicts must remain stable.

**Regression classes:**
- Field omission from serialization dict
- Field reordering in dict construction
- Addition of unexpected fields to serialization dict
- Article field mapping drift (`ArticleReview.to_dict()` via `dataclasses.asdict()`)

**Detection mechanism:** Checksum comparison, save/load roundtrip, JSON diff across runs.

---

### 2. Checksum Boundary Surface

**Location:** `session_persistence_service.py` — `CHECKSUM_FIELDS` constant, `compute_checksum()`, `compute_session_hash()`

**Deterministic invariant:** The set of fields contributing to the checksum and the canonical serialization format must be stable.

**Regression classes:**
- Field added to or removed from CHECKSUM_FIELDS
- `sort_keys` parameter change in `json.dumps()`
- `ensure_ascii` parameter change
- Hash algorithm substitution (SHA256 → other)
- Checksum truncation length change

**Detection mechanism:** Checksum comparison across loads, cross-run checksum identity.

---

### 3. Workflow Transition Surface

**Location:** `workflow_state_service.py` — `STAGE_ORDER`, `can_transition_to_stage()`, `get_next_stage()`, `STAGE_FIELD_MAP`, `STAGE_COUNTER_MAP`

**Deterministic invariant:** EC → IC → QC → COMPLETE ordering must be preserved. Stage field and counter mappings must be consistent.

**Regression classes:**
- Stage reordering (e.g., IC before EC)
- Stage addition or removal
- Field mapping drift (ec_stage → wrong field)
- Counter mapping drift
- Transition logic inversion (allowing illegal transitions)
- Blocking legal transitions

**Detection mechanism:** Workflow validation tests, traversal tests, stage-dependent query parity.

---

### 4. Navigation Surface

**Location:** `session_navigation.py` — `advance()`, `next_index()`, `previous_index()`, `skip_unreviewable()`, `clamp_index()`

**Deterministic invariant:** Navigation traversal order must be deterministic and bounds-safe.

**Regression classes:**
- Off-by-one in index calculation
- Skip logic inversion (skipping undecided instead of decided)
- Bounds-check removal or weakening
- `advance(skip=False)` behavior drift (stopping on decided vs undecided)
- `clamp_index()` bounds shift

**Detection mechanism:** Navigation parity tests, repeated advance produces identical indices.

---

### 5. Audit Chain Surface

**Location:** `session_audit_service.py` — `append_event()`, `verify_chain()`, `detect_tampering()`

**Deterministic invariant:** Hash chain integrity, event ordering, and tamper detection must be deterministic.

**Regression classes:**
- Hash chain computation change (payload fields included/excluded)
- Previous hash linking broken
- GENESIS root changed
- Event ordering reversal
- Tamper detection logic weakened (false negatives)
- Verify chain returning false positives

**Detection mechanism:** Audit verification tests, tampered fixture detection.

---

### 6. Query Semantic Surface

**Location:** `session_query_service.py` — `get_discussion_articles()`, `get_wl_articles()`, `get_gl_articles()`, `get_progress()`, `filter_articles()`, `get_pending_for_stage()`

**Deterministic invariant:** Filtering, classification, and aggregation logic must be deterministic and stable.

**Regression classes:**
- Stage field reference drift in query predicates
- Literature type classification drift
- Progress counter aggregation drift
- Pending calculation logic changed
- Filter predicate inversion (includes instead of excludes)

**Detection mechanism:** Query parity tests, progress comparison, cross-run identity.

---

### 7. Replay Oracle Surface

**Location:** `session_persistence_service.py` — `compute_checksum()`, `compute_session_hash()`, serialization functions
**Location:** `screening_session.py` — `save_to_json()`, `load_from_json()`, `compute_checksum()`, `_to_dict_full()`
**Location:** `reproducibility_engine.py` — `replay_session()`, `_validate_bundle()`, `compare_outputs()`

**Deterministic invariant:** Save/load roundtrip, checksum computation, and replay comparison must be deterministic.

**Regression classes:**
- Checksum computation drift between save and load
- Serialization format asymmetry (what's saved ≠ what's compared)
- Missing fields in comparison subset
- Replay validation accepting invalid bundles
- Export comparison weakened

**Detection mechanism:** Replay corpus tests, roundtrip parity, repeated load identity.

---

### 8. Governance DAG Surface

**Location:** All files in `src/core/` — import dependency graph

**Deterministic invariant:** Layered architecture with strict dependency direction:

```
Layer 0: SessionState, SessionAuditService, WorkflowStateService
    ↓ (Layer 0 → Layer 1)
Layer 1: NavigationService, SessionQueryService, SessionPersistenceService,
         SessionIngestionService, SessionDecisionService
    ↓ (Layer 1 → Layer 2)
Layer 2: SessionOrchestrationService
    ↓ (Layer 2 → Layer 3)
Layer 3: ScreeningSession
```

**Regression classes:**
- Lower layer importing from higher layer
- Orchestration importing from facade
- State container importing services
- UI/advisory imports in core services
- Circular dependencies between layers

**Detection mechanism:** AST-level import analysis, source string checks.

---

## Mutation Operator Catalog

| Operator | Surface | Invariant | Detection |
|----------|---------|-----------|-----------|
| SerializationFieldOmission | Serialization | Dict field completeness | Checksum mismatch |
| ChecksumFieldAddition | Checksum | CHECKSUM_FIELDS membership | Checksum identity |
| WorkflowReordering | Workflow | STAGE_ORDER sequence | Transition validation |
| NavigationOffByOne | Navigation | Index bounds | Navigation parity |
| AuditChainBreak | Audit | Hash continuity | verify_chain failure |
| QueryFilterInversion | Query | Filter predicate | Query parity |
| ChecksumSortKeys | Checksum | Canonical JSON format | Checksum mismatch |
| SerializationRoundtrip | Serialization | Save/load parity | Field value mismatch |

## Sensitivity Philosophy

- Each mutation represents a **plausible deterministic regression**, not adversarial corruption
- **Equivalent mutations** (formatting-only, ordering-preserving) are expected and valid
- Detection MUST occur ONLY when semantic invariant is violated
- No optimization for mutation score or detection rate
- All mutations are **runtime-only** via monkeypatching — no production code is modified
