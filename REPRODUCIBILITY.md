# APOLLO Reproducibility Manifest

## For Researchers - Ensuring Reproducible Systematic Reviews

---

## 1. Reproducibility Philosophy

APOLLO is designed as a **deterministic screening engine**. This means:

```
SAME INPUT + SAME PROTOCOL = SAME OUTPUT (EVERY TIME)
```

This guarantee is fundamental to APOLLO's scientific validity.

---

## 2. Deterministic Assumptions

### What APOLLO Guarantees is Deterministic

| Component | Deterministic? | Evidence |
|-----------|----------------|-----------|
| Input processing | ✅ Yes | Fixed schema, no random sampling |
| EC evaluation | ✅ Yes | Keyword matching, no randomness |
| IC evaluation | ✅ Yes | Keyword matching, no randomness |
| QC scoring | ✅ Yes | Keyword scoring, no randomness |
| Output generation | ✅ Yes | Fixed column structure |
| Duplicate detection | ✅ Yes | Global_ID-based, order-independent |
| GL policy | ✅ Yes | Explicit SKIPPED policy |

### What APOLLO Explicitly Does NOT Use

| Component | Why Excluded |
|-----------|--------------|
| Large Language Models (LLM) for decisions | Non-deterministic |
| Random sampling | Breaks reproducibility |
| Time-dependent logic | Breaks reproducibility |
| External API calls | May change over time |
| Mutable global state | Breaks reproducibility |

---

## 3. Supported Environments

### Python Version

- **Minimum**: Python 3.10
- **Recommended**: Python 3.11 or 3.12
- **Tested**: Python 3.14

### Required Dependencies

```
pandas>=2.0.0
openpyxl>=3.1.0
```

### Operating Systems

| OS | Status |
|----|--------|
| Windows | ✅ Tested |
| macOS | ✅ Compatible |
| Linux | ✅ Compatible |

---

## 4. Dependency Locking Recommendations

### For Reproducible Results

We **strongly recommend** locking dependencies:

```bash
# Create requirements.txt with locked versions
pip freeze > requirements.locked.txt

# Install from locked file
pip install -r requirements.locked.txt
```

### Version Pinning Example

```
pandas==2.2.0
openpyxl==3.1.2
```

---

## 5. Protocol Checksum Philosophy

### Why Checksums Matter

Each protocol has a SHA256 checksum:

```python
protocol_json = json.dumps(protocol, sort_keys=True)
checksum = sha256(protocol_json.encode()).hexdigest()[:16]
```

This ensures:
- Protocol file hasn't been tampered with
- Same protocol = same checksum
- Verification possible without sharing full protocol

### Protocol Version vs Checksum

| Field | Purpose |
|-------|---------|
| Protocol Version | Human-readable version (e.g., "1.0") |
| Protocol Checksum | Machine-verifiable integrity |

---

## 6. Audit Philosophy

### What APOLLO Logs

| Logged | NOT Logged |
|--------|------------|
| Input file name | Full article text |
| Protocol info | LLM reasoning |
| Processing stats | User-identifiable info |
| Determinism hash | Temporary variables |
| Execution duration | Debug details |
| Checksums | Internal state |

### Why This Matters

- **Auditability**: Can trace each run
- **Privacy**: No article content stored
- **Reproducibility**: Can verify determinism

---

## 7. Reproducibility Checklist

Before publishing results from APOLLO:

### Input Documentation

- [ ] I kept the original ATLAS Excel input file
- [ ] I recorded the file name and path
- [ ] I noted the file size and row count

### APOLLO Execution

- [ ] I noted the APOLLO version used (check with `--version` or startup message)
- [ ] I noted the protocol version used (check audit log)
- [ ] I recorded the execution date and time

### Output Verification

- [ ] I saved the output Excel file
- [ ] I verified the output exists and has data
- [ ] I noted the deterministic hash from audit log

### Re-run Verification

- [ ] I re-ran APOLLO with the same input
- [ ] I verified the same results (determinism check)
- [ ] I compared the determinism hashes

