# Provenance UI Specification

## Overview

Provenance visualization in APOLLO ensures that article lineage, metadata completeness, decision history, and audit trails are always visible without requiring export inspection.

## Provenance Hierarchy

```
Article
├── Literature Type (WL/GL)
├── Source Lineage
│   ├── Source (database/platform)
│   ├── Year
│   ├── Year Source (atlas/doi/manual)
│   ├── DOI
│   └── URL
├── Author Information
├── Metadata Completeness
├── Decision History
│   ├── EC Decision + Timestamp
│   ├── IC Decision + Timestamp
│   └── QC Decision + Timestamp
└── Audit State
```

## Component Specifications

### ArticleDecisionCard

**Purpose**: Canonical display of article with full provenance

**Elements**:
1. **Header**
   - Literature type badge (WL/GL)
   - Article ID (truncated)
   - Current decision badge

2. **Title & Authors**
   - Article title
   - Authors
   - Publication year

3. **Source Lineage**
   - Source/database
   - Library (if applicable)
   - DOI (if available)
   - URL (if available)
   - Year source indicator

4. **Stage Decisions Summary**
   - EC decision with color
   - IC decision with color
   - QC decision with color

5. **QC State** (if applicable)
   - QC score
   - QC decision

6. **Metadata Completeness**
   - Badge: Complete/Partial/Minimal

7. **Audit Trail**
   - Timestamps for each decision

8. **Researcher Notes**
   - Stage-specific notes with timestamps

### ProvenancePanel

**Purpose**: Detailed provenance metadata display

**Elements**:
- Title
- Authors
- Year
- DOI
- URL
- Source
- Library
- Literature type
- Year source
- Metadata completeness
- Raw data (expandable)

### LiteratureTypeIndicator

**Purpose**: Display literature type with full context

**Variants**:
- **WL (White Literature)**: Green badge, "Peer-reviewed academic sources"
- **GL (Grey Literature)**: Yellow badge, "Non-peer-reviewed sources"

### MetadataCompleteness

**Purpose**: Display metadata quality indicator

**Variants**:
- **Complete**: Green badge, full metadata available
- **Partial**: Yellow badge, some fields missing
- **Minimal**: Red badge, limited metadata
- **Unknown**: Grey badge, completeness unknown

### DecisionHistory

**Purpose**: Timeline of article decisions across stages

**Format**:
```
├─ [EC] INCLUDE @ 2024-01-15T10:30:00
│  └── Researcher notes here
├─ [IC] INCLUDE @ 2024-01-15T11:45:00
│  └── Additional notes
└─ [QC] INCLUDE @ 2024-01-16T09:00:00
```

### SourceLineage

**Purpose**: Display source database and year determination

**Elements**:
- Source: Database/platform name
- Year: Publication year
- Year Source: How year was determined (ATLAS, DOI, Manual)

## Visual States

### Article States

| State | Badge | Border | Background |
|-------|-------|--------|------------|
| EC Include | INCLUDED | Green | Green tint |
| EC Exclude | EXCLUDED | Red | Red tint |
| EC Pending | PENDING | Grey | Grey tint |
| IC Include | INCLUDED | Green | Green tint |
| IC Exclude | EXCLUDED | Red | Red tint |
| QC Include | INCLUDED | Green | Green tint |
| QC Exclude | EXCLUDED | Red | Red tint |

### Literature Type States

| Type | Badge | Semantic |
|------|-------|----------|
| WL | Green | Peer-reviewed |
| GL | Yellow | Non-peer-reviewed |

### Metadata Completeness States

| State | Badge | Implication |
|-------|-------|-------------|
| Complete | Green | Full provenance available |
| Partial | Yellow | Some provenance gaps |
| Minimal | Red | Manual verification recommended |
| Unknown | Grey | Completeness unverified |

## Accessibility

### Semantic Labels
All provenance components include `aria-label` attributes:
- `accessibility_label: "White Literature"`
- `accessibility_label: "Included"`
- `accessibility_label: "Complete Metadata"`

### Color Independence
Provenance is communicated through:
1. Color coding
2. Text labels
3. Icons (when applicable)
4. Structural layout

### Contrast Requirements
- All text meets 4.5:1 contrast
- Badge text on colored backgrounds: 3:1 minimum
- Grey text for secondary information: 4.5:1 on dark background

## Data Source Mapping

### ArticleReview Class

| Field | Provenance Component | Display |
|-------|---------------------|---------|
| `article_id` | Header | Article ID badge |
| `title` | Title Section | Article title |
| `abstract` | Abstract Expander | Full abstract |
| `metadata['literature_type']` | Header | WL/GL badge |
| `metadata['authors']` | Authors | Author list |
| `metadata['year']` | Source Lineage | Year |
| `metadata['year_source']` | Source Lineage | Year source badge |
| `metadata['doi']` | Source Lineage | DOI link |
| `metadata['source']` | Source Lineage | Source name |
| `metadata['library']` | Source Lineage | Library name |
| `metadata['metadata_completeness']` | Completeness | Badge |
| `ec_stage` | Decision Summary | EC badge |
| `ec_timestamp` | Audit Trail | Timestamp |
| `ec_notes` | Notes | Notes text |
| `ic_stage` | Decision Summary | IC badge |
| `ic_timestamp` | Audit Trail | Timestamp |
| `ic_notes` | Notes | Notes text |
| `qc_stage` | Decision Summary | QC badge |
| `qc_timestamp` | Audit Trail | Timestamp |
| `qc_notes` | Notes | Notes text |

## Usage Examples

### Render Article Decision Card
```python
from src.ui.design_system import render_article_decision_card

render_article_decision_card(
    article_review=article,
    current_stage="ec",
    show_full_details=True,
    show_qc_state=True,
    show_audit_state=True
)
```

### Render Provenance Panel
```python
from src.ui.design_system import render_provenance_panel

render_provenance_panel(
    article_metadata=article.metadata,
    include_raw=False
)
```

### Render Literature Type Indicator
```python
from src.ui.design_system import render_literature_type_indicator

render_literature_type_indicator("WL")
# Output: Green badge with "White Literature" description
```

### Render Metadata Completeness
```python
from src.ui.design_system import render_metadata_completeness

render_metadata_completeness("partial")
# Output: Yellow badge with "Partial Metadata" label
```

### Render Decision History
```python
from src.ui.design_system import render_decision_history

render_decision_history(article)
# Output: Timeline showing EC → IC → QC decisions
```

## Verification Checklist

- [ ] Provenance visible without inspecting exports
- [ ] Lineage preserved visually
- [ ] Literature type always displayed
- [ ] DOI/source/year always visible when available
- [ ] Metadata completeness indicated
- [ ] Decision history complete
- [ ] QC state shown when applicable
- [ ] Audit verification state displayed
- [ ] Researcher notes visible
- [ ] Accessibility labels present
