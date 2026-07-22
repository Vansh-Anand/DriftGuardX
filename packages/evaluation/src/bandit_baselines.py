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
