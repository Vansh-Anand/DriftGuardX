import os

import pytest
from alembic import command
from alembic.config import Config


def test_alembic_migrations():
    """
    Test that Alembic can upgrade to head and downgrade to base without crashing.
    This guarantees that our migration scripts are bi-directional and valid.
    """
    # Create an in-memory or temp sqlite DB for the test
    db_path = "sqlite:///./test_migrations.db"

    alembic_cfg = Config("apps/api/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_path)

    # Clean up old db if it exists
    if os.path.exists("./test_migrations.db"):
        os.remove("./test_migrations.db")

    try:
        # Upgrade to head
        command.upgrade(alembic_cfg, "head")

        # Downgrade to base
        command.downgrade(alembic_cfg, "base")
    finally:
        if os.path.exists("./test_migrations.db"):
            os.remove("./test_migrations.db")
