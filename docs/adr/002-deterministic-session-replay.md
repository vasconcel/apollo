# ADR-002: Deterministic Session Replay

**Status:** Accepted  
**Date:** 2026-05-20  
**Deciders:** APOLLO Architecture Team

## Context

APOLLO is scientific infrastructure. Screening sessions must be fully reproducible:
given the same inputs, the same decisions, and the same workflow configuration, the
system must produce identical outputs regardless of when or where the replay occurs.

The original design had implicit state scattered across the session object, making it
difficult to capture a complete snapshot for replay.

## Decision

Implement a deterministic replay architecture with these properties:

1. **Full state capture** — `_to_dict_full()` serializes every field including audit
   chain and dynamic protocol.
2. **SHA-256 checksum** — `compute_checksum()` generates an integrity hash over all
   deterministic fields. Checksum fields are explicitly enumerated in `CHECKSUM_FIELDS`.
3. **Stateless services** — All service methods are pure functions. Replaying the same
   sequence of decisions produces identical state transitions.
4. **Canonical JSON** — All serialization uses `json.dumps` with `sort_keys=True` and
   `ensure_ascii=False` for stable output.
5. **Audit chain integrity** — Every decision creates a hash-chained audit event.
   `verify_chain()` detects any break in the chain.

## Consequences

### Positive
- Full reproducibility of any session from its serialized state
- Checksum verification catches data corruption or tampering
- Replay engine can reconstruct any prior session state

### Negative
- Timestamp fields (`last_saved`, event timestamps) are non-deterministic by nature
  and excluded from equality assertions in tests

## Rejected Alternatives

- **Event sourcing**: Too complex for a local-first application with a single user.
- **Database-backed state**: Adds deployment complexity; JSON files are simpler for
  scientific reproducibility and manual inspection.
