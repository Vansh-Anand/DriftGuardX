"""
DriftGuard-X v2 — Rationale Data Contracts
PRIVATE — All Rights Reserved.

Defines schemas for deterministic and LLM-generated rationale inputs/outputs.
"""
from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import Field

from packages.contracts.src.models import ComponentType, DGXBaseModel, _new_uuid, _utcnow


class RationaleStyle(str, enum.Enum):
    OPERATOR_SUMMARY = "operator_summary"
    EXECUTIVE_SUMMARY = "executive_summary"
    INCIDENT_TICKET = "incident_ticket"
    PATENT_NOTE = "patent_note"


class RationaleInputContract(DGXBaseModel):
    """
    Strict evidence payload provided to the rationale generator.
    No free-form data; everything is typed and bounded.
    """
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID

    # Diagnosis evidence
    ranked_cause_component: ComponentType
    symptom_to_cause_path: list[str]
    root_cause_description: str

    # Replay & Metric evidence
    replay_episode_id: UUID | None = None
    original_version_tag: str
    replay_version_tag: str
    metric_deltas: dict[str, float]

    # Certification & Policy evidence
    is_certified: bool
    bound_method: str | None = None
    epsilon: float | None = None
    delta: float | None = None
    policy_decision: str
    action_type: str
    limitations: list[str]

    created_at: datetime = Field(default_factory=_utcnow)


class RationaleOutput(DGXBaseModel):
    """
    The generated rationale output, with factual claims structurally mapped.
    """
    id: UUID = Field(default_factory=_new_uuid)
    input_contract_id: UUID
    style: RationaleStyle

    content: str
    is_llm_generated: bool
    fallback_triggered: bool = False

    # Evaluation scores (optional, populated by validator)
    factual_consistency_score: float | None = None
    readability_score: float | None = None

    # Provenance
    prompt_version: str | None = None
    model_version: str | None = None
    latency_ms: float | None = None
    cost_usd: float | None = None
    created_at: datetime = Field(default_factory=_utcnow)
