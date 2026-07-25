# Statistical Validation Report

## 1. BCRB vs Exhaustive Replay
- **Effect Size (Cohen's d)**: 0.1486
- **Paired Bootstrap Interval (95%)**: [-0.0034, 0.0258]
- **Permutation Test p-value**: 0.1260
- **Bonferroni Corrected p-value**: 0.3780

## 2. Cost Analysis
- **Exhaustive Cost**: $5.00
- **BCRB Cost**: $2.00
- **Cases where BCRB fails to reduce cost**: 0 cases in matched candidate sets.

## 3. Certified Bound Coverage
- **Nominal Coverage**: 95%
- **Empirical Coverage (Retriever)**: 94.2%
- **Empirical Coverage (Generator)**: 95.1%
- **Undercoverage**: Minor undercoverage in retrieval layer due to discrete metric space.
