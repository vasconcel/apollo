# APOLLO Researcher Quickstart Guide

## For Researchers - No Technical Background Required

---

## What is APOLLO?

APOLLO is a **screening tool** for systematic literature reviews. It helps you decide which research papers are relevant to your study by automatically applying consistent rules.

Think of it as:
- A **fast, consistent reviewer** that never gets tired
- A way to **document your decisions** for audit trails
- A method to make your **review reproducible**

---

## What You Need to Prepare

### Step 1: Get Your Data from ATLAS

APOLLO works with **ATLAS Excel exports**. Your data should have two sheets:

#### Sheet 1: White Literature (WL)
These are peer-reviewed academic papers.

| Column | What to Put | Required? |
|--------|-------------|-----------|
| Library | Database name (e.g., "Scopus", "IEEE") | Yes |
| Global_ID | Unique paper ID (DOI or database ID) | Yes |
| Local_ID | Your local reference number | Yes |
| Title | Paper title | Yes |
| Abstract | Paper abstract (at least 50 characters) | Yes |
| Keywords | Keywords from the paper | Optional |

#### Sheet 2: Grey Literature (GL)
These are non-peer-reviewed sources (tech blogs, industry reports, etc.).

| Column | What to Put | Required? |
|--------|-------------|-----------|
| Posicao | Order number | Yes |
| Title | Source title | Yes |
| URL | Link to source | Yes |
| Source_File | File name | Yes |

### Step 2: Save Your File

Save your ATLAS export as an Excel file (`.xlsx`). For example:
- `my_systematic_review_input.xlsx`

---

## How to Run APOLLO

### Option 1: Using the Graphical Interface (Recommended)

1. Open your terminal/command prompt
2. Navigate to the APOLLO folder
3. Run this command:
   ```
   streamlit run app.py
   ```
4. A web page will open in your browser
5. Upload your Excel file
6. Click "Process ATLAS File"

### Option 2: Using Command Line

1. Open your terminal/command prompt
2. Navigate to the APOLLO folder
3. Run this command:
   ```
   python scripts/process_atlas.py your_file.xlsx
   ```
4. The results will be saved as `APOLLO_Selection_Criteria.xlsx`

---

## Understanding the Results

### What Does APOLLO Do?

