import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
from packages.contracts.src.agent_models import AgentInvocation

pytestmark = pytest.mark.asyncio

async def test_end_to_end_recovery_pipeline():
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
            start_time=datetime.now(UTC),
            end_time=datetime.now(UTC),
        ),
    ]

    # Execute with mocked successful canary
    with patch("apps.api.src.services.recovery_pipeline.CanaryTestFramework.execute_canary") as mock_exec, \
         patch("apps.api.src.services.recovery_pipeline.CanaryTestFramework.validate_quarantine", return_value=True):
        
        from packages.contracts.src.bcrb_models import BCRBStep, BCRBStepStatus
        def mock_execute_canary(candidate, run_id):
            return BCRBStep(
                step_id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                candidate_id=candidate.candidate_id,
                status=BCRBStepStatus.COMPLETED,
                replay_episode_id=uuid.uuid4(),
                utility_observed=0.95,
                cost_incurred=0.02
            )
        mock_exec.side_effect = mock_execute_canary

        certificate = await pipeline.execute_recovery_loop(
            run_id=run_id, invocations=invocations, failure_symptom="stale_context"
        )

    # Validate
    assert certificate is not None
    assert certificate.run_id == uuid.UUID(run_id)
    assert certificate.tenant_id == uuid.UUID(tenant_id)
    assert certificate.is_valid is True
    from packages.contracts.src.evidence import RecoveryEvidenceKind
    assert certificate.evidence_kind == RecoveryEvidenceKind.SYNTHETIC_SIMULATION
    assert "retriever" in certificate.payload_summary
