# APOLLO v1.0.0 System State Summary

**Generated**: 2026-05-14
**Version**: APOLLO v2.0.0 Primal

---

# 1. System Overview

## Purpose
APOLLO (Audit Pipeline for Literature Operations & Layered Observation) is a deterministic screening engine for systematic literature reviews (SLRs). It implements a Human-in-the-Loop (HITL) workflow for screening academic articles through Exclusion Criteria (EC), Inclusion Criteria (IC), and Quality Criteria (QC) stages.

## Workflow Stages
1. **Protocol Configuration** — Define and lock screening criteria
2. **EC Screening** — Apply exclusion criteria to all articles
3. **IC Screening** — Apply inclusion criteria to EC-passed articles
4. **QC Assessment** — Quality assessment of IC-passed articles
5. **Export & Audit** — Generate audit packages and exports
6. **Replay** — Deterministic session reconstruction for verification

## Architectural Philosophy
- **Researcher Authority**: All final decisions made by human researcher
- **LLM Advisory Only**: AI suggestions are non-binding, on-demand only
- **Deterministic**: Same inputs produce same outputs (reproducibility)
- **Immutable Audit**: Cryptographically chained decision events
- **Forensic-grade UI**: Terminal-aesthetic research operations console

---

# 2. Canonical Workflow

## Routing Path (app.py)
```
app.py (Streamlit entry)
    └── Sidebar Navigation
        ├── "Protocol Configuration" → protocol_view.py
        ├── "EC Screening" → ec_screening_view.py
        ├── "IC Screening" → ic_screening_view.py
        ├── "Inter-Rater Calibration" → calibration_view.py
        └── "Exports & Audit" → export_view.py
```

## Authority Boundaries
| View | Authority | Notes |
|------|-----------|-------|
| protocol_view.py | **AUTHORITATIVE** | REQUIRED before screening; defines EC/IC criteria |
| ec_screening_view.py | **AUTHORITATIVE** | Stage 1: applies EC criteria |
| ic_screening_view.py | **AUTHORITATIVE** | Stage 2: applies IC criteria to EC-passed |
| calibration_view.py | **AUTHORITATIVE** | Cohen's Kappa export |
| export_view.py | **AUTHORITATIVE** | Session + manifest + reproducibility bundle |

## Stage Transitions
```
EC (all articles) → IC (EC-passed only) → QC (IC-passed only)
```
- **Skip**: Articles can be skipped and recovered
- **Discuss**: Articles flagged for team discussion
- **Deterministic**: Each article decision propagates through funnel

---

# 3. Core Domain Model

## ArticleReview (`src/core/screening_session.py`)
**Responsibilities**: Single article review state with metadata lineage

**Key Fields**:
- `article_id`: Unique identifier
- `title`, `abstract`: Core content
- `metadata`: Dict containing year, year_source, authors, literature_type, etc.
- `ec_stage`, `ic_stage`: Decision at each stage
- `ec_llm_suggestion`, `ic_llm_suggestion`: Advisory snapshots
- `cis1`, `ces1`, `revisor1`: Reviewer codes

**Properties**:
- `is_ec_included`: True if passed EC
- `is_ic_included`: True if passed IC (requires EC pass first)
- `is_discussion_needed`: True if flagged at any stage
- `get_literature_type()`: Returns "WL" or "GL"
- `get_metadata_completeness()`: Returns "complete"/"partial"/"minimal"
- `get_year_source()`: Returns provenance flag

## ScreeningSession (`src/core/screening_session.py`)
**Responsibilities**: Session state management with workflow rules

**Key Fields**:
- `session_id`, `created_at`, `stage` (ec/ic/complete)
- `articles`: List[ArticleReview]
- `dynamic_protocol`: Dict from DynamicProtocol
- `current_index`, `total_count`, `ec_completed`, `ic_completed`
- `_audit_chain`: Immutable event chain

