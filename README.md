# APOLLO — AI-Assisted Systematic Literature Review Engine

**APOLLO** is a local-first, privacy-focused platform for conducting and auditing Systematic Literature Reviews (SLR) and Multivocal Literature Reviews (MLR). It combines deterministic heuristic filters, locally-hosted Large Language Model (LLM) screening, automated quality assessment, and an interactive PRISMA 2020 flowchart into a single, self-contained web application.

---

## Abstract

Systematic Literature Reviews remain a cornerstone of evidence synthesis in Software Engineering and related disciplines, yet they are notoriously time-consuming and labour-intensive. APOLLO addresses this bottleneck through a three-stage AI-assisted pipeline that runs entirely on the researcher's own hardware — no data ever leaves the local machine. The platform supports **Stage 1 Heuristics** (millisecond-level deterministic exclusion rules), **Stage 2 AI Screening** (locally-hosted LLM inference via Ollama), and **Stage 3 Quality Assessment** (automated methodological evaluation of included studies). A built-in **Calibration & Certification Phase** allows researchers to audit LLM decisions against a human-labelled gold-standard sample, producing a confusion matrix, Cohen's Kappa, precision, recall, and F1-score before authorising a full-scale run. The system exposes a real-time PRISMA 2020 flowchart, a privacy-preserving RAG chatbot over the included corpus, and comprehensive XLSX export with full audit trails.

---

## Key Architectural Features

### Three-Stage Screening Pipeline

| Stage | Component | Description |
|-------|-----------|-------------|
| **1** | Heuristics | Instant deterministic filters — duplicate detection (EC6), publication year < 2015 (EC4), short papers / editorials (EC3), non-English language (EC1). Runs in milliseconds with no LLM dependency. |
| **2** | AI Screening | Locally-hosted LLM (`qwen2.5:7b-instruct-q4_K_M` via Ollama) evaluates each paper against configurable inclusion/exclusion criteria. Uses dual-concurrency semaphore locks and deterministic `temperature=0.0` for reproducible decisions. |
| **3** | Quality Assessment | Automated methodological quality scoring (Q1–Q4) for included papers. WL papers trigger a DOI-based open-access PDF crawl (Unpaywall API + `pypdf`) for full-text extraction before evaluation. |

### Calibration & Certification Phase

Before executing a full screening run, APOLLO guides the researcher through a mandatory calibration workflow:

1. A stratified 100-paper sample (proportional across WL and GL sources) is drawn from the deduplicated dataset.
2. The AI screens the sample while the researcher independently audits each decision (INCLUDED / EXCLUDED).
3. The system computes a **Confusion Matrix**, **Cohen's Kappa**, **Precision**, **Recall**, and **F1-Score** from the human-vs-AI comparison.
4. Only after the researcher certifies the calibrated model can the full pipeline proceed.

This design ensures transparency and provides quantitative evidence of AI reliability for audit trails and methodological appendices.

### Privacy & Local-First Architecture

- **No external API calls** for screening — all LLM inference runs on the local machine via Ollama.
- The SQLite database (`data/processed/screening.db`) persists all decisions, criteria, calibration state, and quality scores.
- The imported dataset file is stored under `data/imported/` and is cleaned on reset.
- The entire application serves from `127.0.0.1`; no telemetry, no tracking, no cloud dependencies.

### Interactive PRISMA 2020 Flowchart

The PRISMA tab renders a real-time Sankey-style flowchart showing:
- Records identified (split by WL / GL source)
- Duplicates removed (EC6)
- Records screened (heuristic exclusions, AI exclusions)
- Studies included in synthesis

All counts update live as the screening pipeline progresses.

### Corpus Chat (Private RAG)

A local Retrieval-Augmented Generation chatbot that allows the researcher to query the included literature corpus using natural language. The system dynamically compiles paper metadata, abstracts, and full-text PDFs into the LLM context window. All processing stays on the local GPU — no data is sent to external services.

### Dynamic Protocol Configuration

Researchers can edit inclusion/exclusion criteria (titles, descriptions) live through the Protocol Settings tab. Changes are compiled into the LLM prompt on the next screening request without requiring a server restart.

