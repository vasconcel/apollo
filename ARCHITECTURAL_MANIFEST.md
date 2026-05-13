# APOLLO Architectural Manifest

**Version:** 2.0.0
**Date:** 2026-05-13
**Philosophy:** Deterministic Screening Engine for Systematic Literature Reviews

---

## 1. Core Design Principles

- **Single-User Desktop Instrument**: No multi-user, no authentication, no REST API
- **Session-Driven Architecture**: JSON session files are the single source of truth
- **Forensic Terminal Aesthetic**: Research operations console UI
- **Human-in-the-Loop**: Researcher controls every screening decision
- **Deterministic Reproducibility**: Same protocol + same input = same output

---

## 2. Active Modules

### UI Layer (`src/ui/`)
| Module | Purpose |
|--------|---------|
| `app.py` | Entry point - Streamlit main navigation |
| `protocol_view.py` | Protocol Configuration (EC/IC/QC criteria) |
| `ec_screening_view.py` | Exclusion Criteria (Stage 1) |
| `ic_screening_view.py` | Inclusion Criteria (Stage 2) |
| `qc_assessment_view.py` | Quality Assessment (Stage 3) |
| `export_view.py` | Exports & Audit (Excel + JSON) |
| `calibration_view.py` | Inter-Rater Reliability (Cohen's Kappa) |
| `ingestion_view.py` | ATLAS Excel file upload |

### Core Engine (`src/core/`)
| Module | Purpose |
|--------|---------|
| `screening_session.py` | **Sole persistence** - JSON session state |
| `export_engine.py` | Excel export with xlsxwriter styling |
| `llm_assistant.py` | AI advisory (lazy-loaded, advisory-only) |
| `dynamic_protocol.py` | Protocol state machine (Draft → Locked) |
| `calibration_engine.py` | Cohen's Kappa calculation |
| `atlas_processor.py` | ATLAS Excel parsing (WL/GL sheets) |

---

## 3. Persistence Architecture

**Single Source of Truth:** JSON Session Files (`sessions/` directory)

```
sessions/
├── session_<uuid>.json    # Full session state
└── ...
```

**Session Contents:**
- `session_id`: Unique identifier
- `protocol_version`: Locked protocol version
- `articles[]`: Article records with EC/IC/QC decisions
- `researcher_id`: Single researcher (no multi-user)
- `stage`: Current screening stage (ec/ic/qc)
- `ec_completed`, `ic_completed`, `qc_completed`: Counters

**No Database:** `src/core/database.py` is orphaned and not imported anywhere.

---

## 4. Purged Components

The following have been removed (Sprint 9.0):

- ❌ `backend/` folder (FastAPI, JWT, auth)
- ❌ `src/ui/api_client.py` (orphaned REST client)
- ❌ Multi-user role logic
- ❌ Article assignment to users
- ❌ `src/ui/modules/planning_view.py` (orphaned)
- ❌ `src/ui/modules/overview_view.py` (orphaned)

---

## 5. Dependencies

### Required
- `streamlit` - UI framework
- `pandas` - Data handling
- `openpyxl` / `xlsxwriter` - Excel exports
- `python-dotenv` - Environment config

### Removed
- `sqlalchemy` - Not used
- `fastapi` - Decommissioned
- `jose` (JWT) - Decommissioned
- `passlib` - Decommissioned

---

## 6. Navigation Flow

```
app.py (Entry)
├── Protocol Configuration
│   └── Define EC/IC/QC criteria → Lock Protocol
├── EC Screening
│   └── Upload ATLAS → Screen by EC codes → Export
├── IC Screening
│   └── Auto-filter: only EC-passed papers → Screen by IC codes
├── Inter-Rater Calibration
│   └── Load 2 JSON sessions → Compute Cohen's Kappa
└── Exports & Audit
    └── PRISMA counts → Excel download → Audit JSON
```

---

## 7. File Cleanup Status

- ✅ No `temp_*.xlsx` files in root
- ✅ Test outputs only in `tests/` folder
- ✅ Ingestion cleanup implemented (finally block)
- ✅ No __pycache__ in critical paths

---

## 8. Verification Commands

```bash
# Verify no database imports
grep -r "from src.core.database" src/

# Verify no backend references
grep -r "backend" src/

# Verify session-only persistence
grep -r "session.save\|ScreeningSession" src/

# Run app
streamlit run app.py
```

---

**End of Manifest**