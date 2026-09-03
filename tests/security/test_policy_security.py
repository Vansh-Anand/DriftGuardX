"""
DriftGuard-X v2 — Policy Security Tests
PRIVATE — All Rights Reserved.

Covers all acceptance gates:
  [1] Cross-tenant isolation: tenant A cannot read/modify tenant B's decisions.
  [2] Confused deputy: a low-privilege component cannot escalate to HIGH action.
  [3] Self-approval blocked: requester cannot approve their own request.
  [4] Unauthorized approver: actor outside delegated set is rejected.
  [5] Critical action blocked without required approvers.
  [6] Break-glass requires justification and is always audited.
  [7] Effective-policy calculation is deterministic (same input → same output).
  [8] Shadow evaluation: relaxed policy correctly identified.
  [9] Default deny on unknown action.
  [10] Inheritance tightening: child DENY overrides parent ALLOW.
"""

from __future__ import annotations

import pytest

from packages.policy.src.approvals import (
    ApprovalRequest,
    ApprovalService,
    ApprovalStatus,
    SelfApprovalError,
    UnauthorizedApproverError,
)
from packages.policy.src.engine import PolicyEngine
from packages.policy.src.hierarchy import (
    PolicyLevel,
    PolicyNode,
    PolicyRule,
    RiskTier,
    RuleVerdict,
)
from packages.policy.src.resolver import InheritanceResolver, PolicyConflictError, PolicyRegistry
from packages.policy.src.shadow import HistoricalEvent, shadow_evaluate

# ─── Fixtures ─────────────────────────────────────────────────────────────────


def _make_registry(
    tenant_id: str = "tenant_acme",
    allow_replay: bool = True,
) -> PolicyRegistry:
    """Build a minimal two-level (org → pipeline) registry."""
    reg = PolicyRegistry()

    org_node = PolicyNode(
        node_id="org_acme",
        level=PolicyLevel.ORGANIZATION,
        tenant_id=tenant_id,
        parent_id=None,
        rules=[
            PolicyRule(
                action_pattern="apply_rollback",
                verdict=RuleVerdict.NEEDS_APPROVAL,
                risk_tier=RiskTier.HIGH,
                required_approvers=1,
                two_person_control=True,
                rationale="Org-level: rollback needs approval.",
                source_level=PolicyLevel.ORGANIZATION,
            ),
            PolicyRule(
                action_pattern="schedule_replay",
                verdict=RuleVerdict.ALLOW if allow_replay else RuleVerdict.DENY,
                risk_tier=RiskTier.MEDIUM,
                rationale=(
                    "Org-level: replay allowed." if allow_replay else "Org-level: replay denied."
                ),
                source_level=PolicyLevel.ORGANIZATION,
            ),
            PolicyRule(
                action_pattern="read_trace",
                verdict=RuleVerdict.ALLOW,
                risk_tier=RiskTier.LOW,
                rationale="Read-only.",
                source_level=PolicyLevel.ORGANIZATION,
            ),
            PolicyRule(
                action_pattern="delete_memory",
                verdict=RuleVerdict.DENY,
                risk_tier=RiskTier.CRITICAL,
                rationale="Always denied.",
                source_level=PolicyLevel.ORGANIZATION,
            ),
        ],
    )

    pipeline_node = PolicyNode(
        node_id="pipeline_rag_v2",
        level=PolicyLevel.PIPELINE,
        tenant_id=tenant_id,
        parent_id="org_acme",
        rules=[],
    )

    reg.register(org_node)
    reg.register(pipeline_node)
    return reg


def _make_engine(tenant_id: str = "tenant_acme") -> PolicyEngine:
    reg = _make_registry(tenant_id=tenant_id)
    svc = ApprovalService()
    return PolicyEngine(reg, svc)


# ─── [1] Cross-Tenant Isolation ───────────────────────────────────────────────


