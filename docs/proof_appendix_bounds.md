# Proof Appendix: Statistical Bounds for DriftGuard-X Diagnoses

**Status: Engineering Draft — Not a Legal or Safety Certification**

---

## 1. Statistical Setup

Let $X_1, X_2, \ldots, X_n \in [0, 1]$ be the reliability-improvement reward observations from $n$ replay episodes for a given intervention candidate $a$.

Define $\bar{X}_n = \frac{1}{n} \sum_{i=1}^n X_i$ as the sample mean.

Our goal is to bound the probability that the true expected reward $\mu = \mathbb{E}[X]$ lies within a computed interval $[\bar{X}_n - \varepsilon, \bar{X}_n + \varepsilon]$.

---

## 2. Hoeffding Bound

**Theorem (Hoeffding, 1963):** If $X_1, \ldots, X_n$ are independent bounded random variables with $X_i \in [a_i, b_i]$, then for any $\varepsilon > 0$:

$$P\!\left(\bar{X}_n - \mu \geq \varepsilon\right) \leq \exp\!\left(\frac{-2n^2\varepsilon^2}{\sum_{i=1}^n (b_i - a_i)^2}\right)$$

For identically bounded rewards in $[0, 1]$ and failure probability $\delta = 1 - \text{confidence}$:

$$\varepsilon = \sqrt{\frac{\ln(2/\delta)}{2n}}$$

**Implemented Assumptions:**
1. All $n$ rewards lie in $[0, 1]$ (checked programmatically; bound is rejected if violated).
2. Independence / i.i.d. — satisfied in the fault-injection lab; *approximately* satisfied under bandit sampling (mild correlation introduced by adaptive selection, handled via union bound over arms).
3. $n \geq 1$ required; $n \geq 30$ recommended for the bound to be practically informative.

**Implemented in:** `packages/evaluation/src/bounds.py::hoeffding_bound`

---

## 3. Bootstrap Interval

A non-parametric percentile bootstrap resamples $B = 2000$ times from the observed rewards and computes the $[\alpha/2, 1-\alpha/2]$ empirical quantiles.

**Assumptions:**
1. $n \geq 10$ (minimum for a meaningful resample distribution).
2. Observations are exchangeable (approximately satisfied under replay conditions).
3. No distributional shape assumption.

Bootstrap intervals are **empirical**, not analytic. They do not carry Hoeffding's finite-sample guarantee, but are generally tighter in practice.

**Implemented in:** `packages/evaluation/src/bounds.py::bootstrap_bound`

---

## 4. Conformal Prediction Interval

Split-conformal prediction uses a held-out calibration split of nonconformity scores $s_1, \ldots, s_{n_{\text{cal}}}$ to find a threshold $\tau$ such that:

$$P\!\left(s_{\text{test}} \leq \tau\right) \geq 1 - \alpha - \frac{1}{n_{\text{cal}} + 1}$$

**Marginal coverage is guaranteed** when calibration and test scores are exchangeable (i.i.d.). This guarantee is distribution-free.

**Key requirement:** The calibration split must be *strictly separate* from arm-selection / development episodes.

**Implemented in:** `packages/evaluation/src/bounds.py::conformal_bound`

---

## 5. UnsupportedBound

If none of the above assumption sets can be satisfied given the provided data, the system returns an `UnsupportedBound` sentinel (`is_supported=False`). This causes the certification policy to issue an `UNCERTIFIED` or `REJECTED` verdict, depending on severity.

**This is the correct fail-closed behavior.** Manufacturing a confidence interval when assumptions are violated would be worse than admitting uncertainty.

---

## 6. Engineering Interpretation

> **This appendix does NOT claim that DriftGuard-X provides an end-to-end system safety guarantee.**

The bounds described above are statistically valid under the listed assumptions for the specific quantity being measured: *the mean reliability-improvement reward of a replay intervention over $n$ sampled episodes*.

They do **not** imply:
- That the diagnosed fault is the unique causal root cause in a mathematical sense.
- That applying the recommended repair will achieve the predicted improvement in production.
- That the system is safe for use in safety-critical infrastructure without additional human review and domain-specific validation.

All diagnoses flagged `UNCERTIFIED` or `REJECTED` require explicit human review before consequential actions are taken. This is enforced at the policy layer (`packages/evaluation/src/certification.py`).

---

## 7. Empirical Coverage Measurement

Calibration coverage is measured separately using held-out fault-injection episodes (see `packages/evaluation/src/calibration.py`). Coverage at each nominal level is reported alongside the nominal value in every `RootCauseReport`. Undercoverage alerts are issued when observed coverage falls more than 5 percentage points below nominal.

| Nominal | Minimum Accepted Observed |
|---------|--------------------------|
| 80%     | 75%                      |
| 90%     | 85%                      |
| 95%     | 90%                      |
| 99%     | 94%                      |

---

## References
- Hoeffding, W. (1963). Probability inequalities for sums of bounded random variables. *JASA*.
- Vovk, V., Gammerman, A., Shafer, G. (2005). *Algorithmic Learning in a Random World*. Springer.
- Tibshirani et al. (2019). Conformal prediction under covariate shift. *NeurIPS*.