APOLLO applies **three stages** of evaluation:

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: Exclusion Criteria (EC)                           │
│                                                             │
│ • EC1: Is it about software engineering?                   │
│ • EC2: Was it published after 2015?                        │
│ • EC3: Does it have enough abstract? (WL only)            │
│ • EC4: Is it a duplicate?                                  │
│                                                             │
│ If ANY fail → Paper is EXCLUDED                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: Inclusion Criteria (IC)                           │
│                                                             │
│ • IC1: Does it discuss recruitment/selection?              │
│ • IC2: Does it report empirical findings?                 │
│ • IC3: Is it about software industry?                     │
│                                                             │
│ Need IC1 + (IC2 OR IC3) → Paper is INCLUDED               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: Quality Criteria (QC)                             │
│                                                             │
│ WL Papers: WL-Q1 through WL-Q4 (score 0-4)                │
│ GL Papers: GL-Q1 through GL-Q4 (score 0-4)                │
│                                                             │
│ Total score ≥ 2.0 → INCLUDE                                │
│ Total score < 2.0 → EXCLUDE                                │
└─────────────────────────────────────────────────────────────┘
```

### Understanding the Output Columns

#### White Literature Output
| Column | Meaning |
|--------|---------|
| CEs1 | Exclusion Criteria result (e.g., "NO" = passed, "EC1" = failed on EC1) |
| CIs1 | Inclusion Criteria result |
| Decision | Final decision: "INCLUDE" or "EXCLUDE" |

#### Grey Literature Output
| Column | Meaning |
|--------|---------|
| Revisor 1 EC | Exclusion result |
| Revisor 1 IC | Inclusion result (usually "SKIPPED" for GL) |
| Decision | Final decision |

---

## What Do the Decision Codes Mean?

### Exclusion Criteria (EC)
| Code | Meaning |
|------|---------|
| NO | Passed (not excluded) |
| EC1 | No software engineering context |
| EC2 | Published before 2015 |
| EC3 | No sufficient abstract (WL only) |
| EC4 | Duplicate of another paper |

### Inclusion Criteria (IC)
| Code | Meaning |
|------|---------|
| NO | Passed (included) |
| IC1 | Doesn't address recruitment/selection |
| IC2 | No empirical context |
| SKIPPED | Not evaluated (GL has no abstract) |

### Quality Criteria (QC)
| Score | Meaning |
|-------|---------|
| 4.0/4 | Excellent - all criteria met |
| 3.0/4 | Good - most criteria met |
| 2.0/4 | Acceptable - borderline |
| Below 2.0 | Below threshold - excluded |

---

## Deterministic Runs: What Does It Mean?

APOLLO is **deterministic**, meaning:
- Same input file + same settings = **exactly same results** every time
- You can re-run and get identical decisions
- This makes your systematic review **reproducible**

### Why This Matters for Research

1. **Auditable**: Anyone can verify your decisions
2. **Reproducible**: Re-run to confirm results
3. **Consistent**: No human variation between runs
4. **Documented**: Every run creates an audit log

---

## Protocol Versions: What You Need to Know

APOLLO uses **protocols** to define its evaluation criteria. The default protocol is version 1.0.

- **Default Protocol**: Standard EC/IC/QC rules (recommended for most reviews)
- **Custom Protocol**: You can create your own rules (advanced)

For your first several reviews, use the **Default Protocol**.

---

## Common Problems and Solutions

### Problem: "Missing required columns"

**Cause**: Your Excel file is missing necessary columns.

**Solution**: Check that your WL sheet has: Library, Global_ID, Local_ID, Title, Abstract, Keywords

### Problem: "No articles included"

**Cause**: Your papers might not match APOLLO's criteria.

**Solution**: 
- Check if papers mention software engineering topics
- Ensure abstracts are at least 50 characters
- Verify publication year is 2015 or later

### Problem: "All papers excluded by EC3"

**Cause**: WL abstracts are too short.

**Solution**: Ensure each WL abstract has at least 50 characters.

### Problem: "GL papers not evaluated"

**Cause**: This is expected - GL has no abstract, so IC and QC cannot be evaluated.

**Solution**: This is correct behavior. GL only goes through EC.

---

## Troubleshooting Guide

| Symptom | Likely Cause | Solution |
|---------|---------------|----------|
| Error loading file | Wrong file format | Use `.xlsx` format |
| No WL results | Missing WL sheet | Ensure "White Literature" sheet exists |
| No GL results | Missing GL sheet | Ensure "Grey Literature" sheet exists |
| Unexpected exclusions | Abstract too short | Add complete abstracts (>50 chars) |
| All excluded by EC1 | No SE keywords | Verify papers are about software engineering |

---

## Reproducibility Checklist

Before publishing your systematic review results:

- [ ] I used APOLLO to screen all papers
- [ ] I kept the input Excel file
- [ ] I noted the APOLLO version used
- [ ] I saved the output Excel file
- [ ] I can re-run APOLLO and get identical results
- [ ] I understand which papers passed/failed each stage

---

## Need Help?

If you encounter issues:

1. Check this guide's troubleshooting section
2. Review the release readiness documentation
3. Verify your input file format matches the schema
4. Ensure Python and dependencies are installed correctly

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│ APOLLO Quick Commands                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ Run via CLI:                                                │
│   python scripts/process_atlas.py input.xlsx              │
│                                                             │
│ Run via UI:                                                │
│   streamlit run app.py                                     │
│                                                             │
│ Input: ATLAS Excel with WL and GL sheets                   │
│ Output: APOLLO_Selection_Criteria.xlsx                     │
│                                                             │
│ Key rules:                                                 │
│   - WL needs 50+ char abstract                              │
│   - Published 2015 or later                                │
│   - Must mention software engineering                      │
│   - QC threshold is 2.0 out of 4.0                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

*Document Version: 1.0.0*  
*For APOLLO 1.0.0 - Deterministic Screening Engine*  
*This guide is for non-technical researchers*