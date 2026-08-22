"""
DriftGuard-X v2 — Bandit Baselines
PRIVATE — All Rights Reserved.
"""
import random
from typing import List, Dict, Optional
from pydantic import BaseModel
from uuid import UUID

class CandidateArm(BaseModel):
    arm_id: str
    cost: float
    prior: float
    
class BaseScheduler:
    def __init__(self, total_budget: float):
        self.total_budget = total_budget
        self.remaining_budget = total_budget
        self.pulls: Dict[str, int] = {}
        
    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        raise NotImplementedError
        
    def update(self, arm_id: str, reward: float, cost: float):
        self.remaining_budget -= cost
        self.pulls[arm_id] = self.pulls.get(arm_id, 0) + 1

class RandomBudgetScheduler(BaseScheduler):
    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        eligible = [a for a in arms if a.cost <= self.remaining_budget]
        if not eligible:
            return None
        return random.choice(eligible).arm_id

class CheapestFirstScheduler(BaseScheduler):
    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        eligible = [a for a in arms if a.cost <= self.remaining_budget]
        if not eligible:
            return None
        eligible.sort(key=lambda x: x.cost)
        return eligible[0].arm_id

class GreedyPriorScheduler(BaseScheduler):
    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        eligible = [a for a in arms if a.cost <= self.remaining_budget]
        if not eligible:
            return None
        eligible.sort(key=lambda x: x.prior, reverse=True)
        return eligible[0].arm_id

class StandardUCBScheduler(BaseScheduler):
    """Unconstrained UCB (no knapsack division by cost)."""
    def __init__(self, total_budget: float, exploration_constant: float = 1.0):
        super().__init__(total_budget)
        self.c = exploration_constant
        self.rewards: Dict[str, float] = {}
        self.total_pulls = 0

    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        eligible = [a for a in arms if a.cost <= self.remaining_budget]
        if not eligible:
            return None
            
        # Tie-breaking sort
        eligible.sort(key=lambda x: x.arm_id)
        
        best_arm = None
        best_value = float("-inf")
        
        for arm in eligible:
            pulls = self.pulls.get(arm.arm_id, 0)
            if pulls == 0:
                ucb_score = arm.prior + self.c
            else:
                expected_reward = self.rewards.get(arm.arm_id, 0.0) / pulls
                ucb_score = expected_reward + self.c * __import__("math").sqrt(__import__("math").log(self.total_pulls) / pulls)
                
            if ucb_score > best_value:
                best_value = ucb_score
                best_arm = arm.arm_id
                
        return best_arm
        
    def update(self, arm_id: str, reward: float, cost: float):
        super().update(arm_id, reward, cost)
        self.rewards[arm_id] = self.rewards.get(arm_id, 0.0) + reward
        self.total_pulls += 1

class ExhaustiveReplayScheduler(BaseScheduler):
    """Runs everything sequentially until failure (exhausts budget without smart selection)."""
    def __init__(self, total_budget: float):
        super().__init__(total_budget)
        
    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        eligible = [a for a in arms if a.cost <= self.remaining_budget]
        if not eligible:
            return None
        
        # Always pick the first eligible arm (like a naive queue)
        eligible.sort(key=lambda x: x.arm_id)
        return eligible[0].arm_id
