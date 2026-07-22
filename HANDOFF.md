# Mandatory Antigravity Handoff Format

**1. Stage completed:** Prompt 10 — Certified Recovery Bounds, Calibration, and Coverage Monitoring
**2. Estimated cumulative completion after verified gates:** 71%

**3. Repository audit and design decisions:**
Extended the existing `contribution.py` bootstrap CI (which used a naive `±1.96 * std_err` approximation) with three rigorous bound calculators: Hoeffding analytic, Bootstrap percentile, and Split-conformal. Each returns a typed `BoundResult` dataclass with explicit `assumptions_met` / `assumptions_violated` lists. When any bound assumption is violated, `UnsupportedBound` is returned — no fabricated number. The certification policy enforces five gates (bound assumptions, episode count, valid replay fraction, calibration age, empirical coverage); critical failures default to REJECTED with automated actions blocked.

**4. Files created, modified, migrated, or deprecated:**
- `packages/evaluation/src/bounds.py` (New: Hoeffding, Bootstrap, Conformal, UnsupportedBound)
- `packages/evaluation/src/calibration.py` (New: Empirical coverage pipeline, subgroup analysis, UndercoverageAlert, conformal baseline)
- `packages/evaluation/src/certification.py` (New: 5-gate CERTIFIED/UNCERTIFIED/REJECTED policy)
- `packages/evaluation/src/coverage_monitor.py` (New: Production-stream drift monitor, certificate downgrade)
- `packages/contracts/src/models.py` (Modified: RootCauseReport extended with 11 new certification fields)
- `apps/web/app/reports/[run_id]/page.tsx` (Modified: Gated CertificationBadge; Execute Action disabled unless CERTIFIED)
- `docs/proof_appendix_bounds.md` (New: Statistical proof appendix + engineering interpretation)
- `docs/patent_evidence_bounds.md` (New: Mechanism 3.C patent claims mapping)
- `tests/e2e/test_bounds_calibration.py` (New: 15 tests covering all 5 acceptance gates)
- `CHANGELOG.md` (Modified)

**5. Commands executed and exact test/results summary:**
```
$env:PYTHONPATH="."; python -m pytest tests/e2e/test_bounds_calibration.py -v
============================= 15 passed in 0.30s ==============================

Tests cover:
  test_hoeffding_bound_is_supported_with_sufficient_n          PASSED
  test_hoeffding_low_n_still_supported_but_warns               PASSED
  test_hoeffding_returns_unsupported_when_reward_out_of_range  PASSED
  test_bootstrap_returns_unsupported_on_tiny_n                 PASSED
  test_conformal_returns_unsupported_on_small_calibration      PASSED
  test_bootstrap_bound_is_tighter_than_hoeffding_on_same_data  PASSED
  test_conformal_coverage_satisfied                            PASSED
  test_calibration_coverage_report_fields                      PASSED
  test_undercoverage_alert_triggered                           PASSED
  test_certify_returns_certified_when_all_gates_pass           PASSED
  test_certify_returns_uncertified_when_calibration_expired    PASSED
  test_certify_returns_rejected_when_no_replays                PASSED
  test_certify_blocked_when_insufficient_episodes              PASSED
  test_coverage_monitor_downgrade_on_expiry                    PASSED
  test_coverage_monitor_no_downgrade_for_uncertified           PASSED
```

**6. Demonstration or experiment artifacts with paths:**
- `docs/proof_appendix_bounds.md` — statistical assumptions and engineering interpretation
- `docs/patent_evidence_bounds.md` — mechanism 3.C claims ledger with negative results
- `apps/web/app/reports/[run_id]/page.tsx` — CertificationBadge UI (id="execute-action-button" is disabled for non-CERTIFIED)

**7. Security, privacy, safety, and IP-disclosure checks:**
- All files created locally; no external publication.
- `docs/proof_appendix_bounds.md` explicitly states "NOT a system safety guarantee" and this language is enforced in the UI disclaimer text.
- Fail-closed: REJECTED blocks automated downstream actions entirely.

**8. Known limitations and failed/negative results:**
- Hoeffding bounds are very wide for n < 30 (spans ~80% of [0,1] at 90% confidence, n=5). This is the correct behavior — the bound is valid but uninformative. Bootstrap tightens this at n ≥ 10 but requires exchangeability.
- Conformal intervals require a strictly separate calibration split. In bandit scheduling scenarios where all episodes are used for arm selection, conformal is unavailable (UnsupportedBound returned). This limitation is documented in the patent evidence pack.
- CoverageMonitor currently operates in-memory; persistent monitoring across process restarts requires the BanditState SQLite table integration (next prompt scope).

**9. Data migrations and rollback notes:**
- `RootCauseReport` schema in `models.py` extended with 11 new fields, all with safe defaults (`UNCERTIFIED`, `True` for human_review_required and block_automated_action). No migration required — existing rows default to the most conservative (fail-safe) values.

**10. HANDOFF.md updated; next prompt:** 11
