"""
DriftGuard-X v2 — SDK Models
Public DTO contracts for the Trace SDK, separating the SDK interface from internal API schemas.
"""

from typing import Any, Literal
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class FinalizeRunRequest(BaseModel):
    status: Literal["COMPLETED", "FAILED", "CANCELLED"]
    error_type: str | None = None
    error_message: str | None = None
    reliability_score: float | None = None
    reliability_vector: dict[str, float] = Field(default_factory=dict)
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    total_latency_ms: float | None = None
    
    model_config = ConfigDict(extra="ignore")

class SpanIngestItem(BaseModel):
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    name: str
    kind: str = "INTERNAL"
    start_time: str # ISO format string
    end_time: str | None = None
    status_code: Literal["UNSET", "OK", "ERROR"] = "UNSET"
    attributes: dict[str, Any] = Field(default_factory=dict)
    run_id: str
    tenant_id: str
    pipeline_id: str
    
    model_config = ConfigDict(extra="ignore")

class SpanIngestRequest(BaseModel):
    spans: list[SpanIngestItem]
