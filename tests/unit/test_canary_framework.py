import uuid

from packages.contracts.src.bcrb_models import BCRBCandidate, BCRBStepStatus
from packages.contracts.src.models import ComponentType, InterventionType
from packages.isolation.src.isolator import QuarantineRule
from packages.replay.src.test_framework import CanaryTestFramework


def test_canary_execution():
    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    original_run = str(uuid.uuid4())

    from packages.contracts.src.bcrb_models import ReplayCost
    candidate = BCRBCandidate(
        candidate_id=uuid.uuid4(),
        component_type=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ROLLBACK,
        cost_estimate=ReplayCost(total_cost=0.02),
    )

    import asyncio
    step = asyncio.run(framework.execute_canary(candidate, original_run, str(uuid.uuid4()), None))
    assert step.candidate_id == candidate.candidate_id
    assert step.status == BCRBStepStatus.FAILED
    assert "No DB provided" in step.decision_reason
    # The test framework explicitly does not fake utility to prevent leaking synthetic evidence
    assert step.utility_observed is None


def test_quarantine_validation():
    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    original_run = str(uuid.uuid4())

    rule1 = QuarantineRule(target_component=ComponentType.RETRIEVER, description="test")
    rule2 = QuarantineRule(target_component=ComponentType.AGENT, description="test")

    import pytest
    with pytest.raises(NotImplementedError, match="Fabricating quarantine confirmation is forbidden"):
        framework.validate_quarantine(rule1, original_run)
