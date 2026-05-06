# APOLLO - AI-Powered Multivocal Literature Review Systematic Pipeline

<div align="center">

**APOLLO** is a complete, end-to-end platform for conducting Systematic Literature Reviews (SLR) and Multivocal Literature Reviews (MLR) in Software Engineering and related fields, following the Garousi et al. (2019) methodology.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-Research-brightgreen)

</div>

## 🚀 Overview

APOLLO is a **full-stack research platform** that operationalizes the complete multivocal literature review protocol:

- **Data Ingestion**: Import White Literature (WL) and Grey Literature (GL) from multiple formats
- **Formal Screening**: Criteria-driven decision making with explicit exclusions
- **Multi-Reviewer Consensus**: Inter-rater reliability (Cohen's Kappa) and conflict resolution
- **Qualitative Synthesis**: Open coding, thematic organization, and traceable synthesis
- **AI-Powered Insights**: Comparative WL/GL synthesis using LLMs
- **Publication-Ready Export**: Audit trails, traceability matrices, and research packages

## 📊 Current Status

- **Project**: SE R&S Multivocal Literature Review (Software Engineering Recruitment & Selection)
- **Research Questions**: 5 defined (RQ1-RQ5 covering distribution, conceptualization, challenges, practices, WL/GL divergence)
- **Inclusion Criteria**: IC1-IC5 defined
- **Exclusion Criteria**: EC1-EC6 defined (language, availability, publication length, date, relevance, duplicates)
- **Data Sources**: 5 imported (WoS, Scopus, Springer Nature, IEEE Xplore, ACM)

## 📊 Architecture vs Protocol Mapping

| UI Page | Protocol Stage | Description |
|--------|-------------|------------|
| **Planning** | Step 1-2 | Research Questions, Inclusion/Exclusion Criteria |
| **Ingestion** | Search | WL/GL Import from multiple sources |
| **Overview** | Step 1-2: Planning | PRISMA Flow Diagram, Research Questions, Project Metrics |
| **Screening** | Step 3.1.1: Title/Abstract Screening | Formal Eligibility Criteria Funnel (IC/EC selection) |
| **Consensus** | Step 3.1.3: Conflict Resolution | Kappa calculation, Conflict Resolver, Auto-consensus |
| **Quality Assessment** | Step 3.2: Quality Appraisal | WL/GL quality criteria scoring |
| **Extraction** | Step 3.2.1: Data Extraction | Fragment extraction with RQ categorization |
| **Synthesis** | Step 3.3: Thematic Synthesis | Open coding, Theme organization, Traceability |
| **Export & Audit** | Step 4: Reporting | Audit Dashboard, Data Export, System Health |

## 📊 Current Research Status

### Active Project
- **Topic**: SE R&S Multivocal Literature Review (Software Engineering Recruitment & Selection)
- **Methodology**: Garousi et al. (2019)
- **Database**: SQLite with full schema (aims.db)

### Research Questions (RQ1-RQ5)
1. Distribution, nature, and temporal evolution of academic and industry sources
2. Conceptualization of SE R&S and pipeline stages
3. Challenges and friction points across SE R&S pipeline
4. Practices and design principles for effective SE R&S
5. Alignment/divergence between WL and GL perspectives

### Criteria
- **IC1-IC5**: Inclusion criteria defined
- **EC1-EC6**: Exclusion criteria (English, availability, publication length ≥2015, relevance, duplicates)

### Imported Data Sources
- Web of Science (WoS)
- Scopus
- Springer Nature
- IEEE Xplore
- ACM Digital Library

### Testing
- **Unit Tests**: ~127 tests covering core services
- **Integration Tests**: Database, config management

## 🔑 Key Features

### 1. Formal Eligibility Criteria Funnel
Every exclusion decision MUST be tied to a formal Exclusion Criterion (EC). Every inclusion CAN optionally track which Inclusion Criteria (IC) were met. This ensures:
- **Transparency**: Every decision has an explicit rationale
- **Auditability**: Complete traceability of screening logic
- **Reproducibility**: Methodology is formally documented

### 2. Inter-Reviewer Reliability
- **Cohen's Kappa**: Automatically calculates inter-rater agreement
- **Interpretation Guide**: Formal interpretation (Poor/Fair/Moderate/Good/Excellent)
- **Conflict Resolver**: Side-by-side review of disagreement cases with required resolution notes.
- **Auto-Consensus**: Automatically finalizes unanimous decisions

### 3. Complete Traceability Matrix
The system maintains full semantic traceability:
```
Theme → Codes → Fragments → Source Articles
```
Every piece of evidence can be traced back to its original source.

### 4. AI-Powered Comparative Synthesis
The **AI Insight Generator** in the Traceability Matrix tab automatically:
- Separates fragments by literature type (WL vs GL)
- Generates professional comparative synthesis
- Identifies theory-practice gaps (RQ5)
- Highlights actionable practices
- Documents research gaps

### 5. Audit Dashboard
Before export, the system validates:
- **Orphaned Fragments**: Extracted but never coded
- **Orphaned Codes**: Created but never linked to themes
- **Coverage Gaps**: Included articles with no fragments

### 6. Publication-Ready Exports
Generates:
- `traceability_matrix.csv` - Full hierarchical chain
- `fragments_with_sources.csv` - All evidence with metadata
- `codes.csv` - Codebook with RQ associations
- `themes.csv` - Theme definitions
- `aims_research_package.zip` - Complete replication package

## 🖥️ Usage

### Starting APOLLO
```bash
streamlit run app.py
```

### Environment Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure (optional) Groq API key for AI features:
```bash
export GROQ_API_KEY=your_key_here
```

### Environment Setup
1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure (optional) Groq API key for AI features:
```bash
export GROQ_API_KEY=your_key_here
```

### Workflow
1. **Plan** → Define RQs and criteria in Planning page
2. **Import Data** → Use Ingestion page to import CSV/Excel files (WoS, Scopus, Springer, IEEE, ACM)
3. **Screen Articles** → Each reviewer performs formal screening
4. **Resolve Conflicts** → Use Consensus page to mediate disagreements
5. **Quality Assessment** → Score included articles
6. **Extract Evidence** → Create fragments for analysis
7. **Code & Thematize** → Use Synthesis pages
8. **Generate AI Insights** → Run comparative synthesis
9. **Audit & Export** → Validate and export

## 📁 Project Structure

```
rs-se-mlr-pipeline/
├── app/main.py                 # Main Streamlit application (v2)
├── src/                      # Core modules
│   ├── core/                # Business logic (database, services, ingestion, etc.)
│   └── ui/modules/          # UI views (screening, consensus, synthesis, etc.)
├── backend/                 # FastAPI backend (optional)
├── data/raw/wl/             # White literature imports
├── data/raw/gl/             # Grey literature imports
├── tests/                   # Unit and integration tests
├── aims.db                 # SQLite database
└── README.md
```

## 🔍 Reliability Metrics

The system calculates and reports:

| Metric | Description |
|--------|------------|
| **Cohen's Kappa** | Inter-reviewer agreement (0-1) |
| **Conflict Rate** | % of articles with disagreement |
| **Resolution Rate** | % of conflicts resolved |
| **Coverage** | % of included articles with fragments |

## 🤖 AI Integration

APOLLO integrates with Groq LLMs for:
- **Screening Recommendations**: AI suggests include/exclude with confidence
- **Comparative Synthesis**: WL vs GL analysis

Configure via `GROQ_API_KEY` environment variable.

## 📋 Database Schema

Key tables:
- `articles` - Source articles
- `screening_decisions` - Multi-reviewer screening decisions with criteria
- `final_decisions` - Resolved consensus decisions
- `quality_assessments` - QC scores
- `fragments` - Extracted evidence
- `codes` - Open codes
- `themes` - Thematic groupings
- `fragment_codes` - Code-fragment links
- `code_themes` - Code-theme links

## 📄 License

MIT License - See LICENSE file

## 🙏 Acknowledgments

Built following the Garousi et al. (2019) methodology for multivocal literature reviews in Software Engineering.

---

<div align="center">

**APOLLO** - From Raw Data to publishable insights with full traceability 🔬

</div>