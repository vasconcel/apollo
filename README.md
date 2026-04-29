# AIMS - AI-Powered Multivocal Literature Review Systematic Pipeline

<div align="center">

**AIMS** is an open-source, modular pipeline for conducting Systematic Literature Reviews (SLR) and Multivocal Literature Reviews (MLR) in Software Engineering and related fields.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

</div>

## Overview

AIMS supports the systematic collection and analysis of academic literature from both **White Literature** (WL) - peer-reviewed journals and conferences from WoS/Scopus - and **Grey Literature** (GL) - preprints, technical reports, and other non-peer-reviewed sources.

The pipeline follows the methodology proposed by Garousi et al. for multivocal literature reviews and can optionally integrate with LLMs for AI-assisted screening.

## Features

- **Multi-format Import**: Supports BibTeX, RIS, Excel, and Web of Science TSV formats
- **Automatic Deduplication**: Removes duplicates via DOI and title matching
- **Configurable Criteria**: Define your own Inclusion/Exclusion/Quality criteria via JSON
- **AI-Assisted Screening**: Optional integration with Groq LLM for smart recommendations
- **Streamlit Dashboard**: Interactive UI for screening and dataset exploration

## Prerequisites

- Python 3.10 or higher
- pip package manager

## Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-repo/aims.git
cd aims
```

2. **Create and activate virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

## Setup

### Step 1: Configure Your Project

1. Duplicate the template configuration file:
```bash
cp project_config_template.json project_config.json
```

2. Edit `project_config.json` with your research details:
   - Set `project_name` and `description`
   - Define your `research_questions`
   - Customize `inclusion_criteria` and `exclusion_criteria`
   - Adjust `quality_criteria` for WL and GL sources

### Step 2: Set Up API Key (Optional)

For AI-assisted screening, create a `.env` file:

```bash
cp .env.example .env
```

Edit `.env` and add your Groq API key:
```
GROQ_API_KEY=your_api_key_here
```

You can get a free API key at [groq.com](https://groq.com).

## Project Structure

```
aims/
├── project_config_template.json   # Template for your research configuration
├── project_config.json          # Your customized configuration
├── data/
│   ├── raw/
│   │   ├── wl/              # White Literature input files
│   │   └── gl/              # Grey Literature input files
│   ├── processed/          # Converted CSV files
│   └── master_table.csv     # Final merged dataset
├── src/
│   └── core/               # Core pipeline modules
├── app/                    # Streamlit dashboard
├── logs/                   # Execution logs
├── output/                 # Results and exports
└── README.md
```

## Usage

### Running the Pipeline

1. **Step 1: Convert raw files to CSV**
```bash
python -m src.core.converter
```

2. **Step 2: Ingest and create master table**
```bash
python -m src.core.ingestion
```

3. **Step 3: Run the dashboard (optional)**
```bash
streamlit run app/main.py
```

## Configuration Reference

### project_config.json Structure

```json
{
  "project_name": "My SLR Project",
  "research_questions": ["RQ1: ...", "RQ2: ..."],
  "inclusion_criteria": {"IC1": "Description", ...},
  "exclusion_criteria": {"EC1": "Description", ...},
  "quality_criteria": {"WL": {...}, "GL": {...}},
  "column_aliases": {"Original": "canonical", ...},
  "source_columns": ["title", "year", ...]
}
```

## Documentation

For detailed methodology and examples, see the [Wiki](https://github.com/your-repo/aims/wiki).

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please read the CONTRIBUTING.md for guidelines.

## Citation

If you use AIMS in your research, please cite:

```
@software{aims2025,
  title = {AIMS - AI-Powered Multivocal Literature Review Pipeline},
  author = {Your Name},
  year = {2025},
  url = {https://github.com/your-repo/aims}
}
```

---

<div align="center">

**AIMS** - Empowering Systematic Literature Reviews with AI 🚀

</div>