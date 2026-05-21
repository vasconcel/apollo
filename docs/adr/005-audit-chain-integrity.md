# ADR-005: Audit Chain Integrity

**Status:** Accepted  
**Date:** 2026-05-20  
**Deciders:** APOLLO Architecture Team

## Context

In a scientific screening workflow, every reviewer decision must be auditable.
The audit trail must be tamper-evident: if any event in the chain is modified after
creation, the system must detect it. This is essential for:

- Regulatory compliance (systematic review standards)
- Reproducibility (verifying that decisions haven't been altered)
- Provenance (tracking the full decision history for each article)

## Decision

Implement a hash-chained audit event system in `SessionAuditService`:

1. **Event structure**: Each event contains `event_id`, `timestamp`, `researcher_id`,
   `article_id`, `decision`, `notes`, `stage`, plus `previous_hash` and `event_hash`.
2. **Genesis event**: The first event has `previous_hash = "GENESIS"`.
3. **Hash chain**: `event_hash = SHA256(previous_hash + event_data)`. Each event's
   hash depends on all prior events.
4. **Verification**: `verify_chain()` walks the chain and confirms each event's
   `previous_hash` matches the prior event's `event_hash`. Returns `(is_valid, count)`.
5. **Tamper detection**: `detect_tampering()` re-computes each event's hash from its
   data and compares to the stored `event_hash`. Returns `(is_clean, count)`.
6. **Immutable after creation**: Events are never modified in place. The `append_event`
   method creates new events only.

## Consequences

### Positive
- Tampering with any event is detected by `detect_tampering()`
- Broken chain links are detected by `verify_chain()`
- Full audit history is preserved in `save_to_json` output

### Negative
- Audit chain grows with each decision (linear in memory)
- Hash computation adds minimal overhead per decision

## Rejected Alternatives

- **Simple list append without hashing**: Would not detect tampering.
- **External audit database**: Adds deployment complexity for a local-first tool.
- **Digital signatures**: Requires key management infrastructure unnecessary for
  a single-researcher workflow.
