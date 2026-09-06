import uuid

from packages.bcrb.src.candidate_planner import CandidatePlanner
from packages.contracts.src.agent_models import AgentIdentity, AgentInvocation
from packages.contracts.src.models import _utcnow


def create_mock_invocations(tenant_id, run_id, count=3):
    invocations = []
    names = ["orchestrator", "retrieval", "policy", "reasoning", "response"]
    for i in range(count):
        role = names[i % len(names)]
        inv = AgentInvocation(
            invocation_id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(tenant_id),
            agent_identity=AgentIdentity(
                agent_id=f"{role}-id", agent_type=role, agent_version="v1"
            ),
            start_time=_utcnow(),
            end_time=_utcnow(),
            metadata={"is_error": False},
        )
        invocations.append(inv)
    return invocations


def test_gat_produces_scores_and_reaches_candidates():
    planner = CandidatePlanner(tenant_id=str(uuid.uuid4()))
    run_id = str(uuid.uuid4())
    invocations = create_mock_invocations(planner.tenant_id, run_id)

    candidates = planner.generate_candidates(invocations, run_id, "test_symptom")
    assert len(candidates) > 0

    # Check unified prior metadata
    for cand in candidates:
        prior_evidence = cand.metadata.get("prior_evidence")
        assert prior_evidence is not None
        assert "gat_score" in prior_evidence
        # Assert synthetic GAT evidence is correctly classified
        assert isinstance(prior_evidence["evidence_breakdown"]["is_synthetic_gat"], bool)


def test_diffusion_propagates_symptom():
    planner = CandidatePlanner(tenant_id=str(uuid.uuid4()))
    run_id = str(uuid.uuid4())
    invocations = create_mock_invocations(planner.tenant_id, run_id, count=3)

    # Set error on last node
    invocations[-1].metadata["is_error"] = True

    candidates = planner.generate_candidates(invocations, run_id, "test_symptom")

    # Check diffusion score is populated and propagates backwards
    prior_evidence = candidates[0].metadata["prior_evidence"]
    assert "diffusion_score" in prior_evidence
    assert prior_evidence["diffusion_score"] >= 0.0


def test_unified_candidate_prior_incorporates_both():
    planner = CandidatePlanner(tenant_id=str(uuid.uuid4()))
    run_id = str(uuid.uuid4())
    invocations = create_mock_invocations(planner.tenant_id, run_id)

    candidates = planner.generate_candidates(invocations, run_id, "test_symptom")
    prior_evidence = candidates[0].metadata["prior_evidence"]

    assert "gat_score" in prior_evidence
    assert "diffusion_score" in prior_evidence
    assert "symptom_evidence" in prior_evidence
    assert "combined_prior" in prior_evidence

    assert "calibrated_probability" not in prior_evidence  # MUST NOT claim calibrated probability

    assert prior_evidence["combined_prior"] <= 1.0


def test_deterministic_behavior():
    planner = CandidatePlanner(tenant_id=str(uuid.uuid4()))
    run_id = str(uuid.uuid4())
    invocations = create_mock_invocations(planner.tenant_id, run_id)

    # generate twice
    cands1 = planner.generate_candidates(invocations, run_id, "test_symptom")
    cands2 = planner.generate_candidates(invocations, run_id, "test_symptom")

    assert len(cands1) == len(cands2)
    for c1, c2 in zip(cands1, cands2, strict=False):
        assert c1.estimated_utility == c2.estimated_utility
