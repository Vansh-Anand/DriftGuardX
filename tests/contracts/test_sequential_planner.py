"""
DriftGuard-X v2 — Tests for Sequential Planner
PRIVATE — All Rights Reserved.
"""

import pytest
import math
from uuid import uuid4

from packages.contracts.src.planner import (
    SafetyRisk, 
    RootCauseBeliefModel, 
    CausalExperimentCandidate, 
    ExperimentPlannerState
)
from packages.contracts.src.models import ExecutionBudget, ComponentType, _new_uuid
from packages.contracts.src.envelope import CausalIntervention, CausalInterventionType, ReplayEquivalenceEnvelope
from packages.replay.src.sequential_planner import RiskLimitedSequentialPlanner


@pytest.fixture
def mock_beliefs():
    return RootCauseBeliefModel(
        priors={
            "retriever": 0.5,
            "generator": 0.5
        },
        is_calibrated=True
    )

@pytest.fixture
def mock_budget():
    return ExecutionBudget(wall_clock_time_s=100.0, used_wall_clock_s=0.0)


@pytest.fixture
def base_intervention():
    return CausalIntervention(
        component_id="retriever_123",
        variable_key="version",
        original_value_hash="1" * 64,
        replacement_value_hash="2" * 64,
        intervention_type=CausalInterventionType.ROLLBACK_VERSION,
        reason="test"
    )

@pytest.fixture
def base_envelope(base_intervention):
    return ReplayEquivalenceEnvelope(
        envelope_id=uuid4(),
        original_trace_id=uuid4(),
        replay_id=uuid4(),
        tenant_id=uuid4(),
        intervention=base_intervention,
        original_state_hash="3" * 64,
        policy_version="1.0",
        frozen_variables=[],
        intervened_variables=["x"],
        exogenous_variables=[],
        allowed_descendant_components=[],
        forbidden_divergence_components=[]
    )


def test_admissibility_filter_rejects_unsafe(mock_beliefs, mock_budget, base_intervention, base_envelope):
    planner = RiskLimitedSequentialPlanner(
        incident_id=uuid4(),
        initial_beliefs=mock_beliefs,
        budget=mock_budget
    )
    
    safe_candidate = CausalExperimentCandidate(
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=1.0,
        replay_validity_probability=1.0,
        execution_cost_estimate=10.0,
        execution_cost_uncertainty=2.0,
        safety_risk=SafetyRisk.NO_SIDE_EFFECT,
        expected_blast_radius=0.0,
        expected_duration=10.0,
        evidence_quality=1.0
    )
    
    unsafe_candidate = CausalExperimentCandidate(
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=1.0,
        replay_validity_probability=1.0,
        execution_cost_estimate=10.0,
        execution_cost_uncertainty=2.0,
        safety_risk=SafetyRisk.IRREVERSIBLE_EXTERNAL_CHANGE,
        expected_blast_radius=1.0,
        expected_duration=10.0,
        evidence_quality=1.0
    )
    
    admissible = planner.filter_admissible([safe_candidate, unsafe_candidate])
    assert len(admissible) == 1
    assert admissible[0].experiment_id == safe_candidate.experiment_id


def test_admissibility_filter_rejects_expensive(mock_beliefs, mock_budget, base_intervention, base_envelope):
    planner = RiskLimitedSequentialPlanner(
        incident_id=uuid4(),
        initial_beliefs=mock_beliefs,
        budget=mock_budget
    )
    
    expensive_candidate = CausalExperimentCandidate(
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=1.0,
        replay_validity_probability=1.0,
        execution_cost_estimate=95.0,
        execution_cost_uncertainty=10.0, # Total 105 > 100 budget
        safety_risk=SafetyRisk.NO_SIDE_EFFECT,
        expected_blast_radius=0.0,
        expected_duration=95.0,
        evidence_quality=1.0
    )
    
    admissible = planner.filter_admissible([expensive_candidate])
    assert len(admissible) == 0


