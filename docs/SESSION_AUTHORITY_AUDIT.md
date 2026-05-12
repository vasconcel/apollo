# SESSION AUTHORITY AUDIT — Sprint 2 Phase 4

**Purpose**: Document the three independent dict-based sessions, confirm they bypass `ScreeningSession` authority, and assess scientific integrity impact.

**Evidence standard**: Every claim must cite file:line with exact code excerpt.

---

## 1. EXECUTIVE SUMMARY

| Session | Location | Type | Authority | Status |
|---|---|---|---|---|
| `ec_session` | `st.session_state` | Raw dict | NONE — bypasses ScreeningSession | VIOLATION |
| `ic_session` | `st.session_state` | Raw dict | NONE — bypasses ScreeningSession | VIOLATION |
| `qc_session` | `st.session_state` | Raw dict | NONE — bypasses ScreeningSession | VIOLATION |
| `ScreeningSession` | `src/core/screening_session.py` | Canonical model | FULL authority (not used) | ORPHANED (canonical but unused) |

**No single canonical session authority exists**. The canonical `ScreeningSession` exists but is **never instantiated** by any routed view. All three canonical views use independent raw dict sessions.

---

## 2. THREE INDEPENDENT DICT SESSIONS

### 2.1 ec_session

**File**: `src/ui/modules/ec_screening_view.py:49-55`

```python
if "ec_session" not in st.session_state:
    st.session_state.ec_session = {
        "articles": [],       # List[dict] — not List[ArticleReview]
        "current_index": 0,
        "decisions": {},     # Dict[str, dict] — raw dict decisions
        "loaded": False
    }
```

**Usage** (lines 109-112):
```python
st.session_state.ec_session["articles"] = articles
st.session_state.ec_session["current_index"] = 0
st.session_state.ec_session["decisions"] = {}
st.session_state.ec_session["loaded"] = True
```

**Access** (line 164):
```python
session = st.session_state.ec_session
```

### 2.2 ic_session

**File**: `src/ui/modules/ic_screening_view.py:44-50`

```python
if "ic_session" not in st.session_state:
    st.session_state.ic_session = {
        "articles": [],
        "current_index": 0,
        "decisions": {},
        "loaded": False
    }
```

**Usage** (lines 104-107):
```python
st.session_state.ic_session["articles"] = articles
st.session_state.ic_session["current_index"] = 0
st.session_state.ic_session["decisions"] = {}
st.session_state.ic_session["loaded"] = True
```

**Access** (line 155):
```python
session = st.session_state.ic_session
```

### 2.3 qc_session

**File**: `src/ui/modules/qc_assessment_view.py:44-50`

```python
if "qc_session" not in st.session_state:
    st.session_state.qc_session = {
        "articles": [],
        "current_index": 0,
        "assessments": {},
        "loaded": False
    }
```

**Usage** (lines 106-109):
```python
st.session_state.qc_session["articles"] = articles
st.session_state.qc_session["current_index"] = 0
st.session_state.qc_session["assessments"] = {}
st.session_state.qc_session["loaded"] = True
```

**Access** (line 159):
```python
session = st.session_state.qc_session
```

---

## 3. SCREENINGSESSION — CANONICAL MODEL (NOT USED)

**File**: `src/core/screening_session.py`

`ScreeningSession` is a fully-implemented canonical model with proper authority:

```
ArticleReview (dataclass)
    article_id, title, abstract, metadata
    ec_stage, ec_notes, ec_timestamp, ec_llm_suggestion
    ic_stage, ic_notes, ic_timestamp, ic_llm_suggestion
    qc_stage, qc_notes, qc_timestamp, qc_scores, qc_total
    final_decision, provenance

ScreeningSession
    articles: List[ArticleReview]       ← canonical article authority
    decisions: List[ReviewDecisionLog]  ← audit trail
    snapshots: List[ReviewSnapshot]       ← temporal lineage
    apply_decision()                     ← canonical decision authority
    add_article()                        ← canonical article ingestion
    take_snapshot()                      ← metadata lineage preservation
    _to_dict() / from_dict()             ← serialization
```

**Key authority methods**:

| Method | Line | Purpose |
|---|---|---|
| `apply_decision()` | ~220 | Canonical decision authority — validates and records decisions with timestamps |
| `add_article()` | ~180 | Canonical article ingestion — ensures ArticleReview instances |
| `take_snapshot()` | ~460 | Captures temporal state with protocol hash |
| `included_count` | property | Computed from authoritative decisions |
| `excluded_count` | property | Computed from authoritative decisions |

