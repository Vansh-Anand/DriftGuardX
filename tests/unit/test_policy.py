"""
DriftGuard-X v2 — Policy Gate Tests (2 tests)
"""

from __future__ import annotations

import pytest

from packages.policy.src.gate import PolicyAction, PolicyGate, PolicyRequest


@pytest.mark.unit
def test_policy_default_deny_unknown_action() -> None:
    """Unknown actions are denied by default."""
    gate = PolicyGate()
    result = gate.evaluate(PolicyRequest(action="unknown_action", resource="something"))
    assert result.action == PolicyAction.DENY
    assert result.rule_id == "DEFAULT_DENY"


@pytest.mark.unit
def test_policy_always_deny_high_risk() -> None:
    """High-risk actions like delete_memory are always denied."""
    gate = PolicyGate()
    for dangerous in [
        "delete_memory",
        "mutate_production_kb",
        "grant_permissions",
        "execute_arbitrary_shell",
    ]:
        result = gate.evaluate(PolicyRequest(action=dangerous, resource="system"))
        assert result.action == PolicyAction.DENY, f"Expected DENY for {dangerous}"
        assert result.rule_id == "ALWAYS_DENY"
        assert result.requires_human_approval is False  # no approval path for critical denials
