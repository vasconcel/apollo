# APOLLO — System Context Package

> **Domain:** Systematic Literature Review (SLR) — Recruitment & Selection (R&S) in Software Engineering  
> **Language:** Python 3.14.4 (backend), JavaScript/React 18 (frontend)  
> **Framework:** FastAPI / Uvicorn (backend), Vite + Tailwind CSS 3 (frontend)  
> **Database:** SQLite 3 (single-connection, no WAL journal)  
> **LLM Protocol:** OpenAI-compatible `/chat/completions` (Ollama, Groq, OpenAI, Gemini)

---

## 1. ARCHITECTURAL BLUEPRINT & FLOWS

### 1.1 Backend Layering (Clean / Hexagonal)

```
src/api/          ── Controllers / route handlers    (FastAPI routers)
src/use_cases/    ── Orchestration logic             (screening pipeline, export)
src/domain/       ── Enterprise models & interfaces  (zero external deps)
src/infrastructure/ ── External adapters             (SQLite, HTTP, SVM, scraping)
```

The dependency rule is strict: `api` → `use_cases` → `domain` ← `infrastructure`. No layer imports from a layer above itself.

### 1.2 ASGI Process & Concurrency Model

- **Server:** `uvicorn` with one `asyncio` event loop.
- **Route handlers** are `async def` — FastAPI coroutines.
- **Background screening** runs as a single `asyncio.Task` created via `asyncio.create_task()` in the `POST /api/screening/start` handler.
- **Task registry:** `_active_tasks: dict[str, asyncio.Task]` global dict in `routes.py`. Key `"screening"` holds the current task. A `done_callback` pops the task on completion.
- **Cancellation:** `task.cancel()` is called on stop, raising `asyncio.CancelledError` inside the pipeline which is caught, logged, and re-raised for clean teardown.
- **Concurrency within the pipeline:** `asyncio.Semaphore(N)` — dynamically set to `3` for local Ollama, `1` for cloud providers (Groq/OpenAI/Gemini). Each paper acquisition inside the semaphore is serialized per permit.
- **Concurrent HTTP requests inside a single screening step:** None — every `screen_paper` call is a single `POST /chat/completions`. The semaphore controls how many papers are in-flight simultaneously.

### 1.3 SQLite Single-Connection Repository

- `SQLiteScreeningDecisionRepository` opens **one persistent connection** at `__init__` and never closes it for the app lifetime.
- **No connection pooling.** All reads/writes share the same `sqlite3.Connection` object.
- **No WAL journal.** Default `DELETE` journal mode (potential read contention under heavy concurrent writes, but mitigated by single-threaded async design).
- Every write calls `self._conn.commit()` immediately (no explicit transaction batching).
- Reader endpoints (`GET /api/screening/progress`, `GET /api/papers`) create **new ad-hoc connections** per call to avoid blocking the writer connection. The `DecisionRepositoryProtocol` returned by `_get_decision_repo()` uses a fresh connection for progress/paper reads.

### 1.4 Dynamic LLM Connection Layer

`UnifiedLLMService` (alias `OllamaLLMService`) wraps the OpenAI-compatible chat completions API. Key design points:

- **`settings_provider: Callable[[str, str], str] | None`** — a lambda injected at construction time that resolves settings at each API call via `provider("llm_provider", "ollama")`, `provider("llm_base_url", ...)`, etc. If `None`, falls back to env vars `OLLAMA_BASE_URL` / `OLLAMA_MODEL` and the constructor defaults.
- **Per-call HTTP client:** When `settings_provider` is active, a **new `httpx.AsyncClient`** is created per `screen_paper` / `evaluate_quality` invocation so that base URL and API key changes take effect immediately. The client is destroyed in `finally` with a `TypeError` guard for mock compatibility.
- **Cached client:** When `settings_provider` is `None` (legacy mode), a single shared client is used for the service lifetime.
- **Retry logic:** `_post_with_retry` — up to 4 attempts, **only HTTP 429** triggers exponential backoff (`3s × 2^attempt`). The `Retry-After` response header is preferred when present. Non-429 errors re-raise immediately. After exhausting all retries, a `RuntimeError` propagates to the caller's catch block which converts it to a `NEEDS_REVIEW` fallback decision.

