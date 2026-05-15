# APOLLO v1.0.0 Human-Verifiable Audit

**Date**: 2026-05-14

This document provides EXECUTABLE COMMANDS to independently verify all major claims without trusting any narrative.

---

## PHASE 1: TEST VALIDATION

### 1.1 Test Collection (Working Tests)

**COMMAND:**
```bash
cd D:\Projetos\apollo
python -m pytest tests/unit/test_design_system_ux.py tests/unit/test_structured_advisory.py tests/unit/test_visual_logic.py -v --tb=no
```

**EXPECTED OUTPUT:**
```
tests/unit/test_design_system_ux.py::TestWorkflowOrderVisibility::test_workflow_stages_defined PASSED
tests/unit/test_design_system_ux.py::TestWorkflowOrderVisibility::test_workflow_stage_order PASSED
...
tests/unit/test_visual_logic.py::test_semantic_search_query_format PASSED [ 98%]
tests/unit/test_visual_logic.py::test_visual_theme_colors PASSED [100%]

======================== 1 failed, 65 passed in 0.66s =========================
```

**HOW TO INTERPRET:** 65 tests pass, 1 fails (test_workflow_components_importable). The failure is about expecting 6 workflow stages but only 5 exist.

**PASS/FAIL:** PASS - Tests execute correctly

---

### 1.2 Failing Test Details

**COMMAND:**
```bash
cd D:\Projetos\apollo
python -m pytest tests/unit/test_design_system_ux.py::TestDesignSystemIntegration::test_workflow_components_importable -v
```

**EXPECTED OUTPUT:**
```
FAILED tests/unit/test_design_system_ux.py::TestDesignSystemIntegration::test_workflow_components_importable
AssertionError: Should have 6 workflow stages
assert 5 == 6
```

**WHY IT FAILS:** WORKFLOW_STAGES has 5 entries (protocol, ec, ic, export, replay), test expects 6.

**PASS/FAIL:** FAIL - QC stage missing from workflow components

---

### 1.3 Collection Errors

**COMMAND:**
```bash
cd D:\Projetos\apollo
python -m pytest tests/ --collect-only -q 2>&1 | tail -30
```

**EXPECTED OUTPUT:**
```
ERROR tests/integration/test_architectural_integrity.py
ERROR tests/integration/test_config_manager.py
ERROR tests/test_protocol_layer.py
...
ERROR tests/unit/test_synthesis_aggregator.py
```

**WHY ERRORS OCCUR:**
- test_protocol_layer.py: Calls `sys.exit(0)` at line 63
- Others: Missing modules (QCProtocol, database, config_manager, etc.)

**PASS/FAIL:** N/A - Collection errors, not test failures

---

## PHASE 2: REPLAY DETERMINISM VALIDATION

### 2.1 Session Checksum Determinism

**COMMAND:** Run this Python script:
```python
import os
os.chdir(r'D:\Projetos\apollo')
from src.core.screening_session import ScreeningSession, ArticleReview

checksums = []
for run in range(3):
    session = ScreeningSession(session_id='det-001', created_at='2026-05-14T10:00:00', protocol_version='1.0')
    for i in range(3):
        session.articles.append(ArticleReview(article_id=f'A-{i:03d}', title=f'Article {i}', abstract=f'Abstract {i}', metadata={'literature_type': 'WL'}))
    session.ec_completed = 2
    checksums.append(session.compute_checksum())

print("Checksums:", checksums)
print("All identical:", len(set(checksums)) == 1)
```

**EXPECTED OUTPUT:**
```
Checksums: ['6eb307fe681e6acc...', '6eb307fe681e6acc...', '6eb307fe681e6acc...']
All identical: True
```

**PASS/FAIL:** PASS - Same state produces same checksum

---

### 2.2 Replay Checksum Comparison

