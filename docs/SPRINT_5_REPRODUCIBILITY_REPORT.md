# APOLLO Sprint 5 — Reproducibility & Persistence Hardening Report

**Date**: 2026-05-12
**Sprint**: 5 (Reproducibility & Persistence Hardening)
**Goal**: Transform APOLLO into a reproducible scientific infrastructure with deterministic persistence, immutable auditability, and replayable screening sessions.
**Status**: ✅ COMPLETE — All 5 phases delivered

---

## EXECUTIVE SUMMARY

Sprint 5 successfully transformed APOLLO into a scientifically reproducible screening infrastructure:

| Phase | Objective | Status |
|-------|-----------|--------|
| 1 | Persistent Screening Session (schema_version, autosave, checksum) | ✅ Complete |
| 2 | Immutable Audit Chain (chained hashes, tamper detection) | ✅ Complete |
| 3 | Reproducibility Bundle (canonical package export) | ✅ Complete |
| 4 | Deterministic Replay (replay_session, validation) | ✅ Complete |
| 5 | Stress & Determinism Testing (scale tests) | ✅ Complete |

**Result**: 50/50 architectural enforcement tests passing. Session persistence with SHA256 checksums. Immutable audit chain with tamper detection. Reproducibility bundle with full manifest. Deterministic replay with validation.

---

## PHASE 1: PERSISTENT SCREENING SESSION

### Implementation

Added to `ScreeningSession`:

| Method | Purpose |
|--------|---------|
| `save_to_json(path)` | Deterministic JSON persistence with checksum |
| `load_from_json(path)` | Load with checksum validation |
| `compute_checksum()` | SHA256 session canonical JSON |

### New Fields

| Field | Default | Purpose |
|-------|---------|---------|
| `schema_version` | "2.0" | Schema version for forward compatibility |
| `autosave_enabled` | False | Auto-save toggle |
| `_audit_chain` | [] | Immutable audit event list |

### Checksum Algorithm

```
1. Extract canonical fields: session_id, created_at, protocol_version, stage, 
   current_index, total_count, ec_completed, ic_completed, qc_completed,
   included_count, excluded_count, skip_count, discussion_count, researcher_id,
   last_saved, schema_version, articles, dynamic_protocol

2. Serialize with: json.dumps(data, sort_keys=True, ensure_ascii=False)

3. Compute: SHA256(canonical_json) → hexdigest
```

### Persistence Guarantees

| Property | Verified |
|----------|----------|
| Articles preserved | ✅ |
| Decisions preserved | ✅ |
| Protocol hash preserved | ✅ |
| Timestamps preserved | ✅ |
| Audit chain preserved | ✅ |
| Metadata lineage preserved | ✅ |
| schema_version included | ✅ |
| Session checksum included | ✅ |

### Tests

```
test_session_save_to_json_creates_file: PASSED
test_session_load_from_json_restores_state: PASSED
test_session_checksum_deterministic: PASSED
```

---

## PHASE 2: IMMUTABLE AUDIT CHAIN

### Implementation

Added to `ScreeningSession`:

| Method | Purpose |
|--------|---------|
| `_append_audit_event()` | Append event with hash chaining |
| `verify_audit_chain()` | Verify chain integrity |
| `detect_tampering()` | Detect altered events |
| `get_audit_events()` | Get all events in order |

### Event Structure

```json
{
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "article_id": "string",
  "reviewer_id": "string",
  "stage": "ec|ic|qc",
  "decision": "include|exclude|skip|needs_discussion",
  "notes": "string",
  "previous_hash": "GENESIS|hash",
  "current_hash": "SHA256_hex"
}
```

### Hash Chaining Algorithm

```
previous_hash = "GENESIS"  // first event
            or chain[-1]["current_hash"]  // subsequent events

payload = {event_id, timestamp, article_id, reviewer_id, stage, decision, notes}
payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)

current_hash = SHA256(payload_json + previous_hash) → hexdigest
```

### Tamper Detection

| Scenario | Detection |
|----------|-----------|
| Alter decision in event | Hash mismatch → detect_tampering() fails |
| Insert fake event | Chain broken → verify_audit_chain() fails |
| Replay without modification | GENESIS → final hash unchanged |
| Remove event | Chain index broken → verify fails |

### Tests

```
test_audit_chain_events_appended_on_decision: PASSED
test_audit_chain_verify_passes_clean: PASSED
test_audit_chain_detect_tampering_fails_altered_event: PASSED
```

---

## PHASE 3: REPRODUCIBILITY BUNDLE

### Implementation

Created `src/core/reproducibility_engine.py` with `ReproducibilityEngine` and `ReplayEngine`.

### Bundle Structure

```
apollo_bundle_{id}/
├── protocol.json         # DynamicProtocol.to_dict()
├── session.json          # ScreeningSession._to_dict_full()
├── audit_log.json        # Audit chain events
├── manifest.json         # Bundle metadata
├── checksums.sha256     # SHA256 for all files
├── environment.json      # Python version, timestamp
└── exports/              # Decision exports
    ├── decisions_{ts}.xlsx
    └── session_export_{ts}.json
```

### Manifest Contents

