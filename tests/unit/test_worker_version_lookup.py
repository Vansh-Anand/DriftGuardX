from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.src.models import ComponentVersionORM
from apps.worker.src.worker import _DatabaseVersionLookup, _graph_edge_pk


@pytest.mark.asyncio
async def test_worker_uses_persisted_version_identity():
    tenant_id, version_id = uuid4(), uuid4()
    record = ComponentVersionORM(
        id=version_id,
        tenant_id=tenant_id,
        component_type="retriever",
        version_tag="v2",
        config_hash="a" * 64,
        state="stable",
        description="candidate",
    )
    session = AsyncMock()
    session.get.return_value = record
    version = await _DatabaseVersionLookup(session).get_version(tenant_id, version_id)
    assert version is not None
    assert version.id == version_id
    assert version.config_hash == record.config_hash
    assert version.version_tag == "v2"


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", [True, False])
async def test_worker_refuses_missing_or_foreign_version(missing):
    session = AsyncMock()
    session.get.return_value = None if missing else ComponentVersionORM(tenant_id=uuid4())
    assert await _DatabaseVersionLookup(session).get_version(uuid4(), uuid4()) is None


def test_graph_edge_pk_is_stable_and_bounded_for_postgres_schema():
    graph_hash = "a" * 64
    edge_id = "event:ab0f9c1bd0034e0c->version:00000000-0000-0000-0004-000000000001"

    first = _graph_edge_pk(graph_hash, edge_id)
    second = _graph_edge_pk(graph_hash, edge_id)

    assert first == second
    assert len(first) <= 128
    assert first.startswith(f"{graph_hash}:")
