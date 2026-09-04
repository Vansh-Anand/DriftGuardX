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
        target_component: ComponentType | str,
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

    async def async_apply_quarantine(
        self, root_cause_component: ComponentType | str, description: str, db=None
    ) -> QuarantineRule:
        """
        Creates and registers a quarantine rule for a failing component. Durably stores it if db provided.
        """
        rule = QuarantineRule(
            target_component=root_cause_component,
            description=description,
            enforce_network_isolation=True,
        )
        self._active_rules.append(rule)

        if db:
            from apps.api.src.models import QuarantineRuleORM
            comp_str = root_cause_component.value if hasattr(root_cause_component, "value") else str(root_cause_component)
            orm_rule = QuarantineRuleORM(
                id=uuid.UUID(rule.rule_id),
                tenant_id=uuid.UUID(self.tenant_id),
                target_component=comp_str,
                description=description,
                enforce_network_isolation=True,
                active=True,
            )
            db.add(orm_rule)
            await db.flush()

        return rule

    async def async_remove_quarantine(self, rule_id: str, db=None) -> None:
        """
        Removes/deactivates a quarantine rule, rolling back its effect. Durably updates db if provided.
        """
        for rule in self._active_rules:
            if rule.rule_id == rule_id:
                rule.active = False
                
        if db:
            from sqlalchemy import select
            from apps.api.src.models import QuarantineRuleORM
            stmt = select(QuarantineRuleORM).where(QuarantineRuleORM.id == uuid.UUID(rule_id))
            result = await db.execute(stmt)
            rule_orm = result.scalar_one_or_none()
            if rule_orm:
                rule_orm.active = False
                await db.flush()

    def apply_quarantine(
        self, root_cause_component: ComponentType | str, description: str
    ) -> QuarantineRule:
        """Sync wrapper for tests or legacy code without DB access."""
        rule = QuarantineRule(
            target_component=root_cause_component,
            description=description,
            enforce_network_isolation=True,
        )
        self._active_rules.append(rule)
        return rule

    async def async_get_quarantined_agents(self, db=None) -> set[str]:
        """
        Returns a set of quarantined agent names for routing (combining in-memory and durable rules).
        """
        quarantined = set()
        for rule in self._active_rules:
            if rule.active:
                comp_str = rule.target_component.value if hasattr(rule.target_component, "value") else str(rule.target_component)
                quarantined.add(comp_str)

        if db:
            from sqlalchemy import select
            from apps.api.src.models import QuarantineRuleORM
            stmt = select(QuarantineRuleORM).where(
                QuarantineRuleORM.tenant_id == uuid.UUID(self.tenant_id),
                QuarantineRuleORM.active == True
            )
            result = await db.execute(stmt)
            for rule_orm in result.scalars().all():
                quarantined.add(rule_orm.target_component)

        return quarantined

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
        comp_str = component.value if hasattr(component, "value") else str(component)
        for rule in self._active_rules:
            r_comp_str = rule.target_component.value if hasattr(rule.target_component, "value") else str(rule.target_component)
            if rule.active and r_comp_str == comp_str:
                return False  # Quarantined
        return True

    def list_active_quarantines(self) -> list[QuarantineRule]:
        return [rule for rule in self._active_rules if rule.active]
