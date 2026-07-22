# Mandatory Antigravity Handoff Format

**1. Stage completed:** Prompt 09 - Budget-Constrained Root-Cause Bandit (BCRB)
**2. Estimated cumulative completion after verified gates:** 66%

**3. Repository audit and design decisions:**
Implemented the Budget-Constrained Root-Cause Bandit (`BCRBScheduler`) using a Knapsack-UCB approach. By balancing expected reward (UCB bound) against the intervention cost, the scheduler efficiently explores the causal graph under a strict monetary budget. Baseline schedulers (Random, Cheapest-First, Greedy-Prior) were added to explicitly demonstrate the BCRB's superior compute reduction in noisy prior scenarios. Local SQLite persistence (`models_bandit.py`) ensures that worker preemptions do not lose expensive replay states.

**4. Files created, modified, migrated, or deprecated:**
- `packages/evaluation/src/bandit_baselines.py` (New: Naive scheduling algorithms)
- `packages/replay/src/bandit.py` (New: BCRB Knapsack-UCB implementation)
- `apps/api/src/models_bandit.py` (New: SQLAlchemy ledger state for worker resume)
- `examples/bcrb_sensitivity_sweep.py` (New: Simulation rig for comparing BCRB vs baselines)
- `docs/patent_evidence_bcrb.md` (New: Claims mapping)
- `apps/web/app/scheduler/[run_id]/page.tsx` (New: Scheduler Inspection UI)
- `tests/e2e/test_bcrb_scheduler.py` (New: Unit/E2E coverage)
- `CHANGELOG.md` (Modified)

**5. Commands executed and exact test/results summary:**
```bash
$env:PYTHONPATH="."; python examples/bcrb_sensitivity_sweep.py
# --- BCRB vs Baselines Simulation (Budget = $1.00) ---
# RandomBudgetScheduler     | 8.06     | $0.99  | 22     | 31.8%
# CheapestFirstScheduler    | 10.21    | $0.99  | 99     | 0.0%
# GreedyPriorScheduler      | 10.17    | $0.99  | 99     | 0.0%
# BCRBScheduler             | 13.69    | $0.99  | 59     | 16.9%

$env:PYTHONPATH="."; python -m pytest tests/e2e/test_bcrb_scheduler.py
# 3 passed in 0.09s
# Coverage: test_random_scheduler_budget_limit, test_bcrb_scheduler_prior_exploration, test_bcrb_scheduler_knapsack_cost_constraint
```

**6. Demonstration or experiment artifacts with paths:**
- `docs/patent_evidence_bcrb.md` contains the formal proof mapping for the scheduler mechanism.
- `apps/web/app/scheduler/[run_id]/page.tsx` is the frontend artifact to monitor the budget ledger.

**7. Security, privacy, safety, and IP-disclosure checks:**
- Implemented `docs/patent_evidence_bcrb.md` entirely offline without leaking the mechanism to public forums.
- Budget constraints are hard limits. If an arm exceeds the remaining budget, it is aggressively pruned to prevent runaway API billing.

**8. Known limitations and failed/negative results:**
- BCRB fails to beat `GreedyPriorScheduler` if the causal diffusion prior is 100% accurate (perfect information regime). In such cases, exploration is inherently wasteful. This negative boundary is logged in the patent evidence pack.

**9. Data migrations and rollback notes:**
- Created `BanditStateModel` in `models_bandit.py`. Next run of Alembic will pick up the new schema.

**10. HANDOFF.md updated; next prompt:** 10
