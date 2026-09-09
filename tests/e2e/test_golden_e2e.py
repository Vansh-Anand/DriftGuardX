import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.src.database import Base, get_db
from apps.api.src.main import app
from apps.api.src.models import AgentPipelineORM, ComponentVersionORM, TenantORM
from apps.api.src.pipeline.mock_rag import (
    ALL_COMPONENT_VERSIONS,
    PIPELINE_WITH_EXPERIMENTAL_RETRIEVER,
    PIPELINE_WITH_STABLE_RETRIEVER,
    RETRIEVER_V1,
    RETRIEVER_V2_EXP,
)
from apps.worker.src.worker import (
    execute_bcrb_diagnosis_job,
    execute_graph_construction_job,
    execute_recovery_job,
    execute_replay_job,
)
from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.interfaces import ResourceContext
from packages.replay.src.admission_receipt import ReplayAdmissionReceipt
from packages.replay.src.admission_store import AdmissionReceiptStore
from packages.trace_sdk.src.tracer import hash_payload

pytestmark = pytest.mark.asyncio


async def _seed_mock_catalog(session: AsyncSession) -> None:
    tenant_id = PIPELINE_WITH_STABLE_RETRIEVER.tenant_id
    await session.merge(TenantORM(id=tenant_id, name="Acme Corp", slug="acme-corp"))
    for pipeline in (PIPELINE_WITH_STABLE_RETRIEVER, PIPELINE_WITH_EXPERIMENTAL_RETRIEVER):
        await session.merge(
            AgentPipelineORM(
                id=pipeline.id,
                tenant_id=pipeline.tenant_id,
                name=pipeline.name,
                version=pipeline.version,
                is_active=True,
                component_version_ids={
                    component.component_type.value: str(component.id)
                    for component in pipeline.component_versions
                },
            )
        )
    for component in ALL_COMPONENT_VERSIONS:
        await session.merge(
            ComponentVersionORM(
                id=component.id,
                tenant_id=tenant_id,
                component_type=component.component_type.value,
                version_tag=component.version_tag,
                state=component.state.value,
                config_hash=component.config_hash,
                description=component.description,
            )
        )
    await session.commit()


