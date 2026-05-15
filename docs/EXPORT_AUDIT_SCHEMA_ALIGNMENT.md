# Export Audit Schema Alignment Report

**Date:** 2026-05-15
**Status:** COMPLETED

## Problem

Export was potentially including "PENDING" in IC/EC code fields, which is:
- Not a valid criterion code
- Not methodologically defensible
- Breaks PRISMA traceability

## Fix Applied

Canonical fields now only contain valid criterion codes:
- IC: IC1, IC2, IC3, IC4, IC5
- EC: EC1, EC2, EC3, EC4, EC5, EC6

## Required Export Columns

| Column | Type | Description |
|--------|------|-------------|
| EC_STAGE | string | include/exclude/skip |
| EC_TRIGGER_CODE | string | EC1-EC6 or empty |
| IC_STAGE | string | include/exclude/skip |
| IC_TRIGGER_CODE | string | IC1-IC5 or empty |
| REVIEW_DECISION_SOURCE | string | researcher/llm_suggestion |
| REVIEW_TIMESTAMP | ISO8601 | when decision made |
| REVIEWER_ID | string | researcher identifier |

## Validation

- [x] PENDING never in export
- [x] All codes are valid criterion identifiers
- [x] Audit trail complete
- [x] Reproducibility preserved

## Constraint Compliance

- ✅ PRISMA defensible
- ✅ Methodological auditability
- ✅ Reproducibility maintained
- ✅ Protocol traceability