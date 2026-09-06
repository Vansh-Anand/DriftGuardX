import uuid
from unittest.mock import MagicMock, patch

import pytest

from apps.api.src.models import QuarantineRuleORM
from apps.api.src.services.recovery_pipeline import EndToEndRecoveryPipeline
from packages.contracts.src.models import ComponentType
from packages.isolation.src.isolator import CausalIsolator
from packages.rag_pipeline.src.agents import AgentPipeline


@pytest.mark.asyncio
async def test_61_durable_quarantine(db_session):
    # Test #61: Quarantine is durable
    tenant_id = str(uuid.uuid4())
    isolator = CausalIsolator(tenant_id)

    await isolator.async_apply_quarantine(
        root_cause_component=ComponentType.RETRIEVER, description="Data drift", db=db_session
    )

    # Verify it was persisted
    from sqlalchemy import select

    result = await db_session.execute(
        select(QuarantineRuleORM).where(QuarantineRuleORM.tenant_id == uuid.UUID(tenant_id))
    )
    persisted_rules = result.scalars().all()
    assert len(persisted_rules) == 1
    assert persisted_rules[0].target_component == "retriever"

    quarantined_agents = await isolator.async_get_quarantined_agents(db=db_session)
    assert "retriever" in quarantined_agents


def test_62_fallback_routing():
    # Test #62: Fallback routing
    pipeline = AgentPipeline()
    quarantined = {"retrieval"}
    state = pipeline.run(
        "test query", str(uuid.uuid4()), str(uuid.uuid4()), quarantined_agents=quarantined
    )

    # Should have bypassed retrieval and gone to fallback, eventually hitting response
    assert state.is_finished
    # The output from standard flow if retrieval is skipped and fallback is hit
    assert state.read_memory("reasoning") == "Fallback triggered. Using general knowledge."


@pytest.mark.asyncio
async def test_63_canary_validation():
    # Test #63: Canary mechanism
    from packages.isolation.src.isolator import QuarantineRule
    from packages.replay.src.test_framework import CanaryTestFramework

    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    rule = QuarantineRule(target_component=ComponentType.RETRIEVER, description="Test")

    # Since it falls back safely, canary should pass
    assert await framework.async_validate_quarantine(rule, str(uuid.uuid4()), db=None)


@pytest.mark.asyncio
async def test_59_safety_gate():
    # Test #59: No auto-repair from synthetic evidence
    pipeline = EndToEndRecoveryPipeline(tenant_id=str(uuid.uuid4()))
    pipeline._force_automated = True  # Simulate an automated pipeline path

    # Mock BCRB and Diagnosis to return valid data
    pipeline.engine = MagicMock()
    pipeline.engine.generate_diagnosis.return_value.root_cause_component = ComponentType.RETRIEVER
    pipeline.engine.generate_diagnosis.return_value.root_cause_description = "Test drift"

    pipeline.canary_framework = MagicMock()
    from unittest.mock import AsyncMock

    pipeline.canary_framework.async_validate_quarantine = AsyncMock(return_value=True)

    class MockCandidate:
        pass

    class MockStep:
        utility_observed = 1.0
        replay_episode_id = uuid.uuid4()

    # We must patch BCRBOrchestrator
    with patch("packages.bcrb.src.orchestrator.BCRBOrchestrator") as mock_bcrb:
        mock_session = MagicMock()
        mock_session.candidates = [MockCandidate()]
        mock_session.steps = [MockStep()]

        async def mock_execute(*args, **kwargs):
            return mock_session

        mock_bcrb.return_value.execute_session = mock_execute

        # We mock BCRB and Canary to succeed and see if the gate blocks it
        from datetime import UTC, datetime

        from packages.contracts.src.agent_models import AgentInvocation

        invocations = [
            AgentInvocation(
                invocation_id=uuid.uuid4(),
                run_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                agent_name="retrieval",
                start_time=datetime.now(UTC),
                end_time=datetime.now(UTC),
            )
        ]

        with pytest.raises(
            RuntimeError,
            match="Safety violation: cannot automatically repair from synthetic evidence",
        ):
            await pipeline.execute_recovery_loop(str(uuid.uuid4()), invocations, "drift")
