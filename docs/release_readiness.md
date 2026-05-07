# APOLLO Release Readiness Audit

## Version: 1.0.0 (Release Candidate)

---

## 1. Architecture Summary

APOLLO is a deterministic screening engine for systematic literature review (SLR) in Software Engineering recruitment & selection domain.

```
┌─────────────────────────────────────────────────────────────────┐
│                        APOLLO Pipeline                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ATLAS Excel Input                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│   │ White        │───▶│ Exclusion    │───▶│ Inclusion    │     │
│   │ Literature   │    │ Criteria     │    │ Criteria     │     │
│   └──────────────┘    └──────────────┘    └──────────────┘     │
│           │                                       │              │
│           ▼                                       ▼              │
│   ┌──────────────┐                        ┌──────────────┐     │
│   │ Grey         │───▶┌──────────────┐     │ Quality      │     │
│   │ Literature   │    │ EC Only      │───▶│ Criteria     │     │
│   └──────────────┘    └──────────────┘    └──────────────┘     │
│                                                │                 │
│                                                ▼                 │
│                                          Excel Output            │
│                                          ┌────────────┐          │
│                                          │ WL Sheet   │          │
│                                          │ GL Sheet   │          │
│                                          │ Seeds Sheet│          │
│                                          └────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Purpose | Location |
|-----------|---------|----------|
| `ATLASLoader` | Load and validate input Excel files | `src/core/atlas_processor.py` |
| `APOLLODecisionEngine` | Execute EC → IC → QC pipeline | `src/core/atlas_processor.py` |
| `ExclusionCriteria` | Apply EC1-EC4 rules | `src/core/atlas_processor.py` |
| `InclusionCriteria` | Apply IC1-IC3 rules | `src/core/atlas_processor.py` |
| `QualityCriteria` | Apply WL-Q1-Q4 or GL-Q1-Q4 scoring | `src/core/atlas_processor.py` |
| `ProtocolEngine` | Configurable EC/IC/QC evaluation | `src/core/protocol_engine.py` |
| `AuditLogger` | Deterministic run logging | `src/core/audit_logger.py` |

---

## 2. Bounded Scope Definition

### APOLLO IS:

1. **Article Ingestion**: Load ATLAS Excel exports (WL and GL sheets)
2. **EC/IC/QC Evaluation**: Apply deterministic exclusion, inclusion, and quality criteria
3. **Selection/Export**: Generate clean Excel output with structured decisions
4. **Traceability Preparation**: Export stable identifiers for future systems
5. **Auditability/Reproducibility**: Deterministic logging with checksums

### APOLLO IS NOT:

1. ❌ **Snowballing Execution** - Delegated to future HERMES system
2. ❌ **Citation Network Analysis** - Future HERMES responsibility
3. ❌ **ML/AI Decision Making** - Deterministic keyword-based only
4. ❌ **Multiple Reviewer Support** - Single-reviewer simulation
5. ❌ **Database Persistence** - Stateless processing
6. ❌ **Web API** - Standalone CLI/UI only
7. ❌ **PDF Extraction** - Not implemented

---

## 3. Determinism Guarantees

### Verified Guarantees

| Guarantee | Status | Evidence |
|-----------|--------|----------|
| Same input + same protocol = same output | ✅ PASS | Regression test run twice |
| Protocol parity: default == protocol | ✅ PASS | `test_protocol_parity.py` |
| EC4 duplicate detection deterministic | ✅ PASS | Global_ID-based |
| GL policy (SKIPPED) deterministic | ✅ PASS | Explicit policy |
| No randomness in decisions | ✅ PASS | Keyword-based only |

### Deterministic Components

1. **Input Processing**: Fixed schema, no random sampling
2. **EC Evaluation**: Keyword matching (no LLM for decisions)
3. **IC Evaluation**: Keyword matching (no LLM for decisions)
4. **QC Evaluation**: Keyword scoring (no LLM for decisions)
5. **Output Generation**: Deterministic column structure

---

## 4. Reproducibility Guarantees

### Verified Guarantees

| Guarantee | Status |
|-----------|--------|
| Determinism hash per run | ✅ Implemented |
| Protocol checksum tracking | ✅ Implemented |
| Input file reference in logs | ✅ Implemented |
| Execution time tracking | ✅ Implemented |
| Processing stats logging | ✅ Implemented |

### Audit Log Example

```json
{
  "run_id": "run_20260507_164152",
  "timestamp": "2026-05-07T16:41:52.120456",
  "input_file": "temp_atlas_input.xlsx",
  "protocol": {
    "name": "Default APOLLO Protocol",
    "version": "1.0",
    "checksum": "707ac0628abc7cf3"
  },
  "processing_stats": {
    "wl_total": 21,
    "wl_included": 9,
    "duplicates_detected": 1
  },
  "determinism_hash": "5a38a122428a1dd3",
  "export_checksum": "f4243ea3ba279aaf"
}
```

---

## 5. Protocol Guarantees

### Current Protocols

| Protocol | Version | Status |
|----------|---------|--------|
| Default APOLLO Protocol | 1.0 | ✅ Stable |
| Custom Protocol (JSON/YAML) | 1.0+ | ✅ Supported |

### Protocol Parity Verification

```
default_behavior == protocol(get_default_protocol())
```

All protocol evaluations must produce identical results to default behavior with zero tolerance.

### Protocol Structure

```yaml
protocol_version: "1.0"
exclusion_criteria:
  EC1: { field, operator, value, action }
  EC2: { field, operator, value, action }
  ...
