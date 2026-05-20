# APOLLO Deterministic Guarantees

## System Invariants

### Protocol Invariants

1. **Protocol Locking**
   - `INVARIANT`: Protocol must be LOCKED before screening begins
   - `ENFORCEMENT`: `ensure_protocol_locked()` in protocol_service.py
   - `BREACH`: Warning displayed, screening blocked

2. **Protocol Version Stability**
   - `INVARIANT`: Protocol version cannot change during active screening session
   - `ENFORCEMENT`: Version captured at session creation, validated on each advisory

3. **Protocol Hash**
   - `INVARIANT`: Each protocol has deterministic hash for reproducibility
   - `COMPUTATION`: MD5 of sorted criteria IDs + version string

### Advisory Invariants

4. **Advisory is Advisory Only**
   - `INVARIANT`: AI advisory cannot finalize decisions
   - `ENFORCEMENT`: Human must explicitly confirm/override/escalate
   - `BREACH`: None allowed - no autonomous decision path

5. **Grounding Validation**
   - `INVARIANT`: All advisory justifications must be grounded in source text
   - `COMPUTATION`: Word overlap ratio between justification and article
   - `ENFORCEMENT`: `grounding_strength` computed, displayed to reviewer

6. **Hallucination Detection**
   - `INVARIANT`: All advisories have hallucination risk assessed
   - `COMPUTATION`: Deterministic additive scoring (no ML, no embeddings)
   - `ENFORCEMENT`: `hallucination_risk_score` computed for all advisories

7. **Advisory Cache Determinism**
   - `INVARIANT`: Same article + protocol + stage = same advisory (cached)
   - `COMPUTATION`: MD5 hash of (article_id, protocol_version, stage)
   - `ENFORCEMENT`: advisory_cache.py uses deterministic keys

### Risk Invariants

8. **Risk Classification Determinism**
   - `INVARIANT`: Same AdvisoryResult always produces same RiskClassification
   - `COMPUTATION`: Fixed threshold rules in `compute_risk_classification()`
   - `ENFORCEMENT`: Unit tested, no random components

9. **Validation Queue Routing**
   - `INVARIANT`: Same risk classification always routes to same queue
   - `COMPUTATION`: Fixed mapping in `compute_validation_queue()`
   - `ENFORCEMENT`: No branching based on runtime state

10. **Sampling Reproducibility**
    - `INVARIANT`: Same article set + same protocol = same sample
    - `COMPUTATION`: MD5 hash-based sampling (not random.random())
    - `ENFORCEMENT`: `should_validate()` uses deterministic hash

### Workflow Invariants

11. **Index Bounds**
    - `INVARIANT`: Current index must always be within article bounds
    - `ENFORCEMENT`: `validate_session_index()` on each navigation

12. **Queue Filter Stability**
    - `INVARIANT`: Queue filter does not modify articles, only selects
    - `ENFORCEMENT`: `filter_articles_by_queue()` is read-only

13. **Review Mode Isolation**
    - `INVARIANT`: Each review mode filters independently
    - `ENFORCEMENT`: Separate filter functions per mode

### Calibration Invariants

14. **Append-Only Logging**
    - `INVARIANT`: Calibration events never modified or deleted
    - `ENFORCEMENT`: JSONL append mode in `_append_event()`

15. **Duplicate Prevention**
    - `INVARIANT`: Same event cannot be logged twice
    - `ENFORCEMENT`: Check (article_id, stage, timestamp) before append

16. **Disagreement Tracking**
    - `INVARIANT`: Every override logged with both AI and human decisions
    - `ENFORCEMENT`: `log_calibration_event()` captures both

### Session Invariants

17. **Session ID Uniqueness**
    - `INVARIANT`: Each session has unique ID
    - `COMPUTATION`: UUID v4 (acceptably unique for session scope)

18. **State Restoration**
    - `INVARIANT`: Same session state produces same UI state
    - `ENFORCEMENT`: All state derived from deterministic computations

## Non-Deterministic Components (Acknowledged)

The following components have non-deterministic aspects by design:

1. **LLM Advisory Generation**
   - LLM response may vary even with same prompt
   - MITIGATION: Ground truth validation, confidence scoring
   - NOT MITIGATED: This is a source of non-determinism we accept

2. **Retry Backoff Jitter**
   - Advisory generation uses random jitter in backoff
   - MITIGATION: Can be removed for full determinism (config option)
   - IMPACT: Low - only affects timing, not outcomes

## Determinism Verification

To verify deterministic behavior:

```python
# Test 1: Same advisory for same inputs
advisory1 = generate_advisory(article, protocol, stage)
advisory2 = generate_advisory(article, protocol, stage)
assert advisory1.cache_key == advisory2.cache_key

# Test 2: Same risk classification
risk1 = compute_risk_classification(advisory1)
risk2 = compute_risk_classification(advisory2)
assert risk1 == risk2

# Test 3: Same queue routing
queue1 = compute_validation_queue(advisory1)
queue2 = compute_validation_queue(advisory2)
assert queue1 == queue2
```

## Reproducibility Audit Trail

For research reproducibility, log:
- Protocol version hash
- Protocol criteria (full)
- Article IDs (sorted)
- LLM model version
- All calibration events
- Session start/end timestamps
- Export metadata