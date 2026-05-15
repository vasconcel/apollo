# APOLLO v1.0.0 Replay Determinism Root Cause Analysis

**Date:** 2026-05-14
**Status:** Root Cause Identified
**Issue:** Replay checksums differ across runs

---

## Executive Summary

The non-determinism in replay checksums originates from **session state creation** - specifically the `last_saved` field being set to `datetime.now().isoformat()` during `record_decision()`. Each fresh session creation gets a different timestamp, resulting in different checksums across runs, even though original and replay within each run are identical.

---

## Test Results

### Observed Behavior

```
Replay checksums across 3 runs:
  Run #1: 0d42656e5fd6c82ba9c075956f645b68938a010c135230153382660fa5af1eba
  Run #2: f85707e2ca5180b7565be4c02f7ff8507efb8878fb42fd2499be982a6d4477fe
  Run #3: ba1ad45aadba7d613c84733692bbb90dca2729b24ed46f937a19e07d6999cb25

All identical: False
```

### Within-Run Comparison (Original vs Replay)

| Run | Original Checksum | Replay Checksum | Match |
|-----|-------------------|-----------------|-------|
| #1  | 0d42656e5fd6c82... | 0d42656e5fd6c82... | YES |
| #2  | f85707e2ca5180... | f85707e2ca5180... | YES |
| #3  | ba1ad45aadba7d... | ba1ad45aadba7d... | YES |

**Finding:** Within each run, original and replay checksums MATCH perfectly. The issue is cross-run determinism.

---

## Field-Level Analysis

### 1. Primary Non-Deterministic Field: `last_saved`

| Attribute | Value |
|-----------|-------|
| **Field Path** | `ScreeningSession.last_saved` |
| **Original Value** | `2026-05-14T13:54:35.764922` (Run 1), `2026-05-14T13:54:36.394148` (Run 2), etc. |
| **Replay Value** | Same as original (restored from bundle) |
| **Why It Changes** | Set by `record_decision()` at line 434 in `screening_session.py` using `datetime.now().isoformat()` |
| **In Checksum** | YES - included in `fields_for_checksum` at line 880-886 |
| **Determinism Severity** | **HIGH** - causes cross-run checksum variance |

### 2. Bundle Metadata Timestamp Fields (Not in Checksum)

| Field Path | Source Location | Value | In Checksum |
|------------|-----------------|-------|--------------|
| `bundle_export_timestamp` | `reproducibility_engine.py:147` | `2026-05-14T13:54:35.770170` | NO |
| `created_at` (bundle) | `reproducibility_engine.py:111` | `datetime.now().isoformat()` | NO |
| `manifest.created_at` | `reproducibility_engine.py:229` | `datetime.now().isoformat()` | NO |
| `manifest.export_timestamp` | `reproducibility_engine.py:245` | `datetime.now().isoformat()` | NO |
| `environment.export_timestamp` | `reproducibility_engine.py:177` | `datetime.now().isoformat()` | NO |
| `protocol.bundle_export_timestamp` | `reproducibility_engine.py:135` | `datetime.now().isoformat()` | NO |
| `audit_log.exported_at` | `reproducibility_engine.py:159` | `datetime.now().isoformat()` | NO |

### 3. Article Timestamp Fields

| Field Path | Source Location | Original Value | Replay Value |
|------------|-----------------|----------------|---------------|
| `ArticleReview.ec_timestamp` | `screening_session.py:410` | `2026-05-14T13:54:35.764922` | `2026-05-14T13:54:35.764922` |
| `ArticleReview.ic_timestamp` | `screening_session.py:420` | (set when IC decision made) | (same) |
| `ArticleReview.qc_timestamp` | (similar pattern) | (set when QC decision made) | (same) |

**Finding:** Article timestamps ARE included in serialization (via `ArticleReview.to_dict()`) but are deterministic within session context.

### 4. Audit Chain Fields

| Field Path | Source Location | Behavior |
|------------|-----------------|-----------|
| `event_id` | `screening_session.py:444` | `str(uuid.uuid4())` - NEW each run |
| `timestamp` | `screening_session.py:445` | `datetime.now().isoformat()` - DIFFERENT each run |
| `current_hash` | `screening_session.py:454-456` | Computed from payload including timestamp |

**CRITICAL FINDING:** Audit chain is NOT included in session checksum (not in `fields_for_checksum`), but more importantly...