**Evidence of completeness**: `screening_session.py:38-50` defines `ArticleReview` dataclass, `screening_session.py:1-592` is a complete, self-consistent model. It has NO imports from orphaned modules.

**PROBLEM**: `ScreeningSession` is **never instantiated** by any routed view. Zero runtime evidence of `ScreeningSession()` being called.

**grep evidence** (no ScreeningSession instantiation):
```bash
rg "ScreeningSession\(" src/ui/modules/ → NO MATCHES
```

---

## 4. THE BYPASS CHAIN

```
atlas_processor.py (canonical DataFrame ops)
    ↓ (ArticleReview objects)
ScreeningSession.articles ← NEVER REACHED (bypassed)
    ↓
st.session_state.ec_session["articles"] ← DICT (not ArticleReview)
st.session_state.ic_session["articles"] ← DICT (not ArticleReview)
st.session_state.qc_session["articles"] ← DICT (not ArticleReview)
    ↓
export_view reads dict sessions (lines 92-105)
    ↓
No canonical session → no deterministic hash → no reproducible exports
```

**No view ever calls**:
- `ScreeningSession()` — constructor never called
- `session.add_article()` — never called
- `session.apply_decision()` — never called
- `session.take_snapshot()` — never called

---

## 5. DECISION FLOW — DICT vs CANONICAL

### 5.1 ACTUAL (dict-based) — ec_screening_view.py

```python
# Line 164: session = st.session_state.ec_session
# Decisions stored as raw dict:
session["decisions"][article_id] = {
    "decision": decision,
    "notes": notes,
    "timestamp": datetime.now().isoformat()
}
```

**No validation**. No hash. No audit trail. No reproducible verification.

### 5.2 EXPECTED (ScreeningSession-based)

```python
session = ScreeningSession(protocol=protocol, researcher_id=researcher_id)
session.add_article(article)  # ArticleReview instance
session.apply_decision(article_id, decision, notes)  # Validated, hashed, timestamped
session.take_snapshot()  # Temporal lineage preserved
```

**Authority enforced**. Decision hashing. Timestamp. Audit trail. Reproducible.

---

## 6. SCALABILITY VIOLATION

| Aspect | Dict Sessions | ScreeningSession |
|---|---|---|
| Article count limit | Unlimited (memory) | Unlimited |
| Cross-stage decision tracking | NONE — each session independent | Canonical across all stages |
| Snapshot/restore | NOT POSSIBLE | `take_snapshot()` / `restore_snapshot()` |
| Session persistence | Streamlit memory only | `to_json()` / `from_json()` |
| Decision hashing | NOT IMPLEMENTED | SHA256 hash per decision |
| Metadata lineage | NOT TRACKED | `ReviewSnapshot` preserves protocol hash |
| Type safety | NONE — `articles: List[dict]` | STRONG — `articles: List[ArticleReview]` |
| Validation | NONE | Stage-aware validation |
| Inter-stage flow | Manual (dict copies) | `get_included_articles()` |

### 6.1 Inter-stage data flow (ACTUAL — dict)

```
ec_screening_view
    → ec_session["articles"]: [{"title": ..., "ec_decision": ...}]
    → researcher saves to file
ic_screening_view
    → reads uploaded file via pd.read_excel / .iterrows (VIOLATION from UI_BOUNDARY_AUDIT)
    → ic_session["articles"]: [{"title": ..., "ec_decision": ...}]
    → different dict shape, metadata stripped
qc_assessment_view
    → reads uploaded file via pd.read_excel / .iterrows (VIOLATION from UI_BOUNDARY_AUDIT)
    → qc_session["articles"]: [{"title": ..., "qc_scores": {}}]
    → yet another dict shape
```

Each stage re-ingests from file, creating independent article lists with NO shared identity. Article "Article-001" in EC is NOT linked to "Article-001" in IC — they're separate dict objects.

### 6.2 Inter-stage data flow (EXPECTED — canonical)

```
ScreeningSession(protocol=protocol)
    → add_article(ArticleReview(...)) for EC stage
    → apply_decision() records EC decision
    → get_ec_included() returns filtered list
    → pass same ArticleReview instances to IC stage (identity preserved)
    → apply_decision() records IC decision
    → get_ic_included() returns filtered list
    → pass same ArticleReview instances to QC stage (identity preserved)
    → apply_decision() records QC decision
    → take_snapshot() preserves full lineage
```

Article identity is preserved across all stages. Metadata lineage is maintained.

---

## 7. EXPORT ENGINE DISCONNECTION

**File**: `src/core/export_engine.py`

