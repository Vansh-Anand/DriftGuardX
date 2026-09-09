from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from apps.api.src.models import ComponentVersionORM
from apps.worker.src.worker import (
    _agent_invocation_from_payload,
    _DatabaseVersionLookup,
    _graph_edge_pk,
)


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


def test_agent_invocation_payload_hydrates_stored_json_contract_fields():
    run_id = uuid4()
    tenant_id = uuid4()

    invocation = _agent_invocation_from_payload(
        {
            "invocation_id": "1d71fca86e6f6dbe",
            "run_id": str(run_id),
            "tenant_id": str(tenant_id),
            "agent_name": "retriever",
            "start_time": "2026-09-09T09:50:25.059081Z",
            "end_time": "2026-09-09T09:50:25.159081Z",
            "metadata": {"source": "golden-e2e"},
        }
    )

    assert invocation.run_id == run_id
    assert invocation.tenant_id == tenant_id
    assert isinstance(invocation.invocation_id, UUID)
    assert invocation.metadata["source"] == "golden-e2e"
    assert invocation.metadata["source_invocation_id"] == "1d71fca86e6f6dbe"
    assert invocation.start_time.tzinfo is not None
    assert invocation.end_time is not None
