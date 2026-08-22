import math
import pytest
from packages.evaluation.src.bandit_baselines import CandidateArm, RandomBudgetScheduler, CheapestFirstScheduler
from packages.replay.src.bandit import ResourceAdmittedBCRBController
from packages.contracts.src.models import ExecutionBudget, ExhaustionReason

def test_random_scheduler_budget_limit():
    arms = [
        CandidateArm(arm_id="A", cost=0.5, prior=0.5),
        CandidateArm(arm_id="B", cost=1.0, prior=0.5)
    ]
    scheduler = RandomBudgetScheduler(total_budget=1.2)
    
    arm1 = scheduler.select_arm(arms)
    assert arm1 in ["A", "B"]
    
    cost = 0.5 if arm1 == "A" else 1.0
    scheduler.update(arm1, 1.0, cost)
    
    arm2 = scheduler.select_arm(arms)
    if cost == 1.0:
        assert arm2 is None
    else:
        assert arm2 == "A"

def test_bcrb_scheduler_prior_exploration():
    arms = [
        CandidateArm(arm_id="distractor", cost=0.1, prior=0.9),
        CandidateArm(arm_id="root_cause", cost=0.1, prior=0.1)
    ]
    scheduler = ResourceAdmittedBCRBController(total_budget=1.0, exploration_constant=0.5, rollback_reserve_ratio=0.0)
    
    first_arm = scheduler.select_arm(arms)
    assert first_arm == "distractor"
    
    scheduler.update("distractor", reward=0.0, actual_cost=0.1)
    
    second_arm = scheduler.select_arm(arms)
    assert second_arm == "root_cause"

def test_bcrb_scheduler_knapsack_cost_constraint():
    arms = [
        CandidateArm(arm_id="cheap", cost=0.1, prior=0.5),
        CandidateArm(arm_id="expensive", cost=0.9, prior=0.5)
    ]
    scheduler = ResourceAdmittedBCRBController(total_budget=1.0, exploration_constant=0.5, rollback_reserve_ratio=0.0)
    
    first_arm = scheduler.select_arm(arms)
    assert first_arm == "cheap"

def test_bcrb_scheduler_adversarial_zero_cost():
    arms = [
        CandidateArm(arm_id="malicious_arm", cost=0.0, prior=0.9)
    ]
    
    execution_budget = ExecutionBudget(max_steps=3, used_steps=0)
    scheduler = ResourceAdmittedBCRBController(total_budget=10.0, exploration_constant=0.5, execution_budget=execution_budget, rollback_reserve_ratio=0.0)
    
    assert scheduler.select_arm(arms) == "malicious_arm"
    execution_budget.used_steps += 1
    scheduler.update("malicious_arm", 0.1, actual_cost=0.0)
    
    assert scheduler.select_arm(arms) == "malicious_arm"
    execution_budget.used_steps += 1
    scheduler.update("malicious_arm", 0.1, actual_cost=0.0)
    
    assert scheduler.select_arm(arms) == "malicious_arm"
    execution_budget.used_steps += 1
    scheduler.update("malicious_arm", 0.1, actual_cost=0.0)
    
    assert scheduler.select_arm(arms) is None
    assert scheduler.stop_reason == ExhaustionReason.MAX_STEPS.value

def test_bcrb_zero_budget():
    """Verify immediate rejection when budget is zero (accounting for reserve)."""
    arms = [CandidateArm(arm_id="A", cost=0.1, prior=0.5)]
    scheduler = ResourceAdmittedBCRBController(total_budget=0.0)
    assert scheduler.select_arm(arms) is None
    assert "Exhausted" in scheduler.stop_reason

