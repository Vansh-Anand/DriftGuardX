"""
DriftGuard-X v2 — Unified Policy Engine
PRIVATE — All Rights Reserved.

Integrates the hierarchy resolver, risk tier registry, and approval service
into a single evaluator. This is the single entry point for all policy checks.

All policy decisions are logged with: action, tenant, node, verdict, rule_id,
policy_version, requester_role, and timestamp.

Default-deny contract:
  - Unknown action → DENY
  - Missing policy node → DENY
  - Resolver error → DENY (fail-closed)
  - Missing approval for HIGH/CRITICAL → NEEDS_APPROVAL (not ALLOW)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from packages.policy.src.hierarchy import EffectivePolicy, RuleVerdict
from packages.policy.src.resolver import InheritanceResolver, PolicyRegistry
from packages.policy.src.tiers import get_tier, get_approval_requirements
from packages.policy.src.approvals import (
    ApprovalRequest,
    ApprovalService,
    ApprovalStatus,
)

# Re-export the existing gate for backward compatibility
from packages.policy.src.gate import PolicyGate, PolicyAction, PolicyRisk, PolicyResult  # noqa: F401


# ─── Engine Decision ──────────────────────────────────────────────────────────

@dataclass
class EngineDecision:
    """
    Full policy decision including hierarchy resolution and approval status.
    Machine-readable fields for audit and certificate integration.
    """
    decision_id: str = field(default_factory=lambda: str(uuid4()))
    action: str = ""
    tenant_id: str = ""
    node_id: str = ""
    requester_id: str = ""
    requester_role: str = ""
    verdict: str = "deny"           # "allow" | "deny" | "needs_approval"
    risk_tier: str = "high"
    rule_id: str = "DEFAULT_DENY"
    policy_version: str = "unknown"
    rationale: str = ""
    requires_approval: bool = False
    two_person_control: bool = False
    approval_request_id: Optional[str] = None
    effective_policy: Optional[EffectivePolicy] = None
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Policy Engine ────────────────────────────────────────────────────────────

class PolicyEngine:
    """
    Unified policy evaluator.

    Usage:
        engine = PolicyEngine(registry, approval_service)
        decision = engine.evaluate(
            action="apply_rollback",
            tenant_id="tenant_acme",
            node_id="pipeline_rag_v2",
            requester_id="user_alice",
            requester_role="operator",
        )
        if decision.verdict == "deny":
            raise PermissionError(decision.rationale)
        elif decision.verdict == "needs_approval":
            # create approval request via decision.approval_request_id
    """

    def __init__(
        self,
        registry: PolicyRegistry,
        approval_service: ApprovalService,
    ):
        self._resolver = InheritanceResolver(registry)
        self._approvals = approval_service
        self._decision_log: list[EngineDecision] = []

    def evaluate(
        self,
        action: str,
        tenant_id: str,
        node_id: str,
        requester_id: str,
        requester_role: str = "operator",
        existing_approval_id: Optional[str] = None,
    ) -> EngineDecision:
        """
        Full policy evaluation pipeline:
        1. Resolve effective policy from hierarchy.
        2. Check risk tier requirements.
        3. If approval required, check for existing approved request.
        4. Log and return decision.
        """
        decision = EngineDecision(
            action=action,
            tenant_id=tenant_id,
            node_id=node_id,
            requester_id=requester_id,
            requester_role=requester_role,
        )

        # ── Step 1: Hierarchy resolution ──────────────────────────────────────
        try:
            ep = self._resolver.resolve(tenant_id, node_id, action, requester_role)
        except Exception as exc:
            decision.verdict = "deny"
            decision.rationale = f"Policy resolution error (fail-closed): {exc}"
            decision.rule_id = "RESOLUTION_ERROR"
            self._log(decision)
            return decision

        decision.effective_policy = ep
        decision.risk_tier = ep.risk_tier.value
        decision.rule_id = ep.winning_rule.rule_id
        decision.policy_version = ep.winning_rule.version

        # ── Step 2: Base verdict from hierarchy ───────────────────────────────
        if ep.verdict == RuleVerdict.DENY:
            decision.verdict = "deny"
            decision.rationale = ep.winning_rule.rationale or "Denied by policy."
            self._log(decision)
            return decision

        # ── Step 3: Role check ────────────────────────────────────────────────
        if ep.allowed_roles and requester_role not in ep.allowed_roles:
            decision.verdict = "deny"
            decision.rationale = (
                f"Role '{requester_role}' not in allowed roles {ep.allowed_roles}."
            )
            decision.rule_id = "ROLE_DENIED"
            self._log(decision)
            return decision

        # ── Step 4: Approval check ────────────────────────────────────────────
        if ep.verdict == RuleVerdict.NEEDS_APPROVAL or ep.required_approvers > 0:
            decision.requires_approval = True
            decision.two_person_control = ep.two_person_control

            if existing_approval_id:
                # Validate the existing approval
                req = self._approvals.get_request(existing_approval_id)
                if (req and req.status == ApprovalStatus.APPROVED
                        and req.action == action
                        and req.tenant_id == tenant_id):
                    decision.verdict = "allow"
                    decision.rationale = f"Approved via request {existing_approval_id}."
                    decision.approval_request_id = existing_approval_id
                    self._log(decision)
                    return decision
                elif req and req.status == ApprovalStatus.BREAK_GLASS:
                    decision.verdict = "allow"
                    decision.rationale = f"Break-glass override {existing_approval_id}."
                    decision.approval_request_id = existing_approval_id
                    self._log(decision)
                    return decision

            # No valid approval → create approval request and return needs_approval
            tier_reqs = get_approval_requirements(action)
            new_req = ApprovalRequest(
                action=action,
                resource=node_id,
                requester_id=requester_id,
                tenant_id=tenant_id,
                node_id=node_id,
                risk_tier=ep.risk_tier.value,
                required_approvers=max(ep.required_approvers, tier_reqs["required_approvers"]),
                two_person_control=ep.two_person_control or tier_reqs["two_person_control"],
            )
            self._approvals.create_request(new_req)
            decision.verdict = "needs_approval"
            decision.rationale = (
                f"Action '{action}' requires {new_req.required_approvers} approver(s). "
                f"Approval request created: {new_req.request_id}"
            )
            decision.approval_request_id = new_req.request_id
            self._log(decision)
            return decision

        # ── Step 5: ALLOW ─────────────────────────────────────────────────────
        decision.verdict = "allow"
        decision.rationale = ep.winning_rule.rationale or f"Action '{action}' is permitted."
        self._log(decision)
        return decision

    def decision_log(self) -> list[EngineDecision]:
        return list(self._decision_log)

    def _log(self, decision: EngineDecision) -> None:
        self._decision_log.append(decision)
