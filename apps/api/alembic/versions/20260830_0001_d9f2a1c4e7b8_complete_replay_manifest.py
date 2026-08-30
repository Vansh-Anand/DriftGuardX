"""Complete immutable replay-state manifest fields.

Revision ID: d9f2a1c4e7b8
Revises: c9562519a269
Create Date: 2026-08-30 00:01:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "d9f2a1c4e7b8"
down_revision: str | None = "c9562519a269"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("replay_state_manifests") as batch:
        batch.add_column(sa.Column("original_query_hash", sa.String(length=64), nullable=True))
        batch.add_column(sa.Column("corpus_version_id", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("retriever_settings", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=True))

    op.execute(
        sa.text(
            "UPDATE replay_state_manifests "
            "SET retriever_settings = :settings, retrieved_chunk_ids = :chunks "
            "WHERE retriever_settings IS NULL OR retrieved_chunk_ids IS NULL"
        ).bindparams(
            sa.bindparam("settings", value={}, type_=sa.JSON()),
            sa.bindparam("chunks", value=[], type_=sa.JSON()),
        )
    )

    with op.batch_alter_table("replay_state_manifests") as batch:
        batch.alter_column("retriever_settings", existing_type=sa.JSON(), nullable=False)
        batch.alter_column("retrieved_chunk_ids", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("replay_state_manifests") as batch:
        batch.drop_column("retrieved_chunk_ids")
        batch.drop_column("retriever_settings")
        batch.drop_column("corpus_version_id")
        batch.drop_column("original_query_hash")
