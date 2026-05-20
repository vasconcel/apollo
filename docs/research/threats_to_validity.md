# APOLLO Threats to Validity

## Overview

This document identifies known threats to internal and external validity for empirical evaluations using APOLLO.

## Internal Validity Threats

### 1. LLM Non-Determinism

**Threat**: LLM responses vary even with identical prompts, making reproducibility difficult.

**Severity**: HIGH

**Mitigation**:
- Protocol version hashing enables tracking of protocol state
- Advisory confidence scores provide uncertainty quantification
- Grounding validation detects unsupported claims
- Multiple runs can assess variance

**Limitation**: Cannot fully eliminate LLM variance.

### 2. Reviewer Bias

**Threat**: Human reviewers may be influenced by seeing AI recommendations.

**Severity**: MEDIUM

**Mitigation**:
- Record independent decisions before seeing AI advisory
- Compare advisory-assisted vs manual-only conditions
- Track override reasons for bias analysis

**Limitation**: Single-blind design only (reviewer sees AI).

### 3. Learning Effects

**Threat**: Reviewers may improve during session based on pattern recognition.

**Severity**: LOW

**Mitigation**:
- Randomize article order within risk strata
- Track review time as covariate
- Include sufficient sample size

### 4. Fatigue Effects

**Threat**: Reviewer performance degrades over time.

**Severity**: MEDIUM

**Mitigation**:
- Track elapsed time per review
- Include rest periods in protocol
- Monitor throughput over time

### 5. Protocol Dependence

**Threat**: Results may be specific to particular protocol criteria.

**Severity**: HIGH

**Mitigation**:
- Document full protocol criteria
- Include protocol hash in exports
- Conduct multi-protocol studies
- Report protocol version explicitly

### 6. Calibration Drift

**Threat**: System calibration may change over time (LLM updates, criteria changes).

**Severity**: MEDIUM

**Mitigation**:
- Track calibration events longitudinally
- Monitor agreement rate over time
- Include calibration review in protocol
- Report LLM model version explicitly

### 7. Selection Bias

**Threat**: Imported articles may not represent target population.

**Severity**: MEDIUM

**Mitigation**:
- Document inclusion criteria for import
- Report dataset characteristics
- Include source database metadata

## External Validity Threats

### 1. Domain Specificity

**Threat**: Results may not generalize to other research domains.

**Severity**: HIGH

**Mitigation**:
- Conduct multi-domain validation studies
- Report domain characteristics explicitly
- Include protocol flexibility for adaptation

**Limitation**: System designed for systematic review workflows.

### 2. Dataset Dependence

**Threat**: Performance may depend on specific dataset characteristics.

**Severity**: MEDIUM

**Mitigation**:
- Report dataset statistics (size, date range, sources)
- Include multiple datasets in evaluation
- Document import criteria

### 3. LLM Model Dependence

**Threat**: Results may be specific to current LLM model.

**Severity**: HIGH

**Mitigation**:
- Report exact LLM model and version
- Include model temperature setting
- Consider multiple models in evaluation

**Limitation**: LLM technology evolving rapidly.

### 4. Temporal Effects

**Threat**: Literature characteristics change over time.

**Severity**: LOW-MEDIUM

**Mitigation**:
- Report article date distribution
- Include temporal markers in analysis
- Re-evaluate periodically

## Construct Validity Threats

### 1. Ground Truth Ambiguity

**Threat**: True inclusion/exclusion may be ambiguous for some articles.

**Severity**: MEDIUM

**Mitigation**:
- Use multiple independent reviewers
- Include adjudication for disagreements
- Document adjudication process

### 2. Risk Construct Validity

**Threat": Risk classification may not capture relevant uncertainty dimensions.

**Severity**: MEDIUM

**Mitigation**:
- Include multiple risk indicators (confidence, grounding, hallucination)
- Report risk distribution
- Validate against actual disagreements

### 3. Workload Construct Validity

**Threat**: Workload reduction may not capture actual time savings.

**Severity**: LOW

**Mitigation**:
- Track actual review time
- Include reviewer feedback
- Compare to baseline conditions

## Statistical Conclusion Validity Threats

### 1. Sample Size Limitations

**Threat**: Insufficient sample size for statistical power.

**Severity**: MEDIUM

**Mitigation**:
- Conduct power analysis a priori
- Report confidence intervals
- Use appropriate statistical tests

### 2. Multiple Comparisons

**Threat**: Multiple metrics increase false positive rate.

**Severity**: LOW

**Mitigation**:
- Pre-register primary outcomes
- Adjust for multiple comparisons
- Report all metrics transparently

### 3. Effect Size Interpretation

**Threat**: Statistical significance does not imply practical significance.

**Severity**: LOW

**Mitigation**:
- Report effect sizes with confidence intervals
- Interpret in practical context
- Report absolute values, not just relative

## Reporting Requirements

For scientific publication, explicitly report:

1. Protocol version and hash
2. Dataset source and characteristics
3. LLM model and version
4. LLM temperature setting
5. Sample size
6. Agreement metrics with confidence intervals
7. All limitations identified above

## Unresolved Limitations

1. **LLM non-determinism** - Cannot be eliminated, only characterized
2. **Single-blind design** - Cannot blind reviewer to AI recommendations in current workflow
3. **Domain specificity** - Designed for systematic review, may not generalize
4. **Protocol dependence** - Results tied to specific criteria sets
5. **Temporal instability** - LLM and literature evolve over time