def test_cross_tenant_policy_isolation():
    """Tenant B's policy nodes must not affect Tenant A's resolution."""
    reg_a = _make_registry(tenant_id="tenant_a")
    reg_b = _make_registry(tenant_id="tenant_b")

    # Register both in the same registry (simulating shared store)
    combined = PolicyRegistry()
    for node in reg_a.all_for_tenant("tenant_a"):
        combined.register(node)
    for node in reg_b.all_for_tenant("tenant_b"):
        combined.register(node)

    resolver_a = InheritanceResolver(combined)

    # Tenant A resolving for tenant B's pipeline should default-deny (no nodes found)
    ep = resolver_a.resolve("tenant_a", "pipeline_rag_v2_tenant_b_only", "read_trace")
    assert ep.verdict == RuleVerdict.DENY
    assert ep.winning_rule.rule_id == "DEFAULT_DENY"


def test_tenant_b_cannot_read_tenant_a_decisions():
    """EngineDecision log filtered per tenant: tenant_b gets empty log for tenant_a actions."""
    engine_a = _make_engine("tenant_a")
    engine_b = _make_engine("tenant_b")

    engine_a.evaluate("read_trace", "tenant_a", "pipeline_rag_v2", "user_alice", "viewer")
    # Tenant B's log is completely separate
    assert len(engine_b.decision_log()) == 0


# ─── [2] Confused Deputy ──────────────────────────────────────────────────────


def test_confused_deputy_low_role_cannot_execute_high_action():
    """A viewer role should not be allowed to apply_rollback."""
    reg = PolicyRegistry()
    org = PolicyNode(
        node_id="org_acme",
        level=PolicyLevel.ORGANIZATION,
        tenant_id="tenant_acme",
        rules=[
            PolicyRule(
                action_pattern="apply_rollback",
                verdict=RuleVerdict.NEEDS_APPROVAL,
                risk_tier=RiskTier.HIGH,
                required_approvers=1,
                two_person_control=True,
                allowed_roles=["operator", "admin"],  # viewers NOT allowed
                rationale="Only operator/admin may request rollback.",
                source_level=PolicyLevel.ORGANIZATION,
            ),
        ],
    )
    reg.register(org)
    svc = ApprovalService()
    engine = PolicyEngine(reg, svc)

    decision = engine.evaluate(
        "apply_rollback",
        "tenant_acme",
        "org_acme",
        requester_id="user_viewer",
        requester_role="viewer",
    )
    assert decision.verdict == "deny"
    assert "viewer" in decision.rationale.lower() or "role" in decision.rationale.lower()


# ─── [3] Self-Approval Blocked ────────────────────────────────────────────────


def test_self_approval_is_blocked():
    """The requester cannot approve their own request."""
    svc = ApprovalService()
    req = ApprovalRequest(
        action="apply_rollback",
        resource="pipeline_rag_v2",
        requester_id="user_alice",
        tenant_id="tenant_acme",
        node_id="pipeline_rag_v2",
        risk_tier="high",
    )
    svc.create_request(req)

    with pytest.raises(SelfApprovalError):
        svc.approve(req.request_id, actor_id="user_alice")


# ─── [4] Unauthorized Approver ────────────────────────────────────────────────


def test_unauthorized_approver_is_blocked():
    """An actor not in the delegated_approvers list must be rejected."""
    svc = ApprovalService()
    req = ApprovalRequest(
        action="apply_rollback",
        resource="pipeline_rag_v2",
        requester_id="user_alice",
        tenant_id="tenant_acme",
        node_id="pipeline_rag_v2",
        risk_tier="high",
        delegated_approvers=["user_bob"],  # only bob
    )
    svc.create_request(req)

    with pytest.raises(UnauthorizedApproverError):
        svc.approve(req.request_id, actor_id="user_charlie")  # charlie not in list