@pytest.mark.e2e
async def test_golden_e2e_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_url = os.getenv("DGX_SERVICE_DATABASE_URL", "")
    redis_url = os.getenv("REDIS_URL", "")

    if not database_url.startswith("postgresql+") or not redis_url:
        pytest.skip(
            "Golden E2E requires live PostgreSQL and Redis (DGX_SERVICE_DATABASE_URL and REDIS_URL)"
        )

    # 1. Setup real PostgreSQL and Redis
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setenv("DGX_ADMISSION_STORE_PATH", str(tmp_path / "admission_receipts.sqlite3"))

    async def override_get_db():
        async with SessionLocal() as session:
            yield session
            await session.commit()

    app.dependency_overrides[get_db] = override_get_db

    redis = Redis.from_url(redis_url)
    assert await redis.ping() is True
    async with SessionLocal() as db_session:
        await _seed_mock_catalog(db_session)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.headers["Authorization"] = "Bearer mock-admin-token"

            # --- 2. Create Run (synthetic controlled fault) ---
            run_resp = await client.post(
                "/v1/runs",
                json={
                    "query": "End-to-End Fault Detection Test",
                    "is_synthetic": True,
                    "use_experimental_retriever": True,
                    "seed": 42,
                },
            )
            assert run_resp.status_code == 201, run_resp.text
            run_data = run_resp.json()
            run_id = run_data["id"]
            tenant_id = run_data["tenant_id"]

            # Assertions for controlled synthetic fault outcome
            assert run_data["is_synthetic"] is True
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
            ctx = {"redis": redis, "db_session_factory": SessionLocal}
            graph_res = await execute_graph_construction_job(
                ctx, str(uuid.uuid4()), tenant_id, {"run_id": run_id}
            )
            assert graph_res["status"] == "completed"
            assert graph_res["nodes_count"] > 0

            # --- 5. Worker: BCRB Diagnosis ---
            bcrb_res = await execute_bcrb_diagnosis_job(
                ctx,
                str(uuid.uuid4()),
                tenant_id,
                {"run_id": run_id, "failure_symptom": "Reliability drop in production"},
            )
            assert bcrb_res["status"] == "completed"
            assert "diagnosed_root_cause" in bcrb_res
            assert bcrb_res["total_spent_usd"] >= 0.0

            # --- 6. Worker: Replay (with candidate from BCRB or a manual intervention) ---
            from apps.api.src.models import (
                InterventionORM,
                ReplayStateManifestORM,
                TraceArtifactORM,
            )

            intervention_id = uuid.uuid4()

            async with SessionLocal() as db_session:
                inv = InterventionORM(
                    id=intervention_id,
                    run_id=uuid.UUID(run_id),
                    tenant_id=uuid.UUID(tenant_id),
                    intervention_type="rollback",
                    target_component_type=RETRIEVER_V2_EXP.component_type.value,
                    from_version_id=RETRIEVER_V2_EXP.id,
                    to_version_id=RETRIEVER_V1.id,
                    from_version_tag=RETRIEVER_V2_EXP.version_tag,
                    to_version_tag=RETRIEVER_V1.version_tag,
                    created_at=datetime.now(UTC),
                )
                db_session.add(inv)
                await db_session.commit()

                manifest_orm = await db_session.scalar(
                    select(ReplayStateManifestORM).where(
                        ReplayStateManifestORM.run_id == uuid.UUID(run_id)
                    )
                )
                trace_orm = await db_session.scalar(
                    select(TraceArtifactORM).where(TraceArtifactORM.run_id == uuid.UUID(run_id))
                )
                assert manifest_orm is not None
                assert trace_orm is not None

                trace_root_hash = hash_payload(
                    {
                        "root_span_id": trace_orm.root_span_id,
                        "total_span_count": trace_orm.total_span_count,
                        "spans": trace_orm.spans_json,
                    }
                )
                intervention_hash = ReplayAdmissionReceipt.intervention_binding_hash(
                    str(intervention_id),
                    RETRIEVER_V2_EXP.component_type.value,
                    RETRIEVER_V2_EXP.version_tag,
                    RETRIEVER_V1.version_tag,
                )
                admission_receipt = ReplayAdmissionReceipt.issue(
                    resource_context=ResourceContext(budget_usd=10.0),
                    tenant_id=tenant_id,
                    manifest_hash=manifest_orm.manifest_hash,
                    trace_root_hash=trace_root_hash,
                    intervention_hash=intervention_hash,
                    current_version=RETRIEVER_V2_EXP.version_tag,
                    candidate_version=RETRIEVER_V1.version_tag,
                    policy_hash=manifest_orm.policy_config_hash or "",
                    predicted_cost=0.1,
                    uncertainty_margin=0.05,
                    rollback_reserve=0.1,
                    evidence_ceiling=EvidenceClassification.SYNTHETIC_SIMULATION,
                    capsule_hash="",
                    expires_at=datetime.now(UTC) + timedelta(minutes=10),
                )
                AdmissionReceiptStore().issue(admission_receipt)

            replay_res = await execute_replay_job(
                ctx,
                str(uuid.uuid4()),
                tenant_id,
                {
                    "run_id": run_id,
                    "intervention_id": str(intervention_id),
                    "admission_receipt_id": admission_receipt.receipt_id,
                    "seed": 42,
                },
            )
            assert replay_res["status"] == "completed"
            assert replay_res["reliability_improvement"] is not None

            # --- 7. Worker: Recovery ---
            # Execute end-to-end recovery loop
            # Extract invocations from real trace instead of a dummy invocation
            agent_spans = [
                s
                for s in trace_data.get("spans", [])
                if str(s.get("component_type")).upper() == "AGENT"
                or str(s.get("kind")).upper() == "AGENT"
            ]
            invocations = []
            for s in agent_spans:
                invocations.append(
                    {
                        "invocation_id": s.get("span_id"),
                        "run_id": run_id,
                        "tenant_id": tenant_id,
                        "agent_name": s.get("name", "unknown_agent"),
                        "start_time": s.get("start_time"),
                        "end_time": s.get("end_time") or s.get("start_time"),
                    }
                )

            if not invocations:
                # Fallback to root span if no agent spans are specifically tagged
                root_span = next(
                    (s for s in trace_data.get("spans", []) if not s.get("parent_span_id")), None
                )
                if root_span:
                    invocations.append(
                        {
                            "invocation_id": root_span.get("span_id"),
                            "run_id": run_id,
                            "tenant_id": tenant_id,
                            "agent_name": root_span.get("name", "pipeline"),
                            "start_time": root_span.get("start_time"),
                            "end_time": root_span.get("end_time") or root_span.get("start_time"),
                        }
                    )

            rec_res = await execute_recovery_job(
                ctx,
                str(uuid.uuid4()),
                tenant_id,
                {
                    "run_id": run_id,
                    "failure_symptom": "E2E Test Symptom",
                    "invocations_data": invocations,
                },
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
