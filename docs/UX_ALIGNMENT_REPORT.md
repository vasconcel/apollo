# UX Alignment Report

## Executive Summary

This report documents the alignment of APOLLO's UI/UX with the canonical scientific workflow, reproducibility guarantees, audit chain semantics, and deterministic screening authority.

## Alignment Objectives

### Preserved Business Rules

1. **Canonical Execution Flow**
   - Protocol → EC → IC → QC → Export → Replay
   - No stage skipping allowed
   - EC failure blocks IC progression
   - IC failure blocks QC progression

2. **Deterministic Behavior**
   - Session checksums computed for integrity
   - Protocol hash required for authority
   - Reproducibility bundle generation

3. **Reproducibility Semantics**
   - Replay verification with parity check
   - Checksum verification panel
   - Determinism status indicator

4. **Audit-Chain Visibility**
   - Immutable audit events
   - Hash chain verification
   - Tampering detection

5. **Export Authority**
   - Protocol export for reproducibility
   - Session export with full lineage
   - PRISMA-compatible reporting

6. **Protocol Authority**
   - Protocol must be locked before screening
   - Protocol hash displayed for verification
   - Version tracking

## UI Semantic Mapping

### Visual States → Business Rules

| Visual State | Business Rule | Enforcement |
|--------------|---------------|-------------|
| Workflow stepper shows locked future stages | Cannot skip stages | `can_proceed_to_stage()` check |
| Stage colors indicate state | EC=red, IC=yellow, QC=green | Workflow stage colors |
| Include badge = green | INCLUDE decision | `get_decision_semantic()` |
| Exclude badge = red | EXCLUDE decision | `get_decision_semantic()` |
| Provenance panel visible | Metadata lineage required | `render_provenance_panel()` |
| Audit chain verification | Immutable audit chain | `verify_audit_chain()` |
| Replay parity indicator | Reproducibility check | `render_replay_verification_panel()` |
| Protocol authority banner | Locked protocol required | `render_protocol_authority_banner()` |

### Workflow State → Visual Mapping

#### Protocol Stage
- Protocol authority banner displayed
- Protocol hash visible
- Version and criteria counts shown
- State: DRAFT (grey) → LOCKED (blue)

#### EC Stage
- Workflow stepper highlights EC
- Red accent color for exclusion theme
- Article decision card shows EC decision
- EC decisions summary visible

#### IC Stage
- Workflow stepper highlights IC
- Yellow accent color for inclusion theme
- Only EC-included articles shown
- IC decisions summary visible

#### QC Stage
- Workflow stepper highlights QC
- Green accent color for quality theme
- Only IC-included articles shown
- QC scores visible

#### Export Stage
- Export button enabled after QC complete
- PRISMA flow counts displayed
- Protocol JSON export available

#### Replay Stage
- Reproducibility bundle creation
- Replay verification panel
- Parity status indicator

## Component Mapping

### Design System → Business Logic

| Component | Source of Truth | Business Rule |
|-----------|-----------------|---------------|
| `WorkflowStepper` | `SessionStage` enum | Stage ordering |
| `ArticleDecisionCard` | `ArticleReview` class | Stage progression rules |
| `ProvenancePanel` | `ArticleReview.metadata` | Metadata completeness |
| `AuditStatusBadge` | `ScreeningSession._audit_chain` | Audit integrity |
| `HashVerificationPanel` | `ScreeningSession.compute_checksum()` | Integrity verification |
| `ReplayVerificationPanel` | `ReproducibilityEngine` | Reproducibility check |
| `ProtocolAuthorityBanner` | `DynamicProtocol` | Protocol state |
| `SessionLineagePanel` | `ScreeningSession` | Session metadata |

### Business Logic → Design System

| Business Class | Design System Token |
|-----------------|---------------------|
| `ArticleReview.ec_stage == "include"` | `get_semantic_color("INCLUDED")` |
| `ArticleReview.ec_stage == "exclude"` | `get_semantic_color("EXCLUDED")` |
| `ScreeningSession.stage == "ec"` | `get_workflow_stage_color("ec")` |
| `session.verify_audit_chain()` valid | `get_semantic_color("VERIFIED")` |
| `session.verify_audit_chain()` invalid | `get_semantic_color("AUDIT_MISMATCH")` |
| `article.literature_type == "WL"` | `get_semantic_color("WL")` |
| `article.literature_type == "GL"` | `get_semantic_color("GL")` |

## Verification Matrix

| Requirement | Implementation | Test |
|-------------|----------------|------|
| Workflow order visible | `render_workflow_stepper()` | `test_workflow_stages_defined()` |
| Stage colors match semantics | `get_workflow_stage_color()` | `test_workflow_stage_colors_unique()` |
| Decisions have distinct colors | `get_decision_semantic()` | `test_all_decisions_have_colors()` |
| Provenance always visible | `render_provenance_panel()` | `test_article_metadata_propagation()` |
| Audit state clear | `render_audit_status_badge()` | `test_audit_states_defined()` |
| Reproducibility indicators | `render_replay_verification_panel()` | `test_replay_state_defined()` |
| Protocol authority shown | `render_protocol_authority_banner()` | Manual verification |
| Session lineage tracked | `render_session_lineage_panel()` | Manual verification |

## Accessibility Verification

| Requirement | Standard | Implementation |
|-------------|----------|----------------|
| Color contrast | WCAG AA (4.5:1) | `test_color_contrast_ratios()` |
| Font sizes | Minimum 0.6rem | `test_font_sizes_meet_minimum()` |
| Touch targets | 44px minimum | `test_touch_target_minimum()` |
| Semantic labels | Required | `test_semantic_has_accessibility_labels()` |

## Anti-Patterns Prevented

### Prohibited Visual Patterns

1. **Dashboard-style overview** - Prevented by explicit workflow stepper showing stage progression
2. **Hidden workflow order** - Prevented by linear stepper with connectors
3. **Stage skipping UI** - Prevented by locked/future stage states
4. **Disconnected widgets** - Prevented by design system token consistency
5. **Business logic duplication** - Prevented by direct use of business classes

### Visual Enforcement

| Anti-Pattern | Prevention |
|--------------|------------|
| Generic dashboard | Workflow stepper forces canonical view |
| Hidden workflow | Stepper is always visible |
| Stage skipping | Future stages locked, greyed out |
| Ambiguous decisions | Distinct colors + text labels |
| Hidden provenance | Provenance panel in article card |

## Recommendations

1. **Enforce design system usage** - All new UI components should import from `src.ui.design_system`
2. **Add linting rule** - Detect inline colors that don't use semantic tokens
3. **Document exceptions** - Any deviation from design system must be documented
4. **Update routed views** - Ensure all views use design system components
5. **Add integration tests** - Test UI renders correctly from business state
