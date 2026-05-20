# APOLLO Experimental Design

## Design Types

### 1. Within-Subjects Design

**Description**: Same reviewer conducts multiple conditions.

**Advantages**:
- Controls for individual differences
- Requires fewer reviewers
- Higher statistical power

**Disadvantages**:
- Order effects possible
- Learning/fatigue effects

**Mitigation**: Randomize order, include washout period.

### 2. Between-Subjects Design

**Description**: Different reviewers in different conditions.

**Advantages**:
- No order effects
- Cleaner comparison

**Disadvantages**:
- More reviewers required
- Individual differences confound

**Mitigation**: Random assignment, stratify by experience.

### 3. Factorial Design

**Description**: Combine multiple factors (e.g., condition × risk level).

**Advantages**:
- Interaction effects visible
- Efficient

**Disadvantages**:
- Complex analysis
- Requires larger sample

## Study Configurations

### Configuration A: Efficiency Study

**Question**: Does APOLLO reduce workload without sacrificing accuracy?

**Design**: Within-subjects, crossover
- Phase 1: Manual-only (50% of articles)
- Phase 2: Advisory-assisted (50% of articles)
- Randomize order

**Metrics**: Agreement rate, workload reduction, throughput

### Configuration B: Quality Study

**Question**: Does APOLLO improve or maintain decision quality?

**Design**: Between-subjects
- Group A: Manual-only
- Group B: Advisory-assisted

**Metrics**: Agreement with gold standard (if available), override distribution

### Configuration C: Calibration Study

**Question**: Is AI confidence calibrated to actual agreement?

**Design**: Within-subjects
- Collect confidence scores
- Bin by confidence level
- Calculate agreement per bin

**Metrics**: Calibration curve, Brier score

### Configuration D: Inter-Rater Reliability Study

**Question**: Do multiple reviewers agree with AI consistently?

**Design**: Multiple reviewers, same condition
- 2+ reviewers per condition
- Independent decisions
- Adjudication for disagreements

**Metrics**: Cohen's Kappa, percent agreement

## Randomization Strategies

### Article Randomization

```python
import hashlib

def get_deterministic_order(articles, seed):
    """Generate deterministic article order."""
    def sort_key(a):
        article_id = getattr(a, 'article_id', '')
        combined = f"{seed}_{article_id}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    return sorted(articles, key=sort_key)
```

### Condition Randomization

```python
def assign_conditions(n_articles, n_manual, n_assisted, seed):
    """Assign conditions deterministically."""
    import random
    
    random.seed(seed)
    indices = list(range(n_articles))
    random.shuffle(indices)
    
    assignments = ["MANUAL"] * n_manual + ["ASSISTED"] * n_assisted
    
    return dict(zip(indices, assignments))
```

## Statistical Analysis

### Primary Analysis

1. **Agreement Rate**: Proportion + 95% CI (Wilson score)
2. **Workload Reduction**: Proportion + 95% CI
3. **Override Rate**: Proportion + 95% CI

### Secondary Analysis

1. **Chi-Square Test**: Compare override rates across conditions
2. **T-Test**: Compare throughput (time per article)
3. **Correlation**: Confidence vs agreement

### Sensitivity Analysis

1. Exclude high-hallucination-risk articles
2. Exclude low-grounding-strength articles
3. Vary risk classification thresholds

## Power Analysis

For detecting 10% difference in agreement rate:

- Baseline agreement: 80%
- Expected with AI: 90%
- Alpha: 0.05
- Power: 0.80

Required sample: ~200 articles per condition

## Ethical Considerations

1. **Informed Consent**: Reviewers should know they are in study
2. **Data Privacy**: anonymize reviewer IDs
3. **Withdrawal**: Allow reviewers to stop at any time
4. **Feedback**: Provide summary after study completion

## Replication Guidelines

For reproducibility, document:

1. Protocol hash
2. Dataset hash
3. LLM model + temperature
4. Sample size
5. Randomization seed
6. Analysis code
7. Full results (including null findings)