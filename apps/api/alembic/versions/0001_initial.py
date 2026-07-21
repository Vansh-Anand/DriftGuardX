"""
Initial schema — DriftGuard-X v2 Prompt 01

Creates all core tables:
- tenants
- component_versions
- agent_pipelines
- request_runs
- trace_artifacts
- span_records
- interventions
- replay_episodes

Revision ID: 0001_initial
Revises: (none)
Create Date: 2024-01-01 00:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ─── tenants ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"])
    op.create_index("ix_tenants_is_active", "tenants", ["is_active"])

    # ─── component_versions ───────────────────────────────────────────────────
    op.create_table(
        "component_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("component_type", sa.String(64), nullable=False),
        sa.Column("version_tag", sa.String(64), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="stable"),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("component_type", "version_tag", name="uq_component_versions_type_tag"),
    )
    op.create_index("ix_component_versions_type", "component_versions", ["component_type"])
    op.create_index("ix_component_versions_state", "component_versions", ["state"])

    # ─── agent_pipelines ──────────────────────────────────────────────────────
    op.create_table(
        "agent_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("component_version_ids", postgresql.JSONB(), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_pipelines_tenant_id", "agent_pipelines", ["tenant_id"])

    # ─── request_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "request_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_pipelines.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("request_id", sa.String(255), nullable=True),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("config_hash", sa.String(64), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("hardware_id", sa.String(128), nullable=True),
        sa.Column("response_hash", sa.String(64), nullable=True),
        sa.Column("reliability_score", sa.Float(), nullable=True),
        sa.Column("reliability_vector", postgresql.JSONB(), server_default="{}"),
        sa.Column("total_latency_ms", sa.Float(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("error_type", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default="true"),
    )
    op.create_index("ix_request_runs_tenant_id", "request_runs", ["tenant_id"])
    op.create_index("ix_request_runs_pipeline_id", "request_runs", ["pipeline_id"])
    op.create_index("ix_request_runs_status", "request_runs", ["status"])
    op.create_index("ix_request_runs_created_at", "request_runs", ["created_at"])

    # ─── trace_artifacts ──────────────────────────────────────────────────────
    op.create_table(
        "trace_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("request_runs.id"), nullable=False, unique=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spans_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("root_span_id", sa.String(16), nullable=True),
        sa.Column("total_span_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trace_artifacts_run_id", "trace_artifacts", ["run_id"])
    op.create_index("ix_trace_artifacts_tenant_id", "trace_artifacts", ["tenant_id"])

    # ─── span_records ─────────────────────────────────────────────────────────
    op.create_table(
        "span_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("span_id", sa.String(16), nullable=False, unique=True),
        sa.Column("parent_span_id", sa.String(16), nullable=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("request_runs.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), server_default="INTERNAL"),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_code", sa.String(16), server_default="UNSET"),
        sa.Column("status_message", sa.Text(), server_default=""),
        sa.Column("attributes_json", postgresql.JSONB(), server_default="{}"),
        sa.Column("component_type", sa.String(64), nullable=True),
        sa.Column("component_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("component_version_tag", sa.String(64), nullable=True),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("output_hash", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("token_count_input", sa.Integer(), nullable=True),
        sa.Column("token_count_output", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("policy_result", sa.String(32), nullable=True),
        sa.Column("policy_rule_id", sa.String(128), nullable=True),
        sa.Column("error_type", sa.String(128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("redaction_json", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_span_records_run_id", "span_records", ["run_id"])
    op.create_index("ix_span_records_trace_id", "span_records", ["trace_id"])
    op.create_index("ix_span_records_tenant_id", "span_records", ["tenant_id"])
    op.create_index("ix_span_records_component_type", "span_records", ["component_type"])

    # ─── interventions ────────────────────────────────────────────────────────
    op.create_table(
        "interventions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("request_runs.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intervention_type", sa.String(64), nullable=False),
        sa.Column("target_component_type", sa.String(64), nullable=False),
        sa.Column("from_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_version_tag", sa.String(64), nullable=False),
        sa.Column("to_version_tag", sa.String(64), nullable=False),
        sa.Column("rationale", sa.Text(), server_default=""),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requires_human_approval", sa.Boolean(), server_default="true"),
    )
    op.create_index("ix_interventions_run_id", "interventions", ["run_id"])
    op.create_index("ix_interventions_tenant_id", "interventions", ["tenant_id"])

    # ─── replay_episodes ──────────────────────────────────────────────────────
    op.create_table(
        "replay_episodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("original_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("request_runs.id"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intervention_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("interventions.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("swapped_component_type", sa.String(64), nullable=False),
        sa.Column("original_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("replay_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("original_version_tag", sa.String(64), nullable=False),
        sa.Column("replay_version_tag", sa.String(64), nullable=False),
        sa.Column("pinned_version_ids", postgresql.JSONB(), server_default="{}"),
        sa.Column("original_reliability_vector", postgresql.JSONB(), server_default="{}"),
        sa.Column("replay_reliability_vector", postgresql.JSONB(), server_default="{}"),
        sa.Column("reliability_delta", postgresql.JSONB(), server_default="{}"),
        sa.Column("original_reliability_score", sa.Float(), nullable=True),
        sa.Column("replay_reliability_score", sa.Float(), nullable=True),
        sa.Column("reliability_improvement", sa.Float(), nullable=True),
        sa.Column("original_request_hash", sa.String(64), nullable=True),
        sa.Column("replay_response_hash", sa.String(64), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("commit_sha", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_synthetic", sa.Boolean(), server_default="true"),
    )
    op.create_index("ix_replay_episodes_original_run_id", "replay_episodes", ["original_run_id"])
    op.create_index("ix_replay_episodes_tenant_id", "replay_episodes", ["tenant_id"])
    op.create_index("ix_replay_episodes_status", "replay_episodes", ["status"])


def downgrade() -> None:
    """Rollback: drop all tables in reverse order."""
    op.drop_table("replay_episodes")
    op.drop_table("interventions")
    op.drop_table("span_records")
    op.drop_table("trace_artifacts")
    op.drop_table("request_runs")
    op.drop_table("agent_pipelines")
    op.drop_table("component_versions")
    op.drop_table("tenants")
