"""
DriftGuard-X v2 — Telemetry Fabric Tests
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio

async def test_telemetry_quality_endpoint(client: AsyncClient):
    """Verify that the telemetry quality endpoint returns valid stats."""
    # Using a dummy tenant_id
    tenant_id = "11111111-1111-1111-1111-111111111111"
    response = await client.get(f"/v1/telemetry/quality/{tenant_id}")
        
    assert response.status_code == 200
    data = response.json()
    
    assert data["tenant_id"] == tenant_id
    assert "metrics" in data
    assert "total_spans" in data["metrics"]
    assert "total_traces" in data["metrics"]
    assert "spans_missing_tags" in data["metrics"]

async def test_telemetry_search_endpoint(client: AsyncClient):
    """Verify that the telemetry search endpoint returns a list of traces."""
    tenant_id = "11111111-1111-1111-1111-111111111111"
    response = await client.get(f"/v1/telemetry/search/{tenant_id}?limit=10")
        
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)