`ExportEngine` is architecturally correct but **never wired to the UI**:

| Method | Line | Purpose | Called from export_view? |
|---|---|---|---|
| `export_decisions_excel()` | 79 | Excel export with WL/GL sheets | NO |
| `export_session_json()` | 151 | Full session JSON | NO |
| `export_audit_log()` | 164 | Audit trail | NO |
| `export_manifest()` | 200 | Export metadata | NO |
| `export_all()` | 228 | Full multi-format export | NO |

`export_view.py` (lines 88–194) reads from dict sessions and produces:
1. Protocol JSON (broken — `str(dict)`, not valid JSON)
2. PRISMA counts display (UI-only)
3. Audit log JSON (just protocol metadata, not decision audit)

`export_engine.py` methods expect `ScreeningSession`:
```python
# export_engine.py:88
for article in session.articles:
    meta = article.metadata  # expects ArticleReview object
```

But `export_view` never passes anything to `export_engine`. The engine is unreachable code from the UI perspective.

---

## 8. SCIENTIFIC INTEGRITY IMPACT

| Impact | Description |
|---|---|
| **No decision hashing** | Dict sessions store raw decision strings. No SHA256 hash per decision. Cannot verify that a decision was made by a specific researcher at a specific time. |
| **No temporal snapshots** | `ScreeningSession.take_snapshot()` never called. Protocol hash not captured per decision. Cannot prove which version of the protocol was active when a decision was made. |
| **Article identity loss** | Same article across EC/IC/QC stages has NO shared ID. "Article-001" at EC ≠ "Article-001" at QC — they are separate dict objects. Cannot trace a decision back through stages. |
| **Metadata lineage dropout** | IC and QC views do not call `normalize_wl_metadata` / `normalize_gl_metadata`. Provenance chain broken at export. |
| **No session persistence** | Dict sessions exist only in Streamlit memory. Page refresh = data loss. No JSON save/restore. |
| **No reproducibility** | `export_view` produces counts from dict sessions, but no canonical session means no deterministic hash. Same input file + same decisions ≠ same output hash. |

---

## 9. VERIFICATION CHECKLIST

- [ ] **CONFIRMED**: `ec_session`, `ic_session`, `qc_session` are all raw dicts (lines 49-55, 44-50, 44-50 respectively)
- [ ] **CONFIRMED**: No `ScreeningSession()` constructor call in any UI module (grep evidence)
- [ ] **CONFIRMED**: No `session.add_article()` call in any UI module
- [ ] **CONFIRMED**: No `session.apply_decision()` call in any UI module
- [ ] **CONFIRMED**: No `session.take_snapshot()` call in any UI module
- [ ] **CONFIRMED**: `export_engine.py` methods expect `ScreeningSession` (line 88: `for article in session.articles`)
- [ ] **CONFIRMED**: `export_view.py` reads from dict sessions, never calls export_engine methods
- [ ] **CONFIRMED**: `ScreeningSession` is a complete, self-consistent canonical model (0 imports from orphaned modules)

---

## 10. ROOT CAUSE ASSESSMENT

**Architectural drift**: `ScreeningSession` was likely designed as the canonical session model but the UI views were built in parallel using dict-based sessions. Neither path was fully completed:
- Dict sessions: complete enough to function, but lack authority/hashing/snapshots
- ScreeningSession: complete enough as a model, but never wired to views

**This is NOT dead code in ScreeningSession** — it is canonical code that was never connected. The model is well-designed and should be the authority. The dict sessions are the legacy pattern.

---

## 11. RECOMMENDATIONS (FOR PHASE 7 — LEGACY RETIREMENT PLAN)

1. **Wire ScreeningSession to views**: Replace `st.session_state.{ec,ic,qc}_session` with `st.session_state.screening_session: ScreeningSession`
2. **Preserve article identity**: All three stages reference the same `ScreeningSession.articles` list — ArticleReview objects persist across stages
3. **Call authority methods**: Replace dict-mutation with `session.add_article()`, `session.apply_decision()`, `session.take_snapshot()`
4. **Fix export pipeline**: Wire `ExportEngine` to use `ScreeningSession` — `export_decisions_excel()` already handles the canonical model
5. **Add session persistence**: `ScreeningSession.to_json()` / `from_json()` for save/restore across page refreshes
6. **Add decision hashing**: `apply_decision()` computes SHA256 hash per decision — enable reproducibility
7. **DO NOT delete ScreeningSession**: It is canonical code that needs to be wired, not removed

**The dict sessions are the legacy pattern to retire**. `ScreeningSession` is the canonical target.
