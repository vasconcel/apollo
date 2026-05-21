# APOLLO Replay Oracle Semantics

## Purpose

This document defines the precise replay oracle semantics for APOLLO's deterministic replay governance system. It specifies what constitutes replay parity, replay failure, and the boundaries of deterministic equivalence.

## Replay Parity Definition

Replay parity exists ONLY if ALL of the following are identical across repeated runs using the same fixture input:

| Criterion | Description | Detection Mechanism |
|-----------|-------------|-------------------|
| Checksum outputs | `compute_checksum()` returns identical SHA256 hash | Direct checksum comparison |
| Serialized deterministic fields | `_to_dict_full()` produces identical dict (excluding time-variant fields) | JSON serialization comparison |
| Navigation traversal order | `advance()`, `next_index()`, `skip_unreviewable()` produce same indices | Navigation service parity tests |
| Query outputs | `get_discussion_articles()`, `get_wl_articles()`, etc. return same counts | Query parity tests |
| Progress outputs | `get_progress()`, `get_wl_progress()`, `get_gl_progress()` return same dicts | Progress parity tests |
| Audit verification outputs | `verify_chain()` returns same `(valid, errors)` tuple | Audit parity tests |
| Replay status outputs | Session counters (included, excluded, skip, discussion) identical | Replay results comparison |
| Workflow stage ordering | `stage` field, `ec_completed`, `ic_completed` values identical | Stage comparison |
| Inclusion/exclusion/discussion counters | `included_count`, `excluded_count`, `discussion_count` identical | Counter comparison |

## Replay Failure Definition

Replay failure occurs if ANY of the following occur:

| Failure Mode | Example | Detection |
|-------------|---------|-----------|
| Checksum drift | `compute_checksum()` returns different hash for same fixture | Benchmark expectation mismatch |
| Deterministic field drift | `ec_completed` counter changes across loads | Replay output comparison |
| Replay ordering drift | `advance()` returns different index for same fixture | Navigation parity failure |
| Audit verification drift | `verify_chain()` returns different result | Audit parity failure |
| Query result drift | `get_discussion_articles()` returns different count | Query parity failure |
| Navigation drift | `get_current_article()` returns different article | Navigation parity failure |
| Workflow state drift | `stage` field has different value | Stage comparison failure |
| Corrupted fixtures silently validate | Broken audit chain passes `verify_chain()` | Corrupted fixture detection |
| Replay normalization occurs | Saved/loaded corrupted fixture becomes valid | Preserved corruption test |
| Corrupted sessions become accepted | Tampered checksum considered valid | Checksum mismatch detection |

## Timestamp Variance Rules

### Acceptable Variance

Timestamp variance is acceptable ONLY for fields already documented as intentionally time-variant:

| Field | Location | Reason |
|-------|----------|--------|
| `last_saved` | Session state | Set to `datetime.now().isoformat()` on every save |
| Audit event `timestamp` | Audit chain event | Set to `datetime.now().isoformat()` on decision creation |
| Article `ec_timestamp` | ArticleReview | Set to `datetime.now().isoformat()` on EC decision |
| Article `ic_timestamp` | ArticleReview | Set to `datetime.now().isoformat()` on IC decision |
| `created_at` (in DynamicProtocol) | Protocol creation | Set to `datetime.now().isoformat()` on construction |
| Bundle export timestamps | Bundle artifacts | Set to `datetime.now().isoformat()` on bundle creation |

### Prohibited Effects

Timestamp variance MUST NOT:
- Alter checksums unexpectedly
- Alter replay ordering
- Alter deterministic comparison fields
- Normalize corrupted fixtures

### Enforcement

Timestamp variance is isolated by:
1. Excluding time-variant fields from CHECKSUM_FIELDS where possible
2. Testing that non-deterministic timestamps do not leak into deterministic surfaces
3. Verifying that `last_saved` changes do not affect other deterministic fields

## Canonical Comparison Boundaries

### Excluded from Replay Comparison

ONLY the following are excluded:

- `last_saved` timestamp (explicitly documented as time-variant)
- Audit event `timestamp` fields (documented as time-variant)
- Article-level decision timestamps (documented as time-variant)
- `session_hash` (derives from full data which includes last_saved)

### Included in Replay Comparison (ALL other fields)

All other fields in CHECKSUM_FIELDS are replay-critical:

```
session_id, created_at, protocol_version, stage,
current_index, total_count, ec_completed, ic_completed,
included_count, excluded_count, skip_count,
discussion_count, researcher_id, schema_version,
articles (entire list), dynamic_protocol (entire dict)
```

Plus:
- `audit_chain` (all events except timestamp fields)
- `autosave_enabled`
- Article `article_id`, `title`, `abstract`, `metadata`
- Article stage decisions: `ec_stage`, `ic_stage`, `qc_stage`
- Article `final_decision`
- `protocol_hash`

## Replay Equivalence Classes

### Deterministic Equivalence

Two runs are deterministically equivalent if:
1. All replay-critical fields compare equal
2. Time-variant field changes do not affect deterministic fields
3. Checksums are identical
4. Navigation produces identical traversal
5. Query results are identical
6. Progress results are identical
7. Audit verification is identical

### Equivalent Mutation Classes (acceptable non-detection)

The following are equivalent mutations where detection is NOT required:
- Field ordering changes in dict construction (where sort_keys neutralizes them)
- Representation-preserving refactors (e.g., `dataclass.asdict()` vs manual dict)
- Adding/removing fields not in CHECKSUM_FIELDS that don't affect replay
- Formatting-only JSON changes that don't alter semantic content

## Detection Sensitivity Requirements

The replay oracle MUST detect:
1. Any change to CHECKSUM_FIELDS membership
2. Any change to serialization field values
3. Any change to audit chain content or ordering
4. Any change to navigation logic
5. Any change to query filtering semantics
6. Any change to workflow ordering or transition rules
7. Any change to checksum computation algorithm

The replay oracle SHOULD detect:
1. Addition of non-deterministic fields to deterministic serialization
2. Introduction of new time-variant fields to checksum boundary

## Fixture Classification

### Canonical Deterministic Fixtures
- Serve as replay oracle for deterministic parity
- All fields are deterministic (fixed timestamps in fixtures)
- Checksums are stable and pre-computed

### Corrupted Fixtures
- Serve as tamper-detection verification
- Corruption types: audit chain, checksum, workflow
- MUST remain corrupted permanently
- MUST fail deterministic validation every time

### Migration Fixtures
- Test backward compatibility
- Old schema versions must remain loadable
- Deterministic parity must be preserved

### Scale Fixtures
- Test deterministic behavior under load
- 1000+ articles with deterministic traversal
- Checksum stability under scale

## Cross-Run Determinism

All replay oracle tests MUST pass 3 consecutive runs with identical results.

Cross-run determinism is verified by:
1. Running the full replay corpus test suite 3 times
2. Comparing pass/fail counts per file
3. Comparing output values per test case

Any cross-run discrepancy represents a reproducibility failure.
