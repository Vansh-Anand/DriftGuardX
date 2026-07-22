"""
DriftGuard-X v2 — BCRB Sensitivity Sweep Simulation
PRIVATE — All Rights Reserved.
"""
import random
from typing import List, Dict, Type

from packages.evaluation.src.bandit_baselines import CandidateArm, BaseScheduler, RandomBudgetScheduler, CheapestFirstScheduler, GreedyPriorScheduler
from packages.replay.src.bandit import BCRBScheduler

# Mock Ground Truth for simulation
class SimulatedArm:
    def __init__(self, arm_id: str, cost: float, prior: float, true_mean_reward: float):
        self.arm_id = arm_id
        self.cost = cost
        self.prior = prior
        self.true_mean_reward = true_mean_reward

    def pull(self) -> float:
        # Simulate noise: true_mean + uniform noise
        noise = random.uniform(-0.05, 0.05)
        return max(0.0, min(1.0, self.true_mean_reward + noise))

def run_simulation(
    scheduler: BaseScheduler, 
    simulated_arms: List[SimulatedArm], 
    num_steps: int = 100
) -> Dict:
    candidate_arms = [
        CandidateArm(arm_id=a.arm_id, cost=a.cost, prior=a.prior)
        for a in simulated_arms
    ]
    
    arm_map = {a.arm_id: a for a in simulated_arms}
    
    total_reward = 0.0
    
    for _ in range(num_steps):
        selected_id = scheduler.select_arm(candidate_arms)
        if selected_id is None:
            break
            
        arm = arm_map[selected_id]
        reward = arm.pull()
        
        scheduler.update(selected_id, reward, arm.cost)
        total_reward += reward

    best_arm_id = max(simulated_arms, key=lambda a: a.true_mean_reward).arm_id
    best_arm_pulls = scheduler.pulls.get(best_arm_id, 0)
    
    return {
        "scheduler_type": type(scheduler).__name__,
        "total_reward": total_reward,
        "total_cost": scheduler.total_budget - scheduler.remaining_budget,
        "total_pulls": sum(scheduler.pulls.values()),
        "best_arm_pulls": best_arm_pulls,
        "best_arm_percentage": (best_arm_pulls / max(1, sum(scheduler.pulls.values()))) * 100
    }

def main():
    # Setup: 4 arms
    # Arm 1: The true root cause (High reward, med cost, med prior)
    # Arm 2: Irrelevant (Low reward, low cost, high prior - distractor!)
    # Arm 3: Expensive (Med reward, high cost, low prior)
    
    sim_arms = [
        SimulatedArm("arm_root_cause", cost=0.05, prior=0.5, true_mean_reward=0.9),
        SimulatedArm("arm_distractor", cost=0.01, prior=0.9, true_mean_reward=0.1),
        SimulatedArm("arm_expensive",  cost=0.50, prior=0.2, true_mean_reward=0.5)
    ]
    
    budget = 1.0
    
    schedulers = [
        RandomBudgetScheduler(total_budget=budget),
        CheapestFirstScheduler(total_budget=budget),
        GreedyPriorScheduler(total_budget=budget),
        BCRBScheduler(total_budget=budget, exploration_constant=0.5)
    ]
    
    print("--- BCRB vs Baselines Simulation (Budget = $1.00) ---")
    print(f"{'Scheduler':<25} | {'Reward':<8} | {'Cost':<6} | {'Pulls':<6} | {'% on Best Arm'}")
    print("-" * 75)
    
    for s in schedulers:
        res = run_simulation(s, sim_arms)
        print(f"{res['scheduler_type']:<25} | {res['total_reward']:<8.2f} | ${res['total_cost']:<5.2f} | {res['total_pulls']:<6} | {res['best_arm_percentage']:.1f}%")

if __name__ == "__main__":
    main()
