import pytest
from uuid import uuid4

from packages.contracts.src.planner import (
    RootCauseBeliefModel, 
    StoppingPolicy, 
    StoppingReason,
    DiagnosticOutcome,
    SafetyRisk
)
from packages.contracts.src.models import ExecutionBudget
from packages.replay.src.sequential_planner import RiskLimitedSequentialPlanner
from packages.contracts.src.envelope import CausalIntervention, CausalInterventionType, ReplayEquivalenceEnvelope
from packages.contracts.src.planner import CausalExperimentCandidate

def create_candidate(ig=0.1, safety=SafetyRisk.NO_SIDE_EFFECT, cost=0.0, component_id="retriever_123"):
    intervention = CausalIntervention(
        component_id=component_id,
        variable_key="version",
        original_value_hash="1" * 64,
        replacement_value_hash="2" * 64,
        intervention_type=CausalInterventionType.ROLLBACK_VERSION,
        reason="test"
    )
    envelope = ReplayEquivalenceEnvelope(
        envelope_id=uuid4(),
        original_trace_id=uuid4(),
        replay_id=uuid4(),
        tenant_id=uuid4(),
        intervention=intervention,
        original_state_hash="3" * 64,
        policy_version="1.0",
        frozen_variables=[],
        intervened_variables=["x"],
        exogenous_variables=[],
        allowed_descendant_components=[],
        forbidden_divergence_components=[]
    )
    return CausalExperimentCandidate(
        intervention=intervention,
        envelope=envelope,
        estimated_information_gain=ig,
        replay_validity_probability=1.0,
        execution_cost_estimate=cost,
        execution_cost_uncertainty=0.0,
        expected_duration=cost,
        safety_risk=safety,
        expected_blast_radius=0.0,
        evidence_quality=1.0
    )


def test_high_posterior_but_high_next_ig():
    # Posterior is high enough, margin is high enough, but next IG is too high -> continue
    beliefs = RootCauseBeliefModel(priors={"A": 0.85, "B": 0.15})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    candidates = [create_candidate(ig=0.5)] # Next IG is 0.5 > max_next_ig (0.1)
    
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is False
    assert decision.reason is None


def test_high_posterior_and_low_next_ig():
    # Posterior > 0.8, Margin > 0.2, Next IG < 0.1 -> Stop (POSTERIOR_CONFIDENCE)
    beliefs = RootCauseBeliefModel(priors={"A": 0.85, "B": 0.15})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    candidates = [create_candidate(ig=0.05)] # Next IG is 0.05 < max_next_ig (0.1)
    
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is True
    assert decision.reason == StoppingReason.POSTERIOR_CONFIDENCE
    assert decision.outcome == DiagnosticOutcome.DIAGNOSIS_CONFIRMED


def test_low_posterior_continue():
    beliefs = RootCauseBeliefModel(priors={"A": 0.5, "B": 0.5})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    candidates = [create_candidate(ig=0.05)]
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is False


def test_no_admissible_experiment():
    beliefs = RootCauseBeliefModel(priors={"A": 0.5, "B": 0.5})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    # Unsafe candidate (IRREVERSIBLE)
    candidates = [create_candidate(safety=SafetyRisk.IRREVERSIBLE_EXTERNAL_CHANGE)]
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is True
    assert decision.reason == StoppingReason.NO_ADMISSIBLE_EXPERIMENT
    assert decision.outcome == DiagnosticOutcome.DIAGNOSIS_UNRESOLVED


def test_resource_exhaustion_via_admissibility():
    beliefs = RootCauseBeliefModel(priors={"A": 0.5, "B": 0.5})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=10.0))
    
    # Candidate costs 20.0, budget is 10.0 -> no admissible experiment -> Stop
    candidates = [create_candidate(cost=20.0)]
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is True
    assert decision.reason == StoppingReason.NO_ADMISSIBLE_EXPERIMENT
    assert decision.outcome == DiagnosticOutcome.DIAGNOSIS_UNRESOLVED


def test_entropy_plateau_convergence():
    beliefs = RootCauseBeliefModel(priors={"A": 0.6, "B": 0.4})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    # Force entropy history to have converged (deltas < 0.05)
    planner.entropy_history = [1.0, 0.99, 0.98, 0.97]
    
    candidates = [create_candidate(ig=0.5)] # Admissible, valid IG
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is True
    assert decision.reason == StoppingReason.CONVERGED
    assert decision.outcome == DiagnosticOutcome.DIAGNOSIS_TENTATIVE


def test_valid_evidence_counting():
    beliefs = RootCauseBeliefModel(priors={"A": 0.85, "B": 0.15})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    candidates = [create_candidate(ig=0.05)]
    
    # Only 1 valid replay, min required is 2 -> Don't stop yet
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=1)
    
    assert decision.stop is False


def test_posterior_tie_handling():
    # Tie, margin is 0
    beliefs = RootCauseBeliefModel(priors={"A": 0.5, "B": 0.5})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    candidates = [create_candidate(ig=0.05)]
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is False
    assert decision.posterior_margin == 0.0


def test_low_expected_diagnostic_value():
    beliefs = RootCauseBeliefModel(priors={"A": 0.5, "B": 0.5})
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    # IG is very low, Cost is very high -> Utility < 0
    candidates = [create_candidate(ig=0.0, cost=50.0)]
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is True
    assert decision.reason == StoppingReason.LOW_EXPECTED_DIAGNOSTIC_VALUE
    assert decision.outcome == DiagnosticOutcome.DIAGNOSIS_UNRESOLVED


def test_heuristic_vs_calibrated_metadata():
    beliefs = RootCauseBeliefModel(priors={"A": 0.85, "B": 0.15}, is_calibrated=True)
    planner = RiskLimitedSequentialPlanner(uuid4(), beliefs, ExecutionBudget(wall_clock_time_s=100.0))
    
    candidates = [create_candidate(ig=0.05)]
    decision = planner.evaluate_stopping_rule(candidates, valid_replay_count=3)
    
    assert decision.stop is True
    assert decision.confidence_metadata["is_calibrated"] is True
