# APOLLO Versioning Strategy

## Version 1.0.0 - Semantic Versioning

---

## 1. Semantic Versioning Policy

APOLLO uses **Semantic Versioning 2.0.0** (semver):

```
MAJOR.MINOR.PATCH
```

### Version Number Definition

| Version Type | When to Increment | Example |
|--------------|-------------------|---------|
| **MAJOR** | Breaking changes to API, schema, or behavior | 1.0.0 → 2.0.0 |
| **MINOR** | New features, backward-compatible | 1.0.0 → 1.1.0 |
| **PATCH** | Bug fixes, no behavioral changes | 1.0.0 → 1.0.1 |

---

## 2. What Constitutes Major Changes

### Breaking Changes (MAJOR)

| Change Type | Example |
|-------------|---------|
| **Export Schema** | Removed or renamed columns |
| **EC/IC/QC Logic** | Changed decision criteria |
| **Input Schema** | Required columns changed |
| **Protocol Format** | Protocol JSON structure changed |
| **CLI Interface** | Changed command-line arguments |
| **Output Format** | Different file structure |

**Decision Rule**: If existing runs would produce different outputs → MAJOR

### Non-Breaking Changes (MINOR)

| Change Type | Example |
|-------------|---------|
| **New Protocol** | Added new default protocol version |
| **New Criteria** | Added new EC/IC/QC rules (optional) |
| **Documentation** | New guides, expanded docs |
| **Audit Fields** | Added new log fields (backward compatible) |
| **Tests** | Added new test coverage |

**Decision Rule**: Existing runs unchanged, new capabilities added → MINOR

### Bug Fixes (PATCH)

| Change Type | Example |
|-------------|---------|
| **Logic Fixes** | Fixed EC1 keyword matching |
| **Edge Cases** | Fixed handling of empty abstracts |
| **Performance** | Faster processing |
| **Documentation** | Fixed typos, clarified guides |

**Decision Rule**: Same input + same protocol = same output → PATCH

---

## 3. Protocol Versioning

### Default Protocol

The default protocol has its own version:

```yaml
protocol_version: "1.0"
name: "Default APOLLO Protocol"
```

### Protocol Version Rules

| Change | Protocol Version Change |
|--------|-------------------------|
| Added new EC rule | MINOR (backward compatible) |
| Changed keyword list | MINOR |
| Changed threshold | MAJOR (behavior change) |
| Changed decision logic | MAJOR |
| Removed EC rule | MAJOR |

### Protocol Checksum

Each protocol has a checksum:

```python
def _compute_protocol_checksum(protocol):
    protocol_json = json.dumps(protocol, sort_keys=True)
    return sha256(protocol_json.encode()).hexdigest()[:16]
```

**Purpose**: Verify protocol integrity without comparing entire JSON

### Protocol Parity Guarantee

```
default_behavior == protocol(get_default_protocol())
```

All protocol versions must pass parity tests against default behavior.

---

## 4. Schema Versioning

### Input Schema (ATLAS Excel)

| Version | Changes |
|---------|---------|
| 1.0 | Initial release |

**Input Schema Changes**: Always MAJOR (breaks processing)

### Output Schema (APOLLO Excel)

| Sheet | Columns | Version |
|-------|---------|---------|
| WL | 13 columns | 1.0 |
| GL | 7 columns | 1.0 |
| WL Seeds for HERMES | 13 columns | 1.0 |

**Output Schema Changes**: Always MAJOR (breaks downstream)

### Schema Validation

```python
class ATLASLoader:
    WL_REQUIRED_COLUMNS = {"Library", "Global_ID", "Local_ID", "Title", "Abstract", "Keywords"}
    GL_REQUIRED_COLUMNS = {"Posicao", "Title", "URL", "Source_File"}
```

---

## 5. Audit Log Versioning

### Log Structure Version

Current: **1.0**

```json
{
  "run_id": "run_20260507_164152",
  "version": "1.0",
  "timestamp": "...",
  ...
}
```

### Audit Log Version Rules

| Change | Log Version Change |
|--------|-------------------|
| Added new required field | MAJOR |
| Added optional field | MINOR |
| Fixed field name | MAJOR |
| Changed field type | MAJOR |

---

## 6. Reproducibility Between Versions

### Guarantee

```
APOLLO X.Y.Z + Protocol P.Q.R + Input I
→
Same Output (deterministic)
```

### Version Compatibility Matrix

| APOLLO Version | Protocol Version | Reproducibility |
|----------------|------------------|-----------------|
| 1.0.0 | 1.0 | ✅ Verified |
| 1.1.0 | 1.0 | ✅ Verified (minor adds) |
| 1.1.0 | 1.1 | ✅ Verified (minor adds) |
| 2.0.0 | 2.0 | ⚠️ New release - verify |

### Cross-Version Testing

Before each release:
1. Run with latest protocol
2. Run with previous protocol versions
3. Verify determinism hash matches
4. Verify protocol parity maintained

---

## 7. Release Classification

### Pre-Release Versions

```
1.0.0-alpha.1    # Alpha - early testing
1.0.0-beta.1    # Beta - feature complete
1.0.0-rc.1      # Release Candidate - final testing
1.0.0           # Stable release
```

### Current Status

**APOLLO 1.0.0** - Release Candidate

- All tests passing
- Protocol parity verified
- Documentation complete
- Ready for stable release

---

## 8. Version Number in Practice

### Current Version Information

```python
# src/core/atlas_processor.py
__version__ = "1.0.0"
__protocol_version__ = "1.0"
```

### CLI Version Check

```bash
$ python scripts/process_atlas.py --version
APOLLO 1.0.0
Protocol 1.0
```

---

## 9. Deprecation Policy

###宣布 Deprecation

1. **Announce**: In release notes and documentation
2. **Timeline**: Support for 2 minor versions
3. **Migration**: Provide clear migration path

### Example

```
[DEPRECATED in 1.1.0]
Old parameter: --output-format
New parameter: --output
Removal in: 2.0.0
```

---

## 10. Version Number Display

### Where Version Appears

| Location | Information |
|----------|-------------|
| CLI startup | APOLLO version |
| Audit log | APOLLO version + protocol version |
| Export filename | No version in filename (stable schema) |
| Documentation | Version in URL and headers |

---

## Summary

| Version Type | Current | Next Major | Next Minor |
|--------------|---------|------------|------------|
| APOLLO | 1.0.0 | 2.0.0 | 1.1.0 |
| Protocol | 1.0 | 2.0 | 1.1 |
| Schema | 1.0 | 2.0 | 1.0 (stable) |
| Audit Log | 1.0 | 2.0 | 1.1 |

### Release Criteria

- [x] All tests passing
- [x] Protocol parity verified
- [x] Documentation complete
- [x] Breaking changes identified
- [x] Deprecation policy defined
- [x] Ready for stable release

---

*Document Version: 1.0.0*  
*APOLLO Versioning Strategy - Semantic Versioning 2.0.0*