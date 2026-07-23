"""
DriftGuard-X v2 — Rationale Data Contracts
PRIVATE — All Rights Reserved.

Defines schemas for deterministic and LLM-generated rationale inputs/outputs.
"""
from __future__ import annotations

import enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from uuid import UUID

from pydantic import Field
from packages.contracts.src.models import DGXBaseModel, ComponentType, _utcnow, _new_uuid


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
    symptom_to_cause_path: List[str]
    root_cause_description: str
    
    # Replay & Metric evidence
    replay_episode_id: Optional[UUID] = None
    original_version_tag: str
    replay_version_tag: str
    metric_deltas: Dict[str, float]
    
    # Certification & Policy evidence
    is_certified: bool
    bound_method: Optional[str] = None
    epsilon: Optional[float] = None
    delta: Optional[float] = None
    policy_decision: str
    action_type: str
    limitations: List[str]
    
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
    factual_consistency_score: Optional[float] = None
    readability_score: Optional[float] = None
    
    # Provenance
    prompt_version: Optional[str] = None
    model_version: Optional[str] = None
    latency_ms: Optional[float] = None
    cost_usd: Optional[float] = None
    created_at: datetime = Field(default_factory=_utcnow)
