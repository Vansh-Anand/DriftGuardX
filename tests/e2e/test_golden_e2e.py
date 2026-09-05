import asyncio
import os
import uuid
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from redis.asyncio import Redis

from apps.api.src.main import app
from apps.api.src.database import get_db, Base
from apps.worker.src.worker import (
    execute_replay_job,
    execute_graph_construction_job,
    execute_bcrb_diagnosis_job,
    execute_recovery_job,
)

pytestmark = pytest.mark.asyncio

@pytest.mark.e2e
async def test_golden_e2e_flow():
    database_url = os.getenv("DGX_SERVICE_DATABASE_URL", "")
    redis_url = os.getenv("REDIS_URL", "")
    
    if not database_url.startswith("postgresql+") or not redis_url:
        pytest.skip("Golden E2E requires live PostgreSQL and Redis (DGX_SERVICE_DATABASE_URL and REDIS_URL)")

    # 1. Setup real PostgreSQL and Redis
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session
            await session.commit()
            
    app.dependency_overrides[get_db] = override_get_db

    redis = Redis.from_url(redis_url)
    assert await redis.ping() is True

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.headers["Authorization"] = "Bearer mock-admin-token"
            
            # --- 2. Create Run (Execution mode: controlled) ---
            run_resp = await client.post(
                "/v1/runs",
                json={
                    "query": "End-to-End Fault Detection Test",
                    "execution_mode": "controlled",
                    "seed": 42
                }
            )
            assert run_resp.status_code == 201, run_resp.text
            run_data = run_resp.json()
            run_id = run_data["id"]
            tenant_id = run_data["tenant_id"]
            
            # Assertions for real outcome
            assert run_data["is_synthetic"] is False
            assert run_data["reliability_score"] <= 0.6  # Controlled fault
            
            # Verify trace is saved
            trace_resp = await client.get(f"/v1/runs/{run_id}/trace")
            assert trace_resp.status_code == 200, trace_resp.text
            trace_data = trace_resp.json()
            assert trace_data["total_span_count"] > 0
            
            # --- 3. Evaluate Trace (GAT) ---
            eval_resp = await client.post(f"/v1/detectors/gat/evaluate-run/{run_id}")
            assert eval_resp.status_code == 200, eval_resp.text
            eval_data = eval_resp.json()
            
            assert "candidates" in eval_data
            
            # --- 4. Worker: Build Causal Graph ---
            ctx = {"redis": redis}
            graph_res = await execute_graph_construction_job(ctx, str(uuid.uuid4()), tenant_id, {"run_id": run_id})
            assert graph_res["status"] == "completed"
            assert graph_res["nodes_count"] > 0
            
            # --- 5. Worker: BCRB Diagnosis ---
            bcrb_res = await execute_bcrb_diagnosis_job(
                ctx, str(uuid.uuid4()), tenant_id, 
                {"run_id": run_id, "failure_symptom": "Reliability drop in production"}
            )
            assert bcrb_res["status"] == "completed"
            assert "diagnosed_root_cause" in bcrb_res
            assert bcrb_res["total_spent_usd"] >= 0.0
            
            # --- 6. Worker: Replay (with candidate from BCRB or a manual intervention) ---
            from apps.api.src.models import InterventionORM
            import datetime
            intervention_id = uuid.uuid4()
            
            target_component = bcrb_res.get("diagnosed_root_cause")
            if not target_component or target_component == "INSUFFICIENT_EVIDENCE":
                target_component = "retriever"
                
            async with SessionLocal() as db_session:
                inv = InterventionORM(
                    id=intervention_id,
                    run_id=uuid.UUID(run_id),
                    tenant_id=uuid.UUID(tenant_id),
                    intervention_type="rollback",
                    target_component_type=target_component,
                    from_version_id=uuid.uuid4(),
                    to_version_id=uuid.uuid4(),
                    from_version_tag="v2-exp",
                    to_version_tag="v1-stable",
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                db_session.add(inv)
                await db_session.commit()
            
            replay_res = await execute_replay_job(
                ctx, str(uuid.uuid4()), tenant_id, 
                {"run_id": run_id, "intervention_id": str(intervention_id), "seed": 42}
            )
            assert replay_res["status"] == "completed"
            assert replay_res["reliability_improvement"] is not None
            
            # --- 7. Worker: Recovery ---
            # Execute end-to-end recovery loop
            # Extract invocations from real trace instead of a dummy invocation
            agent_spans = [s for s in trace_data.get("spans", []) if str(s.get("component_type")).upper() == "AGENT" or str(s.get("kind")).upper() == "AGENT"]
            invocations = []
            for s in agent_spans:
                invocations.append({
                    "invocation_id": s.get("span_id"),
                    "run_id": run_id,
                    "tenant_id": tenant_id,
                    "agent_name": s.get("name", "unknown_agent"),
                    "start_time": s.get("start_time"),
                    "end_time": s.get("end_time") or s.get("start_time")
                })
                
            if not invocations:
                # Fallback to root span if no agent spans are specifically tagged
                root_span = next((s for s in trace_data.get("spans", []) if not s.get("parent_span_id")), None)
                if root_span:
                    invocations.append({
                        "invocation_id": root_span.get("span_id"),
                        "run_id": run_id,
                        "tenant_id": tenant_id,
                        "agent_name": root_span.get("name", "pipeline"),
                        "start_time": root_span.get("start_time"),
                        "end_time": root_span.get("end_time") or root_span.get("start_time")
                    })
            
            rec_res = await execute_recovery_job(
                ctx, str(uuid.uuid4()), tenant_id,
                {"run_id": run_id, "failure_symptom": "E2E Test Symptom", "invocations_data": invocations}
            )
            assert rec_res["status"] == "completed"
            assert rec_res.get("verification_passed") is True or "approval_request_id" in rec_res
            
            # --- 8. Evidence Ledger (API check) ---
            certs_resp = await client.get("/v1/recovery")
            assert certs_resp.status_code == 200
            certs = certs_resp.json()
            assert isinstance(certs, list)
            
    finally:
        app.dependency_overrides.clear()
        await redis.aclose()
        # Clean up database tables created by test
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