**COMMAND:** Run this Python script:
```python
import os
import tempfile
os.chdir(r'D:\Projetos\apollo')
from src.core.screening_session import ScreeningSession, ArticleReview
from src.core.reproducibility_engine import create_reproducibility_bundle, ReplayEngine

replay_checksums = []
for run in range(3):
    session = ScreeningSession(session_id='replay-test', created_at='2026-05-14T10:00:00', protocol_version='1.0')
    session.articles.append(ArticleReview('A-1', 'T', 'A', {'literature_type': 'WL'}))
    session.record_decision('include', notes='Test')

    with tempfile.TemporaryDirectory() as tmpdir:
        bundle = create_reproducibility_bundle(session, tmpdir)
        replayed, _ = ReplayEngine.replay_session(bundle.bundle_path)
        replay_checksums.append(replayed.compute_checksum())

print("Replay checksums:", replay_checksums)
print("All identical:", len(set(replay_checksums)) == 1)
```

**EXPECTED OUTPUT:**
```
Replay checksums: ['30f202eee5416588', '02b6bb061d10fa95', 'eb30344ee9f33e17']
All identical: False
```

**INTERPRETATION:** Replay is NOT deterministic - different checksums on each run.

**PASS/FAIL:** FAIL - Replay produces different state each time

---

## PHASE 3: AUDIT CHAIN VALIDATION

### 3.1 Audit Chain in session.json

**COMMAND:** Run this Python script:
```python
import os
import json
import tempfile
os.chdir(r'D:\Projetos\apollo')
from src.core.screening_session import ScreeningSession, ArticleReview
from src.core.reproducibility_engine import create_reproducibility_bundle

session = ScreeningSession('test', '2026-05-14')
session.articles.append(ArticleReview('A-1', 'T', 'A', {'literature_type': 'WL'}))
session.record_decision('include', notes='Test')

print("=== Original Session ===")
print(f"Audit chain events: {len(session._audit_chain)}")

with tempfile.TemporaryDirectory() as tmpdir:
    bundle = create_reproducibility_bundle(session, tmpdir)
    
    with open(bundle.session_json) as f:
        session_data = json.load(f)
    print("\n=== session.json ===")
    print(f"audit_chain present: {'audit_chain' in session_data}")
    print(f"audit_chain length: {len(session_data.get('audit_chain', []))}")
    
    with open(bundle.audit_log_json) as f:
        audit_data = json.load(f)
    print("\n=== audit_log.json ===")
    print(f"Events: {len(audit_data.get('events', []))}")
```

**EXPECTED OUTPUT:**
```
=== Original Session ===
Audit chain events: 1

=== session.json ===
audit_chain present: False
audit_chain length: 0

=== audit_log.json ===
Events: 1
```

**INTERPRETATION:** Audit chain is exported to audit_log.json but NOT to session.json. This causes replay to lose audit events.

**PASS/FAIL:** FAIL - Audit chain NOT in session.json

---

### 3.2 Verify _to_dict_full Missing Audit Chain

**COMMAND:**
```bash
cd D:\Projetos\apollo
sed -n '892,912p' src/core/screening_session.py
```

**EXPECTED OUTPUT:**
```python
def _to_dict_full(self) -> Dict:
    """Convert to dictionary with full metadata lineage."""
    return {
        "session_id": self.session_id,
        "created_at": self.created_at,
        "protocol_version": self.protocol_version,
        "stage": self.stage,
        "current_index": self.current_index,
        "total_count": self.total_count,
        "ec_completed": self.ec_completed,
        "ic_completed": self.ic_completed,
        "included_count": self.included_count,
        "excluded_count": self.excluded_count,
        "skip_count": self.skip_count,
        "discussion_count": self.discussion_count,
        "researcher_id": self.researcher_id,
        "last_saved": self.last_saved,
        "schema_version": self.schema_version,
        "articles": [a.to_dict() for a in self.articles],
        "dynamic_protocol": self.dynamic_protocol,
    }
```

**EVIDENCE:** `_audit_chain` is NOT in the returned dictionary.