### 1.5 Data Flow — Full Screening Cycle

```
POST /api/screening/start?mode=calibration&target=ALL
  │
  ├─ Set _screening_active = True           ← synchronous, before create_task
  ├─ Calibration branch: check DB for existing calibration sample
  │   ├─ IDs exist → reuse them (no redraw, no clear_calibration_flags)
  │   └─ No IDs → mark 100 random papers with is_calibration=1
  ├─ Full branch: clear_calibration_flags(), train SVM on human audits
  ├─ asyncio.create_task(_run_screening_background(...))
  └─ Return {"status": "started", "task_id": "screening_current"}
       │
       ▼  (background task)
  RunScreeningPipelineUseCase.execute()
       │
       ├─ Deduplicate by normalized title  (EC6 auto-exclude)
       ├─ For each paper:
       │   ├─ SVM cascade (if trained): fast-track exclusion → skip LLM
       │   ├─ await asyncio.sleep(1.5)     ← only when cloud provider (needs_throttle)
       │   └─ async with semaphore:
       │       ├─ GL scrape (if no abstract, source_type=GL, has URL)
       │       ├─ await ScreenPaperUseCase.execute()
       │       │   ├─ Heuristic screening (EC1/EC3/EC4) → return if matched
       │       │   └─ LLM screening → UnifiedLLMService.screen_paper()
       │       └─ decision_repo.save_decision(...)
       │
       └─ Return processed count
            │
            ▼
        finally block:
          _screening_active = False
          _stopping_active = False
```

### 1.6 Start/Stop Race-Condition Guarantee

- `_screening_active` is set to `True` **synchronously in the request handler** (line 259 of `routes.py`), **before** `asyncio.create_task()` (line 296). This guarantees that the very first `GET /api/screening/progress` response after the `POST /api/screening/start` 200 OK will include `is_active: true`, preventing the frontend polling loop from aborting prematurely.
- `_stopping_active` is set to `True` by `POST /api/screening/stop`, reset to `False` on the next `start` and in the background task's `finally` block.

---

## 2. DATABASE SCHEMA SPECIFICATIONS

### 2.1 `screening_decisions`

```sql
CREATE TABLE IF NOT EXISTS screening_decisions (
    paper_id                TEXT PRIMARY KEY,
    status                  TEXT    NOT NULL,   -- INCLUDED | EXCLUDED | NEEDS_REVIEW
    confidence_score        REAL    NOT NULL,
    rationale               TEXT    NOT NULL,
    applied_criteria_codes  TEXT    NOT NULL,   -- semicolon-delimited, e.g. "IC1;IC4"
    is_calibration          INTEGER DEFAULT 0,  -- 1 = part of calibration sample
    gl_q1                   REAL,               -- Grey Lit quality Q1 (0.0/0.5/1.0)
    gl_q2                   REAL,
    gl_q3                   REAL,
    gl_q4                   REAL,
    wl_q1                   REAL,               -- White Lit quality Q1
    wl_q2                   REAL,
    wl_q3                   REAL,
    wl_q4                   REAL,
    quality_score           REAL,               -- overall quality score
    wl_quality_score        REAL,               -- WL-specific quality score
    full_text               TEXT,               -- extracted/scraped full-text content
    pdf_url                 TEXT,               -- URL to PDF if found
    human_decision          TEXT DEFAULT NULL,   -- YES | NO (human audit ground truth)
    is_audited              INTEGER DEFAULT 0,   -- 1 = has been human-audited
    title                   TEXT DEFAULT '',     -- denormalized for export
    abstract                TEXT DEFAULT ''      -- denormalized for export
);
```

Columns `human_decision` and `is_audited` are added by `_migrate_audit_columns()` (ALTER TABLE ADD COLUMN).  
Columns `title` and `abstract` are added by `_migrate_title_abstract_columns()`.

### 2.2 `criteria`

```sql
CREATE TABLE IF NOT EXISTS criteria (
    id              VARCHAR(10) PRIMARY KEY,   -- e.g. "EC1", "IC5"
    title           VARCHAR(255) NOT NULL,
    description     TEXT        NOT NULL,
    type            VARCHAR(10) NOT NULL,       -- "EXCLUSION" | "INCLUSION"
    is_heuristic    INTEGER     DEFAULT 0       -- 1 = evaluable without LLM
);
```

