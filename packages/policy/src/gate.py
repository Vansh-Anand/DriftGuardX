"""
DriftGuard-X v2 — Policy Gate

Default-deny policy that requires human approval for all high-risk actions.
Never auto-applies mutations to production state.

PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class PolicyAction(str, enum.Enum):
    ALLOW = "allow"
    DENY = "deny"
    NEEDS_APPROVAL = "needs_approval"


class PolicyRisk(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PolicyRequest:
    """A request for policy evaluation."""

    action: str
    resource: str
    context: dict[str, Any] = field(default_factory=dict)
    requester: str = "system"


@dataclass
class PolicyResult:
    """Result of a policy evaluation."""

    action: PolicyAction
    rule_id: str
    rationale: str
    risk_level: PolicyRisk = PolicyRisk.LOW
    requires_human_approval: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── Built-in Rules ───────────────────────────────────────────────────────────


class PolicyGate:
    """
    Simple policy gate with default-deny for high-risk actions.

    Safety contract:
    - Production state mutations: DENY (always require explicit approval)
    - Memory deletes: DENY
    - Permission grants: DENY
    - Replay creation: NEEDS_APPROVAL (low risk, tracked)
    - Read operations: ALLOW
    """

    # Actions that are always denied without human intervention
    ALWAYS_DENY_ACTIONS: frozenset[str] = frozenset(
        {
            "delete_memory",
            "mutate_production_kb",
            "grant_permissions",
            "execute_arbitrary_shell",
            "modify_external_system",
            "publish_source_code",
            "delete_trace",
            "overwrite_experiment",
        }
    )

    # Actions that need human approval
    NEEDS_APPROVAL_ACTIONS: frozenset[str] = frozenset(
        {
            "apply_rollback",
            "create_replay",
            "apply_repair_decision",
            "apply_intervention",
            "mutate_staging_kb",
        }
    )

    # Read-only actions always allowed
    ALWAYS_ALLOW_ACTIONS: frozenset[str] = frozenset(
        {
            "read_trace",
            "list_runs",
            "get_run",
            "get_replay",
            "read_diagnosis",
            "health_check",
            "ingest_spans",
            "create_run",  # synthetic/mock runs allowed
        }
    )

    def evaluate(self, request: PolicyRequest) -> PolicyResult:
        """Evaluate a policy request. Default: DENY."""
        action = request.action.lower()

        if action in self.ALWAYS_DENY_ACTIONS:
            return PolicyResult(
                action=PolicyAction.DENY,
                rule_id="ALWAYS_DENY",
                rationale=f"Action '{action}' is unconditionally denied by safety policy.",
                risk_level=PolicyRisk.CRITICAL,
                requires_human_approval=False,
            )

        if action in self.ALWAYS_ALLOW_ACTIONS:
            return PolicyResult(
                action=PolicyAction.ALLOW,
                rule_id="ALWAYS_ALLOW",
                rationale=f"Action '{action}' is a safe read-only operation.",
                risk_level=PolicyRisk.LOW,
                requires_human_approval=False,
            )

        if action in self.NEEDS_APPROVAL_ACTIONS:
            return PolicyResult(
                action=PolicyAction.NEEDS_APPROVAL,
                rule_id="NEEDS_HUMAN_APPROVAL",
                rationale=f"Action '{action}' requires human approval before execution.",
                risk_level=PolicyRisk.MEDIUM,
                requires_human_approval=True,
            )

        # Default: deny unknown actions
        return PolicyResult(
            action=PolicyAction.DENY,
            rule_id="DEFAULT_DENY",
            rationale=f"Unknown action '{action}' denied by default-deny policy.",
            risk_level=PolicyRisk.HIGH,
            requires_human_approval=False,
        )


# Singleton
_default_gate = PolicyGate()


def evaluate_policy(
    action: str, resource: str, context: dict[str, Any] | None = None
) -> PolicyResult:
    """Evaluate an action against the default policy gate."""
    request = PolicyRequest(action=action, resource=resource, context=context or {})
    return _default_gate.evaluate(request)
