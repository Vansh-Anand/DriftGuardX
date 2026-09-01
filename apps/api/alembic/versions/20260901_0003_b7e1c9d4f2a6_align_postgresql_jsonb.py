"""Align PostgreSQL JSON storage with the runtime JSONB model.

Revision ID: b7e1c9d4f2a6
Revises: a4c8e2f19b73
Create Date: 2026-09-01 19:00:00

The original portable migrations intentionally used ``sa.JSON`` so they could
also run in SQLite.  PostgreSQL deployments use ``JSONB`` in the ORM, however,
which left the migrated schema and model metadata out of parity.  This
revision performs the PostgreSQL-only, lossless type conversion while keeping
the SQLite migration path portable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e1c9d4f2a6"
down_revision: str | None = "a4c8e2f19b73"
branch_labels: str | None = None
depends_on: str | None = None


_JSON_COLUMNS: tuple[tuple[str, str], ...] = (
    ("tenant_memberships", "roles_json"),
    ("idempotency_keys", "response_body"),
    ("audit_events", "metadata_json"),
    ("agent_pipelines", "component_version_ids"),
    ("request_runs", "reliability_vector"),
    ("trace_artifacts", "spans_json"),
    ("span_records", "attributes_json"),
    ("span_records", "redaction_json"),
    ("replay_episodes", "pinned_version_ids"),
    ("replay_episodes", "original_reliability_vector"),
    ("replay_episodes", "replay_reliability_vector"),
    ("replay_episodes", "reliability_delta"),
    ("replay_state_manifests", "retriever_settings"),
    ("replay_state_manifests", "retrieved_chunk_ids"),
    ("replay_state_manifests", "generation_parameters"),
    ("jobs", "result"),
    ("approval_requests", "delegated_approvers"),
    ("approval_requests", "context_json"),
    ("recovery_states", "event_log_json"),
    ("ledger_entries", "payload_json"),
    ("recovery_certificates", "measured_resource_budget_and_usage"),
    ("recovery_certificates", "approval_decision_set"),
    ("index_versions", "chunking_config_json"),
    ("documents", "source_metadata_json"),
)


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _available_columns() -> dict[str, set[str]]:
    inspector = sa.inspect(op.get_bind())
    return {
        table_name: {str(column["name"]) for column in inspector.get_columns(table_name)}
        for table_name in inspector.get_table_names()
    }


def upgrade() -> None:
    if not _is_postgresql():
        return

    jsonb = postgresql.JSONB(astext_type=sa.Text())
    available = _available_columns()
    for table_name, column_name in _JSON_COLUMNS:
        # Two legacy no-op revisions left ingestion tables absent in databases
        # that had already advanced past them.  The following revision repairs
        # those tables; this conversion remains safe for both old and fresh DBs.
        if column_name not in available.get(table_name, set()):
            continue
        op.alter_column(
            table_name,
            column_name,
            existing_type=sa.JSON(),
            type_=jsonb,
            postgresql_using=f'"{column_name}"::jsonb',
        )


def downgrade() -> None:
    if not _is_postgresql():
        return

    jsonb = postgresql.JSONB(astext_type=sa.Text())
    available = _available_columns()
    for table_name, column_name in reversed(_JSON_COLUMNS):
        if column_name not in available.get(table_name, set()):
            continue
        op.alter_column(
            table_name,
            column_name,
            existing_type=jsonb,
            type_=sa.JSON(),
            postgresql_using=f'"{column_name}"::json',
        )