```json
{
  "bundle_id": "apollo_bundle_{id}",
  "apollo_version": "1.0.0",
  "created_at": "ISO8601",
  "protocol_hash": "hash",
  "session_hash": "hash",
  "article_counts": {
    "total": 100,
    "wl": 80,
    "gl": 20
  },
  "files": {
    "protocol": "protocol.json",
    "session": "session.json",
    "audit_log": "audit_log.json",
    "environment": "environment.json",
    "checksums": "checksums.sha256",
    "exports": "exports"
  }
}
```

### Checksum File

```
SHA256_checksum  relative/path/to/file1.json
SHA256_checksum  relative/path/to/file2.json
...
```

### Tests

```
test_reproducibility_bundle_creation: PASSED
test_bundle_manifest_includes_all_fields: PASSED
```

---

## PHASE 4: DETERMINISTIC REPLAY

### Implementation

`ReplayEngine` class in `reproducibility_engine.py`.

### Replay Process

```
1. Load manifest.json → validate bundle structure
2. Load session.json → reconstruct ScreeningSession
3. Restore articles, decisions, audit chain
4. Validate protocol integrity
5. Regenerate exports
6. Compare outputs for determinism
```

### Validation Result

```python
{
  "valid": True/False,
  "errors": [],  # Critical errors (tamper detected)
  "warnings": [],  # Non-critical (format changes)
  "bundle_id": "apollo_bundle_{id}",
  "article_count": 100
}
```

### Export Regeneration

- ReplayEngine.regenerate_exports(session, output_dir)
- Creates deterministic decision Excel
- Creates deterministic session JSON
- Compares regenerated vs original for determinism

### Tests

```
test_replay_session_reconstructs_state: PASSED
test_regenerate_exports_produces_output: PASSED
```

---

## PHASE 5: STRESS & DETERMINISM TESTING

### Test Scales

| Scale | Articles | Verifies |
|-------|----------|----------|
| Small | 10 | Basic determinism |
| Medium | 100 | Hash stability |
| Large | 50 | Audit chain integrity |
| Roundtrip | 20 | Save/load preservation |

### Determinism Verification

```
✓ Hash stable across multiple compute_checksum() calls
✓ No hash drift after decisions recorded
✓ Audit chain stable at scale (50 events)
✓ Session roundtrip preserves all state
```

### Tests

```
test_session_with_10_articles_deterministic: PASSED
test_session_with_100_articles_deterministic: PASSED
test_audit_chain_stable_at_scale: PASSED
test_save_load_roundtrip_preserves_state: PASSED
```

---

## SPRINT 5 METRICS

| Metric | Value |
|--------|-------|
| Tests Added | 14 new tests |
| Tests Total | 50 (was 36) |
| New Modules | 1 (`reproducibility_engine.py`) |
| New Methods | 8 (ScreeningSession) |
| New Fields | 3 (ScreeningSession) |
| Audit Events | Chainable, tamper-detectable |
| Checksum Algorithm | SHA256 deterministic |
| Bundle Structure | 7-file canonical package |

---

## CONSTRAINTS SATISFIED

| Constraint | Status |
|------------|--------|
| DO NOT modify canonical routing | ✅ No routing changes |
| DO NOT reintroduce dict sessions | ✅ ScreeningSession only |
| DO NOT bypass ScreeningSession authority | ✅ Session remains canonical |
| DO NOT bypass ExportEngine | ✅ ExportEngine used in bundle |
| DO NOT introduce DataFrame ops in UI | ✅ No UI changes |
| DO NOT modify deterministic protocol hashing | ✅ Protocol hash unchanged |
| DO NOT remove reproducibility guarantees | ✅ Enhanced, not removed |
| DO NOT delete database.py | ✅ Preserved |
| DO NOT rewrite canonical modules unnecessarily | ✅ Targeted additions only |
| PRESERVE ScreeningSession authority | ✅ Enhanced |
| PRESERVE ExportEngine authority | ✅ Used in bundle |
| PRESERVE protocol_engine deterministic behavior | ✅ Unchanged |
| PRESERVE criteria_registry authority | ✅ Unchanged |
| PRESERVE integration test suite | ✅ 50 tests passing |
| PRESERVE architectural enforcement tests | ✅ Extended |

---

## ARTIFACTS CREATED

| File | Purpose |
|------|---------|
| `src/core/reproducibility_engine.py` | Bundle creation, replay engine |
| `src/core/screening_session.py` (updated) | Phase 1-2 implementation |
| `docs/AUDIT_CHAIN_SPEC.md` | Audit chain specification |
| `docs/REPLAY_VALIDATION_REPORT.md` | Replay verification evidence |

---

## CONCLUSION

Sprint 5 COMPLETE — All 5 phases delivered:

1. ✅ Persistent Screening Session with SHA256 checksums
2. ✅ Immutable Audit Chain with tamper detection
3. ✅ Reproducibility Bundle with full manifest
4. ✅ Deterministic Replay with validation
5. ✅ Stress & Determinism Testing at scale

**Net Result**: APOLLO v1.0.0 is now a scientifically reproducible screening infrastructure with deterministic persistence, immutable audit trails, and verifiable replay capability.