**PASS/FAIL:** FAIL - Audit chain intentionally excluded

---

### 3.3 Audit Chain Verification

**COMMAND:** Run this Python script:
```python
import os
os.chdir(r'D:\Projetos\apollo')
from src.core.screening_session import ScreeningSession, ArticleReview

session = ScreeningSession('test', '2026-05-14')
session.articles.append(ArticleReview('A-1', 'T', 'A', {'literature_type': 'WL'}))
session.record_decision('include', notes='Test')

is_valid, errors = session.verify_audit_chain()
print(f"Audit valid: {is_valid}")
print(f"Errors: {errors}")

is_clean, tampered = session.detect_tampering()
print(f"Clean: {is_clean}")
print(f"Tampered: {tampered}")
```

**EXPECTED OUTPUT:**
```
Audit valid: True
Errors: []
Clean: True
Tampered: []
```

**PASS/FAIL:** PASS - Audit chain verification works for in-memory chain

---

## PHASE 4: LLM CONTEXT VALIDATION

### 4.1 EC Prompt Missing Metadata Completeness

**COMMAND:** Run this Python script:
```python
import os
os.environ['GROQ_API_KEY'] = 'test-key'
os.chdir(r'D:\Projetos\apollo')
from src.core.llm_assistant import LLMAssistant

llm = LLMAssistant()
prompt = llm._build_ec_prompt(
    title='Test Title',
    abstract='Test Abstract about SE recruitment',
    year_str='2023',
    year_source='atlas',
    literature_type='White Literature',
    metadata_completeness='complete',
    criteria={'EC1': 'Test', 'EC2': 'Test2'},
    metadata={'year': '2023', 'metadata_completeness': 'complete'}
)

print("Metadata completeness in EC prompt:", 'complete' in prompt.lower())
print("'Metadata Completeness' in prompt:", 'Metadata Completeness' in prompt)
```

**EXPECTED OUTPUT:**
```
Metadata completeness in EC prompt: False
'Metadata Completeness' in prompt: False
```

**PASS/FAIL:** FAIL - EC prompt does NOT include metadata_completeness

---

### 4.2 IC Prompt Has Metadata Completeness

**COMMAND:** Run this Python script:
```python
import os
os.environ['GROQ_API_KEY'] = 'test-key'
os.chdir(r'D:\Projetos\apollo')
from src.core.llm_assistant import LLMAssistant

llm = LLMAssistant()
prompt = llm._build_ic_prompt(
    title='Test Title',
    abstract='Test Abstract',
    literature_type='White Literature',
    year_source='atlas',
    metadata_completeness='complete',
    criteria={'IC1': 'Test'},
    metadata={'year': '2023'}
)

print("'Metadata Completeness' in IC prompt:", 'Metadata Completeness' in prompt)
```

**EXPECTED OUTPUT:**
```
'Metadata Completeness' in IC prompt: True
```

**PASS/FAIL:** PASS - IC prompt includes metadata_completeness

---

### 4.3 WL/GL Normalization

**COMMAND:** Run this Python script:
```python
import os
os.chdir(r'D:\Projetos\apollo')
from src.core.llm_assistant import normalize_literature_label

tests = ['WL', 'wl', 'White Literature', 'GL', 'gl', 'Grey Literature', 'Gray Literature']
for t in tests:
    print(f"'{t}' -> '{normalize_literature_label(t)}'")
```

**EXPECTED OUTPUT:**
```
'WL' -> 'White Literature'
'wl' -> 'White Literature'
'White Literature' -> 'White Literature'
'GL' -> 'Grey Literature'
'gl' -> 'Grey Literature'
'Grey Literature' -> 'Grey Literature'
'Gray Literature' -> 'Grey Literature'
```

**PASS/FAIL:** PASS - All normalizations work correctly

---

### 4.4 Fallback Detection

