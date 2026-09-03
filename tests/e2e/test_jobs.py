import asyncio

import pytest
from httpx import AsyncClient

from apps.api.src.auth.auth import MOCK_TENANT_ID
from apps.api.src.jobs.orchestrator import orchestrator


async def dummy_slow_job():
    await asyncio.sleep(0.5)
    return "done"


@pytest.mark.asyncio
async def test_job_status_and_cancellation(client: AsyncClient):
    """Verify background jobs can be polled and cancelled."""

    # Submit a job directly to orchestrator (simulating a background task trigger)
    job_id = orchestrator.submit_job("test_task", dummy_slow_job, tenant_id=str(MOCK_TENANT_ID))

    headers = {"Authorization": "Bearer mock-admin-token"}

    # Check status
    response = await client.get(f"/v1/jobs/{job_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("pending", "running")

    # Cancel job
    response = await client.post(f"/v1/jobs/{job_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    # Check status again
    response = await client.get(f"/v1/jobs/{job_id}", headers=headers)
    data = response.json()
    assert data["status"] == "cancelled"


@pytest.mark.asyncio
async def test_providers_endpoint(client: AsyncClient):
    """Verify provider registry lists providers correctly."""
    headers = {"Authorization": "Bearer mock-admin-token"}
    response = await client.get("/v1/providers/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "gpt-4o" in data
    assert "mock-local" in data
    assert data["gpt-4o"]["cost_per_1k"] == 0.005


@pytest.mark.asyncio
async def test_job_identifier_does_not_cross_tenant_boundary(client: AsyncClient):
    job_id = orchestrator.submit_job(
        "tenant_private", dummy_slow_job, tenant_id="11111111-1111-1111-1111-111111111111"
    )
    response = await client.get(f"/v1/jobs/{job_id}")
    assert response.status_code == 404
    orchestrator.jobs[job_id]._task.cancel()