---

## 8. Validation Checklist Before Publication

### Technical Validation

- [ ] Ran regression tests (`python tests/test_apollo_regression.py`)
- [ ] Ran protocol parity tests (`python tests/test_protocol_parity.py`)
- [ ] Verified deterministic hash unchanged on re-run

### Documentation Validation

- [ ] Documented input file used
- [ ] Documented APOLLO version
- [ ] Documented protocol version
- [ ] Documented any custom protocol settings

### Output Validation

- [ ] Verified output file schema matches expected format
- [ ] Verified inclusion/exclusion counts are reasonable
- [ ] Verified QC scores distribution is documented

---

## 9. Reproducibility Verification Commands

### Verify Version

```bash
python scripts/process_atlas.py --version
```

### Run Full Test Suite

```bash
python tests/test_apollo_regression.py
python tests/test_protocol_parity.py
python tests/test_protocol_layer.py
```

### Check Audit Log

```bash
# Find latest audit log
ls -t logs/apollo_run_*.json | head -1

# View audit log
cat logs/apollo_run_20260507_164152.json
```

### Verify Determinism

```bash
# Run twice and compare hashes
python scripts/process_atlas.py input.xlsx
# Note determinism hash from output

# Run again
python scripts/process_atlas.py input.xlsx
# Verify hash matches
```

---

## 10. Known Factors That Could Affect Reproducibility

### Could Change (Document These)

| Factor | Impact | Mitigation |
|--------|--------|------------|
| Python version | Low (same behavior expected) | Document Python version |
| pandas version | Low (API stable) | Document pandas version |
| Input file modifications | HIGH (different results) | Never modify input |
| Protocol modifications | HIGH (different results) | Never modify protocol |

### Cannot Change (Guaranteed)

| Factor | Why |
|--------|-----|
| Same input file | Same Global_IDs, same data |
| Same protocol | Same keywords, same logic |
| Same APOLLO version | Same deterministic code |

---

## 11. Sharing Protocols Safely

### For Collaboration

When sharing protocols with collaborators:

1. **Export Protocol**: Copy the JSON/YAML file
2. **Verify Checksum**: Calculate and share checksum
3. **Document Version**: Note protocol version
4. **Test Parity**: Verify against default protocol

### Example Protocol Sharing

```
# Protocol file: my_protocol.yaml
# Version: 1.0
# Checksum: a1b2c3d4e5f6
# 
# To verify:
# python -c "from src.core.protocol_engine import load_protocol; p = load_protocol('my_protocol.yaml'); from src.core.audit_logger import AuditLogger; print(AuditLogger._compute_protocol_checksum(p))"
```

---

## 12. Reproducibility Best Practices

### For Individual Researchers

1. **Always keep input files** - Never modify after processing
2. **Keep audit logs** - Store alongside output
3. **Document versions** - Note APOLLO and protocol versions
4. **Test determinism** - Re-run at least once to verify

### For Collaborative Research

1. **Share protocols** - Use checksums for verification
2. **Share audit logs** - Show reproducibility proof
3. **Document environment** - Python and dependency versions
4. **Standardize input** - Use same ATLAS template

### For Publication

1. **Include APOLLO version** - In methods section
2. **Include protocol version** - Note if using custom protocol
3. **Include deterministic hash** - Can use as run identifier
4. **Reference documentation** - Point to APOLLO docs

---

## 13. Contact and Support

For reproducibility questions:
- Review: `docs/researcher_quickstart.md`
- Review: `docs/developer_architecture.md`
- Review: `docs/release_readiness.md`

---

## Summary

APOLLO guarantees reproducibility through:

1. ✅ Deterministic evaluation (no randomness)
2. ✅ Protocol checksums (verify integrity)
3. ✅ Audit logging (complete traceability)
4. ✅ Version tracking (document environment)
5. ✅ Schema validation (fail-fast errors)

**Your responsibility**: Document input, versions, and verify re-runs

---

*Document Version: 1.0.0*  
*APOLLO Reproducibility Manifest - For Scientific Publication*