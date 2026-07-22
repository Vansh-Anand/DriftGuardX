"""
DriftGuard-X v2 — Integration Hooks
PRIVATE — All Rights Reserved.

Pre-action policy checks inserted at each stage of the closed loop:
  pre_replay_check      — before scheduling a counterfactual replay
  pre_recovery_check    — before proposing a recovery action
  pre_execution_check   — before executing an approved intervention
  pre_rollback_check    — before applying a rollback capsule

Each hook:
  1. Calls the PolicyEngine.evaluate().
  2. Raises PolicyDeniedError on DENY.
  3. Returns the approval_request_id on NEEDS_APPROVAL for the caller to surface.
  4. Returns None on ALLOW.

Every allow/deny is recorded in the engine decision log with action, tenant,
node, verdict, rule_id, policy_version, requester, and timestamp.
"""
from __future__ import annotations

from packages.policy.src.engine import PolicyEngine, EngineDecision
from typing import Optional


class PolicyDeniedError(PermissionError):
    """Raised when a policy check returns DENY."""
    def __init__(self, decision: EngineDecision):
        self.decision = decision
        super().__init__(
            f"[POLICY DENIED] action={decision.action!r} "
            f"rule={decision.rule_id!r} reason={decision.rationale!r}"
        )


def _check(
    engine: PolicyEngine,
    action: str,
    tenant_id: str,
    node_id: str,
    requester_id: str,
    requester_role: str = "operator",
    existing_approval_id: Optional[str] = None,
) -> Optional[str]:
    """
    Run the engine. On DENY → raise. On NEEDS_APPROVAL → return request ID.
    On ALLOW → return None.
    """
    decision = engine.evaluate(
        action=action,
        tenant_id=tenant_id,
        node_id=node_id,
        requester_id=requester_id,
        requester_role=requester_role,
        existing_approval_id=existing_approval_id,
    )
    if decision.verdict == "deny":
        raise PolicyDeniedError(decision)
    if decision.verdict == "needs_approval":
        return decision.approval_request_id
    return None   # allow


# ─── Hooks ────────────────────────────────────────────────────────────────────

def pre_replay_check(
    engine: PolicyEngine,
    *,
    tenant_id: str,
    node_id: str,
    requester_id: str,
    requester_role: str = "operator",
    existing_approval_id: Optional[str] = None,
) -> Optional[str]:
    """Policy check before scheduling a counterfactual replay."""
    return _check(
        engine, "schedule_replay",
        tenant_id, node_id, requester_id, requester_role, existing_approval_id,
    )


def pre_recovery_check(
    engine: PolicyEngine,
    *,
    tenant_id: str,
    node_id: str,
    requester_id: str,
    requester_role: str = "operator",
    existing_approval_id: Optional[str] = None,
) -> Optional[str]:
    """Policy check before proposing a recovery action."""
    return _check(
        engine, "apply_repair_decision",
        tenant_id, node_id, requester_id, requester_role, existing_approval_id,
    )


def pre_execution_check(
    engine: PolicyEngine,
    *,
    tenant_id: str,
    node_id: str,
    requester_id: str,
    requester_role: str = "operator",
    existing_approval_id: Optional[str] = None,
) -> Optional[str]:
    """Policy check before executing an approved intervention."""
    return _check(
        engine, "apply_intervention",
        tenant_id, node_id, requester_id, requester_role, existing_approval_id,
    )


def pre_rollback_check(
    engine: PolicyEngine,
    *,
    tenant_id: str,
    node_id: str,
    requester_id: str,
    requester_role: str = "operator",
    existing_approval_id: Optional[str] = None,
) -> Optional[str]:
    """Policy check before applying a rollback capsule."""
    return _check(
        engine, "apply_rollback",
        tenant_id, node_id, requester_id, requester_role, existing_approval_id,
    )
