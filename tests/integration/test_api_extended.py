"""
DriftGuard-X v2 — Additional API Tests (5 tests)
Covers span ingestion, list runs, trace retrieval, replay GET, and list pagination.
"""
from __future__ import annotations

from datetime import UTC

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.mark.integration
async def test_span_ingest_endpoint(client: AsyncClient) -> None:
    """POST /v1/ingest/spans returns ingested count."""
    # Create a run first to get a valid run_id
    run_resp = await client.post(
        "/v1/runs",
        json={"query": "ingest test", "use_experimental_retriever": False, "seed": 42, "is_synthetic": True},
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]
    tenant_id = run_resp.json()["tenant_id"]
    pipeline_id = run_resp.json()["pipeline_id"]

    from datetime import datetime
    now = datetime.now(UTC).isoformat()

    resp = await client.post(
        "/v1/ingest/spans",
        json={
            "spans": [
                {
                    "trace_id": "a" * 32,
                    "span_id": "b" * 16,
                    "parent_span_id": None,
                    "name": "test_span",
                    "kind": "INTERNAL",
                    "start_time": now,
                    "end_time": now,
                    "status_code": "OK",
                    "attributes": {"test_key": "test_value"},
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "pipeline_id": pipeline_id,
                }
            ]
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ingested"] == 1
    assert data["skipped"] == 0


@pytest.mark.integration
async def test_list_runs_pagination(client: AsyncClient) -> None:
    """GET /v1/runs supports pagination."""
    # Create 3 runs
    for i in range(3):
        await client.post(
            "/v1/runs",
            json={"query": f"page test {i}", "use_experimental_retriever": False, "seed": 42, "is_synthetic": True},
        )

    resp = await client.get("/v1/runs", params={"skip": 2, "limit": 2})
    assert resp.status_code == 200
    data = resp.json()
    assert "runs" in data
    assert "total" in data
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert len(data["runs"]) <= 2


@pytest.mark.integration
async def test_get_run_trace_endpoint(client: AsyncClient) -> None:
    """GET /v1/runs/{id}/trace returns normalized trace."""
    run_resp = await client.post(
        "/v1/runs",
        json={"query": "trace test", "use_experimental_retriever": False, "seed": 42, "is_synthetic": True},
    )
    run_id = run_resp.json()["id"]

    resp = await client.get(f"/v1/runs/{run_id}/trace")
    assert resp.status_code == 200
    trace = resp.json()
    assert "spans" in trace
    assert trace["total_span_count"] >= 1
    assert "trace_id" in trace
    assert "root_span_id" in trace


@pytest.mark.integration
async def test_replay_endpoint_full_flow(client: AsyncClient) -> None:
    """POST /v1/runs/{id}/replays → GET /v1/replays/{id} full round-trip."""
    # Create experimental run
    run_resp = await client.post(
        "/v1/runs",
        json={"query": "full replay test", "use_experimental_retriever": True, "seed": 42, "is_synthetic": True},
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Create replay
    replay_resp = await client.post(
        f"/v1/runs/{run_id}/replays",
        json={"swap_retriever_to_stable": True, "seed": 42},
    )
    assert replay_resp.status_code == 201
    replay_id = replay_resp.json()["id"]

    # Fetch replay
    get_resp = await client.get(f"/v1/replays/{replay_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == replay_id
    assert data["original_run_id"] == run_id
    assert "reliability_delta" in data


@pytest.mark.integration
async def test_non_synthetic_run_replay_blocked(client: AsyncClient) -> None:
    """The mock API must not label a deterministic simulation as real evidence."""
    run_resp = await client.post(
        "/v1/runs",
        json={"query": "non-synthetic", "use_experimental_retriever": True, "seed": 42, "is_synthetic": False},
    )
    assert run_resp.status_code == 400
    assert "non-synthetic" in run_resp.json()["detail"].lower()