---

## Technical Stack

### Backend

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.12+ |
| Web Framework | FastAPI (ASGI via Uvicorn) |
| Database | SQLite 3 (via `sqlite3` stdlib) |
| Data Processing | pandas, openpyxl |
| LLM Client | httpx (Ollama API) |
| PDF Extraction | pypdf, BeautifulSoup, Unpaywall API |
| Testing | pytest, pytest-asyncio, pytest-mock |

### Frontend

| Component | Technology |
|-----------|-----------|
| Framework | React 18 |
| Build Tool | Vite 5 |
| Styling | Tailwind CSS 3 |
| Icons | Lucide React |
| HTTP | Fetch API (thin `apiFetch` wrapper) |

### LLM Host

- **Ollama** (local inference server)
- Recommended model: `qwen2.5:7b-instruct-q4_K_M`
- GPU acceleration via CUDA / Metal (optional, CPU fallback supported)

---

## Project Structure

```
apollo/
├── frontend/                  # React + Vite single-page application
│   ├── src/
│   │   ├── components/        # UI components (ProgressCard, PaperTable, etc.)
│   │   ├── App.jsx            # Root application component
│   │   └── main.jsx           # Entry point
│   ├── dist/                  # Production build output
│   ├── index.html
│   ├── tailwind.config.js
│   └── vite.config.js
├── src/                       # Python backend
│   ├── api/
│   │   ├── main.py            # FastAPI app factory (CORS, static mount)
│   │   └── routes.py          # All REST endpoints
│   ├── domain/
│   │   ├── enums.py           # SourceType, ScreeningStatus, CriterionType
│   │   ├── interfaces.py      # Abstract repositories & services
│   │   ├── metrics.py         # Cohen's Kappa, confusion matrix, F1
│   │   └── models.py          # Paper, ScreeningDecision, Criterion
│   ├── infrastructure/
│   │   ├── repositories/
│   │   │   ├── dataset_repository.py   # Excel/CSV paper parser
│   │   │   └── sqlite_repository.py    # SQLite-backed decision store
│   │   └── services/
│   │       ├── ollama_service.py       # LLM screening & QA client
│   │       └── scraper.py              # PDF metadata via DOI
│   └── use_cases/
│       ├── export_papers.py
│       ├── heuristic_screening.py
│       ├── import_papers.py
│       ├── run_screening_pipeline.py
│       └── screen_paper.py
├── tests/                     # pytest test suite (167 tests)
├── data/                      # Runtime data directory
│   ├── imported/              # Uploaded dataset files
│   └── processed/             # SQLite DB, exports
├── .env                       # Local configuration (copy of .env.example)
├── .env.example               # Configuration template
├── requirements.txt           # Python dependencies
├── run.py                     # Unified development & production launcher
└── README.md
```

---

## Installation

### Prerequisites

- **Python 3.12+** with `pip` and a virtual environment (`venv` or Conda)
- **Node.js 20+** and **npm** (for frontend build)
- **Ollama** installed and running with a compatible model:
  ```bash
  # Install Ollama: https://ollama.com/download
  ollama pull qwen2.5:7b-instruct-q4_K_M
  ```

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd apollo
   ```

2. **Create and activate a Python virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS / Linux:
   source .venv/bin/activate
   ```

3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to match your setup — default values work with a local Ollama instance:
   ```ini
   OLLAMA_BASE_URL=http://localhost:11434/v1
   OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M
   ```

5. **Install frontend dependencies (automatic on first build):**
   ```bash
   cd frontend && npm install && cd ..
   ```

6. **Ensure Ollama is running** with the configured model loaded:
   ```bash
   ollama list                     # verify qwen2.5:7b-instruct-q4_K_M is present
   ```

---

## Running

APOLLO ships with a unified launcher (`run.py`) supporting two modes:

### Development Mode (Hot-Reload)

```bash
python run.py --dev
```

- Launches **Uvicorn** with `--reload` (backend auto-restarts on file changes) on port `8000`.
- Launches **Vite dev server** (HMR for React components) on port `5173`.
- Opens the browser at `http://127.0.0.1:5173/`.
- Backend API calls are proxied through Vite's dev server.

