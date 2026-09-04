import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.src.models import RequestRunORM
from datetime import UTC, datetime

pytestmark = pytest.mark.asyncio

async def test_finalize_run_idempotency_and_validation(client: AsyncClient, db_session: AsyncSession):
    # Setup test run in DB
    run_id = uuid.uuid4()
    tenant_id = uuid.UUID("00000000-0000-0000-FFFF-000000000001") # matches make_tenant_id() in conftest.py
    
    run = RequestRunORM(
        id=run_id,
        tenant_id=tenant_id,
        pipeline_id=uuid.uuid4(),
        status="RUNNING",
        is_synthetic=True,
        created_at=datetime.now(UTC)
    )
    db_session.add(run)
    await db_session.commit()
    
    # 1. 422 Negative token validation
    res = await client.post(
        f"/v1/runs/{run_id}/finalize",
        json={
            "status": "COMPLETED",
            "total_tokens": -5,
        }
    )
    assert res.status_code == 422
    assert "negative" in res.json()["detail"].lower()

    # 2. 422 Negative cost validation
    res = await client.post(
        f"/v1/runs/{run_id}/finalize",
        json={
            "status": "COMPLETED",
            "total_cost_usd": -10.0,
        }
    )
    assert res.status_code == 422
    
    # 3. 422 Negative latency validation
    res = await client.post(
        f"/v1/runs/{run_id}/finalize",
        json={
            "status": "COMPLETED",
            "total_latency_ms": -1.0,
        }
    )
    assert res.status_code == 422
    
    # 4. Valid finalize
    res = await client.post(
        f"/v1/runs/{run_id}/finalize",
        json={
            "status": "COMPLETED",
            "total_tokens": 100,
        }
    )
    assert res.status_code == 200
    assert res.json()["status"] == "COMPLETED"
    
    # 5. Idempotent finalize
    res = await client.post(
        f"/v1/runs/{run_id}/finalize",
        json={
            "status": "COMPLETED",
            "total_tokens": 100,
        }
    )
    assert res.status_code == 200
    
    # 6. Reject invalid transition
    res = await client.post(
        f"/v1/runs/{run_id}/finalize",
        json={
            "status": "FAILED",
        }
    )
    assert res.status_code == 409

async def test_concurrent_finalize(client: AsyncClient, db_session: AsyncSession):
    import asyncio
    run_id = uuid.uuid4()
    tenant_id = uuid.UUID("00000000-0000-0000-FFFF-000000000001")
    
    run = RequestRunORM(
        id=run_id,
        tenant_id=tenant_id,
        pipeline_id=uuid.uuid4(),
        status="RUNNING",
        is_synthetic=True,
        created_at=datetime.now(UTC)
    )
    db_session.add(run)
    await db_session.commit()

    # Skip if SQLite because it doesn't support SELECT FOR UPDATE
    bind = db_session.get_bind()
    if bind.dialect.name == "sqlite":
        pytest.skip("SQLite does not support row-level locks (SELECT FOR UPDATE)")

    async def call_finalize(status: str):
        return await client.post(
            f"/v1/runs/{run_id}/finalize",
            json={
                "status": status,
                "total_tokens": 100,
            }
        )

    # Fire two concurrent finalize requests that conflict
    res1, res2 = await asyncio.gather(
        call_finalize("COMPLETED"),
        call_finalize("FAILED")
    )
    
    # One should succeed (200), one should fail due to transition conflict (409)
    status_codes = {res1.status_code, res2.status_code}
    assert 200 in status_codes
    assert 409 in status_codes

async def test_finalize_durability_failure(client: AsyncClient, db_session: AsyncSession, monkeypatch):
    import uuid
    run_id = uuid.uuid4()
    tenant_id = uuid.UUID("00000000-0000-0000-FFFF-000000000001")
    
    run = RequestRunORM(
        id=run_id,
        tenant_id=tenant_id,
        pipeline_id=uuid.uuid4(),
        status="RUNNING",
        is_synthetic=True,
        created_at=datetime.now(UTC)
    )
    db_session.add(run)
    await db_session.commit()

    # Monkeypatch AsyncSession.commit globally to raise an Exception
    async def mock_commit(self):
        raise Exception("Simulated DB commit failure")
        
    monkeypatch.setattr("sqlalchemy.ext.asyncio.AsyncSession.commit", mock_commit)

    res = await client.post(
        f"/v1/runs/{run_id}/finalize",
        json={
            "status": "COMPLETED",
            "total_tokens": 100,
        }
    )
    
    # Must fail with 500, not 200
    assert res.status_code == 500
    assert "commit failed" in res.json()["detail"].lower()


async def test_create_run_synthetic_and_real(client: AsyncClient, db_session: AsyncSession):
    # 1. Synthetic execution mode
    res_synth = await client.post(
        "/v1/runs",
        json={
            "query": "Is system running?",
            "execution_mode": "synthetic",
            "is_synthetic": True,
        }
    )
    assert res_synth.status_code == 201
    data_synth = res_synth.json()
    assert data_synth["is_synthetic"] is True
    assert data_synth["status"].lower() == "completed"

    # 2. Real execution mode
    res_real = await client.post(
        "/v1/runs",
        json={
            "query": "What are the latest compliance protocols?",
            "execution_mode": "real",
            "is_synthetic": False,
        }
    )
    assert res_real.status_code == 201
    data_real = res_real.json()
    assert data_real["is_synthetic"] is False
    assert data_real["status"].lower() == "completed"
    assert data_real["total_latency_ms"] > 0

    # 3. Controlled execution mode
    res_ctrl = await client.post(
        "/v1/runs",
        json={
            "query": "Controlled fault test query",
            "execution_mode": "controlled",
        }
    )
    assert res_ctrl.status_code == 201
    data_ctrl = res_ctrl.json()
    assert data_ctrl["is_synthetic"] is False
    assert data_ctrl["reliability_score"] <= 0.6

