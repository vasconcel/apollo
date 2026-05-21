# ADR-003: ScreeningSession as Façade

**Status:** Accepted  
**Date:** 2026-05-20  
**Deciders:** APOLLO Architecture Team

## Context

After extracting all operations into stateless services, `ScreeningSession` no longer
contained business logic. However, it remained the public API consumed by UI modules
(Streamlit views), the reproducibility engine, and export infrastructure. Rewriting
all callers was impractical.

Additionally, `SessionState` was extracted as a pure dataclass, but existing code
accesses fields directly on `ScreeningSession` (e.g., `session.stage`, `session.articles`).

## Decision

Convert `ScreeningSession` to a thin compatibility façade:

1. **Owns `self.state: SessionState`** — all mutable state lives in the dataclass.
2. **Delegates all operations** — every public method calls the appropriate service.
3. **`__getattr__` / `__setattr__` delegation** — field access on `ScreeningSession`
   is transparently forwarded to `self.state`, with aliases for renamed fields
   (`_audit_chain` → `audit_chain`, `_snapshots` → `snapshots`).
4. **Constructor accepts the same parameters** — backward compatibility preserved.
5. **No new business logic** — all new functionality goes into services.

## Consequences

### Positive
- Zero changes required for existing callers (UI, export, replay, tests)
- Clear architectural boundary: state in `SessionState`, logic in services,
  coordination in `ScreeningSession`
- Can deprecate the façade gradually as callers are updated

### Negative
- `__getattr__`/`__setattr__` delegation is implicit and can mask missing attributes
- The façade still imports all services, creating a single hub node

## Rejected Alternatives

- **Remove ScreeningSession entirely**: Would require rewriting every caller.
- **Merge SessionState into ScreeningSession**: Would recreate the monolith.
- **Use `__getattribute__` instead**: More invasive and harder to reason about.
