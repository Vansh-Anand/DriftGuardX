import math
import pytest
from packages.evaluation.src.bandit_baselines import CandidateArm
from packages.contracts.src.models import RAEBEvaluation, AdmissibilityScore, EquivalenceVector
from packages.replay.src.bandit import BCRBScheduler

def _create_eval(info: float, harm: float) -> RAEBEvaluation:
    return RAEBEvaluation(
        equivalence_vector=EquivalenceVector(freshness_score=1.0, determinism_score=1.0, dependency_impact_score=1.0),
        admissibility=AdmissibilityScore.ADMISSIBLE,
        information_gain_estimate=info,
        risk_score=harm
    )

def test_pareto_dominance_2d():
    scheduler = BCRBScheduler(total_budget=10.0)
    
    # 3 arms. Cost is identical, so only IG and Harm matter.
    # Maximize IG, Minimize Harm
    arms = [
        CandidateArm(arm_id="A", cost=1.0, prior=0.5), # info=10, harm=2 -> frontier
        CandidateArm(arm_id="B", cost=1.0, prior=0.5), # info=5, harm=1 -> frontier
        CandidateArm(arm_id="C", cost=1.0, prior=0.5), # info=5, harm=3 -> dominated by B
        CandidateArm(arm_id="D", cost=1.0, prior=0.5), # info=9, harm=2 -> dominated by A
    ]
    
    evals = {
        "A": _create_eval(10.0, 2.0),
        "B": _create_eval(5.0, 1.0),
        "C": _create_eval(5.0, 3.0),
        "D": _create_eval(9.0, 2.0),
    }
    
    pareto_set = scheduler.select_pareto_set(arms, evals)
    frontier_ids = {c.arm_id for c in pareto_set.candidates}
    
    assert frontier_ids == {"A", "B"}
    
def test_pareto_duplicates():
    scheduler = BCRBScheduler(total_budget=10.0)
    # E and F are identical in objectives. Tie-break should drop the one with higher arm_id.
    arms = [
        CandidateArm(arm_id="E", cost=1.0, prior=0.5),
        CandidateArm(arm_id="F", cost=1.0, prior=0.5)
    ]
    evals = {
        "E": _create_eval(10.0, 1.0),
        "F": _create_eval(10.0, 1.0)
    }
    pareto_set = scheduler.select_pareto_set(arms, evals)
    frontier_ids = {c.arm_id for c in pareto_set.candidates}
    assert frontier_ids == {"E"}

def test_pareto_nan_handling():
    scheduler = BCRBScheduler(total_budget=10.0)
    arms = [
        CandidateArm(arm_id="G", cost=1.0, prior=0.5),
        CandidateArm(arm_id="H", cost=1.0, prior=0.5)
    ]
    evals = {
        "G": _create_eval(float("nan"), 1.0),
        "H": _create_eval(10.0, 1.0)
    }
    pareto_set = scheduler.select_pareto_set(arms, evals)
    frontier_ids = {c.arm_id for c in pareto_set.candidates}
    assert frontier_ids == {"H"}
    
def test_pareto_property_no_point_dominated():
    scheduler = BCRBScheduler(total_budget=10.0)
    import random
    
    arms = []
    evals = {}
    for i in range(50):
        a_id = f"arm_{i}"
        cost = random.uniform(1.0, 5.0)
        info = random.uniform(0.0, 10.0)
        harm = random.uniform(0.0, 5.0)
        arms.append(CandidateArm(arm_id=a_id, cost=cost, prior=0.5))
        evals[a_id] = _create_eval(info, harm)
        
    pareto_set = scheduler.select_pareto_set(arms, evals)
    frontier = pareto_set.candidates
    
    # Prove no point in frontier dominates another point in frontier
    for i, c1 in enumerate(frontier):
        for j, c2 in enumerate(frontier):
            if i == j:
                continue
            
            # check if c2 dominates c1
            info_geq = c2.information_gain >= c1.information_gain
            harm_leq = c2.recovery_harm <= c1.recovery_harm
            cost_leq = c2.cost <= c1.cost
            
            info_strict = c2.information_gain > c1.information_gain
            harm_strict = c2.recovery_harm < c1.recovery_harm
            cost_strict = c2.cost < c1.cost
            
            no_worse = info_geq and harm_leq and cost_leq
            strictly_better = info_strict or harm_strict or cost_strict
            
            assert not (no_worse and strictly_better), f"{c2.arm_id} dominates {c1.arm_id} in returned frontier!"
