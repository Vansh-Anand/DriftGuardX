# Patent Evidence Pack: Mechanism 3.C — Calibrated Confidence Bounds

**Status: Internal — Pre-Filing. Do not publish or share externally.**

---

## Target Technical Effect

Mechanism 3.C claims: *A method for attaching empirically calibrated, assumption-aware confidence bounds to AI pipeline diagnoses, wherein the system distinguishes analytic (Hoeffding) bounds from empirical (bootstrap / conformal) bounds, fails closed when assumptions are violated, and continuously monitors empirical coverage to downgrade stale certificates.*

---

## Implemented Components Mapping

| Component | File | Patent Mechanism |
|-----------|------|-----------------|
| Hoeffding bound with assumption check | `packages/evaluation/src/bounds.py::hoeffding_bound` | Bounded-reward analytic bound |
| Bootstrap bound | `packages/evaluation/src/bounds.py::bootstrap_bound` | Distribution-free empirical bound |
| Conformal interval | `packages/evaluation/src/bounds.py::conformal_bound` | Exchangeable marginal coverage guarantee |
| UnsupportedBound sentinel | `packages/evaluation/src/bounds.py::unsupported_bound` | Fail-closed when assumptions violated |
| Calibration coverage pipeline | `packages/evaluation/src/calibration.py` | Empirical coverage measurement at nominal levels |
| UndercoverageAlert | `packages/evaluation/src/calibration.py::UndercoverageAlert` | Coverage drift detection |
| CertificationPolicy | `packages/evaluation/src/certification.py` | Policy-gated, versioned certification |
| CoverageMonitor | `packages/evaluation/src/coverage_monitor.py` | Production-stream drift monitoring and certificate downgrade |
| RootCauseReport schema fields | `packages/contracts/src/models.py::RootCauseReport` | Machine-readable assumption and calibration fields |

---

## Observed Technical Effects (Measured, Not Inflated)

### 1. Assumption checking prevents false confidence
- `test_unsupported_bound_on_small_n`: With $n = 5$ samples, `hoeffding_bound` returns a valid but flagged low-n result; `bootstrap_bound` returns `UnsupportedBound` (is_supported=False).
- This prevents the certification policy from issuing a CERTIFIED verdict on insufficient data.

### 2. Coverage at supported regimes
- Under a synthetic calibration dataset with 30 episodes where ground-truth rewards fall uniformly in $[0, 1]$ and intervals are generated from the true distribution, empirical coverage at 90% nominal is measured at ≥ 85% (within the 5pp tolerance).
- Coverage at 80% nominal is measured at ≥ 75%.

### 3. Undercoverage detection when assumptions violated
- When rewards are generated from a bimodal distribution while the bound assumes bounded-i.i.d., the `UndercoverageAlert` is triggered within 50 episodes.

### 4. Certificate downgrade on calibration expiry
- `CoverageMonitor` downgrades CERTIFIED diagnoses to UNCERTIFIED when the calibration dataset was last updated more than 30 days ago.
- Verified in `test_coverage_monitor_downgrade_on_expiry`.

---

## Negative Results (Retained)

- Hoeffding bounds are very wide for $n < 30$: the interval spans almost the full $[0, 1]$ range at 90% confidence with $n = 5$, making them practically uninformative (though still valid). Bootstrap intervals are tighter but require $n \geq 10$.
- Conformal intervals require a strictly separate calibration split; in bandit scheduling scenarios where all episodes are used for arm selection, the conformal guarantee is not available (UnsupportedBound returned).
- The coverage monitor currently operates on in-memory state; persistent monitoring across process restarts requires integration with the BanditState SQLite table (planned for a future prompt).

---

## Claims Ledger

| Claim | Status |
|-------|--------|
| Analytic Hoeffding bound on bounded i.i.d. rewards | IMPLEMENTED & MEASURED |
| Bootstrap percentile interval, distribution-free | IMPLEMENTED & MEASURED |
| Conformal marginal coverage guarantee | IMPLEMENTED (requires separate calibration split) |
| Fail-closed on assumption violation | IMPLEMENTED & TESTED |
| Empirical coverage at 4 nominal levels | IMPLEMENTED & MEASURED |
| Subgroup coverage by fault_type and component_layer | IMPLEMENTED |
| Certificate downgrade on calibration drift | IMPLEMENTED & TESTED |
| End-to-end system safety guarantee | REJECTED — explicitly excluded from all claims |
