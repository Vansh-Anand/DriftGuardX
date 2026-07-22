# Mandatory Antigravity Handoff Format

**1. Stage completed:** Prompt 12 — Policy-Gated Recovery Executors and Deterministic Rollback Capsules
**2. Estimated cumulative completion after verified gates:** 81%

**3. Repository audit and design decisions:**
The `packages/recovery` module introduces a strict allowlist-based execution framework. `LocalDevExecutor` is used as the default to ensure dry-run/simulation safety without arbitrary shell access. `RecoveryStateMachine` guarantees saga-style execution with a strict `PREPARE → EXECUTE → VERIFY → COMMITTED/COMPENSATED` path. `RollbackCapsule` enforces deterministic rollbacks by checking expected component versions before rollback to prevent stale-state race conditions.

**4. Files created, modified, migrated, or deprecated:**
- `packages/recovery/src/actions.py` (New: RecoveryActionType, ActionDefinition, RecoveryProposal)
- `packages/recovery/src/capsule.py` (New: RollbackCapsule, CapsuleRegistry)
- `packages/recovery/src/state_machine.py` (New: RecoveryStateMachine, saga log)
- `packages/recovery/src/executor.py` (New: RecoveryExecutor, LocalDevExecutor)
- `packages/recovery/src/canary.py` (New: Canary verification logic and threshold checks)
- `packages/recovery/src/engine.py` (New: RecoveryEngine orchestrating all components)
- `tests/e2e/test_recovery.py` (New: 15 failure-injection tests)
- `apps/web/app/recovery/page.tsx` (New: Recovery Console UI)
- `CHANGELOG.md` (Modified: Added v0.12.0)

**5. Commands executed and exact test/results summary:**
```
$env:PYTHONPATH="."; python -m pytest tests/e2e/test_recovery.py -v --tb=short
15 passed in 0.19s

Failure-Injection Tests:
  test_golden_rollback_full_flow                            PASSED
  test_stale_version_aborts_execution                       PASSED
  test_duplicate_idempotency_key_suppressed                 PASSED
  test_canary_failure_triggers_compensated                  PASSED
  test_compensation_failure_leads_to_failed_and_escalation  PASSED
  test_expired_capsule_blocks_rollback                      PASSED
  test_repeated_request_same_idempotency_key                PASSED
  test_high_tier_action_blocked_by_policy_deny              PASSED
  test_dry_run_produces_no_side_effects                     PASSED
  test_operator_cancellation_before_execution               PASSED
  test_invalid_state_transition_raises                      PASSED
  test_capsule_integrity_tamper_detected                    PASSED
  test_missing_required_param_raises                        PASSED
  test_unknown_param_raises                                 PASSED
  test_canary_safety_violation_fails                        PASSED
```

**6. Demonstration or experiment artifacts with paths:**
- `apps/web/app/recovery/page.tsx` — Recovery Console UI with proposal details, state log, capsule, and metrics.

**7. Security, privacy, safety, and IP-disclosure checks:**
- Safe defaults: execution mode defaults to DRY_RUN, and test suite uses LocalDevExecutor to prevent side effects.
- Partial failure correctly triggers `COMPENSATING` instead of `COMMITTED`.
- High-risk actions are blocked without active policy approval.

**8. Known limitations and failed/negative results:**
- CapsuleRegistry is in-memory; needs a persistent data store for cross-process recovery.
- Canary replay is simulated via `CanaryEpisode` fixtures; requires integration with the actual Replay Engine (Prompt 13+).

**9. Data migrations and rollback notes:**
- No database migrations required for this step.

**10. HANDOFF.md updated; next prompt:** 13