**COMMAND:** Run this Python script:
```python
import os
for k in ['GROQ_API_KEY', 'OPENAI_API_KEY']:
    if k in os.environ: del os.environ[k]
os.chdir(r'D:\Projetos\apollo')
from src.core.llm_assistant import LLMAssistant

llm = LLMAssistant()
result = llm.suggest_ec(title='Test', abstract='Test abstract', literature_type='WL')

print(f"is_fallback: {result.is_fallback}")
print(f"decision: {result.decision}")
print(f"confidence: {result.confidence}")
print(f"fallback_reason: {result.fallback_reason}")
```

**EXPECTED OUTPUT:**
```
is_fallback: True
decision: unavailable
confidence: 0.0
fallback_reason: No LLM client
```

**PASS/FAIL:** PASS - Fallback detection works correctly

---

## PHASE 5: UI ROUTING VALIDATION

### 5.1 Sidebar Options (No QC)

**COMMAND:**
```bash
cd D:\Projetos\apollo
grep -A15 "st.radio" app.py | head -20
```

**EXPECTED OUTPUT:**
```python
view = st.radio(
    "MODULE",
    options=[
        "Protocol Configuration",
        "EC Screening",
        "IC Screening",
        "Inter-Rater Calibration",
        "Exports & Audit"
    ],
```

**INTERPRETATION:** QC Screening is NOT in the sidebar options.

**PASS/FAIL:** FAIL - QC stage not accessible via UI

---

### 5.2 No QC Route

**COMMAND:**
```bash
cd D:\Projetos\apollo
grep -n "QC Screening" app.py
```

**EXPECTED OUTPUT:**
```
(nothing)
```

**PASS/FAIL:** FAIL - No QC route exists

---

### 5.3 Protocol Locking

**COMMAND:**
```bash
cd D:\Projetos\apollo
grep -n "protocol.state == ProtocolState.DRAFT" src/ui/modules/ec_screening_view.py
```

**EXPECTED OUTPUT:**
```
39:         if protocol.state == ProtocolState.DRAFT.value:
40:             print("!!! DEBUG UI !!! Auto-locking DRAFT protocol for screening")
41:             protocol.state = ProtocolState.LOCKED.value
42:             protocol.lock()
```

**PASS/FAIL:** PASS - Protocol locking implemented

---

### 5.4 Advisory Separation (Human Makes Final Decision)

**COMMAND:**
```bash
cd D:\Projetos\apollo
grep -B2 -A5 "record_decision.*include" src/ui/modules/ec_screening_view.py | head -10
```

**EXPECTED OUTPUT:**
```python
if incl_clicked:
    session.record_decision("include", notes="")
    article.cis1 = "PENDING"
```

**INTERPRETATION:** Decision is hardcoded "include", NOT from LLM suggestion.

**PASS/FAIL:** PASS - Human makes final decision, not LLM

---

## SUMMARY: REPRODUCIBILITY MATRIX

| Test | File | Pass/Fail |
|------|------|-----------|
| 65 tests pass | tests/unit/ | ✅ PASS |
| Replay deterministic | test_replay.py | ❌ FAIL |
| Audit in session.json | test_audit_persistence.py | ❌ FAIL |
| EC prompt has metadata_completeness | test_prompt_ec.py | ❌ FAIL |
| IC prompt has metadata_completeness | test_prompt_ic.py | ✅ PASS |
| WL/GL normalization | test_normalization.py | ✅ PASS |
| Fallback detection | test_fallback.py | ✅ PASS |
| QC in UI | grep "QC Screening" | ❌ FAIL |
| Audit verification | test_audit_verify.py | ✅ PASS |
| Advisory separation | ec_screening_view.py | ✅ PASS |

---

## HOW TO USE THIS DOCUMENT

1. **Copy each command** exactly as shown
2. **Run in D:\Projetos\apollo** directory
3. **Compare outputs** to expected results
4. **Mark as PASS/FAIL** based on match

Do NOT trust any claim that cannot be reproduced with these exact commands.

---

**END OF HUMAN-VERIFIABLE AUDIT**