**Key Methods**:
- `record_decision(decision, notes, llm_suggestion)`: Records at current stage
- `apply_decision(article_id, stage, decision, notes)`: Records at specific article
- `get_ec_included_articles()`, `get_ic_included_articles()`: Filter accessors
- `get_wl_articles()`, `get_gl_articles()`: Literature type filtering
- `verify_audit_chain()`: Validates chain integrity
- `detect_tampering()`: Detects hash mismatches
- `save_to_json()`, `load_from_json()`: Deterministic persistence with checksum

## DecisionRecord (EC/IC Evaluations)
**Location**: `src/core/criteria_evaluator.py`

**Structure**:
- `decision`: "include" or "exclude"
- `criterion`: Criterion ID (e.g., "EC1", "IC2")
- `reason`: Human-readable justification

## AISuggestion (`src/core/llm_assistant.py`)
**Responsibilities**: Structured LLM advisory with metadata grounding

**Key Components**:
- `StructuredAdvisory`: Full structured response with criterion evaluations
- `CriterionEvaluation`: Per-criterion analysis with evidence/justification
- `AdvisorySuggestion`: Legacy compatibility wrapper

**Properties**:
- `stage`: "ec" or "ic"
- `decision`: "include"/"exclude"/"unavailable"
- `confidence`: 0.0-1.0
- `criterion_evaluations`: Dict[str, CriterionEvaluation]
- `metadata_grounding`: Dict showing which fields were used
- `is_fallback`: True if LLM unavailable

---

# 4. Reproducibility & Audit

## Chained Audit Hashes
**Implementation**: `ScreeningSession._append_audit_event()`

```python
previous_hash = chain[-1]["current_hash"] or "GENESIS"
event_payload = {event_id, timestamp, article_id, reviewer_id, stage, decision, notes}
payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
current_hash = SHA256(payload_json + previous_hash)
```

**Properties**:
- First event: `previous_hash = "GENESIS"`
- Subsequent: Each links to previous event
- Immutable: Cannot modify without breaking chain

## Checksum Validation
**Implementation**: `ScreeningSession.save_to_json()`

- Computes SHA256 of canonical JSON representation
- Stores as `session_checksum` in saved file
- Validated on `load_from_json()`

## Reproducibility Bundle Structure (`reproducibility_engine.py`)
```
apollo_bundle_{id}/
├── protocol.json          # Protocol definition
├── session.json           # Full session state
├── audit_log.json         # All audit events
├── manifest.json          # Bundle metadata + hashes
├── checksums.sha256       # File integrity hashes
├── environment.json       # APOLLO version, Python version
└── exports/               # Regenerated decision exports
```

## Tamper Detection
**Implementation**: `verify_audit_chain()`, `detect_tampering()`

- Validates hash chain integrity
- Detects modified events via hash mismatch
- Returns list of tampered event IDs

---

# 5. LLM Advisory Architecture

## Advisory-Only Role
**Key Principle**: Researcher makes final decisions. LLM ONLY assists interpretation.

**Implementation**:
- `LLMAssistant.suggest_ec()`, `suggest_ic()` return advisory objects
- UI displays suggestion but requires explicit researcher action
- No automatic bulk processing
- All suggestions logged for audit

## Metadata Propagation Pipeline
**Status**: ✅ **OPERATIONAL** (verified in LLM_CONTEXT_FIX_REPORT.md)

**Verified propagations**:
- Year → EC/IC prompts
- year_source → "atlas", "manual", etc.
- metadata_completeness → "complete", "partial", "minimal"
- literature_type → "White Literature" / "Grey Literature"
- Authors, title, abstract → Evidence extraction

**Files verified**:
- `ec_screening_view.py`: Passes metadata to `suggest_ec()`
- `ic_screening_view.py`: Passes metadata to `suggest_ic()`
- `llm_assistant.py`: Accepts metadata in both methods

## Fallback Behavior
**Implementation**: `LLMAssistant._fallback_advisory()`

- Returns `StructuredAdvisory` with `is_fallback=True`
- `decision="unavailable"`, `confidence=0.0`
- `ambiguity_flags=["LLM not available"]`
- Visually distinct from true advisory

## Cache Behavior
**Status**: NOT IMPLEMENTED — LLM requests are not cached. Each "GENERATE ANALYSIS" click triggers fresh API call.