Seeded with 13 rows (6 exclusion EC1–EC6, 5 inclusion IC1–IC5) plus 2 extra heuristic criteria if they exist. Heuristic criteria are EC1 (non-English), EC3 (short publication), EC4 (pre-2015).

### 2.3 `system_settings`

```sql
CREATE TABLE IF NOT EXISTS system_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Seeded with 4 key-value pairs:

| Key               | Default value                                                                 |
|-------------------|-------------------------------------------------------------------------------|
| `llm_provider`    | `"ollama"`                                                                    |
| `llm_base_url`    | `"http://localhost:11434/v1"` (from `OLLAMA_BASE_URL` env var if set)         |
| `llm_model`       | `"qwen2.5:3b-instruct"` (from `OLLAMA_MODEL` env var if set)                  |
| `llm_api_key`     | `""` (empty — no auth required for local Ollama)                              |

All settings are read and written via `get_setting(key, default)` / `save_setting(key, value)` on `SQLiteScreeningDecisionRepository`.

---

## 3. REST API CONTRACTS & JSON SCHEMAS

### 3.1 `GET /api/screening/progress`

**No query parameters.**

**Response `200 OK`:**

```json
{
  "total_papers": 1247,
  "screened_count": 843,
  "pending_count": 404,
  "heuristic_exclusions": 312,
  "ai_exclusions": 421,
  "duplicates_count": 110,
  "included_count": 94,
  "is_active": true,
  "in_calibration": false,
  "qa_active": false,
  "current_qa_paper_id": null,
  "active_provider": "groq",
  "active_model": "llama-3.1-8b-instant",
  "currently_screening": "Machine Learning Approaches for...",
  "stopping_active": false
}
```

**Semantics:**
- `total_papers`: count of papers not excluded by EC6 (duplicates)
- `screened_count`: count of decisions where status is INCLUDED or EXCLUDED (not NEEDS_REVIEW)
- `pending_count`: `max(total_papers - screened_count, 0)` — unscreened papers plus NEEDS_REVIEW
- `heuristic_exclusions`: decisions with code EC1, EC3, or EC4
- `ai_exclusions`: excluded decisions not EC6 and not heuristic
- `duplicates_count`: decisions with code EC6
- `included_count`: decisions with status INCLUDED
- `is_active`: screening task is running
- `in_calibration`: screening was started with `mode=calibration`
- `qa_active`: quality assessment is running
- `current_qa_paper_id`: paper being quality-assessed, if any
- `active_provider`: LLM provider name from `_active_screening_state`
- `active_model`: LLM model name from `_active_screening_state`
- `currently_screening`: paper title being processed, from `_active_screening_state`
- `stopping_active`: stop has been requested but the task has not yet finished

### 3.2 `POST /api/screening/start`

**Query parameters:**

| Parameter | Type   | Default | Valid values                    |
|-----------|--------|---------|---------------------------------|
| `mode`    | string | `"full"`| `"full"` or `"calibration"`     |
| `target`  | string | `"ALL"` | `"ALL"`, `"WL"`, or `"GL"`     |

**Response `200 OK`:**

```json
{
  "status": "started",
  "task_id": "screening_current"
}
```

**Error responses:**
- `400`: No dataset imported yet (`_dataset_path is None`)
- `409`: Screening is already running (`_screening_active is True`)

**Side effects:**
- Resets `_stopping_active = False`
- If `mode=calibration`: either reuses existing calibration paper IDs from DB, or marks 100 random papers as calibration sample
- If `mode=full`: clears calibration flags, trains SVM on human-audited decisions if any exist
- Cancels any stale screening task
- Sets `_screening_active = True` **synchronously** before `asyncio.create_task()`

### 3.3 `POST /api/screening/stop`

**No query parameters, no body.**

**Response `200 OK`:**

```json
{
  "status": "stopping"
}
```

**Error response:**
- `409`: `{"detail": "No screening is currently running."}` — when no task exists or the existing task is already done.

**Side effect:** Sets `_stopping_active = True` and calls `task.cancel()` on the running `asyncio.Task`.

### 3.4 `GET /api/settings/llm`

**No query parameters.**

**Response `200 OK`:**

```json
{
  "llm_provider": "groq",
  "llm_base_url": "https://api.groq.com/openai/v1",
  "llm_model": "llama-3.1-8b-instant",
  "llm_api_key": "****"
}
```

**API key masking:** When a non-empty key exists in the database, the response value is the literal string `"****"`. If no key is stored, the value is `""`. The actual secret is never transmitted to the client.

### 3.5 `PUT /api/settings/llm`

**Request body** (`LLMSettingsBody`):

```json
{
  "llm_provider": "groq",
  "llm_base_url": "https://api.groq.com/openai/v1",
  "llm_model": "llama-3.1-8b-instant",
  "llm_api_key": "gsk_..."
}
```

All fields are optional strings (default `""`).

**Response `200 OK`:**

```json
{
  "status": "saved"
}
```

**API key write logic:**
1. If the submitted key is empty `""` → **clears** the stored key.
2. If the submitted key is non-empty AND stripping asterisks leaves content (i.e. not `"****"`) → **saves** the new key.
3. If the submitted key is `"****"` or any all-asterisk string → **preserves** the previously stored key unchanged (no-op).

**Defaulting behavior:**
- `llm_base_url`: if empty, saved as `"http://localhost:11434/v1"` (with trailing `/` stripped)
- `llm_provider`: if empty, saved as `"ollama"`

### 3.6 `POST /api/settings/llm/test`

**Request body** — same `LLMSettingsBody` as PUT.

**Response `200 OK`:**

```json
{
  "success": true,
  "message": "Connected to groq successfully."
}
```

**Failure examples:**

```json
{"success": false, "message": "HTTP 401: {"error":"Unauthorized"}"}
{"success": false, "message": "Connection failed: ConnectError('...')"}
```

**Test payload:** Sends `POST /chat/completions` to the configured base URL with:
```json
{
  "model": "<configured model>",
  "messages": [{"role": "user", "content": "Respond with only the word OK"}],
  "temperature": 0.0,
  "max_tokens": 10
}
```

### 3.7 `GET /api/papers`

**Query parameters:**

| Parameter          | Type    | Default | Constraints                  |
|--------------------|---------|---------|------------------------------|
| `page`             | int     | `1`     | `>= 1`                       |
| `size`             | int     | `50`    | `>= 1, <= 500`               |
| `status`           | string? | `null`  | `"INCLUDED"`, `"EXCLUDED"`, `"NEEDS_REVIEW"` |
| `source_type`      | string? | `null`  | `"WL"` or `"GL"`             |
| `search`           | string? | `null`  | free text (searches title + abstract) |
| `title_contains`   | string? | `null`  | substring match on title      |
| `abstract_contains`| string? | `null`  | substring match on abstract   |
| `year_from`        | int?    | `null`  | `>= 1900, <= 2100`           |
| `year_to`          | int?    | `null`  | `>= 1900, <= 2100`           |

**Response `200 OK`:**

```json
{
  "page": 1,
  "size": 50,
  "total": 847,
  "total_pages": 17,
  "items": [
    {
      "id": "WOS-001234",
      "title": "Deep Learning for Requirements Engineering",
      "abstract": "This paper presents...",
      "source_library": "Web of Science",
      "source_type": "WL",
      "publication_year": 2023,
      "url": "https://doi.org/...",
      "status": "INCLUDED",
      "rationale": "**EC Analysis:** ... **Conclusion:** ...",
      "confidence_score": 0.95,
      "applied_criteria_codes": ["IC1", "IC4"],
      "human_decision": null,
      "q1": 1.0,
      "q2": 0.5,
      "q3": 0.5,
      "q4": 1.0,
      "quality_score": 0.75,
      "crawled_abstract": null
    }
  ]
}
```

- `applied_criteria_codes` is a JSON array (parsed from the semicolon-delimited TEXT column).
- Quality assessment keys (`q1`, `q2`, `q3`, `q4`, `quality_score`, `wl_quality_score`, etc.) are spread dynamically from the quality map — any key except `"full_text"` is included.
- `crawled_abstract` is the `full_text` from the quality map (the extracted/scraped content).

---

## 4. FRONTEND DESIGN SYSTEM & PALETTE

### 4.1 Framework & Build

- **React 18.3** with hooks (`useState`, `useEffect`, `useCallback`, `useRef`).
- **Vite 5.3** dev server (HMR, JSX via `@vitejs/plugin-react`).
- **Tailwind CSS 3.4** with PostCSS + Autoprefixer.
- **No routing library** — tabs are driven by a `viewTab` state variable.
- **Icons:** `lucide-react` ^0.400.0.

### 4.2 Color Palette — `cyber` Theme

Tailwind config extends the default palette with a custom `cyber` namespace:

| Token              | Hex       | Usage                                    |
|--------------------|-----------|------------------------------------------|
| `cyber-bg`         | `#09090b` | Page background (identical to `zinc-950`)|
| `cyber-surface`    | `#18181b` | Card/surface backgrounds                 |
| `cyber-border`     | `#27272a` | Borders and dividers                     |
| `cyber-text`       | `#d4d4d8` | Primary text color                       |
| `cyber-muted`      | `#71717a` | Secondary / muted text                   |
| `cyber-wl`         | `#22d3ee` | Cyan — WL accent (also `cyan-400`)       |
| `cyber-gl`         | `#d946ef` | Fuchsia — GL accent (also `fuchsia-400`) |
| `cyber-yes`        | `#10b981` | Emerald — Included / YES                 |
| `cyber-no`         | `#f43f5e` | Rose — Excluded / NO                     |
| `cyber-warn`       | `#f59e0b` | Amber — Pending / warnings               |

