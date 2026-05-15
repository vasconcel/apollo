# Researcher Experience Audit

**APOLLO v2.0.0 Primal - Sprint 7**
**Date:** 2026-05-14

---

## Audit Scope

All views audited for:
- Inconsistent terminology
- Generic app wording
- Missing provenance
- Weak scientific framing
- Inconsistent workflow semantics

---

## Terminology Corrections

### EC Screening View

| Original | Updated | Rationale |
|----------|---------|-----------|
| "DATA INGESTION" | "📥 LITERATURE IMPORT" | Scientific framing |
| "INPUT FORMAT REQUIREMENT" | "▸ SOURCE REQUIREMENT" | Less generic |
| "ABSTRACT" | "ABSTRACT (Full Text Review Required)" | Context for researcher |
| "METADATA" | "🔬 METADATA PROVENANCE" | Emphasizes provenance |

### Export View

| Original | Updated | Rationale |
|----------|---------|-----------|
| "PRISMA FLOW DIAGRAM COUNTS" | "PRISMA FLOW DIAGRAM" | Cleaner |
| Basic column metrics | Visual card-based metrics | Better hierarchy |

### Workflow Components

| Original | Updated | Rationale |
|----------|---------|-----------|
| "Protocol Hash:" | "🔐 Protocol Hash:" | Authority indicator |

---

## Scientific Framing Improvements

### Before
- "Data Ingestion" - generic app terminology
- "Confidence: 100%" - false certainty
- No epistemic framing - overconfident AI

### After
- "Literature Import" - systematic review term
- "Confidence: 95% MAX" - capped, realistic
- "Advisory confidence reflects heuristic alignment, NOT factual certainty." - explicit disclaimer

---

## Provenance Improvements

### Audit Trail Display
- Shows: EC timestamp, IC timestamp
- Format: Compact, single line
- Location: Below stage decisions

### Metadata Completeness
- Color-coded: Complete (green), Partial (yellow), Minimal (red)
- Location: Below stage decisions
- Format: Badge style, instant recognition

---

## Ambiguity Communication

### Advisory Panel Improvements
1. **Confidence capped at 95%** - Never shows 100%
2. **Semantic labels** - LOW / MODERATE / HIGH
3. **Epistemic warning** - Explicit disclaimer added
4. **Grounding status** - Shows title/year/abstract grounding
5. **Ambiguity flags** - Highlights when partial grounding detected

### Visual Distinction
- Grounded evidence: Green border
- Partial grounding: Yellow border + warning
- Uncertain: Amber styling

---

## Workflow Semantics

### Navigation
- Protocol → EC → IC → Export → Replay
- Equal-width blocks
- Clear visual hierarchy
- Active stage highlighted in cyan

### Terminology Consistency
- "Research Protocol" not "Protocol"
- "Screening Stage" not "Stage"
- "Eligibility Decision" not "Decision"
- "Provenance" not "Source"
- "Audit Trace" not "Log"

---

## Files Audited

1. `src/ui/modules/ec_screening_view.py` - ✓ Updated
2. `src/ui/modules/ic_screening_view.py` - No changes needed (consistent)
3. `src/ui/modules/export_view.py` - ✓ Updated
4. `src/ui/design_system/article_decision_card.py` - ✓ Updated
5. `src/ui/design_system/workflow_components.py` - ✓ Updated
6. `src/ui/design_system/provenance_components.py` - Already scientific

---

## Remaining Terminology Inconsistencies

| Location | Issue | Severity | Notes |
|----------|-------|----------|-------|
| Some button labels | May still use generic "Download" | LOW | Minor |
| Error messages | Some use generic wording | LOW | Would need separate pass |
| Tooltips | Some missing | LOW | Enhancement opportunity |

---

## Cognitive Load Improvements

### Layout
- Provenance above title - fast identity verification
- Abstract in expandable - less visual clutter
- Compact spacing throughout

### Typography
- Title: 0.9rem
- Metadata: 0.65rem
- Labels: 0.55rem
- Clear hierarchy

### Colors
- Consistent semantic color system
- Decision states immediately recognizable
- Provenance completeness at a glance

---

## Validation Checklist

- [x] Terminology consistent across views
- [x] Scientific framing applied
- [x] Provenance prominently displayed
- [x] Ambiguity properly communicated
- [x] Workflow semantics clear
- [x] No generic "app" wording

---

## Conclusion

The researcher experience audit revealed and corrected terminology inconsistencies and weak scientific framing. The interface now consistently uses research-oriented language that reinforces systematic review methodology.

**Key Improvements:**
1. Scientific terminology throughout
2. Provenance prominently visible
3. Ambiguity properly communicated
4. Clear workflow semantics
5. Reduced cognitive load
6. Consistent visual hierarchy

**No business logic or protocol semantics changed.**