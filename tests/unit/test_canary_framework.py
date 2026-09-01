import uuid
from packages.replay.src.test_framework import CanaryTestFramework
from packages.isolation.src.isolator import QuarantineRule
from packages.contracts.src.models import ComponentType, InterventionType
from packages.contracts.src.bcrb_models import BCRBCandidate, BCRBStepStatus

def test_canary_execution():
    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    original_run = str(uuid.uuid4())
    
    candidate = BCRBCandidate(
        candidate_id=uuid.uuid4(),
        component_type=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ROLLBACK,
        cost_estimate=0.02
    )
    
    step = framework.execute_canary(candidate, original_run)
    assert step.candidate_id == candidate.candidate_id
    assert step.status == BCRBStepStatus.COMPLETED
    assert step.utility_observed == 0.95
    assert step.cost_incurred == 0.02

def test_quarantine_validation():
    framework = CanaryTestFramework(tenant_id=str(uuid.uuid4()))
    original_run = str(uuid.uuid4())
    
    rule1 = QuarantineRule(target_component=ComponentType.RETRIEVER, description="test")
    rule2 = QuarantineRule(target_component=ComponentType.AGENT, description="test")
    
    assert framework.validate_quarantine(rule1, original_run) is True
    assert framework.validate_quarantine(rule2, original_run) is False
