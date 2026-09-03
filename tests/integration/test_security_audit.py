import uuid
from datetime import datetime, UTC
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from apps.api.src.models import TenantORM, UserORM, TenantMembershipORM

@pytest.fixture
async def setup_test_auth(db_session: AsyncSession):
    # Setup test tenant and user with specific roles, using random UUIDs to avoid unique constraints
    u_admin_id = str(uuid.uuid4())
    u_viewer_id = str(uuid.uuid4())
    
    t_admin = TenantORM(name=f"Admin Tenant {u_admin_id}", slug=f"admin-tenant-{u_admin_id}")
    db_session.add(t_admin)
    t_viewer = TenantORM(name=f"Viewer Tenant {u_viewer_id}", slug=f"viewer-tenant-{u_viewer_id}")
    db_session.add(t_viewer)
    
    await db_session.flush()
    
    u_admin = UserORM(auth_subject=f"test-admin-sub-{u_admin_id}", email=f"admin-{u_admin_id}@test.com")
    db_session.add(u_admin)
    u_viewer = UserORM(auth_subject=f"test-viewer-sub-{u_viewer_id}", email=f"viewer-{u_viewer_id}@test.com")
    db_session.add(u_viewer)
    
    await db_session.flush()
    
    m_admin = TenantMembershipORM(user_id=u_admin.id, tenant_id=t_admin.id, roles_json=["admin"])
    db_session.add(m_admin)
    m_viewer = TenantMembershipORM(user_id=u_viewer.id, tenant_id=t_viewer.id, roles_json=["viewer"])
    db_session.add(m_viewer)
    
    await db_session.commit()
    
    return {
        "t_admin": t_admin,
        "u_admin": u_admin,
        "t_viewer": t_viewer,
        "u_viewer": u_viewer
    }


@pytest.mark.asyncio
async def test_unauthenticated_rejection(client: AsyncClient):
    # client fixture automatically adds Bearer mock-admin-token, so we remove it
    client.headers.pop("Authorization", None)
    response = await client.get("/v1/recovery")
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_authenticated_unauthorized_role(client: AsyncClient, monkeypatch, setup_test_auth):
    client.headers["Authorization"] = "Bearer fake-token"
    async def mock_verify_token(*args, **kwargs):
        return {
            "sub": setup_test_auth["u_viewer"].auth_subject,
            "email": setup_test_auth["u_viewer"].email,
            "roles": ["viewer"],
            "tenant_id": str(setup_test_auth["t_viewer"].id)
        }
    monkeypatch.setattr("apps.api.src.dependencies.verify_token", mock_verify_token)
    monkeypatch.setattr("apps.api.src.auth.auth.verify_token", mock_verify_token)
    

    from apps.api.src.models import ApprovalRequestORM
    from packages.contracts.src.recovery_models import RecoveryEvidenceKind
    from datetime import datetime, UTC, timedelta
    import uuid
    
    async def mock_execute_recovery_loop(self, run_id, invocations, failure_symptom, db):
        req = ApprovalRequestORM(
            id=uuid.uuid4(),
            tenant_id=setup_test_auth["t_admin"].id,
            action="RECOVERY_EXECUTION",
            resource=str(uuid.uuid4()),
            requester_id="system_bcrb",
            node_id=str(uuid.uuid4()),
            risk_tier="HIGH",
            required_approvers=1,
            two_person_control=False,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            context_json={
                "run_id": run_id,
                "replay_episode_id": str(uuid.uuid4()),
                "intervention_id": str(uuid.uuid4()),
                "evidence_kind": RecoveryEvidenceKind.SYNTHETIC_SIMULATION.value,
                "cert_hash": "dummy_hash"
            }
        )
        db.add(req)
        await db.flush()
        return req
        
    monkeypatch.setattr("apps.api.src.services.recovery_pipeline.EndToEndRecoveryPipeline.execute_recovery_loop", mock_execute_recovery_loop)
    
    response = await client.post(
        "/v1/recovery/trigger",
        json={"tenant_id": str(setup_test_auth["t_viewer"].id)}
    )
    print(response.json())
    assert response.status_code == 403
    assert "admin role" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_cross_tenant_access_rejection(client: AsyncClient, monkeypatch, setup_test_auth):
    client.headers["Authorization"] = "Bearer fake-token"
    async def mock_verify_token(*args, **kwargs):
        return {
            "sub": setup_test_auth["u_admin"].auth_subject,
            "email": setup_test_auth["u_admin"].email,
            "roles": ["admin"],
            "tenant_id": str(setup_test_auth["t_admin"].id)
        }
    monkeypatch.setattr("apps.api.src.dependencies.verify_token", mock_verify_token)
    monkeypatch.setattr("apps.api.src.auth.auth.verify_token", mock_verify_token)
    

    from apps.api.src.models import ApprovalRequestORM
    from packages.contracts.src.recovery_models import RecoveryEvidenceKind
    from datetime import datetime, UTC, timedelta
    import uuid
    
    async def mock_execute_recovery_loop(self, run_id, invocations, failure_symptom, db):
        req = ApprovalRequestORM(
            id=uuid.uuid4(),
            tenant_id=setup_test_auth["t_admin"].id,
            action="RECOVERY_EXECUTION",
            resource=str(uuid.uuid4()),
            requester_id="system_bcrb",
            node_id=str(uuid.uuid4()),
            risk_tier="HIGH",
            required_approvers=1,
            two_person_control=False,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            context_json={
                "run_id": run_id,
                "replay_episode_id": str(uuid.uuid4()),
                "intervention_id": str(uuid.uuid4()),
                "evidence_kind": RecoveryEvidenceKind.SYNTHETIC_SIMULATION.value,
                "cert_hash": "dummy_hash"
            }
        )
        db.add(req)
        await db.flush()
        return req
        
    monkeypatch.setattr("apps.api.src.services.recovery_pipeline.EndToEndRecoveryPipeline.execute_recovery_loop", mock_execute_recovery_loop)
    
    response = await client.post(
        "/v1/recovery/trigger",
        json={"tenant_id": str(setup_test_auth["t_viewer"].id)}
    )
    print(response.json())
    assert response.status_code == 403
    assert "Cross-tenant recovery trigger forbidden" in response.json()["detail"]


