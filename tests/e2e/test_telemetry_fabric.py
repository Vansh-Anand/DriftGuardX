"""
DriftGuard-X v2 — Telemetry Fabric Tests
"""

import pytest
from httpx import AsyncClient

from apps.api.src.auth.auth import MOCK_TENANT_ID

pytestmark = pytest.mark.asyncio


async def test_telemetry_quality_endpoint(client: AsyncClient):
    """Verify that the telemetry quality endpoint returns valid stats."""
    tenant_id = str(MOCK_TENANT_ID)
    response = await client.get("/v1/telemetry/quality")

    assert response.status_code == 200
    data = response.json()

    assert data["tenant_id"] == tenant_id
    assert "metrics" in data
    assert "total_spans" in data["metrics"]
    assert "total_traces" in data["metrics"]
    assert "spans_missing_tags" in data["metrics"]


async def test_telemetry_search_endpoint(client: AsyncClient):
    """Verify that the telemetry search endpoint returns a list of traces."""
    response = await client.get("/v1/telemetry/search?limit=10")

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)
