"""
DriftGuard-X v2 — Causal Interventions & Quarantine Isolator
PRIVATE — All Rights Reserved.
"""

import uuid
from packages.contracts.src.models import ComponentType

class QuarantineRule:
    def __init__(self, target_component: ComponentType, description: str, enforce_network_isolation: bool = True):
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

    def apply_quarantine(self, root_cause_component: ComponentType, description: str) -> QuarantineRule:
        """
        Creates and registers a quarantine rule for a failing component.
        """
        rule = QuarantineRule(
            target_component=root_cause_component,
            description=description,
            enforce_network_isolation=True
        )
        self._active_rules.append(rule)
        return rule
        
    def check_invocation_allowed(self, component: ComponentType) -> bool:
        """
        Checks if a component is quarantined. Returns True if allowed to run.
        """
        for rule in self._active_rules:
            if rule.active and rule.target_component == component:
                return False # Quarantined
        return True
        
    def list_active_quarantines(self) -> list[QuarantineRule]:
        return [rule for rule in self._active_rules if rule.active]