## Deterministic Constraints
- Temperature set to 0.1 (low randomness)
- Max tokens: 1200
- Prompt includes explicit rules to prevent hallucination
- Structured JSON output with exact schema

---

# 6. Design System & UX Alignment

## Semantic Workflow Visualization
**Components**: `src/ui/design_system/workflow_components.py`

**Stages defined**:
1. PROTOCOL (icon: ◐)
2. EC (icon: ⊘)
3. IC (icon: ⊕)
4. EXPORT (icon: ⇓)
5. REPLAY (icon: ↻)

**Color scheme**: Cyan (#00c8d7) for active, muted grey for inactive

## Provenance Visibility
**Components**: `src/ui/design_system/provenance_components.py`

**Displayed**:
- Literature type (WL/GL) with full definitions
- Year source ("atlas", "regex", "missing")
- Metadata completeness ("complete", "partial", "minimal")
- DOI, URL, authors, library

## Audit Visibility
**Components**: `src/ui/design_system/audit_components.py`

**Features**:
- Audit event display
- Chain integrity status
- Session checksum display

## Reproducibility Indicators
**Components**: `src/ui/design_system/reproducibility_components.py`

**Features**:
- Bundle creation UI
- Replay status display
- Checksum verification

## Scientific State Representation
- Progress bars show EC/IC/QC completion
- WL/GL counters in sidebar
- Protocol hash display in telemetry
- Decision codes (EC1-EC4, IC1-IC3) recorded

---

# 7. Current Test Status

## Test Summary
| Category | Count | Status |
|----------|-------|--------|
| Tests collected | 66 | — |
| Tests passed | 63 | ✅ |
| Tests failed | 3 | ⚠️ |
| Collection errors | 16 | ❌ |

## Failed Tests (Known Issues)
1. `test_session_stage_enum_complete`: QC stage missing from SessionStage enum
2. `test_article_review_stage_progression`: `is_qc_included` property not implemented
3. `test_workflow_components_importable`: 5 stages instead of expected 6

## Collection Errors (Missing Modules)
The following test files fail to import due to missing modules:
- `test_architectural_integrity.py` — QCProtocol missing
- `test_config_manager.py` — config_manager missing
- `test_database.py` — database missing
- `test_review_isolation.py` — missing imports
- `test_protocol_*.py` — protocol layer issues
- Multiple unit tests — missing modules (synthesis_aggregator, ai_handler, etc.)

## Working Tests
- `test_design_system_ux.py`: 28 tests (25 pass, 3 fail)
- `test_structured_advisory.py`: 24 tests (all pass)
- `test_visual_logic.py`: 8 tests (all pass)

---

# 8. Remaining Technical Debt

## Known Architectural Risks
1. **protocol_engine.py syntax error** — Line 306 has indentation error (return statement outside method)
2. **QC stage not fully implemented** — ArticleReview missing QC decision fields
3. **16 orphaned test files** — Cannot run due to missing modules

## Legacy Compatibility Remnants
- `.deprecated/ui_modules/` — Old view modules (ingestion_view, review_view, etc.)
- `.deprecated/core/` — Old core modules (database.py, decision_engine.py, quality.py)
- `app/main.py` — Separate legacy application (not part of canonical path)

## Scalability Concerns
- LLM calls are synchronous (no caching, rate limiting may occur)
- Session state held in Streamlit session (no distributed state)
- No batch processing — individual article review only

## Unresolved UX Problems
- No "jump to article" feature (only prev/next navigation)
- No global search across articles
- No duplicate detection UI (handled deterministically)

## Unresolved LLM Limitations
- No API key validation on startup
- No request timeout handling
- No retry logic beyond single retry on parse failure

---

# 9. Scientific Defensibility Assessment

## Reproducible Screening ✅
- Session state can be saved/loaded with deterministic JSON
- Checksum verification on load
- Reproducibility bundle export enables full reconstruction

## Auditable Decisions ✅
- Every decision appends to audit chain with SHA256 hash
- Chain integrity verifiable (`verify_audit_chain()`)
- Tampering detectable (`detect_tampering()`)
- All decisions recorded with researcher_id and timestamp

## Protocol Traceability ✅
- Protocol locked before screening begins
- Protocol hash displayed in telemetry
- Dynamic protocol snapshots on stage transitions

## Deterministic Replay ✅
- `ReplayEngine.replay_session()` reconstructs session from bundle
- Audit chain restored with validation
- Export regeneration produces deterministic output

## Human-Final-Decision Principle ✅
- LLM suggestions are ADVISORY ONLY
- Researcher must explicitly click Include/Exclude/Skip
- LLM suggestion not auto-applied
- LLM decision flagged as `is_fallback` when unavailable

## Limitations (Conservative Assessment)
- **No external validation**: Checksums are internal, not compared to external registry
- **No cryptographic signing**: Audit chain not digitally signed
- **Time dependency**: Uses system clock, not blockchain
- **No encryption**: Audit chain is plaintext (suitable for audit, not confidentiality)

---

# 10. Recommended Next Priorities

## Stabilization (High Priority)
1. **Fix protocol_engine.py syntax error** — Line 306 indentation
2. **Implement QC stage fully** — Add QC decision fields to ArticleReview
3. **Resolve test collection errors** — Either implement missing modules or remove dead tests

## Methodological Rigor (High Priority)
1. **Add unit tests for audit chain** — verify_audit_chain() coverage
2. **Add integration tests for replay** — bundle → replay → regenerate → compare
3. **Add determinism tests** — Same input → same output verification

## UX Maturity (Medium Priority)
1. **Add article search/jump** — Navigation improvement
2. **Add keyboard shortcuts** — Power user efficiency
3. **Add batch progress indicator** — Show % complete with estimates

## Empirical Validation (Medium Priority)
1. **Conduct user testing** — Verify researcher workflow matches design
2. **Validate export formats** — Ensure PRISMA compatibility
3. **Test with real ATLAS files** — End-to-end integration test

## Publication Readiness (Lower Priority)
1. **Documentation cleanup** — Consolidate reports into single spec
2. **Code signing** — Add cryptographic signing to audit chain
3. **External checksum registry** — Optional: publish hashes to external ledger

---

# Appendix: File Inventory

## Canonical Core Modules
| File | Status | Notes |
|------|--------|-------|
| `src/core/screening_session.py` | ✅ ACTIVE | ArticleReview, ScreeningSession |
| `src/core/protocol_engine.py` | ⚠️ SYNTAX ERROR | Indentation issue at line 306 |
| `src/core/llm_assistant.py` | ✅ ACTIVE | LLMAssistant, StructuredAdvisory |
| `src/core/criteria_registry.py` | ✅ ACTIVE | Single source of truth for keywords |
| `src/core/reproducibility_engine.py` | ✅ ACTIVE | ReproducibilityEngine, ReplayEngine |
| `src/core/dynamic_protocol.py` | ✅ ACTIVE | DynamicProtocol, ProtocolState |
| `src/core/export_engine.py` | ✅ ACTIVE | ExportEngine with audit trail |

## Canonical UI Modules
| File | Status | Routing |
|------|--------|---------|
| `app.py` | ✅ ACTIVE | Entry point |
| `protocol_view.py` | ✅ ACTIVE | "Protocol Configuration" |
| `ec_screening_view.py` | ✅ ACTIVE | "EC Screening" |
| `ic_screening_view.py` | ✅ ACTIVE | "IC Screening" |
| `calibration_view.py` | ✅ ACTIVE | "Inter-Rater Calibration" |
| `export_view.py` | ✅ ACTIVE | "Exports & Audit" |

## Design System
| Component | File |
|-----------|------|
| Workflow | `workflow_components.py` |
| Provenance | `provenance_components.py` |
| Audit | `audit_components.py` |
| Reproducibility | `reproducibility_components.py` |
| Semantic Colors | `semantic_colors.py` |
| Typography | `typography.py` |
| Spacing | `spacing.py` |

## Deprecated/Orphaned
| Path | Classification |
|------|----------------|
| `.deprecated/ui_modules/*` | Deprecated views |
| `.deprecated/core/*` | Deprecated core modules |
| `src/ui/modules/review_view.py` | Not routed |
| `app/main.py` | Separate legacy app |