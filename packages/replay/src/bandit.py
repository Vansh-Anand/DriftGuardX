"""
DriftGuard-X v2 — Budget-Constrained Root-Cause Bandit (BCRB)
PRIVATE — All Rights Reserved.
"""
import math
from typing import List, Dict, Optional
from packages.evaluation.src.bandit_baselines import CandidateArm, BaseScheduler

class BCRBScheduler(BaseScheduler):
    """
    Budget-Constrained Root-Cause Bandit (Knapsack-UCB).
    Balances expected information gain (UCB) with intervention cost.
    """
    def __init__(self, total_budget: float, exploration_constant: float = 1.0):
        super().__init__(total_budget)
        self.c = exploration_constant
        self.rewards: Dict[str, float] = {}
        self.total_pulls = 0
        self.stop_reason = None
        
    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        eligible = [a for a in arms if a.cost <= self.remaining_budget]
        if not eligible:
            self.stop_reason = "Budget Exhausted" if self.remaining_budget < min((a.cost for a in arms), default=float('inf')) else "No Eligible Arms"
            return None
            
        best_arm = None
        best_value = float('-inf')
        
        for arm in eligible:
            pulls = self.pulls.get(arm.arm_id, 0)
            
            # If never pulled, use prior as optimistic initial estimate
            if pulls == 0:
                expected_reward = arm.prior
                ucb_bonus = self.c  # Initial strong exploration bonus
            else:
                expected_reward = self.rewards[arm.arm_id] / pulls
                # Hoeffding-style UCB bound
                ucb_bonus = self.c * math.sqrt(math.log(self.total_pulls) / pulls)
                
            ucb_score = expected_reward + ucb_bonus
            
            # Knapsack constraint: Value per unit cost
            knapsack_score = ucb_score / max(arm.cost, 0.0001)
            
            if knapsack_score > best_value:
                best_value = knapsack_score
                best_arm = arm.arm_id
                
        return best_arm
        
    def update(self, arm_id: str, reward: float, cost: float):
        super().update(arm_id, reward, cost)
        self.rewards[arm_id] = self.rewards.get(arm_id, 0.0) + reward
        self.total_pulls += 1
