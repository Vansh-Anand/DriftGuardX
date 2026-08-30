"""Scope span identity to a tenant.

Revision ID: a4c8e2f19b73
Revises: d9f2a1c4e7b8
"""

from alembic import op

revision: str = "a4c8e2f19b73"
down_revision: str | None = "d9f2a1c4e7b8"
branch_labels: str | None = None
depends_on: str | None = None

_NAMING = {"uq": "uq_%(table_name)s_%(column_0_name)s"}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "span_records", recreate="always", naming_convention=_NAMING
        ) as batch_op:
            batch_op.drop_constraint("uq_span_records_span_id", type_="unique")
            batch_op.create_unique_constraint(
                "uq_span_records_tenant_span", ["tenant_id", "span_id"]
            )
    else:
        op.drop_constraint("span_records_span_id_key", "span_records", type_="unique")
        op.create_unique_constraint(
            "uq_span_records_tenant_span", "span_records", ["tenant_id", "span_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "span_records", recreate="always", naming_convention=_NAMING
        ) as batch_op:
            batch_op.drop_constraint("uq_span_records_tenant_span", type_="unique")
            batch_op.create_unique_constraint("uq_span_records_span_id", ["span_id"])
    else:
        op.drop_constraint("uq_span_records_tenant_span", "span_records", type_="unique")
        op.create_unique_constraint("span_records_span_id_key", "span_records", ["span_id"])
