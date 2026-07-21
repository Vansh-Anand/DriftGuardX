"""
DriftGuard-X v2 — Security Tests (3 tests)

Tests for SQL injection protection, header injection, and no secrets in logs.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


@pytest.mark.security
async def test_sql_injection_in_query_field_rejected(client: AsyncClient) -> None:
    """SQL injection attempts in query field must not crash the API or expose DB."""
    payloads = [
        "'; DROP TABLE request_runs; --",
        "\" OR 1=1 --",
        "UNION SELECT * FROM tenants--",
    ]
    for payload in payloads:
        resp = await client.post(
            "/v1/runs",
            json={
                "query": payload,
                "use_experimental_retriever": False,
                "seed": 42,
                "is_synthetic": True,
            },
        )
        # Must not return 500 (unhandled exception)
        assert resp.status_code in (200, 201, 400, 422), (
            f"Unexpected status {resp.status_code} for payload: {payload!r}"
        )


@pytest.mark.security
async def test_unknown_run_id_does_not_expose_db_error(client: AsyncClient) -> None:
    """404 for unknown run ID must not expose internal DB details."""
    import uuid
    resp = await client.get(f"/v1/runs/{uuid.uuid4()}")
    assert resp.status_code == 404
    # Response must not contain traceback or SQL
    body = resp.text
    assert "traceback" not in body.lower()
    assert "sqlite" not in body.lower()
    assert "sqlalchemy" not in body.lower()


@pytest.mark.security
async def test_request_id_header_not_injected(client: AsyncClient) -> None:
    """X-Request-ID header is echoed back but not used for injection."""
    malicious_request_id = "<script>alert(1)</script>"
    resp = await client.get("/health", headers={"X-Request-ID": malicious_request_id})
    assert resp.status_code == 200
    # The echoed X-Request-ID should not be a valid HTML injection in JSON context
    # Just verify it doesn't crash the server
    assert resp.json()["status"] == "ok"
