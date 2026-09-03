import uuid

from packages.contracts.src.bcrb_models import BCRBCandidate, BCRBStep, BCRBStepStatus
from packages.contracts.src.models import ComponentType, DiagnosisClaimStatus, InterventionType
from packages.diagnosis.src.engine import DiagnosisEngine


def test_diagnosis_engine_generation():
    engine = DiagnosisEngine(tenant_id=str(uuid.uuid4()))
    run_id = str(uuid.uuid4())

    # Create candidates
    c1 = BCRBCandidate(
        candidate_id=uuid.uuid4(),
        component_type=ComponentType.RETRIEVER,
        intervention_type=InterventionType.ROLLBACK,
        cost_estimate=0.01,
        metadata={"rationale": "Retriever suspected"},
    )
    c2 = BCRBCandidate(
        candidate_id=uuid.uuid4(),
        component_type=ComponentType.POLICY_CHECK,
        intervention_type=InterventionType.CONFIG_PATCH,
        cost_estimate=0.001,
        metadata={"rationale": "Policy constraint patch"},
    )
    candidates = [c1, c2]

    # Create evaluated steps
    steps = [
        BCRBStep(
            step_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            candidate_id=c1.candidate_id,
            status=BCRBStepStatus.COMPLETED,
            replay_episode_id=uuid.uuid4(),
            utility_observed=0.92,
            cost_incurred=0.01,
        ),
        BCRBStep(
            step_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            candidate_id=c2.candidate_id,
            status=BCRBStepStatus.COMPLETED,
            replay_episode_id=uuid.uuid4(),
            utility_observed=0.45,
            cost_incurred=0.001,
        ),
    ]

    diagnosis = engine.generate_diagnosis(run_id, steps, candidates)

    assert diagnosis.root_cause_component == ComponentType.RETRIEVER
    assert "restored reliability" in diagnosis.root_cause_description
    assert len(diagnosis.claims) == 1
    assert diagnosis.claims[0].status == DiagnosisClaimStatus.MEASURED
    assert diagnosis.claims[0].confidence == 0.92
