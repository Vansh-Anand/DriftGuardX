"""
DriftGuard-X v2 — BCRB Models
PRIVATE — All Rights Reserved.
"""
import enum
from typing import Any
from uuid import UUID
from datetime import datetime
from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow
from packages.contracts.src.models import ComponentType, InterventionType


class BCRBStepStatus(str, enum.Enum):
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


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


class BCRBSession(DGXBaseModel):
    session_id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    budget_usd: float
    total_spent_usd: float = 0.0
    candidates: list[BCRBCandidate] = Field(default_factory=list)
    steps: list[BCRBStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
