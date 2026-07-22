# Patent Evidence Pack: Mechanism 3.E — Risk-Tiered Multi-Tenant Policy Inheritance

**Status: Internal — Pre-Filing. Do not publish or share externally.**

---

## Target Technical Effect

Mechanism 3.E claims: *A method for enterprise-grade policy governance of AI pipeline operations, wherein policies are organized in a four-level hierarchy (Organization → BusinessUnit → Pipeline → Agent), resolved via tightening-only inheritance with explicit conflict detection, and enforced at every stage of the diagnostic loop with cryptographic audit trails.*

---

## Implemented Components Mapping

| Component | File | Patent Mechanism |
|-----------|------|-----------------|
| Four-level hierarchy schemas | `packages/policy/src/hierarchy.py` | Org→BU→Pipeline→Agent with full audit trace |
| Tightening-only resolver | `packages/policy/src/resolver.py` | Deterministic effective-policy, conflict detection |
| Risk tier registry | `packages/policy/src/tiers.py` | LOW/MEDIUM/HIGH/CRITICAL mapping for all actions |
| Approval service | `packages/policy/src/approvals.py` | Request lifecycle, self-approval block, break-glass |
| Unified policy engine | `packages/policy/src/engine.py` | Single evaluator integrating all subsystems |
| Shadow/simulation mode | `packages/policy/src/shadow.py` | Historical replay against candidate policies |
| Integration hooks | `packages/policy/src/hooks.py` | Pre-replay, pre-recovery, pre-execution, pre-rollback |
| Policy UI | `apps/web/app/policy/page.tsx` | Hierarchy tree, action matrix, approval queue |

---

## Observed Technical Effects (Measured, Not Inflated)

### 1. Cross-tenant isolation verified
- `test_cross_tenant_policy_isolation`: Resolver finds no nodes for a tenant/node combination belonging to a different tenant → DEFAULT_DENY returned.
- `test_tenant_b_cannot_read_tenant_a_decisions`: Engine decision logs are per-engine-instance; tenant B's engine shows 0 decisions from tenant A's engine.

### 2. Confused deputy attack blocked
- `test_confused_deputy_low_role_cannot_execute_high_action`: A viewer role attempting `apply_rollback` on a policy node that restricts the action to `["operator", "admin"]` is denied.

### 3. Self-approval invariant enforced
- `test_self_approval_is_blocked`: `SelfApprovalError` raised before any approval decision is recorded.

### 4. Delegated approver enforcement
- `test_unauthorized_approver_is_blocked`: Actor outside `delegated_approvers` raises `UnauthorizedApproverError`.
- `test_delegated_approver_succeeds`: Actor inside the list succeeds.

### 5. Two-person control for CRITICAL
- `test_critical_action_needs_two_approvers`: With `required_approvers=2`, a single approval leaves status PENDING; only after 2 distinct non-requester approvers does status change to APPROVED.

### 6. Break-glass always audited
- `test_break_glass_is_audited`: Audit log contains exactly one `BREAK_GLASS` entry with `requires_post_hoc_review=True` and the correct `actor_id`.
- Break-glass with justification < 20 chars raises `ValueError`.

### 7. Determinism (property test)
- `test_effective_policy_is_deterministic`: Identical inputs produce identical effective policy on two sequential calls.

### 8. Shadow evaluation
- `test_shadow_evaluation_detects_policy_relaxation`: A candidate policy that allows a previously-denied action is correctly flagged as `n_relaxed=1` with "REVIEW REQUIRED" in summary.

### 9. Tightening inheritance
- `test_child_deny_overrides_parent_allow`: Pipeline-level DENY wins over org-level ALLOW.
- `test_child_cannot_relax_without_justification`: `PolicyConflictError` raised when child is more permissive than parent without `override_justification`.

---

## Test Results
```
tests/security/test_policy_security.py — 15 passed in 0.25s
```

---

## Negative Results (Retained)

- The `PolicyRegistry` is currently in-memory; cross-process consistency requires DB-backed persistence (planned for the next integration prompt).
- The `shadow_evaluate` function processes events sequentially; for large historical datasets (>100k events), parallelization would be required.
- The UI's Approve/Deny buttons are wired to mock state; actual API calls to `/api/policy/approvals/{request_id}` are not yet implemented (API routes are out of scope for this prompt).
- `break_glass` bypasses the delegated_approvers check for emergency use; this is intentional but means it also bypasses the `UnauthorizedApproverError`. Only the self-approval check is retained.

---

## Claims Ledger

| Claim | Status |
|-------|--------|
| Four-level Org→BU→Pipeline→Agent hierarchy | IMPLEMENTED |
| Tightening-only inheritance (DENY overrides ALLOW) | IMPLEMENTED & TESTED |
| Conflict detection on illegal relaxation | IMPLEMENTED & TESTED |
| Risk tier mapping (LOW/MEDIUM/HIGH/CRITICAL) | IMPLEMENTED |
| Approval lifecycle (create, approve, deny, expire) | IMPLEMENTED |
| Self-approval block | IMPLEMENTED & TESTED |
| Delegated approver enforcement | IMPLEMENTED & TESTED |
| Two-person control for CRITICAL | IMPLEMENTED & TESTED |
| Break-glass with mandatory audit | IMPLEMENTED & TESTED |
| Shadow/simulation mode | IMPLEMENTED & TESTED |
| Pre-loop integration hooks | IMPLEMENTED |
| Default-deny on unknown action | IMPLEMENTED & TESTED |
| Cross-tenant isolation | IMPLEMENTED & TESTED |
| Confused deputy protection | IMPLEMENTED & TESTED |
| Policy UI (hierarchy, matrix, queue) | IMPLEMENTED |
| Full system safety guarantee | REJECTED — explicitly excluded |
