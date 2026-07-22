"""
DriftGuard-X v2 — Policy Inheritance Resolver
PRIVATE — All Rights Reserved.

Computes the effective policy for a given (tenant, node, action) triple by
walking the hierarchy from Organization down to Agent, collecting every
matching rule, and applying tightening-only precedence.

Tightening-only rules:
  - DENY always wins over ALLOW or NEEDS_APPROVAL from any parent.
  - NEEDS_APPROVAL wins over ALLOW from any parent.
  - A child can only ADD restrictions (tighten), not remove them.
  - To RELAX a parent restriction the child rule must carry an explicit
    `override_justification`; without it the resolver raises ConflictError.
  - Required approvers can only increase down the hierarchy (never decrease).
  - Budget caps can only decrease down the hierarchy (never increase).

Every call is deterministic: same inputs → same EffectivePolicy.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from packages.policy.src.hierarchy import (
    EffectivePolicy,
    PolicyLevel,
    PolicyNode,
    PolicyRule,
    RiskTier,
    RuleVerdict,
    _action_matches,
)


# ─── Precedence ───────────────────────────────────────────────────────────────
# Lower index = more restrictive = wins when tightening
_VERDICT_PRECEDENCE = {
    RuleVerdict.DENY: 0,
    RuleVerdict.NEEDS_APPROVAL: 1,
    RuleVerdict.ALLOW: 2,
}

_TIER_PRECEDENCE = {
    RiskTier.CRITICAL: 0,
    RiskTier.HIGH: 1,
    RiskTier.MEDIUM: 2,
    RiskTier.LOW: 3,
}

# Hierarchy order (most general → most specific)
_LEVEL_ORDER = [
    PolicyLevel.ORGANIZATION,
    PolicyLevel.BUSINESS_UNIT,
    PolicyLevel.PIPELINE,
    PolicyLevel.AGENT,
]


# ─── Conflict ─────────────────────────────────────────────────────────────────

class PolicyConflictError(ValueError):
    """Raised when a child rule attempts to relax a parent restriction without justification."""
    pass


# ─── PolicyRegistry ───────────────────────────────────────────────────────────

class PolicyRegistry:
    """
    In-memory registry of PolicyNodes keyed by (tenant_id, node_id).
    In production this would be backed by the policy table in the DB.
    """

    def __init__(self):
        self._nodes: Dict[tuple[str, str], PolicyNode] = {}

    def register(self, node: PolicyNode) -> None:
        key = (node.tenant_id, node.node_id)
        self._nodes[key] = node

    def get(self, tenant_id: str, node_id: str) -> Optional[PolicyNode]:
        return self._nodes.get((tenant_id, node_id))

    def all_for_tenant(self, tenant_id: str) -> List[PolicyNode]:
        return [n for (t, _), n in self._nodes.items() if t == tenant_id]


# ─── Resolver ─────────────────────────────────────────────────────────────────

class InheritanceResolver:
    """
    Computes the effective policy for a (tenant, leaf_node_id, action) triple.

    Algorithm:
    1. Walk the ancestor chain from org → leaf, collecting matching rules.
    2. Apply tightening-only precedence:
       a. Verdict: most restrictive wins (DENY > NEEDS_APPROVAL > ALLOW).
       b. Risk tier: most restrictive wins (CRITICAL > HIGH > MEDIUM > LOW).
       c. required_approvers: maximum wins.
       d. max_budget_usd: minimum wins (None = unlimited).
       e. allowed_roles: intersection (most restrictive).
    3. If a child rule is MORE permissive than its parent without an
       override_justification, raise PolicyConflictError.
    4. Return EffectivePolicy with full override_chain for audit.
    """

    def __init__(self, registry: PolicyRegistry):
        self._registry = registry

    def _ancestor_chain(self, tenant_id: str, leaf_node_id: str) -> List[PolicyNode]:
        """Build ancestor chain from org to leaf (inclusive), org first."""
        chain: List[PolicyNode] = []
        node = self._registry.get(tenant_id, leaf_node_id)
        if node is None:
            return []
        visited: set[str] = set()
        while node is not None and node.node_id not in visited:
            chain.append(node)
            visited.add(node.node_id)
            if node.parent_id is None:
                break
            node = self._registry.get(tenant_id, node.parent_id)
        chain.reverse()  # org → leaf order
        return chain

    def resolve(
        self,
        tenant_id: str,
        node_id: str,
        action: str,
        requester_role: str = "operator",
    ) -> EffectivePolicy:
        """
        Compute the effective policy. Raises PolicyConflictError on illegal relaxation.
        Returns a default-deny EffectivePolicy if no matching rules found.
        """
        chain = self._ancestor_chain(tenant_id, node_id)

        if not chain:
            # No policy nodes found for this tenant/node → default deny
            return _default_deny(action, tenant_id, node_id)

        matching_rules: List[PolicyRule] = []
        for node in chain:
            if not node.is_active:
                continue
            rule = node.get_rule_for_action(action)
            if rule is not None:
                matching_rules.append(rule)

        if not matching_rules:
            return _default_deny(action, tenant_id, node_id)

        # ── Apply tightening-only precedence ──────────────────────────────────
        effective_verdict = RuleVerdict.ALLOW  # start permissive, tighten down
        effective_tier = RiskTier.LOW
        effective_approvers = 0
        effective_two_person = False
        effective_budget: Optional[float] = None
        effective_roles: List[str] = []
        winning_rule = matching_rules[0]
        conflict_detected = False
        conflict_description: Optional[str] = None

        for i, rule in enumerate(matching_rules):
            # ── Verdict tightening ────────────────────────────────────────────
            if _VERDICT_PRECEDENCE[rule.verdict] < _VERDICT_PRECEDENCE[effective_verdict]:
                # This rule is MORE restrictive — allowed
                effective_verdict = rule.verdict
                winning_rule = rule
            elif i > 0 and _VERDICT_PRECEDENCE[rule.verdict] > _VERDICT_PRECEDENCE[effective_verdict]:
                # Child is LESS restrictive than parent
                if not rule.override_justification:
                    raise PolicyConflictError(
                        f"Rule {rule.rule_id} at {rule.source_level.value} attempts to relax "
                        f"verdict from {effective_verdict} to {rule.verdict} without override_justification."
                    )
                conflict_detected = True
                conflict_description = (
                    f"Override at {rule.source_level.value}: {rule.override_justification}"
                )

            # ── Risk tier tightening ──────────────────────────────────────────
            if _TIER_PRECEDENCE[rule.risk_tier] < _TIER_PRECEDENCE[effective_tier]:
                effective_tier = rule.risk_tier

            # ── Approvers: take max ───────────────────────────────────────────
            effective_approvers = max(effective_approvers, rule.required_approvers)

            # ── Two-person: sticky true ───────────────────────────────────────
            if rule.two_person_control:
                effective_two_person = True

            # ── Budget: take min (most restrictive) ───────────────────────────
            if rule.max_budget_usd is not None:
                if effective_budget is None:
                    effective_budget = rule.max_budget_usd
                else:
                    effective_budget = min(effective_budget, rule.max_budget_usd)

            # ── Roles: intersection (most restrictive) ────────────────────────
            if rule.allowed_roles:
                if not effective_roles:
                    effective_roles = list(rule.allowed_roles)
                else:
                    effective_roles = [r for r in effective_roles if r in rule.allowed_roles]

        return EffectivePolicy(
            action=action,
            tenant_id=tenant_id,
            node_id=node_id,
            verdict=effective_verdict,
            risk_tier=effective_tier,
            required_approvers=effective_approvers,
            two_person_control=effective_two_person,
            allowed_roles=effective_roles,
            max_budget_usd=effective_budget,
            winning_rule=winning_rule,
            override_chain=matching_rules,
            conflict_detected=conflict_detected,
            conflict_description=conflict_description,
        )


def _default_deny(action: str, tenant_id: str, node_id: str) -> EffectivePolicy:
    """Returns an EffectivePolicy with DENY verdict when no rules match."""
    sentinel = PolicyRule(
        action_pattern=action,
        verdict=RuleVerdict.DENY,
        risk_tier=RiskTier.HIGH,
        rationale="No matching policy rule found. Default deny.",
        source_level=PolicyLevel.ORGANIZATION,
        rule_id="DEFAULT_DENY",
    )
    return EffectivePolicy(
        action=action,
        tenant_id=tenant_id,
        node_id=node_id,
        verdict=RuleVerdict.DENY,
        risk_tier=RiskTier.HIGH,
        required_approvers=0,
        two_person_control=False,
        allowed_roles=[],
        max_budget_usd=None,
        winning_rule=sentinel,
        override_chain=[sentinel],
    )