### 4.3 Neon Glow Shadows

| Class                 | Value                                     |
|-----------------------|-------------------------------------------|
| `shadow-neon-cyan`    | `0 0 15px rgba(34, 211, 238, 0.12)`       |
| `shadow-neon-fuchsia` | `0 0 15px rgba(217, 70, 239, 0.12)`       |
| `shadow-neon-cyan-lg` | `0 0 30px rgba(34, 211, 238, 0.15)`       |
| `shadow-neon-fuchsia-lg` | `0 0 30px rgba(217, 70, 239, 0.15)`    |

### 4.4 Custom Animations

| Class                  | Details                                                     |
|------------------------|-------------------------------------------------------------|
| `animate-neon-pulse`   | 2s ease-in-out infinite: opacity 1 → 0.85, filter brightness 1 → 1.3 at 50% |
| `animate-glide-in`     | 0.25s ease-out: opacity 0→1, translateY 6px→0              |
| `animate-slide-up`     | 0.3s ease-out: opacity 0→1, translateY 16px→0              |

### 4.5 Compositor Classes

| Class              | CSS                                                         |
|--------------------|-------------------------------------------------------------|
| `.cyber-card`      | `border border-cyber-border bg-cyber-surface/50 rounded-sm` |
| `.neon-border-wl`  | `border-cyan-900/50 shadow-neon-cyan`                       |
| `.neon-border-gl`  | `border-fuchsia-900/50 shadow-neon-fuchsia`                 |
| `.scanline-head`   | `background: linear-gradient(90deg, #09090b 0%, #18181b 50%, #09090b 100%); background-size: 200% 100%;` |

