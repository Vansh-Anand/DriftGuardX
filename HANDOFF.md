# Mandatory Antigravity Handoff Format

**1. Stage completed:** Prompt 08 - Causal Contribution Scoring and Exhaustive RCA Baseline
**2. Estimated cumulative completion after verified gates:** 60%

**3. Repository audit and design decisions:**
Developed a mathematical aggregation formula (`ContributionVector`) to balance mean reliability improvements against penalties for latency, cost, and risk. Added a strict `ExhaustiveBenchmarkRunner` for matching trial runs against negative controls. Instituted a strict causal-language guideline that requires reporting outcomes as "likely root cause / recoverable contribution" rather than absolute causal truths.

**4. Files created, modified, migrated, or deprecated:**
- `packages/evaluation/src/contribution.py` (New: Vector aggregation & variance metrics)
- `packages/evaluation/src/rca_metrics.py` (New: Partial-credit MRR, Abstention)
- `packages/evaluation/src/benchmark.py` (New: Exhaustive Negative Control Runner)
- `packages/contracts/src/models.py` (Modified: Added RootCauseReport & RankedCandidate)
- `docs/causal_language_guidelines.md` (New: Wording constraints)
- `apps/web/app/reports/[run_id]/page.tsx` (New: Root Cause Report UI)
- `tests/e2e/test_rca_baseline.py` (New: E2E coverage for metrics and benchmark)
- `CHANGELOG.md` (Modified)

**5. Commands executed and exact test/results summary:**
```bash
python -m pytest tests/e2e/test_rca_baseline.py
# 3 passed in 0.09s
# Coverage: test_contribution_vector, test_benchmark_negative_controls, test_rca_metrics_multi_fault
```

**6. Demonstration or experiment artifacts with paths:**
- `apps/web/app/reports/[run_id]/page.tsx` showcases the Causal Evidence Limitations disclaimer and table.

**7. Security, privacy, safety, and IP-disclosure checks:**
- Implemented `causal_language_guidelines.md` to prevent unsafe IP disclosures or false claims of causal certainty in generated reports.
- `Abstention` threshold explicitly limits the platform from taking risky actions on noisy signals.

**8. Known limitations and failed/negative results:**
- Benchmark currently mocks the `calculate_contribution_vector` calls using synthetic results rather than kicking off thousands of real LLM calls to save developer environment costs.

**9. Data migrations and rollback notes:**
- None. `RootCauseReport` and `RankedCandidate` added cleanly to schemas.

**10. HANDOFF.md updated; next prompt:** 9
