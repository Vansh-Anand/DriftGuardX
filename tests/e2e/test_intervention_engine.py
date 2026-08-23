from uuid import UUID

import pytest

from packages.contracts.src.models import (
    ComponentType,
    Diagnosis,
    DiagnosisClaim,
    DiagnosisClaimStatus,
    ReplayEpisode,
    ReplayStatus,
)
from packages.evaluation.src.pareto import ParetoScorer
from packages.replay.src.candidates import CandidateGenerator
from packages.replay.src.planner import ReplayPlanner


def test_candidate_generation():
    diag = Diagnosis(
        run_id=UUID(int=99),
        tenant_id=UUID(int=1),
        root_cause_component=ComponentType.RETRIEVER,
        claims=[
            DiagnosisClaim(
                claim_id="1",
                description="Retriever failure",
                status=DiagnosisClaimStatus.INFERRED
            )
        ]
    )

    candidates = CandidateGenerator.generate(diag)

    assert len(candidates) > 0
    assert candidates[0].target_component_type == ComponentType.RETRIEVER
    assert candidates[0].requires_human_approval is not None

@pytest.mark.asyncio
async def test_replay_planner_concurrency_and_timeout():
    planner = ReplayPlanner(max_concurrency=2, timeout_sec=1)

    # Generate mock candidates
    diag = Diagnosis(
        run_id=UUID(int=99),
        tenant_id=UUID(int=1),
        root_cause_component=ComponentType.GENERATOR,
        claims=[]
    )
    candidates = CandidateGenerator.generate(diag)
    print(f"Candidates generated: {len(candidates)}")

    # Execute exhaustive
    episodes = await planner.execute_exhaustive(candidates)
    print(f"Episodes returned: {episodes}")

    assert len(episodes) > 0
    for ep in episodes:
        assert isinstance(ep, ReplayEpisode)

def test_pareto_scorer():
    ep1 = ReplayEpisode(
        tenant_id=UUID(int=1),
        run_id=UUID(int=99),
        status=ReplayStatus.COMPLETED,
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=UUID(int=0),
        replay_version_id=UUID(int=1),
        original_version_tag="v1",
        replay_version_tag="v2",
        replay_reliability_score=0.90 # Best score
    )

    ep2 = ReplayEpisode(
        tenant_id=UUID(int=1),
        run_id=UUID(int=99),
        status=ReplayStatus.COMPLETED,
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=UUID(int=0),
        replay_version_id=UUID(int=2),
        original_version_tag="v1",
        replay_version_tag="v3",
        replay_reliability_score=0.80 # Dominated by ep1
    )

    ep_invalid = ReplayEpisode(
        tenant_id=UUID(int=1),
        run_id=UUID(int=99),
        status=ReplayStatus.INVALID,
        invalid_reason="Missing",
        swapped_component_type=ComponentType.RETRIEVER,
        original_version_id=UUID(int=0),
        replay_version_id=UUID(int=3),
        original_version_tag="v1",
        replay_version_tag="v4"
    )

    scorer = ParetoScorer()
    result = scorer.score([ep1, ep2, ep_invalid])

    assert len(result.optimal_episodes) == 1
    assert result.optimal_episodes[0].replay_version_tag == "v2"

    assert len(result.dominated_episodes) == 1
    assert result.dominated_episodes[0].replay_version_tag == "v3"
    assert result.dominated_episodes[0].status == ReplayStatus.NEGATIVE_OUTCOME

    assert len(result.invalid_episodes) == 1
    assert result.invalid_episodes[0].invalid_reason == "Missing"
