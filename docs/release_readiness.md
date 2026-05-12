# APOLLO Release Readiness Audit

## Version: 1.0.0 (Stable Release)
**Status:** PRODUCTION READY
**Last Audit Date:** May 2024 (Updated for HITL Compliance)

---

## 1. Architecture Summary (v1.0.0)

APOLLO is a deterministic screening engine with a **Human-in-the-Loop (HITL)** architecture.

```
┌─────────────────────────────────────────────────────────────────┐
│                        APOLLO Pipeline (v1.0.0)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ATLAS Excel Input                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│   │ White        │───▶│ Exclusion    │───▶│ Inclusion    │      │
│   │ Literature   │    │ Criteria (EC)│    │ Criteria (IC)│      │
│   └──────────────┘    └──────────────┘    └──────────────┘      │
│           │                   │                   │             │
│           ▼                   ▼                   ▼             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│   │ Grey         │───▶│ EC Applied   │───▶│ IC/QC        │      │
│   │ Literature   │    │ (Title Only) │    │ [PENDING]    │      │
│   └──────────────┘    └──────────────┘    └──────────────┘      │
│                                                   │             │
│                                                   ▼             │
│   ┌──────────────┐                        ┌──────────────┐      │
│   │  Audit Log   │◀───────────────────────│ Quality      │      │
│   │  (Checksum)  │                        │ Assessment   │      │
│   └──────────────┘                        └──────────────┘      │
│                                                   │             │
│                                             Final Output        │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components Refined

| Component | Purpose | Status |
|-----------|---------|--------|
| `ATLASLoader` | Schema validation for ATLAS v2.0 | ✅ STABLE |
| `DecisionEngine` | EC → IC → QC workflow orchestration | ✅ HITL-MODIFIED |
| `AuditLogger` | Determinism via **File Content Hash** | ✅ FORENSIC-READY |
| `CalibrationUI` | Cohen's Kappa Inter-Rater Reliability | ✅ NEW (v1.0.0) |
| `MetadataUnit` | Metadata injection for missing abstracts | ✅ ROBUST |

---

## 2. Bounded Scope Definition

### APOLLO IS:
1. **Article Ingestion**: Load ATLAS Excel exports with schema enforcement.
2. **Deterministic Screening**: Hybrid automated EC + Human-led IC/QC.
3. **Inter-Rater Reliability**: Calculation of Cohen's Kappa between two independent reviewers.
4. **Grey Literature Support**: Specialized funnel for GL without abstracts (URL-driven).
5. **Auditability**: Stable reproducibility hash based on input content, not file paths.

### APOLLO IS NOT:
1. ❌ **Snowballing Execution** - Delegated to HERMES.
2. ❌ **Automatic Inclusion/Exclusion** - Humans make all final decisions.
3. ❌ **Database Persistence** - Uses stateless Session JSON for research transparency.

---

## 3. Determinism & Reproducibility Guarantees

| Guarantee | Mechanism | Status |
|-----------|-----------|--------|
| Same Content = Same Hash | SHA256 of file binary (not string path) | ✅ VERIFIED |
| Protocol Consistency | Checksum of JSON protocol definition | ✅ VERIFIED |
| Zero Divergence | Protocol Engine matches Hardcoded fallbacks | ✅ PASS |
| GL Policy Integrity | Articles pass to PENDING (no auto-skip) | ✅ PASS |

---

## 4. Audit Log Specification (v1.0.0)

Example of the new forensic-grade log:

```json
{
  "run_id": "run_20240511_153022",
  "input_file_name": "atlas_export_v2.xlsx",
  "protocol": {
    "name": "Garousi MLR Protocol",
    "version": "1.0",
    "checksum": "707ac0628abc7cf3"
  },
  "processing_stats": {
    "wl_total": 150,
    "gl_total": 45,
    "gl_pending_ic": 42,
    "duplicates_detected": 4
  },
  "determinism_hash": "a4f1e9b2c3d4e5f6", 
  "export_checksum": "f4243ea3ba279aaf"
}
```
*Note: `determinism_hash` is now invariant to file location.*

---

## 5. Known Limitations & Workarounds

| Limitation | Impact | Workaround |
|------------|--------|------------|
| Missing GL Abstracts | Automatic IC fail (Old) | **FIXED:** Now flagged as [PENDING] for manual URL review. |
| Single Reviewer UI | No real-time collab | Use **Calibration Module** to compare independent JSON sessions. |
| Path Dependency | Hash mismatch (Old) | **FIXED:** `AuditLogger` now uses binary checksum of input. |

---

## 6. Supported Workflows

1. **New Research**: Ingest ATLAS → Set Protocol → Screen (EC/IC/QC) → Export.
2. **Validation**: Load Session JSON → Resume work.
3. **Audit**: Verify `determinism_hash` against original dataset.
4. **Consensus**: Load Researcher A + Researcher B JSONs → Cohen's Kappa + Disagreement Report.

---

## 7. Release Readiness Assessment

### Overall Status: ✅ RELEASE CANDIDATE 1 (RC1)

- [x] **Methodological Correction**: GL no longer auto-excluded.
- [x] **Core Stability**: All regression and parity tests PASS.
- [x] **UI Integration**: Ingestion, Review, and Calibration views unified.
- [x] **Forensic Integrity**: Content-based hashing implemented.
- [x] **Documentation**: Schema and Bounded Contexts fully mapped.

### Recommendation
**The APOLLO engine is now methodologically sound for publication-quality Systematic Multivocal Literature Reviews.**

---
*Document Version: 1.0.0-FINAL*  
*Architect: Senior Software Architect & Research Specialist*