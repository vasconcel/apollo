# APOLLO Autonomous Screening Evaluation Report

**Generated:** 2026-05-22T00:24:58.024205
**Experiment:** sample_benchmark
**Protocol Version:** 1.0
**Dataset:** sample_benchmark (25 items)
**Stage:** ec

---


## Classification Metrics

| Metric | Value |
|--------|-------|
| Precision | 90.0% |
| Recall | 100.0% |
| F1 Score | 94.7% |
| Specificity | 93.8% |
| Balanced Accuracy | 96.9% |
| True Positives | 9 |
| True Negatives | 15 |
| False Positives | 1 |
| False Negatives | 0 |
| Total | 25 |

### Confusion Matrix

```
              Gold INCLUDE  Gold EXCLUDE
APOLLO INCLUDE       9           1
APOLLO EXCLUDE       0          15
```

## Safety Metrics

| Metric | Value |
|--------|-------|
| False Inclusion Rate | 4.0% |
| False Exclusion Rate | 0.0% |
| Catastrophic False Exclusions | 0 |
| Catastrophic Exclusion Rate | 0.0% |
| Total Human-Included Papers | 9 |
| Safe Autonomous Rate | 95.0% |

## Autonomy Metrics

| Metric | Value |
|--------|-------|
| Autonomous Coverage | 80.0% |
| Human Review Reduction | 20.0% |
| Abstention Rate | 20.0% |
| Escalation Rate | 0.0% |
| Autonomous Precision | 90.0% |
| Autonomous Recall | 100.0% |
| Autonomous F1 | 94.7% |
| Autonomous Agreement | 95.0% |
| Total Autonomous | 20 |
| Total Human Review | 5 |
| Total Abstained | 5 |
| Total Escalated | 0 |

## Calibration Metrics

| Metric | Value |
|--------|-------|
| Expected Calibration Error (ECE) | 0.7998 |
| Maximum Calibration Error (MCE) | 0.9489 |
| Confidence-Correctness Correlation | 0.0000 |
| Number of Bins | 10 |

### Calibration Bin Details

| Bin | Range | Count | Avg Confidence | Accuracy | Gap |
|-----|-------|-------|----------------|----------|-----|
| 0 | [0.0, 0.1) | 0 | 0.0% | 0.0% | 0.0% |
| 1 | [0.1, 0.2) | 0 | 0.0% | 0.0% | 0.0% |
| 2 | [0.2, 0.3) | 1 | 26.3% | 0.0% | 26.3% |
| 3 | [0.3, 0.4) | 3 | 33.7% | 0.0% | 33.7% |
| 4 | [0.4, 0.5) | 1 | 46.2% | 0.0% | 46.2% |
| 5 | [0.5, 0.6) | 0 | 0.0% | 0.0% | 0.0% |
| 6 | [0.6, 0.7) | 0 | 0.0% | 0.0% | 0.0% |
| 7 | [0.7, 0.8) | 1 | 79.5% | 0.0% | 79.5% |
| 8 | [0.8, 0.9) | 7 | 86.9% | 0.0% | 86.9% |
| 9 | [0.9, 1.0) | 12 | 94.9% | 0.0% | 94.9% |

## Queue Distribution

| Routing | Count | Percentage |
|---------|-------|------------|
| AUTO_INCLUDE | 10 | 40.0% |
| AUTO_EXCLUDE | 10 | 40.0% |
| HUMAN_REVIEW | 5 | 20.0% |
| ESCALATE | 0 | 0.0% |
| UNCERTAIN | 0 | 0.0% |

## Error Analysis

### Error Category Distribution

| Category | Count | Percentage | Most Common Severity |
|----------|-------|------------|---------------------|
| unknown | 20 | 80.0% | medium |
| confidence_miscalibration | 4 | 16.0% | medium |
| keyword_overlap_false_positive | 1 | 4.0% | medium |

### Detailed Error List

1. **BENCH_001** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

2. **BENCH_002** — Error could not be classified into a specific category.
   - APOLLO: `INCLUDE` → Gold: `INCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

3. **BENCH_003** — Error could not be classified into a specific category.
   - APOLLO: `INCLUDE` → Gold: `INCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

4. **BENCH_004** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

5. **BENCH_005** — Paper uses domain keywords (e.g. 'software', 'AI', 'ML') but addresses a completely different research question. APOLLO confuses topical keyword overlap for true relevance.
   - APOLLO: `INCLUDE` → Gold: `EXCLUDE`
   - Categories: keyword_overlap_false_positive
   - Severity: medium
   - Rationale: Unclassified false positive; attributed to keyword overlap

6. **BENCH_006** — Confidence score does not reflect actual decision quality. High confidence on wrong decisions or low confidence on correct ones.
   - APOLLO: `UNCERTAIN` → Gold: `UNCERTAIN`
   - Categories: confidence_miscalibration
   - Severity: medium
   - Rationale: Confidence 36% on correct decision; underconfident

7. **BENCH_007** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

8. **BENCH_008** — Error could not be classified into a specific category.
   - APOLLO: `INCLUDE` → Gold: `INCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

9. **BENCH_009** — Confidence score does not reflect actual decision quality. High confidence on wrong decisions or low confidence on correct ones.
   - APOLLO: `INSUFFICIENT_EVIDENCE` → Gold: `INSUFFICIENT_EVIDENCE`
   - Categories: confidence_miscalibration
   - Severity: medium
   - Rationale: Confidence 26% on correct decision; underconfident

10. **BENCH_010** — Error could not be classified into a specific category.
   - APOLLO: `INCLUDE` → Gold: `INCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

11. **BENCH_011** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

12. **BENCH_012** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

13. **BENCH_013** — Error could not be classified into a specific category.
   - APOLLO: `INCLUDE` → Gold: `INCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

14. **BENCH_014** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

15. **BENCH_015** — Error could not be classified into a specific category.
   - APOLLO: `INCLUDE` → Gold: `INCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

16. **BENCH_016** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

17. **BENCH_017** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

18. **BENCH_018** — Confidence score does not reflect actual decision quality. High confidence on wrong decisions or low confidence on correct ones.
   - APOLLO: `UNCERTAIN` → Gold: `UNCERTAIN`
   - Categories: confidence_miscalibration
   - Severity: medium
   - Rationale: Confidence 30% on correct decision; underconfident

19. **BENCH_019** — Error could not be classified into a specific category.
   - APOLLO: `INCLUDE` → Gold: `INCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

20. **BENCH_020** — Error could not be classified into a specific category.
   - APOLLO: `EXCLUDE` → Gold: `EXCLUDE`
   - Categories: unknown
   - Severity: medium
   - Rationale: Could not determine error category

... and 5 more errors

## Threshold Comparison

| Config | Coverage | Safety | Agreement | FP Rate | FN Rate |
|--------|----------|--------|-----------|---------|---------|
| conservative | 8.0% | 97.9% | 100.0% | 6.2% | 0.0% |
| balanced | 0.0% | 97.9% | 0.0% | 6.2% | 0.0% |
| moderate | 24.0% | 97.9% | 100.0% | 6.2% | 0.0% |
| aggressive | 76.0% | 97.9% | 100.0% | 6.2% | 0.0% |
| ultra_conservative | 0.0% | 97.9% | 0.0% | 6.2% | 0.0% |

---

*Report generated by APOLLO Evaluation Framework*
