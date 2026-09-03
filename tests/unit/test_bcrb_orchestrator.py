import uuid
import pytest
from packages.bcrb.src.orchestrator import BCRBOrchestrator
from packages.contracts.src.bcrb_models import BCRBSession, StoppingCondition, DiagnosisOutcome
from packages.contracts.src.agent_models import AgentInvocation, AgentIdentity
from packages.contracts.src.models import _utcnow
from packages.diagnosis.src.engine import DiagnosisEngine

def create_mock_invocations(tenant_id, run_id, count=3):
    invocations = []
    names = ["orchestrator", "retrieval", "reasoning"]
    for i in range(count):
        role = names[i % len(names)]
        inv = AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(tenant_id),
            agent_identity=AgentIdentity(agent_id=f"{role}-id", agent_type=role, agent_version="v1"),
            start_time=_utcnow(),
            end_time=_utcnow(),
            metadata={"is_error": False}
        )
        invocations.append(inv)
    return invocations

def test_sequential_execution_and_budget_exhaustion():
    tenant_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    orchestrator = BCRBOrchestrator(tenant_id)
    
    # Intentionally low budget to test budget exhaustion
    session = BCRBSession(
        run_id=uuid.UUID(run_id),
        tenant_id=uuid.UUID(tenant_id),
        budget_usd=0.06
    )
    
    invocations = create_mock_invocations(tenant_id, run_id)
    invocations[-1].metadata["is_error"] = True
    
    # Monkey-patch canary executor to return medium reliability so we don't hit confidence
    original_canary = orchestrator.test_framework.execute_canary
    
    def mock_execute(*args, **kwargs):
        step = original_canary(*args, **kwargs)
        if step.recovery_effect:
            step.recovery_effect.reliability_delta = 0.2
        return step
        
    orchestrator.test_framework.execute_canary = mock_execute

    # Execute
    result_session = orchestrator.execute_session(session, invocations, "test symptom")
    
    # Verify budget exhaustion
    assert result_session.stopping_condition_met == StoppingCondition.BUDGET_EXHAUSTED
    assert len(result_session.steps) >= 1
    assert result_session.total_spent_usd > 0
    assert result_session.total_spent_usd <= 0.06 + 0.06 # allowed to exceed slightly by actual cost but stops further

def test_bayesian_posterior_update():
    tenant_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    orchestrator = BCRBOrchestrator(tenant_id)
    
    session = BCRBSession(
        run_id=uuid.UUID(run_id),
        tenant_id=uuid.UUID(tenant_id),
        budget_usd=10.0
    )
    
    invocations = create_mock_invocations(tenant_id, run_id)
    invocations[-1].metadata["is_error"] = True
    
    # Monkey-patch canary executor to return high reliability
    import random
    original_canary = orchestrator.test_framework.execute_canary
    
    def mock_execute(*args, **kwargs):
        step = original_canary(*args, **kwargs)
        if step.recovery_effect:
            step.recovery_effect.reliability_delta = 0.9 # High improvement
        # Force clean
        step.decision_reason = "clean"
        return step
        
    orchestrator.test_framework.execute_canary = mock_execute
    
    result_session = orchestrator.execute_session(session, invocations, "test symptom")
    
    # Assert stopping condition
    assert result_session.stopping_condition_met == StoppingCondition.CONFIDENCE_REACHED
    
    # Assert posterior was updated
    tested_cand = next(c for c in result_session.candidates if c.candidate_id == result_session.steps[-1].candidate_id)
    assert tested_cand.causal_evidence.posterior is not None
    assert tested_cand.causal_evidence.posterior >= 0.9

def test_diagnosis_engine_unknown():
    tenant_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    engine = DiagnosisEngine(tenant_id)
    
    # Mocking steps and candidates without high posterior
    from packages.contracts.src.bcrb_models import BCRBStep, BCRBStepStatus, BCRBCandidate, ComponentType, InterventionType
    
    cand = BCRBCandidate(
        component_type=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ALTERNATE_STABLE
    )
    cand.causal_evidence.posterior = 0.6 # Low confidence
    
    step = BCRBStep(
        session_id=uuid.uuid4(),
        candidate_id=cand.candidate_id,
        status=BCRBStepStatus.COMPLETED
    )
    
    diagnosis = engine.generate_diagnosis(run_id, [step], [cand])
    
    assert diagnosis.root_cause_component is None
    assert "UNKNOWN" in diagnosis.claims[-1].description
    
def test_diagnosis_engine_supported():
    tenant_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    engine = DiagnosisEngine(tenant_id)
    
    # Mocking steps and candidates with high posterior
    from packages.contracts.src.bcrb_models import BCRBStep, BCRBStepStatus, BCRBCandidate, ComponentType, InterventionType, RecoveryEffect
    
    cand = BCRBCandidate(
        component_type=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ALTERNATE_STABLE
    )
    cand.causal_evidence.posterior = 0.95 # High confidence
    
    step = BCRBStep(
        session_id=uuid.uuid4(),
        candidate_id=cand.candidate_id,
        status=BCRBStepStatus.COMPLETED,
        recovery_effect=RecoveryEffect(reliability_delta=0.8)
    )
    
    diagnosis = engine.generate_diagnosis(run_id, [step], [cand])
    
    assert diagnosis.root_cause_component == ComponentType.RETRIEVER
    assert diagnosis.claims[-1].confidence == 0.95
    assert "Bayesian posterior" in diagnosis.root_cause_description
