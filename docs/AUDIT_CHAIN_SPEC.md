# APOLLO Audit Chain Specification

**Date**: 2026-05-12
**Sprint**: 5 (Phase 2: Immutable Audit Chain)
**Status**: ✅ IMPLEMENTED

---

## OVERVIEW

The audit chain provides immutable, tamper-detectable records of all screening decisions. Every decision event is cryptographically linked to the previous event, creating a verifiable chain of custody.

---

## EVENT STRUCTURE

### Raw Event (Python Dict)

```python
{
    "event_id": "550e8400-e29b-41d4-a716-446655440000",  # UUID
    "timestamp": "2026-05-12T14:30:00.123456",           # ISO8601
    "article_id": "G-001",                               # Article global ID
    "reviewer_id": "researcher_1",                      # Researcher identifier
    "stage": "ec",                                      # ec|ic|qc
    "decision": "include",                              # include|exclude|skip|needs_discussion
    "notes": "Paper addresses SE R&S with empirical context",  # Researcher notes
    "previous_hash": "GENESIS",                         # Chain link (or hash)
    "current_hash": "a3f8c2d1e9b7..."                    # SHA256 hexdigest
}
```

### Event Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_id | str (UUID) | Yes | Unique event identifier |
| timestamp | str (ISO8601) | Yes | Decision timestamp |
| article_id | str | Yes | Article identifier |
| reviewer_id | str | Yes | Researcher identifier |
| stage | str | Yes | Screening stage (ec/ic/qc) |
| decision | str | Yes | Decision value |
| notes | str | No | Researcher notes/reasoning |
| previous_hash | str | Yes | Hash of previous event ("GENESIS" for first) |
| current_hash | str | Yes | SHA256(payload + previous_hash) |

---

## HASH CHAINING ALGORITHM

### First Event (Genesis)

```
previous_hash = "GENESIS"

payload = {event_id, timestamp, article_id, reviewer_id, stage, decision, notes}
payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)

current_hash = SHA256(payload_json + "GENESIS") → hexdigest
```

### Subsequent Events

```
previous_hash = chain[-1]["current_hash"]

payload = {event_id, timestamp, article_id, reviewer_id, stage, decision, notes}
payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)

current_hash = SHA256(payload_json + previous_hash) → hexdigest
```

### Key Properties

1. **Immutable**: Cannot modify past events without breaking chain
2. **Linked**: Each event references previous, creating traceable history
3. **Detectable**: Tampering breaks hash verification
4. **Reproducible**: Same events produce same hashes (deterministic)

---

## VERIFICATION

### verify_audit_chain()

```python
def verify_audit_chain(self) -> tuple:
    """
    Verify audit chain integrity.
    
    Returns:
        Tuple of (is_valid: bool, errors: list)
    """
```

**Algorithm**:
```
1. For each event in chain (index 0 to N-1):
   a. Check previous_hash matches chain[index-1].current_hash
      (or "GENESIS" for first event)
   b. Recompute payload hash
   c. Compare with current_hash
   d. If mismatch → add to errors

2. Return (len(errors) == 0, errors)
```

### detect_tampering()

```python
def detect_tampering(self) -> tuple:
    """
    Detect tampering in audit chain.
    
    Returns:
        Tuple of (is_clean: bool, tampered_events: list)
    """
```

**Algorithm**:
```
1. Call verify_audit_chain()
2. If valid → return (True, [])
3. If invalid → extract event_ids with hash mismatches
4. Return (False, [event_ids with mismatches])
```

---

## INTEGRATION POINTS

### ScreeningSession.record_decision()

Every call to `record_decision()` automatically appends an audit event:

```python
def record_decision(self, decision: str, notes: str = "", ...) -> bool:
    # ... existing logic ...
    
    # NEW: Append audit event
    self._append_audit_event(article, decision, notes, stage)
    return True

def _append_audit_event(self, article, decision, notes, stage) -> None:
    previous_hash = self._audit_chain[-1]["current_hash"] if self._audit_chain else "GENESIS"
    
    event_payload = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "article_id": article.article_id,
        "reviewer_id": self.researcher_id,
        "stage": stage,
        "decision": decision,
        "notes": notes,
    }
    
    payload_json = json.dumps(event_payload, sort_keys=True, ensure_ascii=False)
    current_hash = hashlib.sha256(
        (payload_json + previous_hash).encode()
    ).hexdigest()
    
    event = {
        **event_payload,
        "previous_hash": previous_hash,
        "current_hash": current_hash
    }
    
    self._audit_chain.append(event)
```

### Persistence

Audit chain is serialized with session:

```python
# In save_to_json()
data["audit_chain"] = self._audit_chain

# In load_from_json()
self._audit_chain = data.get("audit_chain", [])
```

---

## SECURITY PROPERTIES

| Property | Mechanism | Protection |
|----------|-----------|------------|
| Integrity | Hash chaining | Tamper detection |
| Non-repudiation | reviewer_id + timestamp | Accountability |
| Traceability | previous_hash links | Complete history |
| Determinism | Canonical JSON | Reproducible verification |

---

## LIMITATIONS

1. **No encryption**: Audit chain is plaintext (audit trail, not confidentiality)
2. **No revocation**: Cannot "undo" a decision — only add correction events
3. **Time dependency**: Event timestamps use system clock (not blockchain)

---

## TEST CASES

| Test | Scenario | Expected |
|------|----------|----------|
| test_audit_chain_events_appended_on_decision | record_decision() called | 1 event appended |
| test_audit_chain_verify_passes_clean | Unmodified chain | is_valid = True |
| test_audit_chain_detect_tampering_fails_altered_event | Alter decision field | is_clean = False |

---

## USAGE EXAMPLE

```python
from src.core.screening_session import ScreeningSession, ArticleReview

# Create session and record decisions
session = ScreeningSession("test-session", "2026-05-12T00:00:00", "1.0")
session.articles.append(ArticleReview(
    article_id="TEST-001",
    title="Test Paper",
    abstract="Abstract",
    metadata={"literature_type": "WL"}
))

session.record_decision("include")

# Verify chain
is_valid, errors = session.verify_audit_chain()
print(f"Chain valid: {is_valid}")

# Check for tampering
is_clean, tampered = session.detect_tampering()
print(f"No tampering: {is_clean}")

# Get all events
events = session.get_audit_events()
print(f"Total events: {len(events)}")
```