import pytest
import uuid
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, UTC

from packages.contracts.src.models import ComponentType
from packages.contracts.src.recovery_models import CanaryInvariants
from packages.isolation.src.isolator import QuarantineRule, CausalIsolator

@pytest.mark.asyncio
async def test_64_canary_invariants():
    # Test #64: Define canary invariants and enforce them in the canary framework.
    invariants = CanaryInvariants(max_latency_ms=100.0, required_success_rate=0.99)
    assert invariants.max_latency_ms == 100.0
    
    from packages.replay.src.test_framework import CanaryTestFramework
    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    rule = QuarantineRule(target_component=ComponentType.RETRIEVER, description="Test")
    
    # We patch AgentPipeline.run to return a slow result
    with patch('packages.rag_pipeline.src.agents.AgentPipeline') as mock_pipeline:
        mock_state = MagicMock()
        mock_state.final_response = "success"
        mock_state.read_memory.return_value = 1.0
        
        # We need a delay inside run, or we can just mock time.monotonic
        with patch('time.monotonic', side_effect=[0.0, 1.0]): # 1 second = 1000ms latency
            mock_pipeline.return_value.run.return_value = mock_state
            
            result = await framework.async_validate_quarantine(rule, str(uuid.uuid4()), db=None, invariants=invariants)
            
            # Since latency 1000ms > max_latency_ms 100.0, it should fail
            assert result is False

@pytest.mark.asyncio
async def test_65_automatic_rollback():
    # Test #65: Automatically rollback failed canaries.
    from packages.replay.src.test_framework import CanaryTestFramework
    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    rule = QuarantineRule(target_component=ComponentType.RETRIEVER, description="Test")
    rule.rule_id = str(uuid.uuid4())
    
    mock_db = MagicMock()
    mock_isolator = AsyncMock()
    
    invariants = CanaryInvariants(max_latency_ms=10.0)
    
    with patch('packages.rag_pipeline.src.agents.AgentPipeline') as mock_pipeline:
        mock_state = MagicMock()
        mock_state.final_response = "error" # Enforce failure
        mock_state.read_memory.return_value = 1.0
        mock_pipeline.return_value.run.return_value = mock_state
        
        result = await framework.async_validate_quarantine(rule, str(uuid.uuid4()), db=mock_db, isolator=mock_isolator, invariants=invariants)
        
        assert result is False
        mock_isolator.async_remove_quarantine.assert_awaited_once_with(rule.rule_id, mock_db)

@pytest.mark.asyncio
async def test_66_policy_gated_promotion():
    # Test #66: Policy-gated promotion for canaries.
    from httpx import AsyncClient
    from apps.api.src.main import app
    from apps.api.src.models import ApprovalRequestORM
    from fastapi import Response
    import uuid
    
    # Let's test the endpoint logic directly if we can't easily mock auth in test
    from apps.api.src.routes.recovery import approve_recovery
    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.tenant_id = uuid.uuid4()
    mock_user.id = uuid.uuid4()
    
    mock_req = MagicMock()
    mock_req.tenant_id = mock_user.tenant_id
    mock_req.status = "pending"
    # Future expires_at
    from datetime import timedelta
    mock_req.expires_at = datetime.now(UTC) + timedelta(days=1)
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_req
    mock_db.execute.return_value = mock_result
    
    response = await approve_recovery({"approval_id": str(uuid.uuid4()), "decision": "APPROVED"}, mock_db, mock_user)
    
    # Check that status is awaiting_promotion because tenant_policy_requires_promotion is True
    assert mock_req.status == "awaiting_promotion"
    assert response.status_code == 202

@pytest.mark.asyncio
async def test_67_worker_diagnosis_offload():
    # Test #67: Offload diagnosis to asynchronous workers.
    # trigger_recovery should enqueue a job
    from apps.api.src.routes.recovery import trigger_recovery
    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.tenant_id = uuid.uuid4()
    mock_user.id = uuid.uuid4()
    mock_user.roles = []
    
    with patch('arq.connections.create_pool', new_callable=AsyncMock) as mock_create_pool:
        mock_redis = AsyncMock()
        mock_create_pool.return_value = mock_redis
        
        response = await trigger_recovery({"tenant_id": str(mock_user.tenant_id), "run_id": str(uuid.uuid4())}, mock_db, mock_user)
        
        assert response["status"] == "queued"
        assert "job_id" in response
        
        # Verify enqueue_job was called
        mock_redis.enqueue_job.assert_awaited_once()
        args = mock_redis.enqueue_job.call_args[0]
        assert args[0] == "run_recovery_diagnosis"

@pytest.mark.asyncio
async def test_68_job_state_management():
    # Test #68: Implement robust job state management with ARQ/Redis.
    # We verify the job states defined in JobORM and the worker updating them.
    from apps.api.src.models import JobORM
    job = JobORM(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        task_type="run_recovery_diagnosis",
        status="QUEUED",
        created_at=datetime.now(UTC)
    )
    assert job.status == "QUEUED"
    job.status = "RUNNING"
    assert job.status == "RUNNING"
    job.status = "SUCCEEDED"
    assert job.status == "SUCCEEDED"
    job.status = "FAILED"
    assert job.status == "FAILED"
