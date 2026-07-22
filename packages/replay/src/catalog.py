"""
DriftGuard-X v2 — Intervention Catalog
PRIVATE — All Rights Reserved.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from packages.contracts.src.models import ComponentType, InterventionType

class InterventionSchema(BaseModel):
    intervention_type: InterventionType
    description: str
    estimated_cost_usd: float
    risk_tier: str  # low, medium, high, critical
    rollback_strategy: str
    required_approvals: List[str] = Field(default_factory=list)
    compatibility_constraints: List[str] = Field(default_factory=list)


class InterventionCatalog:
    """
    Catalog of available interventions per component type.
    """
    
    @staticmethod
    def get_catalog() -> Dict[ComponentType, List[InterventionSchema]]:
        return {
            ComponentType.RETRIEVER: [
                InterventionSchema(
                    intervention_type=InterventionType.ROLLBACK,
                    description="Revert retriever index to a prior stable version.",
                    estimated_cost_usd=0.01,
                    risk_tier="medium",
                    rollback_strategy="Pointer swap",
                    required_approvals=["eng_lead"]
                ),
                InterventionSchema(
                    intervention_type=InterventionType.CONFIG_PATCH,
                    description="Adjust Top-K or semantic similarity thresholds.",
                    estimated_cost_usd=0.00,
                    risk_tier="low",
                    rollback_strategy="Dynamic config update",
                )
            ],
            ComponentType.GENERATOR: [
                InterventionSchema(
                    intervention_type=InterventionType.ALTERNATE_STABLE,
                    description="Swap the LLM backend to an alternate provider.",
                    estimated_cost_usd=0.05,
                    risk_tier="high",
                    rollback_strategy="Router fallback",
                    required_approvals=["eng_lead", "cost_owner"],
                    compatibility_constraints=["Requires matching context window"]
                )
            ],
            ComponentType.POLICY_CHECK: [
                InterventionSchema(
                    intervention_type=InterventionType.DISABLE,
                    description="Temporarily bypass a failing guardrail policy.",
                    estimated_cost_usd=0.00,
                    risk_tier="critical",
                    rollback_strategy="Re-enable flag",
                    required_approvals=["security_team", "legal"]
                )
            ]
        }
