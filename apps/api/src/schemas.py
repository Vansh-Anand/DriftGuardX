"""
DriftGuard-X v2 — API Schemas (request/response Pydantic models)

Uses str for IDs (UUID-shaped strings stored as String(36) in SQLite/Postgres).
PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─── Run Schemas ───────────────────────────────────────────────────────────────


class RunCreateRequest(APIBase):
    query: str = Field(min_length=1, max_length=4096, description="The RAG query to run")
    pipeline_id: uuid.UUID | None = None  # if None, uses experimental pipeline (golden demo)
    use_experimental_retriever: bool = False  # True = use v2-exp retriever (triggers failure)
    seed: int = Field(default=42, ge=0, description="Random seed for determinism")
    is_synthetic: bool = Field(default=True, description="Mark as synthetic/demo run")
    request_id: str | None = Field(default=None, max_length=255, description="Idempotency key")


class RunResponse(APIBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    pipeline_id: uuid.UUID
    status: str
    request_hash: str | None
    reliability_score: float | None
    reliability_vector: dict[str, float]
    total_latency_ms: float | None
    total_tokens: int | None
    total_cost_usd: float | None
    error_type: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    is_synthetic: bool

    model_config = ConfigDict(from_attributes=True)


class RunListResponse(APIBase):
    runs: list[RunResponse]
    total: int
    page: int
    page_size: int


# ─── Span Schemas ─────────────────────────────────────────────────────────────


class SpanResponse(APIBase):
    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    start_time: datetime
    end_time: datetime | None
    status_code: str
    component_type: str | None
    component_version_tag: str | None
    input_hash: str | None
    output_hash: str | None
    latency_ms: float | None
    token_count_input: int | None
    token_count_output: int | None
    policy_result: str | None
    error_type: str | None
    error_message: str | None


class TraceResponse(APIBase):
    run_id: uuid.UUID
    trace_id: str
    total_span_count: int
    root_span_id: str | None
    spans: list[SpanResponse]


# ─── Replay Schemas ───────────────────────────────────────────────────────────


class ReplayCreateRequest(APIBase):
    swap_retriever_to_stable: bool = Field(
        default=True,
        description="If True, swaps retriever to v1 (stable). Only supported intervention in Prompt 01.",
    )
    seed: int = Field(default=42, ge=0, description="Must match original run seed for determinism")


class ReplayResponse(APIBase):
    id: uuid.UUID
    original_run_id: uuid.UUID
    status: str
    swapped_component_type: str
    original_version_tag: str
    replay_version_tag: str
    original_reliability_score: float | None
    replay_reliability_score: float | None
    reliability_improvement: float | None
    original_reliability_vector: dict[str, float]
    replay_reliability_vector: dict[str, float]
    reliability_delta: dict[str, float]
    created_at: datetime
    completed_at: datetime | None
    is_synthetic: bool
    evidence_kind: str
    manifest_id: uuid.UUID | None = None
    manifest_hash: str | None = None
    is_pinned: bool = False


# ─── Span Ingestion ───────────────────────────────────────────────────────────


class SpanIngestItem(APIBase):
    trace_id: str = Field(pattern=r"^[0-9a-fA-F]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-fA-F]{16}$")
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{16}$")
    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="INTERNAL", min_length=1, max_length=32)
    start_time: datetime
    end_time: datetime | None = None
    status_code: Literal["UNSET", "OK", "ERROR"] = "UNSET"
    attributes: dict[str, Any] = Field(default_factory=dict)
    run_id: uuid.UUID
    tenant_id: uuid.UUID
    pipeline_id: uuid.UUID


class SpanIngestRequest(APIBase):
    spans: list[SpanIngestItem] = Field(min_length=1, max_length=1000)


class SpanIngestResponse(APIBase):
    ingested: int
    skipped: int
    errors: list[str] = Field(default_factory=list)


# ─── Health ───────────────────────────────────────────────────────────────────


class HealthResponse(APIBase):
    status: str
    version: str
    timestamp: datetime


class ReadinessResponse(APIBase):
    status: str
    checks: dict[str, str]
