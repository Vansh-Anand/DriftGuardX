"""Add worker persistence and preserve legacy certificate evidence.

Revision ID: 8e7a2d4c6f90
Revises: 6d3f1a8c2b7e
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "8e7a2d4c6f90"
down_revision = "6d3f1a8c2b7e"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("payload_json", _json(), nullable=False),
        sa.Column("result_json", _json(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    for suffix, columns in (
        ("tenant_id", ["tenant_id"]),
        ("status", ["status"]),
        ("idempotency", ["tenant_id", "idempotency_key"]),
        ("created_at", ["created_at"]),
    ):
        op.create_index(f"ix_background_jobs_{suffix}", "background_jobs", columns)
    op.create_table(
        "quarantine_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("target_component", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("enforce_network_isolation", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in ("tenant_id", "active"):
        op.create_index(f"ix_quarantine_rules_{column}", "quarantine_rules", [column])

    # Signed legacy records remain byte-for-byte in recovery_certificates.
    # The newer API summary format has different identities and cannot be inferred.
    op.create_table(
        "recovery_certificate_summaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("replay_episode_id", sa.Uuid(), nullable=False),
        sa.Column("intervention_id", sa.Uuid(), nullable=False),
        sa.Column("repair_decision_id", sa.Uuid(), nullable=False),
        sa.Column("certificate_hash", sa.String(64), nullable=False),
        sa.Column("issued_by", sa.String(128), nullable=False),
        sa.Column("payload_summary", sa.Text(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("evidence_class", sa.String(64), nullable=False),
        sa.Column("approval_state", sa.String(32), nullable=False),
        sa.Column("cryptographic_signature", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recovery_certificate_summaries_tenant_id",
        "recovery_certificate_summaries",
        ["tenant_id"],
    )
    op.create_index(
        "ix_recovery_certificate_summaries_run", "recovery_certificate_summaries", ["run_id"]
    )

    for table in ("request_runs", "replay_episodes"):
        op.add_column(
            table,
            sa.Column("evidence_class", sa.String(32), nullable=False, server_default="UNVERIFIED"),
        )
        op.execute(
            sa.text(
                f"UPDATE {table} SET evidence_class = 'SYNTHETIC_SIMULATION' WHERE is_synthetic = true"
            )
        )
    op.add_column(
        "replay_episodes",
        sa.Column("replay_mode", sa.String(32), nullable=False, server_default="exact"),
    )
    with op.batch_alter_table("replay_episodes") as batch:
        batch.alter_column("original_version_id", existing_type=sa.Uuid(), nullable=True)
    for name, column_type in (
        ("original_query", sa.Text()),
        ("embedding_provider", sa.String(64)),
        ("embedding_model_id", sa.String(128)),
        ("embedding_vector_dimension", sa.Integer()),
        ("embedding_config_hash", sa.String(64)),
    ):
        op.add_column("replay_state_manifests", sa.Column(name, column_type, nullable=True))
    op.add_column("span_records", sa.Column("provenance_json", _json(), nullable=True))


def downgrade() -> None:
    # The old schema cannot represent these records; require an explicit export first.
    connection = op.get_bind()
    for table in ("background_jobs", "quarantine_rules", "recovery_certificate_summaries"):
        if connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar():
            raise RuntimeError(f"Export and remove {table} records before downgrade")
    if connection.execute(
        sa.text("SELECT COUNT(*) FROM replay_episodes WHERE original_version_id IS NULL")
    ).scalar():
        raise RuntimeError("Replay episodes without original versions cannot be downgraded")
    op.drop_column("span_records", "provenance_json")
    for name in (
        "original_query",
        "embedding_provider",
        "embedding_model_id",
        "embedding_vector_dimension",
        "embedding_config_hash",
    ):
        op.drop_column("replay_state_manifests", name)
    with op.batch_alter_table("replay_episodes") as batch:
        batch.alter_column("original_version_id", existing_type=sa.Uuid(), nullable=False)
        batch.drop_column("replay_mode")
        batch.drop_column("evidence_class")
    op.drop_column("request_runs", "evidence_class")
    op.drop_table("recovery_certificate_summaries")
    op.drop_table("quarantine_rules")
    op.drop_table("background_jobs")
