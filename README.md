# AIMS - AI-Powered Multivocal Literature Review Systematic Pipeline

<div align="center">

**AIMS** is a complete, end-to-end platform for conducting Systematic Literature Reviews (SLR) and Multivocal Literature Reviews (MLR) in Software Engineering and related fields, following the Garousi et al. (2019) methodology.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Feature--Complete-brightgreen)

</div>

## 🚀 Overview

AIMS is a **full-stack research platform** that operationalizes the complete multivocal literature review protocol:

- **Data Ingestion**: Import White Literature (WL) and Grey Literature (GL) from multiple formats
- **Formal Screening**: Criteria-driven decision making with explicit exclusions
- **Multi-Reviewer Consensus**: Inter-rater reliability (Cohen's Kappa) and conflict resolution
- **Qualitative Synthesis**: Open coding, thematic organization, and traceable synthesis
- **AI-Powered Insights**: Comparative WL/GL synthesis using LLMs
- **Publication-Ready Export**: Audit trails, traceability matrices, and research packages

## 📊 Architecture vs Protocol Mapping

| UI Page | Protocol Stage | Description |
|--------|-------------|------------|
| **Overview** | Step 1-2: Planning | PRISMA Flow Diagram, Research Questions, Project Metrics |
| **Screening** | Step 3.1.1: Title/Abstract Screening | Formal Eligibility Criteria Funnel (IC/EC selection) |
| **Consensus** | Step 3.1.3: Conflict Resolution | Kappa calculation, Conflict Resolver, Auto-consensus |
| **Quality Assessment** | Step 3.2: Quality Appraisal | WL/GL quality criteria scoring |
| **Extraction** | Step 3.2.1: Data Extraction | Fragment extraction with RQ categorization |
| **Synthesis** | Step 3.3: Thematic Synthesis | Open coding, Theme organization, Traceability |
| **Export & Audit** | Step 4: Reporting | Audit Dashboard, Data Export, System Health |

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

### Starting AIMS
```bash
cd aims
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

### Workflow
1. **Import Data** → Use Data Exchange page to import CSV/Excel files
2. **Screen Articles** → Each reviewer performs formal screening
3. **Resolve Conflicts** → Use Consensus page to mediate disagreements
4. **Quality Assessment** → Score included articles
5. **Extract Evidence** → Create fragments for analysis
6. **Code & Thematize** → Use Synthesis pages
7. **Generate AI Insights** → Run comparative synthesis
8. **Audit & Export** → Validate and export

## 📁 Project Structure

```
aims/
├── app.py                      # Main Streamlit application
├── database.py                 # SQLite database with full schema
├── requirements.txt           # Python dependencies
├── project_config.json         # Research configuration
├── research_export/         # Generated export files
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

AIMS integrates with Groq LLMs for:
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

**AIMS** - From Raw Data to publishable insights with full traceability 🔬

</div>