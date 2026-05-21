# ADR-004: Workflow State Centralization

**Status:** Accepted  
**Date:** 2026-05-20  
**Deciders:** APOLLO Architecture Team

## Context

The EC → IC → QC screening workflow defines stage ordering, field mappings
(`ec_stage`, `ic_stage`, `qc_stage`), counter mappings (`ec_completed`,
`ic_completed`, `qc_completed`), and transition rules. Originally, this
knowledge was duplicated across:

- `ScreeningSession` (private `_get_stage_field` helper + inline logic)
- `NavigationService` (private `_stage_field`)
- `SessionQueryService` (private `_stage_field`)

The same stage-to-field mapping appeared in three places, creating a risk of
inconsistent behavior if one copy was updated but not others.

## Decision

Centralize all workflow semantics into `WorkflowStateService`:

1. **`STAGE_ORDER`** — canonical ordered list: `["ec", "ic", "qc", "complete"]`
2. **`STAGE_FIELD_MAP`** — stage → article field name: `{"ec": "ec_stage", ...}`
3. **`STAGE_COUNTER_MAP`** — stage → session counter: `{"ec": "ec_completed", ...}`
4. **Validation** — `is_valid_stage()`, `can_transition_to_stage()`
5. **Navigation** — `get_next_stage()`, `is_workflow_complete()`

All services delegate to `WorkflowStateService` for workflow queries.
`NavigationService._stage_field()` and `SessionQueryService._stage_field()`
are thin wrappers that call `WorkflowStateService.stage_field()`.

## Consequences

### Positive
- Single source of truth for workflow semantics
- Adding a new stage requires changing exactly one file
- Consolidation tests verify no duplicate stage maps exist

### Negative
- `WorkflowStateService` is imported by `NavigationService` and `SessionQueryService`,
  adding a dependency edge from Layer 1 to Layer 0

## Rejected Alternatives

- **Keep duplicate stage maps**: Would continue to diverge over time.
- **Put workflow state in ScreeningSession**: Would recreate the monolith and
  prevent services from accessing stage information without a session reference.