### 4.6 Typography

- **Font:** `font-mono` on root `<div>` — `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace`
- **Size scale:** `text-[9px]`, `text-[10px]`, `text-[11px]`, `text-[12px]`, `text-xs` (13px), `text-sm` (14px)
- **Common patterns:** `uppercase tracking-wider`, `tracking-widest`, `tabular-nums`, `text-zinc-500 font-bold text-[10px] uppercase tracking-widest` for `>`-prefixed section labels

### 4.7 Scrollbar Customization

```css
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #09090b; }
::-webkit-scrollbar-thumb { background: #27272a; border-radius: 0; }
::-webkit-scrollbar-thumb:hover { background: #3f3f46; }
```

### 4.8 State-Polling Lifecycle (App.jsx)

**Critical state variables:**

| Variable            | Initial | Purpose                                                |
|---------------------|---------|--------------------------------------------------------|
| `screeningActive`   | `false` | Controls display of ProgressCard and polling intervals |
| `progress`          | `null`  | Last response from `GET /api/screening/progress`        |
| `viewTab`           | `'explorer'` | Active tab: `explorer`, `prisma`, `audit`, `settings`, `llm`, `chat` |
| `page`, `size`, `total` | 1, 20, 0 | Paper table pagination                              |
| `statusFilter`, `literatureType` | `null`, `'ALL'` | Table filters                        |
| `filters`           | `{}`    | Advanced search filters                                |
| `screenStarted`     | `false` | Whether screening has started (not stopped)             |
| `calibrationBanner` | `false` | Whether calibration complete banner is shown            |

