"""
DriftGuard-X v2 — GAT API Integration Tests
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_gat_status_endpoint(client: AsyncClient) -> None:
    """GET /v1/detectors/gat/status returns status of loaded model."""
    resp = await client.get("/v1/detectors/gat/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_loaded" in data
    assert "device" in data
    assert "model_architecture" in data


async def test_gat_trace_evaluation_endpoint(client: AsyncClient) -> None:
    """POST /v1/detectors/gat/trace evaluates trace spans via GAT."""
    pytest.importorskip("torch")
    pytest.importorskip("torch_geometric")
    payload = {
        "trace_id": "test-trace-1",
        "spans": [
            {
                "span_id": "span_root",
                "parent_id": None,
                "duration_ms": 3200.0,
                "operation_name": "POST /api/order",
                "is_error": True,
            },
            {
                "span_id": "span_payment",
                "parent_id": "span_root",
                "duration_ms": 3100.0,
                "operation_name": "ts-payment-service.pay",
                "is_error": True,
            },
            {
                "span_id": "span_user",
                "parent_id": "span_root",
                "duration_ms": 15.0,
                "operation_name": "ts-user-service.check",
                "is_error": False,
            },
        ],
    }

    resp = await client.post("/v1/detectors/gat/trace", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "is_fault" in data
    assert "fault_probability" in data
    assert data["num_spans"] == 3
    assert len(data["root_cause_candidates"]) > 0
    assert data["root_cause_candidates"][0]["operation_name"] == "ts-payment-service.pay"


async def test_gat_evaluate_run_404_for_unknown_run(client: AsyncClient) -> None:
    """POST /v1/detectors/gat/evaluate-run/{random_id} returns 404 if no spans exist."""
    import uuid

    random_id = str(uuid.uuid4())
    resp = await client.post(f"/v1/detectors/gat/evaluate-run/{random_id}")
    assert resp.status_code == 404
