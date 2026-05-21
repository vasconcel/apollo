# ADR-001: Stateless Services Architecture

**Status:** Accepted  
**Date:** 2026-05-20  
**Deciders:** APOLLO Architecture Team

## Context

The `ScreeningSession` class had grown to ~700 lines encompassing navigation, querying,
persistence, ingestion, audit, decision logic, and workflow orchestration. This monolith
made the code difficult to reason about, test in isolation, and verify for determinism.

The core insight was that most operations on session data are pure transformations:
given an article list, an index, and a decision, produce a new state. These do not
require instance state.

## Decision

Extract all operations into stateless service classes where every public method is a
`@staticmethod`. Each service owns a single architectural concern:

- `NavigationService` — article navigation and index management
- `SessionQueryService` — queries and filters over article collections
- `SessionPersistenceService` — JSON serialization and filesystem I/O
- `SessionIngestionService` — file parsing and metadata normalization
- `SessionAuditService` — hash-chain audit event management
- `SessionDecisionService` — review decision application
- `SessionOrchestrationService` — coordination of multi-service decision flows
- `WorkflowStateService` — canonical stage ordering and transition rules

## Consequences

### Positive
- Each service can be tested in isolation with zero setup
- Determinism is trivial to verify (same inputs → same outputs)
- Architectural boundaries are explicit and enforceable
- Service composition is explicit and auditable

### Negative
- More files and imports to manage
- Callers must pass all required data explicitly (no hidden state)

## Rejected Alternatives

- **Keep monolithic `ScreeningSession`**: Would have continued to grow and become untestable.
- **Use dependency injection framework**: Overkill for a deterministic system; explicit composition is clearer.
- **Instance methods with state**: Would defeat the purpose of statelessness verification.