**Polling architecture (two overlapping intervals):**

1. **`App.jsx`** — `useEffect` with `4s` interval when `screeningActive === true`:
   - Calls `fetchPapersRef.current(true)` (silent papers table refresh)
   - Calls `fetchProgress()` (updates `progress` state)
   - Cleanup: `clearInterval` on deps change or unmount

2. **`ProgressCard.jsx`** — `useEffect` with `2s` interval when `active` prop is `true`:
   - Fetches `GET /api/screening/progress` directly
   - Calls `onProgressUpdate(res.json())` which bubbles to App's `handleProgressUpdate`
   - The `handleProgressUpdate` callback sets `progress` state and, importantly, **unconditionally** sets `screeningActive = false` when `!data.is_active` — this kills both intervals when the task finishes.

**Tab routing** (`viewTab` → component):

| Tab label             | `viewTab`   | Component            |
|-----------------------|-------------|----------------------|
| Dataset Explorer      | `'explorer'`| `<PaperTable>`       |
| PRISMA Flowchart      | `'prisma'`  | `<PrismaFlowchart>`  |
| Quality Audit         | `'audit'`   | `<AccuracyAudit>`    |
| Protocol Settings     | `'settings'`| `<ProtocolSettings>` |
| LLM Config            | `'llm'`     | `<LLMSettings>`      |
| Corpus Chat           | `'chat'`    | `<CorpusChat>`       |

Each tab button shows `text-cyan-400 border-b-2 border-cyan-500 pb-2 -mb-2.5` when active, `text-zinc-600 hover:text-zinc-400` when inactive.

### 4.9 Color-by-Semantic Conventions

- **Cyan** (`text-cyan-400`, `border-cyan-800`, `bg-cyan-950`): Active state, WL papers, primary accent, APOLLO branding, running indicator
- **Fuchsia** (`text-fuchsia-400`, `border-fuchsia-700`, `bg-fuchsia-950`): GL papers, calibration mode
- **Emerald** (`text-emerald-400`, `border-emerald-800`, `bg-emerald-950`): Included / YES, success, completed progress bar
- **Rose** (`text-rose-400`, `border-rose-800`, `bg-rose-950`): Excluded / NO, error states
- **Amber** (`text-amber-400`, `border-amber-700`, `bg-amber-950`): Pending, NEEDS_REVIEW, warnings
- **Zinc** (`zinc-950` → `zinc-300`): All surfaces, borders, neutral text

---

## 5. DIRECTORY STRUCTURE & DEPENDENCIES

### 5.1 Backend — `src/`

```
src/
  __init__.py
  api/
    __init__.py
    main.py                           # FastAPI app factory: CORS, static mount, lifespan
    routes.py                         # ALL route handlers (~996 lines): import, screening, export,
                                      #   audit, settings, quality assessment, chat
  domain/
    __init__.py                       # Re-exports core domain types
    criteria_config.py                # DEFAULT_CRITERIA: 11 predefined IC/EC criteria definitions
    enums.py                          # SourceType (WL|GL), CriterionType (INCLUSION|EXCLUSION),
                                      #   ScreeningStatus (INCLUDED|EXCLUDED|NEEDS_REVIEW)
    interfaces.py                     # ABCs: PaperRepository, LLMService, ScreeningDecisionRepository
    metrics.py                        # Confusion matrix, Cohen's Kappa, precision/recall/F1
    models.py                         # Pydantic models: Paper, Criterion, ScreeningDecision
  infrastructure/
    __init__.py
    repositories/
      __init__.py
      dataset_repository.py           # PaperRepository impl — reads Excel/CSV with WL/GL sheets
      sqlite_repository.py            # ScreeningDecisionRepository impl — SQLite: decisions, criteria, settings
    services/
      __init__.py
      ollama_service.py               # UnifiedLLMService — OpenAI-compatible /chat/completions wrapper
      scraper.py                      # Unpaywall DOI lookup + BeautifulSoup HTML scraper
      svm_service.py                  # SVM cascade (TfidfVectorizer + SGDClassifier) for fast-track exclusions
  use_cases/
    __init__.py
    export_papers.py                  # XLSX workbook generator — WL and GL sheets with criteria codes
    heuristic_screening.py            # Rule-based exclusions: non-English, short publications, pre-2015
    import_papers.py                  # Thin use case: paper_repo.get_all_papers()
    run_screening_pipeline.py         # Orchestrator: dedup → SVM → LLM semaphore → progress callback
    screen_paper.py                   # Composer: heuristic first, fallback to LLM
```