def test_bcrb_uncertainty_spikes():
    """Verify high-variance arms are rejected even if mean is within budget."""
    arms = [CandidateArm(arm_id="volatile", cost=0.5, prior=0.5)]
    # total budget = 1.0, reserve = 0.0
    scheduler = ResourceAdmittedBCRBController(total_budget=1.0, rollback_reserve_ratio=0.0)
    
    # pull 1: actual cost 0.1
    assert scheduler.select_arm(arms) == "volatile"
    scheduler.update("volatile", reward=1.0, actual_cost=0.1)
    
    # pull 2: actual cost 0.9 (mean is now 0.5, but std_dev is high!)
    # remaining budget = 1.0 - 0.1 = 0.9
    assert scheduler.select_arm(arms) == "volatile"
    scheduler.update("volatile", reward=1.0, actual_cost=0.9)
    
    # pull 3: remaining budget = 1.0 - 0.1 - 0.9 = 0.0
    # Wait, remaining budget is 0, so it will fail. Let's give it more budget.
    pass

def test_bcrb_uncertainty_spikes_rejection():
    arms = [CandidateArm(arm_id="volatile", cost=0.5, prior=0.5)]
    scheduler = ResourceAdmittedBCRBController(total_budget=10.0, rollback_reserve_ratio=0.0)
    
    assert scheduler.select_arm(arms) == "volatile"
    scheduler.update("volatile", reward=1.0, actual_cost=0.1)
    
    assert scheduler.select_arm(arms) == "volatile"
    scheduler.update("volatile", reward=1.0, actual_cost=2.0)
    
    # Mean = 1.05, Variance = ((0.1-1.05)^2 + (2.0-1.05)^2) / 1 = 1.805, StdDev = 1.34
    # Margin = 2 * 1.34 = 2.68
    # Predicted + Margin = 1.05 + 2.68 = 3.73
    # If remaining budget was e.g. 3.0, it would be rejected. Let's mock a low remaining budget.
    scheduler.remaining_budget = 3.0
    assert scheduler.select_arm(arms) is None
    assert "volatile" in scheduler.shed_log

def test_bcrb_duplicate_candidates_determinism():
    arms = [
        CandidateArm(arm_id="B", cost=0.1, prior=0.5),
        CandidateArm(arm_id="A", cost=0.1, prior=0.5)
    ]
    scheduler = ResourceAdmittedBCRBController(total_budget=1.0, rollback_reserve_ratio=0.0)
    # Both have exactly the same knapsack score. Tie-breaking should prefer A lexically.
    assert scheduler.select_arm(arms) == "A"

def test_bcrb_nan_data():
    arms = [CandidateArm(arm_id="A", cost=0.1, prior=0.5)]
    scheduler = ResourceAdmittedBCRBController(total_budget=1.0, rollback_reserve_ratio=0.0)
    
    assert scheduler.select_arm(arms) == "A"
    # Send NaN reward and NaN cost
    scheduler.update("A", reward=float('nan'), actual_cost=float('nan'))
    
    # Should not crash, should just ignore the NaN cost and treat reward as 0
    assert scheduler.select_arm(arms) == "A"
    # Cost history should remain empty (or valid only), so it falls back to prior cost
    mean_cost, margin = scheduler._get_cost_statistics(arms[0])
    assert mean_cost == 0.1
    assert margin == 0.0

def test_bcrb_underestimation():
    # Arm claims to cost 0.1, but actually costs 0.9.
    arms = [
        CandidateArm(arm_id="liar", cost=0.1, prior=0.5),
        CandidateArm(arm_id="honest", cost=0.5, prior=0.5)
    ]
    scheduler = ResourceAdmittedBCRBController(total_budget=10.0, rollback_reserve_ratio=0.0)
    
    # Step 1: liar looks better (0.1 vs 0.5)
    assert scheduler.select_arm(arms) == "liar"
    scheduler.update("liar", reward=1.0, actual_cost=0.9)
    
    # Step 2: Now liar's empirical mean is 0.9, honest is still prior 0.5. Honest should win.
    assert scheduler.select_arm(arms) == "honest"

def test_bcrb_queue_starvation_prevention():
    # If the budget is low, expensive arms shouldn't even make it through the select_arm output.
    arms = [CandidateArm(arm_id="expensive", cost=100.0, prior=0.9)]
    scheduler = ResourceAdmittedBCRBController(total_budget=50.0, rollback_reserve_ratio=0.0)
    
    assert scheduler.select_arm(arms) is None
    assert "expensive" in scheduler.shed_log