### Production Mode

```bash
python run.py                 # build (if needed) + serve
python run.py --build         # force rebuild frontend + serve
python run.py --port 8080     # custom port
```

- Builds the React frontend into `frontend/dist/`.
- Serves both the API and the built frontend from a single Uvicorn process on port `8000` (or custom port).
- Opens the browser at `http://127.0.0.1:8000/`.

---

## Usage Workflow

1. **Import Dataset** — Upload an Excel (`.xlsx` / `.xls`) or CSV file containing paper records. The parser auto-detects WL (white literature) and GL (grey literature) sheets by name pattern and maps column names in English or Portuguese.
2. **Calibration** — Click *"Start Calibration (100 Paper Sample)"*. The AI screens a stratified 100-paper sample. Review the results in the Quality Audit tab, provide human decisions, and inspect the metrics (confusion matrix, Kappa, precision, recall, F1).
3. **Full Screening** — Once calibrated, click *"Start Full Screening"*. The AI processes all remaining papers. Progress is displayed in real-time with live telemetry.
4. **Quality Assessment** — For included papers, run automated quality scoring (Q1–Q4) or assess manually.
5. **Export** — Download an XLSX workbook with separate WL and GL sheets, complete with headers, merged cells, formatted columns, and comment placeholders for dual-revisor auditing.
6. **Corpus Chat** — Query your included literature using natural language through the private RAG chatbot.

---

## Testing

```bash
# Run the full test suite (167 tests)
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run a specific test file
pytest tests/test_api.py -v
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/import` | Upload a dataset file (Excel or CSV) |
| `POST` | `/api/screening/start` | Start screening (`mode=full\|calibration`, `target=ALL\|WL\|GL`) |
| `GET` | `/api/screening/progress` | Get current screening progress and telemetry |
| `GET` | `/api/papers` | List papers with pagination, filtering (status, source, search, year) |
| `POST` | `/api/papers/{id}/audit` | Submit a human audit verdict (YES / NO) |
| `POST` | `/api/papers/bulk-audit` | Bulk audit (YES / NO / RESET / CLEAR) |
| `GET` | `/api/audit/sample` | Get a stratified audit sample |
| `GET` | `/api/audit/metrics` | Compute audit metrics (confusion matrix, Kappa, F1) |
| `GET` | `/api/calibration/papers` | List calibration sample papers |
| `POST` | `/api/papers/{id}/quality` | Submit quality assessment (Q1–Q4) |
| `POST` | `/api/quality/assess-all` | Run automated quality assessment on all included papers |
| `GET` | `/api/criteria` | List screening criteria |
| `PUT` | `/api/criteria/{id}` | Update a criterion's title and description |
| `GET` | `/api/export` | Download screening results as XLSX |
| `POST` | `/api/system/reset` | Reset all data (clears DB, removes imported file) |
| `POST` | `/api/chat` | Query the included literature corpus via RAG |

---

## Configuration Reference

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama API endpoint (OpenAI-compatible) |
| `OLLAMA_MODEL` | `qwen2.5:7b-instruct-q4_K_M` | LLM model for screening and QA |
| `APOLLO_DB_PATH` | `data/processed/screening.db` | SQLite database file location |
| `APOLLO_LLM_BASE_URL` | *(falls back to `OLLAMA_BASE_URL`)* | LLM base URL override |
| `APOLLO_LLM_MODEL` | *(falls back to `OLLAMA_MODEL`)* | LLM model override |
| `APOLLO_PORT` | `8000` | Server port (used by `run.py`) |

---

## License

This project is provided for academic and research purposes. No external dependencies transmit data off-host. All LLM inference is performed locally via Ollama. Users are responsible for compliance with their institutional ethics guidelines regarding AI-assisted systematic reviewing.

---

## Citation

If you use APOLLO in your research, please cite the repository:

```
@software{apollo_slr_2025,
  title = {APOLLO: AI-Assisted Systematic Literature Review Engine},
  version = {1.0.0},
  url = {<repository-url>}
}
```
