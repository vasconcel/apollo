# APOLLO Replay Corpus — Deterministic Replay Governance & Reproducibility Benchmark

## Purpose

This corpus is a scientific reproducibility benchmark and regression oracle for APOLLO's deterministic replay infrastructure. It serves as a governance baseline for all replay-sensitive surfaces.

## Replay Semantics

Replay parity exists only if ALL of the following are identical across repeated runs:

- checksum outputs
- serialized deterministic fields
- navigation traversal order
- query outputs
- progress outputs
- audit verification outputs
- replay status outputs
- workflow stage ordering
- inclusion/exclusion/discussion counters

Timestamp variance is acceptable ONLY for fields documented as intentionally time-variant (e.g., `last_saved`, audit event timestamps). Timestamp variance must NOT alter checksums, replay ordering, or deterministic comparison fields.

## Benchmark Governance

Files under `expected/` are canonical replay oracle artifacts.

### Rules

1. Expected benchmark artifacts MUST NOT be regenerated unless explicitly authorized.
2. No silent updates permitted.
3. No auto-rewrite logic permitted.
4. Any benchmark update MUST explain WHY the oracle changed, WHAT deterministic property changed, justify compatibility impact, and document replay implications.
5. Fixtures must NOT be modified casually.
6. Fixture modifications require: explicit rationale, replay impact analysis, determinism impact analysis, benchmark update justification, backward compatibility analysis.

## Corruption Taxonomy

Corrupted fixtures remain corrupted permanently. They serve as tamper-detection verification assets.

| Fixture | Corruption Type | Behavior |
|---------|----------------|----------|
| `corrupted/broken_audit_chain.json` | Audit corruption | Hash mismatch in audit chain; `verify_chain()` returns False |
| `corrupted/tampered_checksum.json` | Checksum corruption | `session_checksum` does not match computed checksum |
| `corrupted/invalid_stage_transition.json` | Workflow corruption | Stage is `qc` but no EC/IC decisions have been made |

Corrupted fixtures MUST:
- remain corrupted
- fail deterministically
- fail reproducibly
- never silently normalize

## Replay Oracle Semantics

### Canonical Fixtures

| Fixture | Purpose | Deterministic Guarantees |
|---------|---------|-------------------------|
| `sessions/minimal_session.json` | Simplest valid session | All fields deterministic; empty audit chain |
| `sessions/ec_completed.json` | EC stage fully completed | Full EC decision audit trail; protocol attached |
| `sessions/ic_completed.json` | EC+IC stages completed | Multi-stage decisions; 7-event audit chain |
| `sessions/discussion_heavy.json` | Many discussion decisions | 6 of 8 articles marked needs_discussion |

## Regeneration Policy

Fixture regeneration is forbidden unless:
- explicitly requested
- benchmark drift is intentionally approved
- replay semantics intentionally evolve under governance review

Automatic expectation regeneration is prohibited.

## Directory Structure

```
tests/replay_corpus/
├── sessions/          # Canonical deterministic fixtures
├── corrupted/         # Intentionally corrupted fixtures
├── migrations/        # Legacy schema compatibility fixtures
├── scale/             # Large-scale determinism benchmark fixtures
├── compatibility/     # Serialization compatibility fixtures
├── expected/          # Canonical benchmark expectations
└── README.md          # This file
```

## Deterministic Guarantees

The following system properties are protected:

- deterministic replay semantics
- advisory isolation
- immutable protocol semantics
- audit-chain continuity
- replay reproducibility
- serialization ordering
- checksum stability
- EC → IC → QC workflow ordering
- human-final-authority semantics
- deterministic traversal ordering
- save/load parity semantics
- replay oracle consistency