### 5. Audit Chain NOT Restored During Replay

| Issue | Details |
|-------|---------|
| **Export** | `ReproducibilityEngine._export_session()` calls `_to_dict_full()` which does NOT include `audit_chain` |
| **Storage** | Audit chain is written to separate `audit_log.json` (line 162) |
| **Restore** | `ReplayEngine.replay_session()` only reads `session.json` (line 305), not `audit_log.json` |
| **Result** | Replayed session has `audit_chain = []` (empty) |

**Severity:** HIGH - Audit chain data is lost during replay, violating reproducibility requirements.

---

## Root Cause Chain

```
replay_check.py loop
    │
    ▼
ScreeningSession() created with fixed created_at='2026-05-14T10:00:00'
    │
    ▼
session.record_decision('include')
    │
    ├──► ArticleReview.ec_timestamp = datetime.now().isoformat()
    │        ▲
    │        └── Different each run
    │
    └──► session.last_saved = datetime.now().isoformat()  (line 434)
             ▲
             └── Different each run (PRIMARY CAUSE)
             │
             ▼
        session._append_audit_event()
             │
             ├──► event_id = str(uuid.uuid4())  (different each run)
             ├──► timestamp = datetime.now().isoformat()  (different each run)
             └──► current_hash = sha256(payload + previous_hash)
                                               ▲
                                               └── Depends on timestamp
             │
             ▼
        create_reproducibility_bundle(session)
             │
             ├──► session.json written with last_saved (preserved)
             └──► audit_log.json written separately (but NOT read during replay)
             │
             ▼
        ReplayEngine.replay_session(bundle_path)
             │
             └──► session = ScreeningSession(...) with last_saved from bundle
                  │
                  └──► replayed.compute_checksum()
                       │
                       └──► Uses last_saved which differs per run
```

---

## Origin of Nondeterminism

### Source A: Bundle Creation - NOT PRIMARY CAUSE
- Multiple timestamp fields added to bundle metadata
- These fields are NOT included in session checksum
- **Verdict:** Not causing the checksum difference

### Source B: Replay Loading - NOT CAUSE  
- Replay correctly restores `last_saved` from bundle
- Within-run original and replay match perfectly
- **Verdict:** Replay is faithful to bundle content

### Source C: Checksum Computation - NOT CAUSE
- Checksum correctly includes `last_saved`
- The field IS part of canonical checksum inputs
- **Verdict:** Checksum computation is correct

### Source D: Audit Restoration - NOT CAUSE (but separate bug)
- Audit chain not restored (different bug)
- Not included in checksum anyway

### Source E: Transient Runtime State - **PRIMARY CAUSE**
- `ScreeningSession.last_saved` is set by `record_decision()` using `datetime.now()`
- Each fresh session gets a different timestamp
- This timestamp is included in checksum computation
- **Verdict:** TRUE ROOT CAUSE

---

## Exact Differing Fields Summary

| # | Field | Original Value | Replay Value | Why Changes | Severity |
|---|-------|----------------|--------------|-------------|----------|
| 1 | `session.last_saved` | `2026-05-14T13:54:35.764922` (Run 1) | Same (restored) | Set by `record_decision()` with `datetime.now()` | HIGH |
| 2 | `session.audit_chain` | 1 event | 0 events | NOT exported in session.json, NOT restored from audit_log.json | CRITICAL |

---

## Field Not in Checksum But Lost

| Field | Original | Replay | Why Lost |
|-------|----------|--------|----------|
| `session._audit_chain` | 1 event | 0 events | `_to_dict_full()` doesn't include it; ReplayEngine doesn't read audit_log.json |

---

## Determinism Severity Assessment

| Aspect | Severity | Notes |
|--------|----------|-------|
| Cross-run checksums | **HIGH** | Each fresh session has different `last_saved` |
| Within-run original vs replay | **NONE** | Perfect match |
| Audit chain preservation | **CRITICAL** | Completely lost during replay |
| Article ordering | **NONE** | Preserved correctly |
| Decision ordering | **NONE** | Preserved via article state |
| Chained hashes | **N/A** | Not in checksum, also lost in replay |

---

## Minimal Safe Fix Strategy

### Fix 1: Remove `last_saved` from Checksum (Priority: HIGH)

**Location:** `src/core/screening_session.py`, lines 880-886

