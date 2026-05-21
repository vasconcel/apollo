# APOLLO Mutation Ownership Specification

## Ownership Principles

1. Every mutable field has exactly **one canonical mutation path**.
2. The owns the mutation; services return structured results.
3. Persistence services serialize state; they do not mutate caller state.
4. Workflow semantics are centralized in `WorkflowStateService`.

---

## Field Ownership Map

### `current_index`

| Property | Value |
|---|---|
| **Canonical owner** | `ScreeningSession` (via `NavigationService` delegation) |
| **Allowed mutation paths** | `ScreeningSession.advance()` → `NavigationService.advance()` returns new index → `self.state.current_index = new_index` |
| | `ScreeningSession.skip_unreviewable()` → `NavigationService.skip_unreviewable()` returns new index → conditional `self.state.current_index = new_index` |
| | `ScreeningSession.apply_decision()` → `OrchestrationService.apply_decision_by_id()` returns saved index → `self.state.current_index = saved_index` |
| **Forbidden paths** | No service mutates `current_index` directly |
| **Replay implications** | Serialized as part of `_to_dict()`; restored on load |
| **Determinism** | Fully deterministic given same article list and decisions |

### `last_saved`

| Property | Value |
|---|---|
| **Canonical owner** | `ScreeningSession` |
| **Allowed mutation paths** | `ScreeningSession.save()` → generates `datetime.now().isoformat()` → `self.state.last_saved = now` BEFORE serialization |
| | `ScreeningSession.save_to_json()` → same pattern |
| | `ScreeningSession._apply_decision_side_effects()` → `self.state.last_saved = result["timestamp"]` (decision timestamp, not persistence timestamp) |
| | `ScreeningSession.load_from_json()` → `self.state.last_saved = result["last_saved"]` |
| **Forbidden paths** | `SessionPersistenceService` does not generate or mutate `last_saved` |
| **Replay implications** | Read from serialized data; value is cosmetic (not behavioral) |
| **Determinism** | Non-deterministic (wall-clock timestamp); excluded from checksum comparisons in tests |

### `audit_chain`

| Property | Value |
|---|---|
| **Canonical owner** | `ScreeningSession` (via `SessionAuditService` and orchestration) |
| **Allowed mutation paths** | `SessionAuditService.append_event()` returns new event → `self.state.audit_chain.append(event)` in `_apply_decision_side_effects` |
| | `ScreeningSession.load_from_json()` → `self.state.audit_chain = result["audit_chain"]` |
| **Forbidden paths** | No service directly mutates the audit chain list |
| **Replay implications** | Full chain serialized in `save_to_json` / `_to_dict_full`; restored on load |
| **Determinism** | Fully deterministic; same decisions produce identical chain |

### `stage`

| Property | Value |
|---|---|
| **Canonical owner** | `ScreeningSession` (via external UI/protocol) |
| **Allowed mutation paths** | External assignment by UI or protocol logic |
| | Set in `__init__` from constructor parameter |
| | Set in `load_from_json()` / `ScreeningSession.load()` from serialized data |
| **Forbidden paths** | Services never mutate `stage`; `WorkflowStateService` validates transitions but does not set the field |
| **Replay implications** | Preserved in serialized data |
| **Determinism** | Fully deterministic |

### `included_count`, `excluded_count`, `skip_count`, `discussion_count`

| Property | Value |
|---|---|
| **Canonical owner** | `ScreeningSession` (via `SessionDecisionService` → orchestration) |
| **Allowed mutation paths** | `SessionDecisionService.apply_review_decision()` returns `counter_increments` dict → `SessionOrchestrationService.record_decision()` passes it through result → `ScreeningSession._apply_decision_side_effects()` applies `setattr(self.state, counter, getattr(self.state, counter) + delta)` |
| **Forbidden paths** | No service directly increments counters; no hardcoded counter names in mutation code |
| **Replay implications** | Serialized; restored on load |
| **Determinism** | Fully deterministic; identical decisions produce identical counter values |

### `snapshots`

| Property | Value |
|---|---|
| **Canonical owner** | `ScreeningSession` (via orchestration) |
| **Allowed mutation paths** | `SessionDecisionService.apply_review_decision()` may return `protocol_snapshot` → `_apply_decision_side_effects` appends it: `self.state.snapshots.append(result["protocol_snapshot"])` |
| **Forbidden paths** | No service directly appends to snapshots |
| **Replay implications** | Serialized in full JSON; restored on load |
| **Determinism** | Fully deterministic; same decisions + protocol produce identical snapshots |

### Fields with Single Init-Only Ownership

These fields are set at construction time and by `load_from_json` / `ScreeningSession.load()`:

- `session_id`, `created_at`, `protocol_version` — immutable after construction
- `total_count` — set when articles are added (`add_articles`, `ingest_from_upload`)
- `researcher_id` — set at construction
- `schema_version` — set at construction
- `autosave_enabled` — set at construction
- `qc_completed` — declared but unused by runtime logic (retained for schema stability)

## Rules for Future Changes

1. **Counter mutations must use the result-dict pattern.** Never increment counters directly.
2. **Persistence services must never mutate caller state.** Return values, accept parameters.
3. **Workflow semantics must remain in `WorkflowStateService`.** Duplicate stage maps are forbidden.
4. **Timestamp generation belongs to the caller**, not the persistence layer.
5. **Audit chain mutations go through `SessionAuditService.append_event()`**, never direct list append.
