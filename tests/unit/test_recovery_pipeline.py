import uuid
from datetime import datetime, timezone
from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
from packages.contracts.src.agent_models import AgentInvocation

def test_end_to_end_recovery_pipeline():
    tenant_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    pipeline = EndToEndRecoveryPipeline(tenant_id=tenant_id)
    
    # Mock invocations
    invocations = [
        AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(tenant_id),
            agent_name="retrieval",
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        ),
    ]
    
    # Execute
    certificate = pipeline.execute_recovery_loop(
        run_id=run_id, 
        invocations=invocations, 
        failure_symptom="stale_context"
    )
    
    # Validate
    assert certificate is not None
    assert certificate.run_id == uuid.UUID(run_id)
    assert certificate.tenant_id == uuid.UUID(tenant_id)
    assert certificate.is_valid is True
    assert "retriever" in certificate.payload_summary