**Current:**
```python
fields_for_checksum = [
    "session_id", "created_at", "protocol_version", "stage",
    "current_index", "total_count", "ec_completed", "ic_completed",
    "included_count", "excluded_count", "skip_count",
    "discussion_count", "researcher_id", "last_saved", "schema_version",
    "articles", "dynamic_protocol"
]
```

**Proposed:**
```python
fields_for_checksum = [
    "session_id", "created_at", "protocol_version", "stage",
    "current_index", "total_count", "ec_completed", "ic_completed",
    "included_count", "excluded_count", "skip_count",
    "discussion_count", "researcher_id", "schema_version",
    "articles", "dynamic_protocol"
]
```

**Rationale:** `last_saved` is runtime metadata, not intrinsic session state. It represents "when" the session was last saved, not "what" the session contains.

**Risk:** LOW - Only affects checksum computation, not session functionality.

---

### Fix 2: Exclude Runtime Timestamps from Article State (Priority: MEDIUM)

**Location:** `src/core/screening_session.py`, lines 404, 410, 420

**Current:**
```python
timestamp = datetime.now().isoformat()
article.ec_timestamp = timestamp
```

**Proposed:** Either:
- Option A: Use a deterministic placeholder (e.g., "EC_TIMESTAMP")
- Option B: Store relative time (offset from session.created_at)
- Option C: Exclude from serialization but keep in runtime

**Rationale:** Timestamps are useful for auditing but not for deterministic replay. Consider whether they're truly required for scientific reproducibility.

**Risk:** MEDIUM - May affect timestamp-based auditing features.

---

### Fix 3: Include Audit Chain in Session Export (Priority: CRITICAL)

**Location:** `src/core/screening_session.py`, `_to_dict_full()` method (around line 892)

**Current:**
```python
def _to_dict_full(self) -> Dict:
    return {
        ...
        "articles": [a.to_dict() for a in self.articles],
        "dynamic_protocol": self.dynamic_protocol,
    }
```

**Proposed:**
```python
def _to_dict_full(self) -> Dict:
    return {
        ...
        "articles": [a.to_dict() for a in self.articles],
        "dynamic_protocol": self.dynamic_protocol,
        "audit_chain": self._audit_chain,  # ADD THIS
    }
```

**Risk:** MEDIUM - Increases bundle size; ensure ReplayEngine reads it correctly.

---

### Fix 4: Ensure ReplayEngine Reads Audit Chain (Priority: CRITICAL)

**Location:** `src/core/reproducibility_engine.py`, `replay_session()` method (around line 335)

**Current:**
```python
session._audit_chain = session_data.get("audit_chain", [])
```

**Verify:** This should work once Fix 3 is applied (session_data will contain audit_chain).

**Alternative:** If audit_chain stored separately in audit_log.json:
```python
audit_log_path = os.path.join(bundle_path, "audit_log.json")
if os.path.exists(audit_log_path):
    with open(audit_log_path, "r", encoding="utf-8") as f:
        audit_data = json.load(f)
        session._audit_chain = audit_data.get("events", [])
```

**Risk:** LOW - Proper restoration of existing data.

---

### Fix 5: Fix ReproducibilityEngine Bundle ID (Priority: LOW)

**Location:** `src/core/reproducibility_engine.py`, line 86-88

**Current:**
```python
bundle_id = hashlib.sha256(
    f"{self.session.session_id}{datetime.now().isoformat()}".encode()
).hexdigest()[:12]
```

**Proposed:**
```python
bundle_id = hashlib.sha256(
    f"{self.session.session_id}{self.session.created_at}".encode()
).hexdigest()[:12]
```

**Rationale:** Bundle ID should be deterministic based on session identity, not current time.

**Risk:** LOW - Cosmetic change for bundle directory naming.

---

## Verification Checklist

After fixes are applied, verify:

- [ ] Cross-run replay checksums are identical
- [ ] Original and replay within same run still match
- [ ] Audit chain is preserved in replay
- [ ] Article ordering unchanged
- [ ] Decision data preserved
- [ ] Protocol state preserved

---

## Conclusion

The deterministic replay issue in APOLLO v1.0.0 has been isolated to:

1. **Primary Cause:** `last_saved` field set to current timestamp during `record_decision()`, causing cross-run checksum variance
2. **Secondary Issue:** Audit chain not preserved during replay (separate bug)

The fixes are straightforward and low-risk. The core session data (articles, decisions, protocol) is correctly serialized and restored - only the runtime metadata and audit chain need adjustment.