# AIMS Contributing Guide

## Developer Quickstart

### Prerequisites
- Python 3.10+
- pip install -r requirements.txt

### Running Tests
```bash
# Run all tests with coverage
pytest --cov=src.core tests/

# Run specific test file
pytest tests/unit/test_metrics.py -v
```

### Test Architecture

This project follows **Test-Driven Development (TDD)** with 82+ automated tests:

#### Test Structure
```
tests/
├── conftest.py              # Shared fixtures (temp DB, sample data)
├── unit/
│   ├── test_analytics.py     # Cohen's Kappa calculations
│   ├── test_metrics.py        # Precision/Recall/F1 metrics
│   ├── test_ingestion.py     # DOI/Year normalization
│   ├── test_quality.py       # QA threshold logic
│   ├── test_active_learning.py
│   ├── test_ai_handler.py
│   └── test_pdf_processor.py
└── integration/
    ├── test_database.py      # Real SQLite CRUD ops
    └── test_config_manager.py
```

#### Key Testing Principles

1. **No Mocking of SUT**: Integration tests hit real SQLite via `temp_db_file` fixture
2. **Edge Cases**: ZeroDivisionError handling in metrics, empty DataFrames in Kappa
3. **Authentic Assertions**: Tests WRITE to DB and READ BACK to verify persistence

### Running the App
```bash
streamlit run app.py
```

### Code Coverage
- Core modules: ~38% (database has many error paths)
- Critical paths: 100% (metrics, quality, analytics)

### Modules

| Module | Purpose |
|--------|---------|
| `database.py` | SQLite CRUD with FK constraints |
| `analytics.py` | Cohen's Kappa with edge cases |
| `metrics.py` | Precision/Recall/F1 |
| `active_learning.py` | Few-shot AI training |
| `ai_handler.py` | LLM integration with retry |
| `pdf_processor.py` | PDF text extraction |
| `ingestion.py` | CSV/BibTeX/RIS import |

### Adding New Features

1. Write test first in `tests/unit/`
2. Implement in `src/core/`
3. Add integration test in `tests/integration/`
4. Ensure 100% pass: `pytest tests/`

### CI/CD

Tests run automatically on each commit. Coverage report generated via `--cov`.
