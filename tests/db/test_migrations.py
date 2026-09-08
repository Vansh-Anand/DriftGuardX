from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
import pytest
from alembic import command
from alembic.config import Config


from apps.api.src.models import LegacyRecoveryCertificateORM, QuarantineRuleORM, TenantORM


def test_alembic_migrations(tmp_path, monkeypatch):
    """Exercise real file-backed migrations, parity and legacy evidence retention."""
    path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{path.as_posix()}")
    cfg = Config("apps/api/alembic.ini")
    command.upgrade(cfg, "6d3f1a8c2b7e")
    engine = sa.create_engine(f"sqlite:///{path.as_posix()}")
    tenant_id, certificate_id = uuid4(), uuid4()
    evidence = dict(
        id=certificate_id,
        tenant_id=tenant_id,
        original_trace_root_hash="trace",
        manifest_hash="manifest",
        intervention_hash="intervention",
        measured_resource_budget_and_usage={"cost": 1.5},
        replay_outcome="passed",
        reliability_delta=0.1,
        policy_version="v1",
        policy_decision="approved",
        approval_decision_set={"approvers": ["reviewer"]},
        canary_result_hash="canary",
        recovery_capsule_hash="capsule",
        executor_image_digest="image",
        signer_identity="signer",
        signature_b64="original-signed-evidence",
        timestamp=datetime.now(UTC),
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                TenantORM.__table__.insert().values(id=tenant_id, name="Test", slug="test")
            )
            connection.execute(LegacyRecoveryCertificateORM.__table__.insert().values(**evidence))
            before = (
                connection.execute(sa.text("SELECT * FROM recovery_certificates")).mappings().one()
            )
        command.upgrade(cfg, "head")
        command.check(cfg)
        with engine.connect() as connection:
            after = (
                connection.execute(sa.text("SELECT * FROM recovery_certificates")).mappings().one()
            )
            assert dict(after) == dict(before)
            assert (
                connection.scalar(sa.text("SELECT COUNT(*) FROM recovery_certificate_summaries"))
                == 0
            )
            assert {"background_jobs", "quarantine_rules"} <= set(
                sa.inspect(connection).get_table_names()
            )
        with engine.begin() as connection:
            connection.execute(
                QuarantineRuleORM.__table__.insert().values(
                    tenant_id=tenant_id, target_component="retriever", description="protected rule"
                )
            )
        with pytest.raises(RuntimeError, match="quarantine_rules records before downgrade"):
            command.downgrade(cfg, "6d3f1a8c2b7e")
        with engine.begin() as connection:
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM quarantine_rules")) == 1
            connection.execute(QuarantineRuleORM.__table__.delete())
        command.downgrade(cfg, "6d3f1a8c2b7e")
        with engine.connect() as connection:
            restored = (
                connection.execute(sa.text("SELECT * FROM recovery_certificates")).mappings().one()
            )
            assert dict(restored) == dict(before)
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        command.check(cfg)
    finally:
        engine.dispose()