@pytest.mark.asyncio
async def test_human_approval_workflow(client: AsyncClient, monkeypatch, setup_test_auth, db_session: AsyncSession):
    client.headers["Authorization"] = "Bearer fake-token"
    async def mock_verify_token(*args, **kwargs):
        return {
            "sub": setup_test_auth["u_admin"].auth_subject,
            "email": setup_test_auth["u_admin"].email,
            "roles": ["admin"],
            "tenant_id": str(setup_test_auth["t_admin"].id)
        }
    monkeypatch.setattr("apps.api.src.dependencies.verify_token", mock_verify_token)
    monkeypatch.setattr("apps.api.src.auth.auth.verify_token", mock_verify_token)
    

    from apps.api.src.models import ApprovalRequestORM
    from packages.contracts.src.recovery_models import RecoveryEvidenceKind
    from datetime import datetime, UTC, timedelta
    import uuid
    
    async def mock_execute_recovery_loop(self, run_id, invocations, failure_symptom, db):
        req = ApprovalRequestORM(
            id=uuid.uuid4(),
            tenant_id=setup_test_auth["t_admin"].id,
            action="RECOVERY_EXECUTION",
            resource=str(uuid.uuid4()),
            requester_id="system_bcrb",
            node_id=str(uuid.uuid4()),
            risk_tier="HIGH",
            required_approvers=1,
            two_person_control=False,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(hours=24),
            context_json={
                "run_id": run_id,
                "replay_episode_id": str(uuid.uuid4()),
                "intervention_id": str(uuid.uuid4()),
                "evidence_kind": RecoveryEvidenceKind.SYNTHETIC_SIMULATION.value,
                "cert_hash": "dummy_hash"
            }
        )
        db.add(req)
        await db.flush()
        return req
        
    monkeypatch.setattr("apps.api.src.services.recovery_pipeline.EndToEndRecoveryPipeline.execute_recovery_loop", mock_execute_recovery_loop)
    
    response = await client.post(
        "/v1/recovery/trigger",
        json={"tenant_id": str(setup_test_auth["t_admin"].id)}
    )
    print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "pending_approval"
    approval_id = data["approval_request_id"]
    
    approve_res = await client.post(
        "/v1/recovery/approve",
        json={"approval_id": approval_id, "decision": "APPROVED"}
    )
    
    assert approve_res.status_code == 200
    cert = approve_res.json()
    assert cert["is_valid"] == True
    assert "cryptographic_signature" in cert
    assert cert["cryptographic_signature"]["algorithm"] == "Ed25519"
    
    verify_res = await client.post(
        "/v1/recovery/verify",
        json={"certificate": cert}
    )
    
    assert verify_res.status_code == 200
    assert verify_res.json()["valid"] is True
    
    cert["certificate_hash"] = "tampered_hash_here"
    verify_res_bad = await client.post(
        "/v1/recovery/verify",
        json={"certificate": cert}
    )
    assert verify_res_bad.status_code == 400
    assert "Signature verification failed" in verify_res_bad.json()["detail"]