def test_pareto_dominance(mock_beliefs, mock_budget, base_intervention, base_envelope):
    planner = RiskLimitedSequentialPlanner(
        incident_id=uuid4(),
        initial_beliefs=mock_beliefs,
        budget=mock_budget
    )
    
    # Candidate A is better than B in every way
    cand_a = CausalExperimentCandidate(
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=1.0,
        replay_validity_probability=1.0,
        execution_cost_estimate=10.0,
        execution_cost_uncertainty=0.0,
        safety_risk=SafetyRisk.NO_SIDE_EFFECT,
        expected_blast_radius=0.0,
        expected_duration=10.0,
        evidence_quality=1.0
    )
    
    cand_b = CausalExperimentCandidate(
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=0.5,  # Worse utility
        replay_validity_probability=1.0,
        execution_cost_estimate=20.0,    # Worse cost
        execution_cost_uncertainty=0.0,
        safety_risk=SafetyRisk.LOCAL_STATE_CHANGE, # Worse safety
        expected_blast_radius=0.0,
        expected_duration=20.0,
        evidence_quality=1.0
    )
    
    # Candidate C is a tradeoff (better cost than A, worse utility)
    cand_c = CausalExperimentCandidate(
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=0.2,
        replay_validity_probability=1.0,
        execution_cost_estimate=5.0,
        execution_cost_uncertainty=0.0,
        safety_risk=SafetyRisk.NO_SIDE_EFFECT,
        expected_blast_radius=0.0,
        expected_duration=5.0,
        evidence_quality=1.0
    )
    
    pareto_front = planner.apply_pareto_filter([cand_a, cand_b, cand_c])
    
    assert len(pareto_front) == 2
    ids = [c.experiment_id for c in pareto_front]
    assert cand_a.experiment_id in ids
    assert cand_c.experiment_id in ids
    assert cand_b.experiment_id not in ids # B is dominated by A


def test_atomic_resource_reservation(mock_beliefs, mock_budget, base_intervention, base_envelope):
    planner = RiskLimitedSequentialPlanner(
        incident_id=uuid4(),
        initial_beliefs=mock_beliefs,
        budget=mock_budget
    )
    
    candidate = CausalExperimentCandidate(
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=1.0,
        replay_validity_probability=1.0,
        execution_cost_estimate=30.0,
        execution_cost_uncertainty=0.0,
        safety_risk=SafetyRisk.NO_SIDE_EFFECT,
        expected_blast_radius=0.0,
        expected_duration=30.0,
        evidence_quality=1.0
    )
    
    # Reserve
    assert planner.reserve_resources(candidate) is True
    assert planner.budget.used_wall_clock_s == 30.0
    
    # Reconcile (actual cost was 20)
    planner.reconcile_resources(candidate, 20.0)
    assert planner.budget.used_wall_clock_s == 20.0
    
    # Release an unused reservation
    candidate2 = CausalExperimentCandidate(
        experiment_id=uuid4(),
        intervention=base_intervention,
        envelope=base_envelope,
        estimated_information_gain=1.0,
        replay_validity_probability=1.0,
        execution_cost_estimate=50.0,
        execution_cost_uncertainty=0.0,
        safety_risk=SafetyRisk.NO_SIDE_EFFECT,
        expected_blast_radius=0.0,
        expected_duration=50.0,
        evidence_quality=1.0
    )
    
    assert planner.reserve_resources(candidate2) is True
    assert planner.budget.used_wall_clock_s == 70.0
    
    planner.release_resources(candidate2)
    assert planner.budget.used_wall_clock_s == 20.0


def test_belief_update(mock_beliefs, mock_budget, base_intervention, base_envelope):
    planner = RiskLimitedSequentialPlanner(
        incident_id=uuid4(),
        initial_beliefs=mock_beliefs,
        budget=mock_budget
    )
    
    candidate = CausalExperimentCandidate(
        intervention=base_intervention, # target is RETRIEVER
        envelope=base_envelope,
        estimated_information_gain=1.0,
        replay_validity_probability=1.0,
        execution_cost_estimate=10.0,
        execution_cost_uncertainty=0.0,
        safety_risk=SafetyRisk.NO_SIDE_EFFECT,
        expected_blast_radius=0.0,
        expected_duration=10.0,
        evidence_quality=1.0
    )
    
    # Initial priors: retriever=0.5, generator=0.5
    # If recovery succeeds, retriever prior should increase
    planner.update_beliefs(candidate, "RECOVERY_SUCCESS")
    
    priors = planner.state.root_cause_beliefs.priors
    assert priors["retriever"] > priors["generator"]
    
    # Check normalization
    total = sum(priors.values())
    assert math.isclose(total, 1.0, rel_tol=1e-5)
    
    # Entropy should decrease (we are more certain)
    new_entropy = planner.state.current_entropy
    assert new_entropy < 1.0 # 1.0 is max entropy for 2 classes