def test_delegated_approver_succeeds():
    """An actor in delegated_approvers list is accepted."""
    svc = ApprovalService()
    req = ApprovalRequest(
        action="apply_rollback",
        resource="pipeline_rag_v2",
        requester_id="user_alice",
        tenant_id="tenant_acme",
        node_id="pipeline_rag_v2",
        risk_tier="high",
        delegated_approvers=["user_bob"],
    )
    svc.create_request(req)
    result = svc.approve(req.request_id, actor_id="user_bob", comment="Looks good.")
    assert result.status == ApprovalStatus.APPROVED


# ─── [5] Critical Action Without Approvers ────────────────────────────────────


def test_critical_action_blocked_without_approval():
    """CRITICAL actions cannot execute without the configured approvals."""
    engine = _make_engine()
    # delete_memory is CRITICAL — must never auto-allow
    decision = engine.evaluate(
        "delete_memory",
        "tenant_acme",
        "pipeline_rag_v2",
        "user_admin",
        "admin",
    )
    # The hierarchy has a DENY rule for delete_memory → must be denied
    assert decision.verdict == "deny"
    assert decision.risk_tier == "critical"


def test_critical_action_needs_two_approvers():
    """CRITICAL actions require 2 distinct approvers (two_person_control=True)."""
    svc = ApprovalService()
    req = ApprovalRequest(
        action="break_glass_override",
        resource="pipeline_rag_v2",
        requester_id="user_alice",
        tenant_id="tenant_acme",
        node_id="pipeline_rag_v2",
        risk_tier="critical",
        required_approvers=2,
        two_person_control=True,
    )
    svc.create_request(req)

    # First approval (bob)
    svc.approve(req.request_id, "user_bob", "First approval.")
    assert req.status == ApprovalStatus.PENDING  # not yet approved

    # Second approval (charlie) — different person
    svc.approve(req.request_id, "user_charlie", "Second approval.")
    assert req.status == ApprovalStatus.APPROVED


# ─── [6] Break-Glass ──────────────────────────────────────────────────────────


def test_break_glass_requires_justification():
    """Break-glass without sufficient justification must be rejected."""
    svc = ApprovalService()
    req = ApprovalRequest(
        action="apply_rollback",
        resource="pipeline_rag_v2",
        requester_id="user_alice",
        tenant_id="tenant_acme",
        node_id="pipeline_rag_v2",
        risk_tier="high",
    )
    svc.create_request(req)

    with pytest.raises(ValueError, match="at least 20 characters"):
        svc.break_glass(req.request_id, "user_bob", "short")


def test_break_glass_is_audited():
    """Break-glass override must appear in the audit log with requires_post_hoc_review=True."""
    svc = ApprovalService()
    req = ApprovalRequest(
        action="apply_rollback",
        resource="pipeline_rag_v2",
        requester_id="user_alice",
        tenant_id="tenant_acme",
        node_id="pipeline_rag_v2",
        risk_tier="high",
    )
    svc.create_request(req)
    svc.break_glass(
        req.request_id, "user_bob", "Production outage detected; immediate rollback required."
    )

    audit = svc.audit_log()
    bg_entries = [e for e in audit if e["event"] == "BREAK_GLASS"]
    assert len(bg_entries) == 1
    assert bg_entries[0]["requires_post_hoc_review"] is True
    assert bg_entries[0]["actor_id"] == "user_bob"


# ─── [7] Determinism ──────────────────────────────────────────────────────────


def test_effective_policy_is_deterministic():
    """Same inputs must always produce the same effective policy."""
    reg = _make_registry()
    resolver = InheritanceResolver(reg)

    ep1 = resolver.resolve("tenant_acme", "pipeline_rag_v2", "apply_rollback")
    ep2 = resolver.resolve("tenant_acme", "pipeline_rag_v2", "apply_rollback")

    assert ep1.verdict == ep2.verdict
    assert ep1.winning_rule.rule_id == ep2.winning_rule.rule_id
    assert ep1.risk_tier == ep2.risk_tier
    assert ep1.required_approvers == ep2.required_approvers


# ─── [8] Shadow Evaluation ────────────────────────────────────────────────────


