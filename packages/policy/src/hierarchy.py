"""
DriftGuard-X v2 — Policy Hierarchy Schemas
PRIVATE — All Rights Reserved.

Defines the four-level policy hierarchy:
  Organization → BusinessUnit → Pipeline → Agent

Inheritance is tightening-only by default: child policies can only restrict,
never expand, permissions inherited from a parent.  Controlled exceptions
require an explicit `override_justification` and reviewer sign-off recorded
in `override_metadata`.

Every effective policy rule can be traced to its source level and override
chain via `source_level` and `override_chain` fields.
"""
from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

# ─── Enums ────────────────────────────────────────────────────────────────────

class PolicyLevel(str, enum.Enum):
    ORGANIZATION = "organization"
    BUSINESS_UNIT = "business_unit"
    PIPELINE = "pipeline"
    AGENT = "agent"


class RuleVerdict(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"


class RiskTier(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ─── Policy Rule ──────────────────────────────────────────────────────────────

@dataclass
class PolicyRule:
    """
    A single immutable policy rule.

    Attributes
    ----------
    rule_id:           Unique identifier (auto-generated).
    action_pattern:    Glob-style action string, e.g. "apply_rollback" or "replay.*".
    verdict:           ALLOW | DENY | NEEDS_APPROVAL.
    risk_tier:         The risk classification of this rule.
    required_approvers: Minimum number of approvers for NEEDS_APPROVAL verdict.
    two_person_control: If True, the approver must be a different person from requester.
    allowed_roles:     If non-empty, only these roles may execute this action.
    max_budget_usd:    Optional spend cap for replay/intervention actions.
    data_retention_days: Optional retention limit.
    rationale:         Human-readable explanation.
    source_level:      Which level in the hierarchy defined this rule.
    override_justification: Required when a child rule expands a parent restriction.
    override_metadata: Reviewer sign-off for override.
    version:           Immutable version hash (auto-computed).
    """
    action_pattern: str
    verdict: RuleVerdict
    risk_tier: RiskTier
    required_approvers: int = 1
    two_person_control: bool = False
    allowed_roles: list[str] = field(default_factory=list)
    max_budget_usd: float | None = None
    data_retention_days: int | None = None
    rationale: str = ""
    source_level: PolicyLevel = PolicyLevel.ORGANIZATION
    override_justification: str | None = None
    override_metadata: dict[str, Any] = field(default_factory=dict)
    rule_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    _version: str = field(default="", init=False, repr=False)

    def __post_init__(self):
        # Compute immutable content hash (excludes created_at and rule_id for determinism)
        payload = json.dumps({
            "action_pattern": self.action_pattern,
            "verdict": self.verdict,
            "risk_tier": self.risk_tier,
            "required_approvers": self.required_approvers,
            "two_person_control": self.two_person_control,
            "allowed_roles": sorted(self.allowed_roles),
            "max_budget_usd": self.max_budget_usd,
            "data_retention_days": self.data_retention_days,
        }, sort_keys=True)
        self._version = hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def version(self) -> str:
        return self._version


# ─── Policy Node ─────────────────────────────────────────────────────────────

@dataclass
class PolicyNode:
    """
    A policy at one level of the hierarchy.

    Attributes
    ----------
    node_id:    Identifier of the org/BU/pipeline/agent this policy governs.
    level:      Which hierarchy level this node is at.
    tenant_id:  Tenant isolation — nodes from different tenants never interact.
    parent_id:  Reference to the parent node_id (None at org level).
    rules:      Ordered list of rules (earlier rules take priority).
    is_active:  Inactive nodes are skipped in resolution.
    schema_version: Policy schema version for forward-compatibility.
    """
    node_id: str
    level: PolicyLevel
    tenant_id: str
    parent_id: str | None = None
    rules: list[PolicyRule] = field(default_factory=list)
    is_active: bool = True
    schema_version: str = "v1.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def get_rule_for_action(self, action: str) -> PolicyRule | None:
        """Return the first matching rule for an action (first-match wins)."""
        for rule in self.rules:
            if _action_matches(rule.action_pattern, action):
                return rule
        return None


def _action_matches(pattern: str, action: str) -> bool:
    """Simple glob: 'replay.*' matches 'replay.create', exact match otherwise."""
    if pattern.endswith(".*"):
        prefix = pattern[:-2]
        return action == prefix or action.startswith(prefix + ".")
    return pattern == action


# ─── Effective Policy ─────────────────────────────────────────────────────────

@dataclass
class EffectivePolicy:
    """
    The computed effective policy for a specific (tenant, node_id, action) tuple.

    Provides full audit trail: which level won, and the full override chain.
    """
    action: str
    tenant_id: str
    node_id: str
    verdict: RuleVerdict
    risk_tier: RiskTier
    required_approvers: int
    two_person_control: bool
    allowed_roles: list[str]
    max_budget_usd: float | None
    winning_rule: PolicyRule
    override_chain: list[PolicyRule]   # ordered: org → BU → pipeline → agent
    conflict_detected: bool = False
    conflict_description: str | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def explain(self) -> str:
        """Human-readable explanation of how this effective policy was derived."""
        lines = [
            f"Action: {self.action}",
            f"Verdict: {self.verdict.value.upper()} (risk={self.risk_tier.value})",
            f"Winning rule: {self.winning_rule.rule_id} at {self.winning_rule.source_level.value}",
            f"Rationale: {self.winning_rule.rationale}",
        ]
        if self.override_chain:
            lines.append("Override chain:")
            for i, r in enumerate(self.override_chain):
                lines.append(f"  [{i+1}] {r.source_level.value}: {r.verdict.value} "
                              f"(rule={r.rule_id}, v={r.version})")
        if self.conflict_detected:
            lines.append(f"⚠ Conflict: {self.conflict_description}")
        return "\n".join(lines)
