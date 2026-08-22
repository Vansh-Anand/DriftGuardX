import math
import random
import statistics
from typing import List, Dict, Type
from packages.evaluation.src.bandit_baselines import (
    CandidateArm,
    BaseScheduler,
    RandomBudgetScheduler,
    CheapestFirstScheduler,
    GreedyPriorScheduler,
    StandardUCBScheduler,
    ExhaustiveReplayScheduler
)
from packages.replay.src.bandit import ResourceAdmittedBCRBController

# Mock true distributions for arms
class ArmEnvironment:
    def __init__(self, arm_id: str, true_reward: float, true_cost: float, variance: float):
        self.arm_id = arm_id
        self.true_reward = true_reward
        self.true_cost = true_cost
        self.variance = variance

    def sample(self) -> tuple[float, float]:
        reward = max(0.0, random.gauss(self.true_reward, self.variance))
        cost = max(0.01, random.gauss(self.true_cost, self.variance))
        return reward, cost

def run_experiment(scheduler_cls: Type[BaseScheduler], arms: List[CandidateArm], environments: Dict[str, ArmEnvironment], total_budget: float, num_trials: int = 100):
    total_rewards = []
    
    for _ in range(num_trials):
        # Instantiate scheduler
        if scheduler_cls == ResourceAdmittedBCRBController:
            scheduler = scheduler_cls(total_budget=total_budget, exploration_constant=1.0, rollback_reserve_ratio=0.05)
        elif scheduler_cls == StandardUCBScheduler:
            scheduler = scheduler_cls(total_budget=total_budget, exploration_constant=1.0)
        else:
            scheduler = scheduler_cls(total_budget=total_budget)
            
        cumulative_reward = 0.0
        
        while True:
            selected = scheduler.select_arm(arms)
            if not selected:
                break
                
            env = environments[selected]
            reward, cost = env.sample()
            
            # If the cost exceeds remaining budget, truncate reward proportional to what was afforded
            if cost > scheduler.remaining_budget:
                # Fractional reward
                fraction = max(0.0, scheduler.remaining_budget / cost)
                reward = reward * fraction
                
            scheduler.update(selected, reward, cost)
            cumulative_reward += reward
            
            # If budget exhausted (checked inside select_arm usually, but just in case)
            if scheduler.remaining_budget <= 0:
                break
                
        total_rewards.append(cumulative_reward)
        
    mean_reward = statistics.mean(total_rewards)
    std_reward = statistics.stdev(total_rewards) if num_trials > 1 else 0.0
    
    # 95% Confidence Interval
    ci = 1.96 * (std_reward / math.sqrt(num_trials))
    return mean_reward, ci

def main():
    random.seed(42)
    
    arms = [
        CandidateArm(arm_id="A (cheap, low reward)", cost=1.0, prior=0.1),
        CandidateArm(arm_id="B (expensive, high reward)", cost=10.0, prior=0.9),
        CandidateArm(arm_id="C (efficient)", cost=2.0, prior=0.5),
        CandidateArm(arm_id="D (volatile liar)", cost=1.0, prior=0.8), # Claims 1.0 cost, actually costs 8.0!
    ]
    
    environments = {
        "A (cheap, low reward)": ArmEnvironment("A (cheap, low reward)", 0.1, 1.0, 0.1),
        "B (expensive, high reward)": ArmEnvironment("B (expensive, high reward)", 0.9, 10.0, 1.0),
        "C (efficient)": ArmEnvironment("C (efficient)", 0.5, 2.0, 0.2),
        "D (volatile liar)": ArmEnvironment("D (volatile liar)", 0.8, 8.0, 4.0)
    }
    
    budget = 20.0
    num_trials = 1000
    
    schedulers = [
        ("Random", RandomBudgetScheduler),
        ("Cheapest-First", CheapestFirstScheduler),
        ("Greedy-Prior", GreedyPriorScheduler),
        ("Standard UCB", StandardUCBScheduler),
        ("Exhaustive", ExhaustiveReplayScheduler),
        ("Measured BCRB (Ours)", ResourceAdmittedBCRBController)
    ]
    
    print(f"Running experiments with Budget = {budget}, Trials = {num_trials}\n")
    print(f"{'Scheduler':<25} | {'Mean Cumulative Reward':<25} | {'95% CI':<15}")
    print("-" * 70)
    
    for name, cls in schedulers:
        mean_rew, ci = run_experiment(cls, arms, environments, budget, num_trials)
        print(f"{name:<25} | {mean_rew:<25.4f} | ±{ci:<15.4f}")

if __name__ == "__main__":
    main()