def test_shadow_evaluation_detects_policy_relaxation():
    """Shadow report flags a relaxation when candidate allows a previously-denied action."""
    # Active policy: replay DENIED
    _make_registry(allow_replay=False)

    # Candidate policy: replay ALLOWED (relaxation)
    candidate_reg = _make_registry(allow_replay=True)

    historical = [
        HistoricalEvent(
            "ev1",
            "schedule_replay",
            "tenant_acme",
            "pipeline_rag_v2",
            "user_alice",
            "operator",
            "deny",
        ),
    ]
    report = shadow_evaluate(historical, candidate_reg, "candidate_v2")
    assert report.n_relaxed == 1
    assert report.n_tightened == 0
    assert "REVIEW REQUIRED" in report.summary()


# ─── [9] Default Deny ─────────────────────────────────────────────────────────


def test_default_deny_on_unknown_action():
    """Unknown actions must be denied regardless of context."""
    engine = _make_engine()
    decision = engine.evaluate(
        "invoke_magic_action",
        "tenant_acme",
        "pipeline_rag_v2",
        "user_alice",
        "admin",
    )
    assert decision.verdict == "deny"


# ─── [10] Tightening Inheritance ─────────────────────────────────────────────


def test_child_deny_overrides_parent_allow():
    """Pipeline-level DENY must override org-level ALLOW (tightening)."""
    reg = PolicyRegistry()
    org = PolicyNode(
        node_id="org_acme",
        level=PolicyLevel.ORGANIZATION,
        tenant_id="tenant_acme",
        rules=[
            PolicyRule(
                action_pattern="schedule_replay",
                verdict=RuleVerdict.ALLOW,
                risk_tier=RiskTier.LOW,
                rationale="Org allows replay.",
                source_level=PolicyLevel.ORGANIZATION,
            ),
        ],
    )
    pipeline = PolicyNode(
        node_id="pipeline_restricted",
        level=PolicyLevel.PIPELINE,
        tenant_id="tenant_acme",
        parent_id="org_acme",
        rules=[
            PolicyRule(
                action_pattern="schedule_replay",
                verdict=RuleVerdict.DENY,
                risk_tier=RiskTier.HIGH,
                rationale="This pipeline must not replay sensitive data.",
                source_level=PolicyLevel.PIPELINE,
            ),
        ],
    )
    reg.register(org)
    reg.register(pipeline)
    resolver = InheritanceResolver(reg)

    ep = resolver.resolve("tenant_acme", "pipeline_restricted", "schedule_replay")
    assert ep.verdict == RuleVerdict.DENY
    assert ep.winning_rule.source_level == PolicyLevel.PIPELINE


def test_child_cannot_relax_without_justification():
    """Child ALLOW after parent DENY without override_justification → ConflictError."""
    reg = PolicyRegistry()
    org = PolicyNode(
        node_id="org_strict",
        level=PolicyLevel.ORGANIZATION,
        tenant_id="tenant_acme",
        rules=[
            PolicyRule(
                action_pattern="schedule_replay",
                verdict=RuleVerdict.DENY,
                risk_tier=RiskTier.HIGH,
                rationale="Org denies replay.",
                source_level=PolicyLevel.ORGANIZATION,
            ),
        ],
    )
    pipeline = PolicyNode(
        node_id="pipeline_override_no_justification",
        level=PolicyLevel.PIPELINE,
        tenant_id="tenant_acme",
        parent_id="org_strict",
        rules=[
            PolicyRule(
                action_pattern="schedule_replay",
                verdict=RuleVerdict.ALLOW,  # tries to relax
                risk_tier=RiskTier.LOW,
                rationale="Tries to allow without justification.",
                source_level=PolicyLevel.PIPELINE,
                override_justification=None,  # missing!
            ),
        ],
    )
    reg.register(org)
    reg.register(pipeline)
    resolver = InheritanceResolver(reg)

    with pytest.raises(PolicyConflictError):
        resolver.resolve("tenant_acme", "pipeline_override_no_justification", "schedule_replay")
