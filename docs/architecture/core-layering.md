# APOLLO Core Architecture — Layering and Dependency Hierarchy

## Dependency Hierarchy

```
Layer 3 — Façade
  ScreeningSession
    Owns SessionState; delegates all operations to services below.

Layer 2 — Orchestration
  SessionOrchestrationService
    Coordinates NavigationService + SessionDecisionService for decision flows.

Layer 1 — Primitive Services
  NavigationService           Stage-aware article navigation.
  SessionQueryService         Query/filter article collections.
  SessionDecisionService      Apply review decisions, generate audit events.
  SessionIngestionService     Parse files, normalize metadata, create articles.
  SessionPersistenceService   JSON serialization, checksum, filesystem I/O.
  SessionAuditService         Audit-chain append, verify, tampering detection.

Layer 0 — Zero-Dependency Leaves
  WorkflowStateService        Canonical stage ordering, field maps, transitions.
  SessionState                Mutable state container (dataclass, no methods).
  architectural_fitness       Test-only governance helpers.
```

## Allowed Import Directions

| Module | May Import From | Must NOT Import From |
|---|---|---|
| WorkflowStateService | (stdlib only) | Any src.core module |
| SessionAuditService | (stdlib only) | Any src.core module |
| SessionState | (stdlib only) | Any src.core module |
| NavigationService | WorkflowStateService | orchestration, façade, decision |
| SessionQueryService | WorkflowStateService | orchestration, façade, decision, persistence, ingestion, audit |
| SessionPersistenceService | logging_config, dynamic_protocol | orchestration, façade, decision, query, navigation, ingestion, audit |
| SessionIngestionService | screening_session (ArticleReview only), article_metadata, year_extraction, logging_config | orchestration, façade, decision, query, navigation, persistence, audit, workflow_state |
| SessionDecisionService | SessionAuditService, dynamic_protocol | orchestration, façade, query, navigation, persistence, ingestion, workflow_state |
| SessionOrchestrationService | NavigationService, SessionDecisionService | All other services |
| ScreeningSession | ALL services + SessionState | streamlit, src.ui, src.advisory |

## Service Responsibilities

### WorkflowStateService (Layer 0)
- Define `STAGE_ORDER`, `STAGE_FIELD_MAP`, `STAGE_COUNTER_MAP`
- `is_valid_stage()`, `can_transition_to_stage()`, `get_next_stage()`
- `stage_field()`, `stage_counter()`, `is_workflow_complete()`

### SessionState (Layer 0)
- Pure `@dataclass` with 21 mutable fields
- Zero methods, zero orchestration logic
- Owned by ScreeningSession as `self.state`

### NavigationService (Layer 1)
- `get_current_article()`, `advance()`, `skip_unreviewable()`
- `is_complete()`, `can_review_current_at_stage()`
- Stage-aware index navigation

### SessionQueryService (Layer 1)
- `get_wl_articles()`, `get_gl_articles()`, `filter_articles()`
- `get_progress()`, `get_ec_included_articles()`, etc.
- Deterministic queries over article lists

### SessionDecisionService (Layer 1)
- `apply_review_decision()` — single decision application
- Creates audit events and protocol snapshots
- Counter increment calculation

### SessionIngestionService (Layer 1)
- `normalize_metadata()`, `normalize_literature_type()`
- `add_articles()`, `ingest_from_bytes()`
- CSV/Excel parsing and ArticleReview creation

### SessionPersistenceService (Layer 1)
- `save()`, `save_to_json()`, `load_from_json()`
- `compute_checksum()`, `compute_session_hash()`
- `list_sessions()`, `recover_session()`

### SessionAuditService (Layer 1)
- `append_event()` — hash-chain event creation
- `verify_chain()`, `detect_tampering()`, `get_events()`

### SessionOrchestrationService (Layer 2)
- `record_decision()` — coordinates decision + navigation
- `apply_decision_by_id()` — decision by article ID with index restore
- Returns structured result dict for caller to apply side effects

### ScreeningSession (Layer 3 — Façade)
- Owns `self.state: SessionState`
- Delegates to all services
- `__getattr__`/`__setattr__` for backward-compatible field access
- Public API consumed by UI, export, and replay infrastructure

## Determinism Guarantees

- All services are stateless (no instance state)
- All service methods are `@staticmethod`
- Same inputs → same outputs (excluding timestamp generation)
- No random number generation in deterministic path
- No I/O side effects outside persistence service

## Replay Guarantees

- Full session state serializable to JSON
- Checksum covers all deterministic fields
- Audit chain cryptographically linked
- Protocol snapshots captured at each decision
- Replay engine reconstructs session from serialized data

## Audit Guarantees

- Every decision creates an audit event
- Events form SHA-256 hash chain
- `verify_chain()` detects broken links
- `detect_tampering()` detects altered events
- Timestamps recorded per event
