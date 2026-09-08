"""Link persisted replay episodes to their durable admission receipt."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "6d3f1a8c2b7e"
down_revision: str | None = "f3a9d8c2e6b1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "replay_episodes",
        sa.Column("admission_receipt_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_replay_episodes_admission_receipt_id",
        "replay_episodes",
        ["admission_receipt_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_replay_episodes_admission_receipt_id",
        table_name="replay_episodes",
    )
    op.drop_column("replay_episodes", "admission_receipt_id")
