# APOLLO - Deterministic Screening Engine

<div align="center">

**APOLLO** is a deterministic screening engine for systematic literature reviews in Software Engineering.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Stable-brightgreen)

</div>

## Overview

APOLLO provides deterministic EC/IC/QC evaluation for systematic literature reviews:

- **Exclusion Criteria (EC)**: EC1-EC4 evaluation
- **Inclusion Criteria (IC)**: IC1-IC3 evaluation  
- **Quality Criteria (QC)**: WL-Q1-Q4 or GL-Q1-Q4 scoring with threshold ≥2.0

### Key Guarantees

| Guarantee | Description |
|-----------|-------------|
| **Deterministic** | Same input + same protocol = same output, every time |
| **Reproducible** | Audit logging with determinism hash |
| **Protocol-Based** | Configurable EC/IC/QC via JSON/YAML protocols |
| **Auditable** | Complete decision trail in logs |
| **Fail-Fast** | Input schema validation before processing |

### What APOLLO Is

- A deterministic screening engine (no randomness)
- Protocol-based configurable criteria
- Audit-logged processing with checksums
- Input validation with clear error messages

### What APOLLO Is NOT

- ❌ Snowballing execution (delegated to future HERMES system)
- ❌ Citation network analysis
- ❌ ML/AI decision-making
- ❌ Multi-reviewer consensus
- ❌ Database persistence
- ❌ Web API

## Quick Start

### CLI

```bash
python scripts/process_atlas.py input.xlsx
```

### Streamlit UI

```bash
streamlit run app.py
```

## Input Format

### White Literature Sheet (ATLAS Excel)

| Column | Required | Description |
|--------|----------|-------------|
| Library | Yes | Source library name |
| Global_ID | Yes | Unique article identifier |
| Local_ID | Yes | Local article identifier |
| Title | Yes | Article title |
| Abstract | Yes | Article abstract (≥50 chars for WL) |
| Keywords | No | Article keywords |

### Grey Literature Sheet

| Column | Required | Description |
|--------|----------|-------------|
| Posicao | Yes | Position/order number |
| Title | Yes | Source title |
| URL | Yes | Source URL |
| Source_File | Yes | Source file name |

## Output Format

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
Empty placeholder for future HERMES system
```

## Architecture

```
ATLAS Excel → ATLASLoader (validate) → APOLLODecisionEngine
                                                    │
                                        ┌───────────┴───────────┐
                                        ▼                       ▼
                                   EC (EC1-EC4)            EC (EC1-EC2)
                                        │                       │
                                        ▼                       ▼
                                   IC (IC1-IC3)           IC = SKIPPED
                                        │                       │
                                        ▼                       ▼
                                   QC (WL-Q1-Q4)          QC = SKIPPED
                                        │
                                        ▼
                                   Excel Export + Audit Log
```

## Documentation

| Document | Audience |
|----------|----------|
| `docs/release_readiness.md` | Release readiness |
| `docs/researcher_quickstart.md` | Researchers (non-technical) |
| `docs/developer_architecture.md` | Developers |
| `docs/versioning_strategy.md` | Version policy |
| `REPRODUCIBILITY.md` | Reproducibility guide |

## Testing

```bash
# Regression tests
python tests/test_apollo_regression.py

# Protocol parity tests  
python tests/test_protocol_parity.py
```

## Version

Current: **1.0.0** (Release Candidate)

- Protocol: 1.0
- Schema: 1.0

## License

MIT License

---

**APOLLO** - Deterministic Screening for Systematic Literature Reviews