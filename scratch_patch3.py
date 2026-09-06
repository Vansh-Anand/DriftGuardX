with open('tests/integration/test_security_audit.py') as f:
    code = f.read()

mock_code = """
    from apps.api.src.models import ApprovalRequestORM
    from packages.contracts.src.bcrb_models import EvidenceClassification
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
                "evidence_kind": EvidenceClassification.SYNTHETIC_SIMULATION.value,
                "cert_hash": "dummy_hash"
            }
        )
        db.add(req)
        await db.flush()
        return req

    monkeypatch.setattr("apps.api.src.services.recovery_pipeline.EndToEndRecoveryPipeline.execute_recovery_loop", mock_execute_recovery_loop)

    response = await client.post(
"""

code = code.replace('    response = await client.post(\n', mock_code)

with open('tests/integration/test_security_audit.py', 'w') as f:
    f.write(code)