inclusion_criteria:
  IC1: { field, operator, value }
  ...
quality_criteria:
  WL:
    WL-Q1: { scoring_rules }
    ...
  GL:
    GL-Q1: { scoring_rules }
    ...
  threshold: 2.0
```

---

## 6. Known Limitations

| Limitation | Impact | Workaround |
|------------|--------|------------|
| No multiple reviewer support | Cannot simulate consensus | Manual post-processing |
| No database persistence | Stateless processing | Re-process on each run |
| No PDF extraction | Cannot process full-text | Use ATLAS pre-extracted data |
| No snowballing | Limited discovery | Future HERMES system |
| No ML/AI decisions | Simpler but less nuanced | Fixed criteria only |
| Limited abstract length (<50 chars fails EC3) | Some papers excluded | Ensure sufficient abstract |

---

## 7. Intentionally Unsupported Features

### Snowballing (Critical)

APOLLO **intentionally excludes** snowballing execution:

- **Reason**: Snowballing creates unbounded exploration with non-deterministic results
- **Future**: Delegated to HERMES system (separate repository)
- **APOLLO's Role**: Export selected papers as seeds for HERMES

> "APOLLO does NOT execute snowballing. It only prepares export artifacts. Snowballing will be handled by the future HERMES system."

### Citation Analysis

- Not implemented
- Future HERMES responsibility
- APOLLO exports Global_ID for citation lookups

### Machine Learning

- Not implemented
- No LLM in decision loop
- Pure keyword-based evaluation

### Web API

- Not implemented
- Standalone CLI/Streamlit UI only

---

## 8. Supported Workflows

### Workflow 1: CLI Processing
```
python scripts/process_atlas.py input.xlsx [--no-llm]
```

### Workflow 2: Streamlit UI
```
streamlit run app.py
```

### Workflow 3: Programmatic
```python
from src.core.atlas_processor import export_apollo_selection_criteria

output = export_apollo_selection_criteria("input.xlsx")
```

### Workflow 4: Protocol-Driven
```python
from src.core.protocol_engine import get_default_protocol
from src.core.atlas_processor import APOLLODecisionEngine

protocol = get_default_protocol()
engine = APOLLODecisionEngine(protocol=protocol)
```

---

## 9. Expected Input Schema

### White Literature Sheet

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| Library | string | Yes | Source library name |
| Global_ID | string | Yes | Unique article identifier |
| Local_ID | string | Yes | Local article identifier |
| Title | string | Yes | Article title |
| Abstract | string | Yes | Article abstract (min 50 chars for WL) |
| Keywords | string | No | Article keywords |

### Grey Literature Sheet

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| Posicao | string | Yes | Position/order number |
| Title | string | Yes | Article title |
| URL | string | Yes | Source URL |
| Source_File | string | Yes | Source file name |

---

## 10. Expected Output Schema

### WL Sheet (13 columns)
```
Library, Global_ID, Local_ID, Title, Abstract, Keywords,
CIs1, CEs1, Revisor 1, CIs2, CEs2, Revisor 2, Decision
```

### GL Sheet (7 columns)
```
Posicao, Title, URL, Source_File, Revisor 1 EC, Revisor 1 IC, Decision
```

### WL Seeds for HERMES Sheet
```
Empty placeholder - future HERMES integration point
```

---

## 11. Validation Guarantees

| Validation | Behavior |
|------------|----------|
| Missing WL columns | FAILS with clear error |
| Missing GL columns | FAILS with clear error |
| Empty input | Processes (0 articles) |
| Invalid Excel | FAILS with error |

### Example Error Messages

```
ValueError: Missing required WL columns: ['Library', 'Global_ID']
ValueError: Missing required GL columns: ['Posicao', 'Title']
```

---

## 12. Audit Logging Guarantees

| Property | Guarantee |
|----------|-----------|
| Log location | `logs/apollo_run_<timestamp>.json` |
| No LLM leakage | Reasoning not logged |
| No article content | Full text not stored |
| Deterministic hash | Input + Protocol → Output |
| Checksum tracking | Export file checksum |

---

## Release Readiness Assessment

### Overall Status: ✅ READY FOR STABLE RELEASE

- [x] Architecture bounded and documented
- [x] Determinism verified
- [x] Reproducibility guaranteed
- [x] Protocol parity maintained
- [x] Input validation implemented
- [x] Audit logging functional
- [x] Snowballing explicitly excluded
- [x] All tests passing

### Risk Assessment: LOW

- No breaking changes to export schema
- Protocol system proven stable
- No hidden nondeterminism
- Clear scope boundaries

---

*Document Version: 1.0.0*  
*Last Updated: 2026-05-07*  
*APOLLO - Deterministic Screening Engine for Systematic Literature Review*