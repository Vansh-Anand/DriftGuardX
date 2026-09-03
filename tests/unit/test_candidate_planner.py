import uuid

from packages.bcrb.src.candidate_planner import CandidatePlanner
from packages.contracts.src.agent_models import AgentInvocation
from packages.contracts.src.models import InterventionType, _utcnow


def test_candidate_planner_generation():
    planner = CandidatePlanner(tenant_id=str(uuid.uuid4()))
    run_id = str(uuid.uuid4())

    # Mock invocation history
    invocations = [
        AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(planner.tenant_id),
            agent_name="orchestrator",
            start_time=_utcnow(),
            end_time=_utcnow(),
        ),
        AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(planner.tenant_id),
            agent_name="retrieval",
            start_time=_utcnow(),
            end_time=_utcnow(),
        ),
        AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(planner.tenant_id),
            agent_name="policy",
            start_time=_utcnow(),
            end_time=_utcnow(),
        ),
    ]

    # Test generation for policy denial
    candidates = planner.generate_candidates(invocations, run_id, "policy_denial")

    assert len(candidates) >= 2

    # We expect a rollback for retrieval and config patch for policy
    intervention_types = {c.intervention_type for c in candidates}
    assert InterventionType.ROLLBACK in intervention_types
    assert InterventionType.CONFIG_PATCH in intervention_types