### 5.2 Frontend — `frontend/src/`

```
frontend/src/
  main.jsx                            # React entry: ReactDOM.createRoot, renders <App />
  index.css                           # Tailwind directives, custom scrollbar, cyber theme classes
  App.jsx                             # Root component: tab nav, state management, API helpers, layout
  components/
    UploadZone.jsx                     # File upload: drag-and-drop CSV/XLSX, import endpoint
    ProgressCard.jsx                   # Screening controls: start/stop, progress bar, live ticker, engine badge
    PaperTable.jsx                     # Paper list: paginated, filterable, expandable rows, bulk audit
    PrismaFlowchart.jsx                # PRISMA 2020 flowchart SVG: identification → screening → included
    AccuracyAudit.jsx                  # Audit panel: Kappa, confusion matrix, QA assessment launcher
    ProtocolSettings.jsx               # Criteria editor: IC/EC cards with save-to-backend
    LLMSettings.jsx                    # LLM config: provider dropdown, URL, model, API key, test button
    CorpusChat.jsx                     # Chat over included papers: LLM-powered Q&A
```

### 5.3 Backend Dependencies

| Package           | Version    | Role                                                   |
|-------------------|------------|--------------------------------------------------------|
| `fastapi`         | (recent)   | ASGI web framework — routing, validation, middleware    |
| `uvicorn`         | (recent)   | ASGI server — single-process event loop                |
| `pydantic`        | `>=2.0`    | Request/response model validation                      |
| `sqlite3`         | (stdlib)   | Embedded database                                      |
| `httpx`           | `>=0.28`   | Async HTTP client — LLM API calls, web scraping        |
| `pypdf`           | `>=5.0`    | PDF text extraction                                    |
| `beautifulsoup4`  | `>=4.0`    | HTML parsing for web scraping                          |
| `scikit-learn`    | `>=1.0`    | SVM classifier (TfidfVectorizer + SGDClassifier)       |
| `pandas`          | `>=2.0`    | Excel/CSV dataset parsing                              |
| `openpyxl`        | `>=3.0`    | XLSX workbook generation                               |
| `python-multipart`| (any)      | File upload form parsing                               |
| `tqdm`            | `>=4.0`    | Console progress bar (screening pipeline)              |
| `python-dotenv`   | `>=1.0`    | .env file loading                                      |
| `pytest`          | `>=8.0`    | Test framework                                         |
| `pytest-mock`     | `>=3.0`    | Mocking support                                        |
| `pytest-asyncio`  | `>=0.25`   | Async test fixture support                             |

### 5.4 Frontend Dependencies

| Package            | Version    | Role                                    |
|--------------------|------------|-----------------------------------------|
| `react`            | `^18.3.1`  | UI framework                            |
| `react-dom`        | `^18.3.1`  | React DOM renderer                      |
| `lucide-react`     | `^0.400.0` | Icon component library (50+ icon types) |
| `vite`             | `^5.3.1`   | Build tool / dev server                 |
| `@vitejs/plugin-react` | `^4.3.1` | Vite HMR + JSX transform                |
| `tailwindcss`      | `^3.4.4`   | Utility-first CSS                       |
| `postcss`          | `^8.4.38`  | CSS post-processor                      |
| `autoprefixer`     | `^10.4.19` | Vendor prefix injection                 |
