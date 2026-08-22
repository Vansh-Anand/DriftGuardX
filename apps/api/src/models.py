"""
DriftGuard-X v2 — SQLAlchemy ORM Models

Compatibility layer for both PostgreSQL (JSONB) and SQLite (JSON) backends.
PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from sqlalchemy.types import Uuid

# Use JSONB on Postgres, JSON on SQLite
_DB_URL = os.environ.get("DATABASE_URL", "sqlite")
if "postgresql" in _DB_URL or "postgres" in _DB_URL:
    from sqlalchemy.dialects.postgresql import JSONB as _JSON_TYPE
    _USE_POSTGRES = True
else:
    from sqlalchemy import JSON as _JSON_TYPE
    _USE_POSTGRES = False


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ─── Tenant ───────────────────────────────────────────────────────────────────

class TenantORM(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    pipelines: Mapped[list["AgentPipelineORM"]] = relationship("AgentPipelineORM", back_populates="tenant")

    __table_args__ = (
        Index("ix_tenants_slug", "slug"),
    )


# ─── Audit Event ──────────────────────────────────────────────────────────────

class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_audit_events_tenant_id", "tenant_id"),
        Index("ix_audit_events_action", "action"),
    )


# ─── ComponentVersion ─────────────────────────────────────────────────────────

class ComponentVersionORM(Base):
    __tablename__ = "component_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="stable")
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        UniqueConstraint("component_type", "version_tag", name="uq_component_versions_type_tag"),
        Index("ix_component_versions_type", "component_type"),
    )


# ─── AgentPipeline ────────────────────────────────────────────────────────────

class AgentPipelineORM(Base):
    __tablename__ = "agent_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    component_version_ids: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped["TenantORM"] = relationship("TenantORM", back_populates="pipelines")
    runs: Mapped[list["RequestRunORM"]] = relationship("RequestRunORM", back_populates="pipeline")

    __table_args__ = (
        Index("ix_agent_pipelines_tenant_id", "tenant_id"),
    )


# ─── RequestRun ───────────────────────────────────────────────────────────────

class RequestRunORM(Base):
    __tablename__ = "request_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agent_pipelines.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")

    request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hardware_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reliability_vector: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)

    total_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

    pipeline: Mapped["AgentPipelineORM"] = relationship("AgentPipelineORM", back_populates="runs")
    trace: Mapped["TraceArtifactORM | None"] = relationship(
        "TraceArtifactORM", back_populates="run", uselist=False,
        foreign_keys="TraceArtifactORM.run_id",
    )
    replay_episodes: Mapped[list["ReplayEpisodeORM"]] = relationship(
        "ReplayEpisodeORM", back_populates="original_run",
        foreign_keys="ReplayEpisodeORM.original_run_id",
    )

    __table_args__ = (
        Index("ix_request_runs_tenant_id", "tenant_id"),
        Index("ix_request_runs_pipeline_id", "pipeline_id"),
        Index("ix_request_runs_status", "status"),
        Index("ix_request_runs_created_at", "created_at"),
    )


# ─── TraceArtifact ────────────────────────────────────────────────────────────

class TraceArtifactORM(Base):
    __tablename__ = "trace_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False, unique=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    spans_json: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False, default=list)
    root_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    total_span_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped["RequestRunORM"] = relationship(
        "RequestRunORM", back_populates="trace", foreign_keys=[run_id]
    )

    __table_args__ = (
        Index("ix_trace_artifacts_run_id", "run_id"),
        Index("ix_trace_artifacts_tenant_id", "tenant_id"),
    )


# ─── SpanRecord (denormalized) ────────────────────────────────────────────────

class SpanRecordORM(Base):
    __tablename__ = "span_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    span_id: Mapped[str] = mapped_column(String(16), nullable=False, unique=True)
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="INTERNAL")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_code: Mapped[str] = mapped_column(String(16), default="UNSET")
    status_message: Mapped[str] = mapped_column(Text, default="")
    attributes_json: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)

    component_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    component_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    component_version_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)

    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    token_count_input: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_count_output: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    policy_result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    policy_rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    redaction_json: Mapped[dict | None] = mapped_column(_JSON_TYPE, nullable=True)

    __table_args__ = (
        Index("ix_span_records_run_id", "run_id"),
        Index("ix_span_records_trace_id", "trace_id"),
        Index("ix_span_records_tenant_id", "tenant_id"),
        Index("ix_span_records_component_type", "component_type"),
    )


# ─── Intervention ─────────────────────────────────────────────────────────────

class InterventionORM(Base):
    __tablename__ = "interventions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    intervention_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    to_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    from_version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    to_version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requires_human_approval: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_interventions_run_id", "run_id"),
    )


# ─── ReplayEpisode ────────────────────────────────────────────────────────────

class ReplayEpisodeORM(Base):
    __tablename__ = "replay_episodes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    intervention_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("interventions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    manifest_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("replay_state_manifests.id"), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    swapped_component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    original_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    replay_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    original_version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    replay_version_tag: Mapped[str] = mapped_column(String(64), nullable=False)
    pinned_version_ids: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)

    original_reliability_vector: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    replay_reliability_vector: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    reliability_delta: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    original_reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    replay_reliability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reliability_improvement: Mapped[float | None] = mapped_column(Float, nullable=True)

    original_request_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    replay_response_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)

    original_run: Mapped["RequestRunORM"] = relationship(
        "RequestRunORM", back_populates="replay_episodes",
        foreign_keys=[original_run_id],
    )
    manifest: Mapped["ReplayStateManifestORM | None"] = relationship(
        "ReplayStateManifestORM",
        foreign_keys=[manifest_id],
    )

    __table_args__ = (
        Index("ix_replay_episodes_original_run_id", "original_run_id"),
        Index("ix_replay_episodes_status", "status"),
    )


# ─── ReplayStateManifest ──────────────────────────────────────────────────────

class ReplayStateManifestORM(Base):
    __tablename__ = "replay_state_manifests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_template_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retriever_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vector_index_snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_schemas_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    memory_snapshot_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generation_parameters: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    container_image_digest: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dependency_lockfile_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trace_root_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_replay_state_manifests_run_id", "run_id"),
        Index("ix_replay_state_manifests_hash", "manifest_hash"),
    )


# ─── Drift Detectors & Symptoms ───────────────────────────────────────────────

class DetectorThresholdORM(Base):
    __tablename__ = "detector_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    detector_name: Mapped[str] = mapped_column(String(128), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(128), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    operator: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_detector_thresholds_tenant_id", "tenant_id"),
    )


class SymptomRegistryEntryORM(Base):
    __tablename__ = "symptom_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False)
    graph_node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    symptom_name: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    detector_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    uncertainty: Mapped[float | None] = mapped_column(Float, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_symptom_registry_run_id", "run_id"),
        Index("ix_symptom_registry_tenant_id", "tenant_id"),
    )
