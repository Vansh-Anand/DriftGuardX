"""
DriftGuard-X v2 — SQLAlchemy ORM Models

Compatibility layer for both PostgreSQL (JSONB) and SQLite (JSON) backends.
PRIVATE — All Rights Reserved.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

# Resolve the storage type at SQL compilation time, not from import-time
# environment state.  This keeps Alembic, tests, and runtime metadata identical.
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    pipelines: Mapped[list[AgentPipelineORM]] = relationship(
        "AgentPipelineORM", back_populates="tenant"
    )

    __table_args__ = (Index("ix_tenants_slug", "slug"),)


# ─── Auth Models ──────────────────────────────────────────────────────────────


class UserORM(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    memberships: Mapped[list[TenantMembershipORM]] = relationship(
        "TenantMembershipORM", back_populates="user"
    )


class TenantMembershipORM(Base):
    __tablename__ = "tenant_memberships"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    roles_json: Mapped[list] = mapped_column(_JSON_TYPE, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    user: Mapped[UserORM] = relationship("UserORM", back_populates="memberships")
    tenant: Mapped[TenantORM] = relationship("TenantORM")

    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_tenant_membership"),
        Index("ix_tenant_memberships_user_id", "user_id"),
        Index("ix_tenant_memberships_tenant_id", "tenant_id"),
    )


# ─── Idempotency ──────────────────────────────────────────────────────────────


class IdempotencyKeyORM(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_path: Mapped[str] = mapped_column(String(255), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),)


# ─── Audit Event ──────────────────────────────────────────────────────────────


class AuditEventORM(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
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
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    component_version_ids: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped[TenantORM] = relationship("TenantORM", back_populates="pipelines")
    runs: Mapped[list[RequestRunORM]] = relationship("RequestRunORM", back_populates="pipeline")

    __table_args__ = (Index("ix_agent_pipelines_tenant_id", "tenant_id"),)


# ─── RequestRun ───────────────────────────────────────────────────────────────


class RequestRunORM(Base):
    __tablename__ = "request_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    pipeline_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agent_pipelines.id"), nullable=False
    )
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

    pipeline: Mapped[AgentPipelineORM] = relationship("AgentPipelineORM", back_populates="runs")
    trace: Mapped[TraceArtifactORM | None] = relationship(
        "TraceArtifactORM",
        back_populates="run",
        uselist=False,
        foreign_keys="TraceArtifactORM.run_id",
    )
    replay_episodes: Mapped[list[ReplayEpisodeORM]] = relationship(
        "ReplayEpisodeORM",
        back_populates="original_run",
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
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False, unique=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    spans_json: Mapped[list] = mapped_column(_JSON_TYPE, nullable=False, default=list)
    root_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    total_span_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    run: Mapped[RequestRunORM] = relationship(
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
    span_id: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False
    )
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
    component_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
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
    provenance_json: Mapped[dict | None] = mapped_column(_JSON_TYPE, nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "span_id", name="uq_span_records_tenant_span"),
        Index("ix_span_records_run_id", "run_id"),
        Index("ix_span_records_trace_id", "trace_id"),
        Index("ix_span_records_tenant_id", "tenant_id"),
        Index("ix_span_records_component_type", "component_type"),
    )


# ─── Intervention ─────────────────────────────────────────────────────────────


class InterventionORM(Base):
    __tablename__ = "interventions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False
    )
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

    __table_args__ = (Index("ix_interventions_run_id", "run_id"),)


# ─── ReplayEpisode ────────────────────────────────────────────────────────────


class ReplayEpisodeORM(Base):
    __tablename__ = "replay_episodes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    original_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("interventions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    manifest_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("replay_state_manifests.id"), nullable=True
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)

    swapped_component_type: Mapped[str] = mapped_column(String(64), nullable=False)
    original_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
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
    replay_mode: Mapped[str] = mapped_column(String(32), default="exact")

    original_run: Mapped[RequestRunORM] = relationship(
        "RequestRunORM",
        back_populates="replay_episodes",
        foreign_keys=[original_run_id],
    )
    manifest: Mapped[ReplayStateManifestORM | None] = relationship(
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
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    original_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_query_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    corpus_version_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_identifier: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_config_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_template_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retriever_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retriever_settings: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    retrieved_chunk_ids: Mapped[list] = mapped_column(_JSON_TYPE, default=list)
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

    __table_args__ = (Index("ix_detector_thresholds_tenant_id", "tenant_id"),)


class SymptomRegistryEntryORM(Base):
    __tablename__ = "symptom_registry"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("request_runs.id"), nullable=False
    )
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


# ─── Durable Workflow & Approvals (Prompt 5) ──────────────────────────────────


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    task_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    result: Mapped[dict | None] = mapped_column(_JSON_TYPE, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_jobs_tenant_id", "tenant_id"),
        Index("ix_jobs_status", "status"),
    )


class ApprovalRequestORM(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(255), nullable=False)
    node_id: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_tier: Mapped[str] = mapped_column(String(32), nullable=False)
    required_approvers: Mapped[int] = mapped_column(Integer, default=1)
    two_person_control: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delegated_approvers: Mapped[list] = mapped_column(_JSON_TYPE, default=list)
    context_json: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)

    decisions: Mapped[list[ApprovalDecisionORM]] = relationship(
        "ApprovalDecisionORM", back_populates="request"
    )

    __table_args__ = (
        Index("ix_approval_requests_tenant_id", "tenant_id"),
        Index("ix_approval_requests_status", "status"),
    )


class ApprovalDecisionORM(Base):
    __tablename__ = "approval_decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("approval_requests.id"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str] = mapped_column(Text, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_break_glass: Mapped[bool] = mapped_column(Boolean, default=False)
    break_glass_justification: Mapped[str | None] = mapped_column(Text, nullable=True)

    request: Mapped[ApprovalRequestORM] = relationship(
        "ApprovalRequestORM", back_populates="decisions"
    )


class RecoveryStateORM(Base):
    __tablename__ = "recovery_states"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    proposal_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    current_status: Mapped[str] = mapped_column(String(32), nullable=False)
    capsule_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timeout_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    event_log_json: Mapped[list] = mapped_column(_JSON_TYPE, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_recovery_states_tenant_id", "tenant_id"),
        Index("ix_recovery_states_status", "current_status"),
    )


class LedgerEntryORM(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    commit_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    timestamp: Mapped[str] = mapped_column(String(64), nullable=False)
    merkle_root: Mapped[str] = mapped_column(String(64), nullable=False)
    certificate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    canary_passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload_json: Mapped[dict] = mapped_column(_JSON_TYPE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_ledger_entries_tenant_id", "tenant_id"),
        Index("ix_ledger_entries_commit_hash", "commit_hash"),
    )


# ─── Recovery Eligibility Certificate (Prompt 7) ──────────────────────────────


class RecoveryCertificateORM(Base):
    __tablename__ = "recovery_certificates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    replay_episode_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    intervention_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    repair_decision_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    
    certificate_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_by: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_summary: Mapped[str] = mapped_column(Text, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_state: Mapped[str] = mapped_column(String(32), nullable=False)
    cryptographic_signature: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_recovery_certificates_tenant_id", "tenant_id"),
        Index("ix_recovery_certificates_run", "run_id"),
    )


# ─── Background Job ORM (Roadmap Item #4) ────────────────────────────────────


class BackgroundJobORM(Base):
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    payload_json: Mapped[dict] = mapped_column(_JSON_TYPE, default=dict)
    result_json: Mapped[dict | None] = mapped_column(_JSON_TYPE, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_background_jobs_tenant_id", "tenant_id"),
        Index("ix_background_jobs_status", "status"),
        Index("ix_background_jobs_idempotency", "tenant_id", "idempotency_key", unique=False),
        Index("ix_background_jobs_created_at", "created_at"),
    )


from sqlalchemy import event
@event.listens_for(ReplayStateManifestORM, 'before_update')
def receive_before_update(mapper, connection, target):
    raise RuntimeError('ReplayStateManifest is immutable and cannot be updated.')
