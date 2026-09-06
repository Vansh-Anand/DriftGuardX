import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from apps.api.src.models import Base, ReplayStateManifestORM
from packages.contracts.src.models import ReplayStateManifest


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_manifest_canonical_hash_ignores_ordering():
    # Dictionary ordering shouldn't matter
    m1 = ReplayStateManifest(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        generation_parameters={"temperature": 0.5, "max_tokens": 100},
    )

    m2 = ReplayStateManifest(
        run_id=m1.run_id,
        tenant_id=m1.tenant_id,
        generation_parameters={"max_tokens": 100, "temperature": 0.5},
    )

    # id and created_at are generated, they shouldn't affect hash
    assert m1.manifest_hash == m2.manifest_hash


def test_manifest_hash_changes_on_material_mutation():
    m1 = ReplayStateManifest(run_id=uuid.uuid4(), tenant_id=uuid.uuid4(), model_identifier="gpt-4")

    m2 = ReplayStateManifest(run_id=m1.run_id, tenant_id=m1.tenant_id, model_identifier="gpt-3.5")

    assert m1.manifest_hash != m2.manifest_hash


def test_manifest_immutability_enforced_by_db(db_session):
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    orm = ReplayStateManifestORM(
        id=uuid.uuid4(),
        run_id=run_id,
        tenant_id=tenant_id,
        original_query="test",
        manifest_hash="testhash",
    )

    db_session.add(orm)
    db_session.commit()

    # Attempt to update it
    orm_fetched = db_session.execute(
        select(ReplayStateManifestORM).where(ReplayStateManifestORM.id == orm.id)
    ).scalar_one()
    orm_fetched.original_query = "mutated"

    with pytest.raises(RuntimeError, match="ReplayStateManifest is immutable"):
        db_session.commit()
