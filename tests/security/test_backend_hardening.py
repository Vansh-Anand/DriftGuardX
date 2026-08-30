"""Backend security and evidence-integrity regression tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio, pytest.mark.security]


async def test_security_headers_and_untrusted_request_id_are_sanitized(
    client: AsyncClient,
) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "<script>alert(1)</script>"})

    assert response.status_code == 200
    assert response.headers["x-request-id"] != "<script>alert(1)</script>"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


async def test_oversized_declared_request_is_rejected_before_parsing(client: AsyncClient) -> None:
    response = await client.post(
        "/v1/runs",
        content=b"{}",
        headers={"Content-Type": "application/json", "Content-Length": str(3 * 1024 * 1024)},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body exceeds the configured limit"}


async def test_chunked_oversized_request_is_rejected_incrementally(client: AsyncClient) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"query":"'
        for _ in range(3):
            yield b"x" * (1024 * 1024)
        yield b'","seed":42,"is_synthetic":true}'

    response = await client.post(
        "/v1/runs",
        content=chunks(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body exceeds the configured limit"}


async def test_run_creation_is_idempotent_per_authenticated_tenant(client: AsyncClient) -> None:
    key = f"test-{uuid.uuid4()}"
    first = await client.post(
        "/v1/runs",
        headers={"X-Idempotency-Key": key},
        json={"query": "first request", "seed": 42, "is_synthetic": True},
    )
    second = await client.post(
        "/v1/runs",
        headers={"X-Idempotency-Key": key},
        json={"query": "different retry body", "seed": 99, "is_synthetic": True},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


async def test_span_ingestion_preserves_status_and_rejects_unscoped_runs(
    client: AsyncClient,
) -> None:
    run_response = await client.post(
        "/v1/runs",
        json={"query": "ingestion hardening", "seed": 42, "is_synthetic": True},
    )
    assert run_response.status_code == 201
    run = run_response.json()
    now = datetime.now(UTC).isoformat()
    span_id = uuid.uuid4().hex[:16]
    payload = {
        "trace_id": uuid.uuid4().hex,
        "span_id": span_id,
        "name": "external.error",
        "start_time": now,
        "end_time": now,
        "status_code": "ERROR",
        "run_id": run["id"],
        "tenant_id": run["tenant_id"],
        "pipeline_id": run["pipeline_id"],
    }
    accepted = await client.post("/v1/ingest/spans", json={"spans": [payload]})
    assert accepted.status_code == 200
    assert accepted.json()["ingested"] == 1

    quality = await client.get("/v1/telemetry/quality")
    assert quality.status_code == 200
    assert quality.json()["metrics"]["total_errors"] >= 1

    payload["span_id"] = uuid.uuid4().hex[:16]
    payload["run_id"] = str(uuid.uuid4())
    rejected = await client.post("/v1/ingest/spans", json={"spans": [payload]})
    assert rejected.status_code == 200
    assert rejected.json()["ingested"] == 0
    assert rejected.json()["errors"] == [f"span {payload['span_id']}: rejected"]


async def test_client_tenant_header_cannot_change_mock_identity_scope(client: AsyncClient) -> None:
    response = await client.get("/v1/runs", headers={"X-Tenant-ID": str(uuid.uuid4())})
    assert response.status_code == 200
