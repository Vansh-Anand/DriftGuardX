"""
DriftGuard-X v2 — Reliability Metrics
PRIVATE — All Rights Reserved.
"""
from typing import Optional
from pydantic import BaseModel, Field

class ReliabilityVector(BaseModel):
    """
    Standardized vector capturing multi-dimensional reliability of an episode.
    """
    faithfulness: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieval_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    task_success: float = Field(default=0.0, ge=0.0, le=1.0)
    citation_consistency: float = Field(default=0.0, ge=0.0, le=1.0)
    tool_validity: float = Field(default=0.0, ge=0.0, le=1.0)
    memory_safety: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_compliance: float = Field(default=1.0, ge=0.0, le=1.0)  # 1.0 = compliant
    
    latency_ms: float = Field(default=0.0, ge=0.0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    operational_errors: int = Field(default=0, ge=0)
    
    # Store evaluator settings for transparency
    evaluator_versions: dict[str, str] = Field(default_factory=dict)
    confidence_labels: dict[str, str] = Field(default_factory=dict)
