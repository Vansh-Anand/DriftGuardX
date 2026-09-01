"""
DriftGuard-X v2 — Diagnosis Models
PRIVATE — All Rights Reserved.
"""
from typing import Any
from uuid import UUID
from datetime import datetime
from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow
from packages.contracts.src.models import ComponentType


class CandidateScore(DGXBaseModel):
    score: float
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class RootCauseCandidate(DGXBaseModel):
    candidate_id: UUID = Field(default_factory=_new_uuid)
    component_type: ComponentType
    node_id: str
    score: CandidateScore
    rationale: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiagnosisEpisode(DGXBaseModel):
    episode_id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    candidates: list[RootCauseCandidate] = Field(default_factory=list)
    selected_candidate_id: UUID | None = None
    start_time: datetime = Field(default_factory=_utcnow)
    end_time: datetime | None = None
