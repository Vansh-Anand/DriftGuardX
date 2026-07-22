import pytest
from packages.evaluation.src.bandit_baselines import CandidateArm, RandomBudgetScheduler, CheapestFirstScheduler
from packages.replay.src.bandit import BCRBScheduler

def test_random_scheduler_budget_limit():
    arms = [
        CandidateArm(arm_id="A", cost=0.5, prior=0.5),
        CandidateArm(arm_id="B", cost=1.0, prior=0.5)
    ]
    scheduler = RandomBudgetScheduler(total_budget=1.2)
    
    # First pull, can pick A or B
    arm1 = scheduler.select_arm(arms)
    assert arm1 in ["A", "B"]
    
    # Update with cost
    cost = 0.5 if arm1 == "A" else 1.0
    scheduler.update(arm1, 1.0, cost)
    
    # Remaining budget is either 0.7 (if A) or 0.2 (if B)
    arm2 = scheduler.select_arm(arms)
    if cost == 1.0:
        # Budget is 0.2, neither A (0.5) nor B (1.0) is affordable
        assert arm2 is None
    else:
        # Budget is 0.7, A is affordable, B is not
        assert arm2 == "A"

def test_bcrb_scheduler_prior_exploration():
    arms = [
        CandidateArm(arm_id="distractor", cost=0.1, prior=0.9),
        CandidateArm(arm_id="root_cause", cost=0.1, prior=0.1)
    ]
    scheduler = BCRBScheduler(total_budget=1.0, exploration_constant=0.5)
    
    # Because 'distractor' has a much higher prior (0.9 vs 0.1) and costs are equal,
    # the scheduler should pick 'distractor' first if we use priors optimistically.
    first_arm = scheduler.select_arm(arms)
    assert first_arm == "distractor"
    
    # We update distractor with terrible reward (0.0). 
    scheduler.update("distractor", reward=0.0, cost=0.1)
    
    # Now root_cause prior (0.1 + UCB) should beat distractor expected reward (0.0 + smaller UCB)
    second_arm = scheduler.select_arm(arms)
    assert second_arm == "root_cause"

def test_bcrb_scheduler_knapsack_cost_constraint():
    arms = [
        CandidateArm(arm_id="cheap", cost=0.1, prior=0.5),
        CandidateArm(arm_id="expensive", cost=0.9, prior=0.5)
    ]
    scheduler = BCRBScheduler(total_budget=1.0, exploration_constant=0.5)
    
    # Both have same prior. 'cheap' has higher Knapsack score (UCB / Cost).
    first_arm = scheduler.select_arm(arms)
    assert first_arm == "cheap"
