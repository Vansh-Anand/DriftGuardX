"""Add distributed admission receipts, audit events, and resource pools.

Revision ID: 4a7c2f9d1e30
Revises: 8e7a2d4c6f90
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "4a7c2f9d1e30"
down_revision = "8e7a2d4c6f90"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "admission_resource_pools",
        sa.Column("pool_id", sa.String(length=255), primary_key=True),
        sa.Column("budget_usd", sa.Numeric(18, 6), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(18, 6), nullable=False),
        sa.Column("spent_usd", sa.Numeric(18, 6), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "admission_receipts",
        sa.Column("receipt_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("binding_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", _json(), nullable=False),
        sa.Column("reserved_cost_usd", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "resource_pool_id",
            sa.String(length=255),
            sa.ForeignKey("admission_resource_pools.pool_id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("binding_hash", name="uq_admission_receipts_binding_hash"),
    )
    op.create_index(
        "ix_admission_receipts_tenant_status",
        "admission_receipts",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_admission_receipts_pool_status",
        "admission_receipts",
        ["resource_pool_id", "status"],
    )
    op.create_table(
        "admission_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "receipt_id",
            sa.Uuid(),
            sa.ForeignKey("admission_receipts.receipt_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_event_hash", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details_json", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("receipt_id", "sequence", name="uq_admission_event_sequence"),
        sa.UniqueConstraint("event_hash", name="uq_admission_event_hash"),
    )
    op.create_index(
        "ix_admission_events_receipt_sequence",
        "admission_audit_events",
        ["receipt_id", "sequence"],
    )
    op.create_table(
        "admission_execution_attestations",
        sa.Column(
            "receipt_id",
            sa.Uuid(),
            sa.ForeignKey("admission_receipts.receipt_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("attestation_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("payload_json", _json(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("admission_execution_attestations")
    op.drop_index("ix_admission_events_receipt_sequence", table_name="admission_audit_events")
    op.drop_table("admission_audit_events")
    op.drop_index("ix_admission_receipts_pool_status", table_name="admission_receipts")
    op.drop_index("ix_admission_receipts_tenant_status", table_name="admission_receipts")
    op.drop_table("admission_receipts")
    op.drop_table("admission_resource_pools")
