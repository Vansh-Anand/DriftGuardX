"""
DriftGuard-X v2 — API Smoke Tests (6 tests)
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


@pytest.mark.unit
async def test_health_endpoint(client: AsyncClient) -> None:
    """GET /health returns 200 with status=ok."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "timestamp" in data


@pytest.mark.unit
async def test_readiness_endpoint(client: AsyncClient) -> None:
    """GET /ready returns status with DB check."""
    resp = await client.get("/ready")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "checks" in data


@pytest.mark.unit
async def test_create_run_stable(client: AsyncClient) -> None:
    """POST /v1/runs with stable retriever returns a completed run."""
    resp = await client.post(
        "/v1/runs",
        json={
            "query": "What is AI safety?",
            "use_experimental_retriever": False,
            "seed": 42,
            "is_synthetic": True,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "completed"
    assert data["is_synthetic"] is True
    assert data["reliability_score"] is not None
    assert 0.0 <= data["reliability_score"] <= 1.0


@pytest.mark.unit
async def test_create_run_experimental_lower_reliability(client: AsyncClient) -> None:
    """POST /v1/runs with experimental retriever has lower reliability than stable."""
    # Stable run
    resp_stable = await client.post(
        "/v1/runs",
        json={"query": "test", "use_experimental_retriever": False, "seed": 42, "is_synthetic": True},
    )
    assert resp_stable.status_code == 201
    stable_score = resp_stable.json()["reliability_score"]

    # Experimental run
    resp_exp = await client.post(
        "/v1/runs",
        json={"query": "test", "use_experimental_retriever": True, "seed": 42, "is_synthetic": True},
    )
    assert resp_exp.status_code == 201
    exp_score = resp_exp.json()["reliability_score"]

    assert exp_score < stable_score, (
        f"Experimental score {exp_score} should be less than stable {stable_score}"
    )


@pytest.mark.unit
async def test_get_run_by_id(client: AsyncClient) -> None:
    """GET /v1/runs/{id} returns the run."""
    # Create a run first
    resp = await client.post(
        "/v1/runs",
        json={"query": "test", "use_experimental_retriever": False, "seed": 42, "is_synthetic": True},
    )
    run_id = resp.json()["id"]

    resp2 = await client.get(f"/v1/runs/{run_id}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == run_id


@pytest.mark.unit
async def test_get_run_not_found(client: AsyncClient) -> None:
    """GET /v1/runs/{id} returns 404 for unknown ID."""
    import uuid
    fake_id = uuid.uuid4()
    resp = await client.get(f"/v1/runs/{fake_id}")
    assert resp.status_code == 404
