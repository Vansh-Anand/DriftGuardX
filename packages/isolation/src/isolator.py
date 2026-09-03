"""
DriftGuard-X v2 — Causal Interventions & Quarantine Isolator
PRIVATE — All Rights Reserved.
"""

import uuid

from packages.contracts.src.models import ComponentType
from packages.contracts.src.recovery_models import ReplayStateManifest
from packages.isolation.src.invariance_checker import ContaminationError, InvarianceChecker


class QuarantineRule:
    def __init__(
        self,
        target_component: ComponentType,
        description: str,
        enforce_network_isolation: bool = True,
    ):
        self.rule_id = str(uuid.uuid4())
        self.target_component = target_component
        self.description = description
        self.enforce_network_isolation = enforce_network_isolation
        self.active = True


class CausalIsolator:
    """
    Enforces runtime boundaries by issuing quarantine rules based on diagnosis.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self._active_rules: list[QuarantineRule] = []

    def apply_quarantine(
        self, root_cause_component: ComponentType, description: str
    ) -> QuarantineRule:
        """
        Creates and registers a quarantine rule for a failing component.
        """
        rule = QuarantineRule(
            target_component=root_cause_component,
            description=description,
            enforce_network_isolation=True,
        )
        self._active_rules.append(rule)
        return rule

    def enforce_invariance_and_quarantine(
        self,
        root_cause_component: ComponentType,
        description: str,
        original_manifest: ReplayStateManifest,
        replay_manifest: ReplayStateManifest,
        allowed_descendants: list[str],
        intervened_variables: list[str],
    ) -> QuarantineRule:
        """
        Cryptographically/mathematically verify that no non-target state diverged.
        If it did, refuse the quarantine. Otherwise, apply it.
        """
        try:
            InvarianceChecker.verify_no_contamination(
                original_manifest=original_manifest,
                replay_manifest=replay_manifest,
                allowed_causal_descendants=allowed_descendants,
                intervened_variables=intervened_variables,
            )
        except ContaminationError as e:
            # Item 160: refuse causal confirmation when replay invariance cannot be demonstrated.
            raise ValueError(f"Refusing quarantine due to invariance violation: {e}")

        return self.apply_quarantine(root_cause_component, description)

    def check_invocation_allowed(self, component: ComponentType) -> bool:
        """
        Checks if a component is quarantined. Returns True if allowed to run.
        """
        for rule in self._active_rules:
            if rule.active and rule.target_component == component:
                return False  # Quarantined
        return True

    def list_active_quarantines(self) -> list[QuarantineRule]:
        return [rule for rule in self._active_rules if rule.active]
