# Workflow Visual Semantics

## Canonical Workflow

The APOLLO workflow follows a strict canonical order:

```
Protocol → EC → IC → QC → Export → Replay
```

This order is **enforced both programmatically and visually**.

## Visual Workflow Representation

### Workflow Stepper

The `render_workflow_stepper()` component displays the complete workflow with:

1. **Stage Icons**: Each stage has a unique icon
   - Protocol: ◈
   - EC: ⊘
   - IC: ⊕
   - QC: ◎
   - Export: ⬇
   - Replay: ⟲

2. **Stage Colors**: Each stage has a semantic color
   - Protocol: Blue (authority)
   - EC: Red (exclusion)
   - IC: Yellow (inclusion)
   - QC: Green (quality)
   - Export: Cyan (output)
   - Replay: Bright Cyan (verification)

3. **State Indicators**:
   - **Completed**: Solid border, filled background
   - **Active**: Highlighted border, pulsing indicator
   - **Locked**: Blue border, lock icon
   - **Future**: Grey, reduced opacity

4. **Connectors**: Lines between stages show flow direction
   - Completed: Green connector
   - Pending: Grey connector

## Stage Progression Rules

### EC Stage (Exclusion Criteria)
- **Purpose**: Remove irrelevant studies
- **Prerequisite**: Protocol locked
- **Input**: All imported articles
- **Output**: Articles with EC decision (include/exclude/skip)
- **Visual**: Red accent, exclusion icon (⊘)

### IC Stage (Inclusion Criteria)
- **Purpose**: Identify relevant studies
- **Prerequisite**: EC complete for article
- **Input**: EC-included articles only
- **Output**: Articles with IC decision
- **Visual**: Yellow accent, inclusion icon (⊕)
- **Enforcement**: Cannot review article at IC without EC pass

### QC Stage (Quality Criteria)
- **Purpose**: Assess study quality
- **Prerequisite**: IC complete for article
- **Input**: IC-included articles only
- **Output**: Articles with QC score and decision
- **Visual**: Green accent, quality icon (◎)
- **Enforcement**: Cannot review article at QC without IC pass

### Export Stage
- **Purpose**: Generate reproducible output
- **Prerequisite**: QC complete
- **Output**: PRISMA report, session JSON, protocol JSON
- **Visual**: Cyan accent, download icon (⬇)

### Replay Stage
- **Purpose**: Verify reproducibility
- **Prerequisite**: Export bundle exists
- **Output**: Parity verification
- **Visual**: Bright cyan accent, replay icon (⟲)

## Visual State Machine

```
┌─────────────────────────────────────────────────────────────┐
│                      PROTOCOL                               │
│  (Must be locked before screening can begin)               │
└────────────────────────┬────────────────────────────────────┘
                         │ Protocol locked
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      EC STAGE                               │
│  ⊘ All articles screened for exclusion criteria            │
│  Red border when active                                     │
└─────────┬─────────────────────────────┬─────────────────────┘
          │ Article EC-included         │ Article EC-excluded
          ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      IC STAGE                               │
│  ⊕ Only EC-passed articles reviewed                        │
│  Yellow border when active                                  │
└─────────┬─────────────────────────────┬─────────────────────┘
          │ Article IC-included         │ Article IC-excluded
          ▼                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      QC STAGE                               │
│  ◎ Only IC-passed articles assessed                        │
│  Green border when active                                   │
└─────────┬─────────────────────────────┬─────────────────────┘
          │ QC passed                    │ QC failed
          ▼                             ▼
┌──────────────────────┐    ┌──────────────────────┐
│     EXPORT           │    │     EXPORT           │
│  ⬇ Final output     │    │  ⬇ Partial output    │
└──────────┬───────────┘    └──────────┬───────────┘
           │                         │
           ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      REPLAY                                 │
│  ⟲ Reproducibility verification                            │
│  Check: Original == Regenerated                            │
└─────────────────────────────────────────────────────────────┘
```

## Color Semantics by Stage

| Stage | Primary Color | Semantic Meaning |
|-------|--------------|------------------|
| EC | #FF4757 (Red) | Exclusion, removal, filter |
| IC | #FFB020 (Yellow) | Inclusion, relevance, selection |
| QC | #00D67E (Green) | Quality, assessment, acceptance |
| Export | #00c8d7 (Cyan) | Output, reporting, documentation |
| Replay | #00FFFF (Bright Cyan) | Verification, validation, trust |

## Accessibility

### Color Independence
All stage information is communicated through:
1. **Color** - Stage accent color
2. **Icon** - Stage-specific icon
3. **Label** - Stage abbreviation (EC, IC, QC)
4. **State** - Active/completed/locked indicators

### Contrast Requirements
- Stage labels: Minimum 4.5:1 contrast
- Icons: Minimum 3:1 contrast
- Progress indicators: Minimum 3:1 contrast

## Implementation

### Component: `WorkflowStepper`
```python
render_workflow_stepper(
    current_stage="ec",
    session_state={"total_count": 100, "current_index": 45},
    locked=False,
    protocol_hash="abc123..."
)
```

### Component: `StageProgress`
```python
render_stage_progress(
    stage="ec",
    completed=45,
    total=100,
    included=30,
    excluded=15
)
```

### Component: `StageLockBanner`
```python
render_stage_lock_banner(
    stage="ic",
    message="Complete EC screening to unlock IC"
)
```

## Visual Verification Checklist

- [ ] Workflow stepper shows all 6 stages
- [ ] Current stage is visually highlighted
- [ ] Completed stages show checkmarks/indicators
- [ ] Future stages are locked/greyed
- [ ] Stage progression follows canonical order
- [ ] Stage colors match semantic meaning
- [ ] Connectors show flow direction
- [ ] Stage icons are distinct
- [ ] Protocol hash visible in header
- [ ] No stage can be skipped visually
