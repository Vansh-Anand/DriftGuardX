"""
DriftGuard-X v2 — BCRB Models
PRIVATE — All Rights Reserved.
"""

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from packages.contracts.src.models import (
    ComponentType,
    DGXBaseModel,
    InterventionType,
    _new_uuid,
    _utcnow,
)


class BCRBStepStatus(str, enum.Enum):
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class UnifiedCandidatePrior(DGXBaseModel):
    candidate_component: str
    gat_score: float
    diffusion_score: float
    symptom_evidence: float
    combined_prior: float
    evidence_breakdown: dict[str, Any]

class BCRBCandidate(DGXBaseModel):
    candidate_id: UUID = Field(default_factory=_new_uuid)
    component_type: ComponentType
    intervention_type: InterventionType
    estimated_utility: float = 0.0
    cost_estimate: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class BCRBStep(DGXBaseModel):
    step_id: UUID = Field(default_factory=_new_uuid)
    session_id: UUID
    candidate_id: UUID
    status: BCRBStepStatus = BCRBStepStatus.PLANNED
    replay_episode_id: UUID | None = None
    utility_observed: float | None = None
    cost_incurred: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None


class StoppingCondition(str, enum.Enum):
    CONFIDENCE_REACHED = "confidence_reached"
    RELIABILITY_RECOVERED = "reliability_recovered"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ALL_SAFE_CANDIDATES_TESTED = "all_safe_candidates_tested"
    EXPECTED_UTILITY_BELOW_THRESHOLD = "expected_utility_below_threshold"


class DiagnosisOutcome(str, enum.Enum):
    CONFIRMED = "confirmed"
    UNKNOWN = "unknown"


class BCRBSession(DGXBaseModel):
    session_id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    budget_usd: float
    total_spent_usd: float = 0.0
    candidates: list[BCRBCandidate] = Field(default_factory=list)
    steps: list[BCRBStep] = Field(default_factory=list)
    stopping_condition_met: StoppingCondition | None = None
    diagnosis_outcome: DiagnosisOutcome | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
