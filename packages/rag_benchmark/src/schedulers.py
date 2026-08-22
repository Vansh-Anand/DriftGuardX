import random
import math
from typing import List, Dict, Any

class BaseScheduler:
    """Base interface for recovery schedulers."""
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        raise NotImplementedError

class ExhaustiveScheduler(BaseScheduler):
    """Tests all candidates iteratively."""
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        tested = {h['candidate'] for h in history}
        for c in candidates:
            if c not in tested:
                return c
        return None

class RandomScheduler(BaseScheduler):
    """Selects a candidate completely at random."""
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        tested = {h['candidate'] for h in history}
        remaining = [c for c in candidates if c not in tested]
        if not remaining:
            return None
        return random.choice(remaining)

class CheapestFirstScheduler(BaseScheduler):
    """Prioritizes candidates with the lowest historical computational cost."""
    def __init__(self, cost_table: Dict[str, float] = None):
        # Default mock costs per component
        self.cost_table = cost_table or {
            "RETRIEVER": 0.01,
            "GENERATOR": 0.5,
            "POLICY_ENFORCER": 0.005,
            "SYSTEM_PROMPT": 0.1
        }
        
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        tested = {h['candidate'] for h in history}
        remaining = [c for c in candidates if c not in tested]
        if not remaining:
            return None
            
        remaining.sort(key=lambda c: self.cost_table.get(c, 1.0))
        return remaining[0]

class GreedyPriorScheduler(BaseScheduler):
    """Selects the hypothesis that historically occurs most often."""
    def __init__(self, priors_table: Dict[str, float] = None):
        # Mock probabilities
        self.priors_table = priors_table or {
            "RETRIEVER": 0.2,
            "GENERATOR": 0.5,
            "POLICY_ENFORCER": 0.05,
            "SYSTEM_PROMPT": 0.25
        }
        
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        tested = {h['candidate'] for h in history}
        remaining = [c for c in candidates if c not in tested]
        if not remaining:
            return None
            
        remaining.sort(key=lambda c: self.priors_table.get(c, 0.1), reverse=True)
        return remaining[0]

class UCBScheduler(BaseScheduler):
    """Standard Upper Confidence Bound exploration vs exploitation."""
    def __init__(self, exploration_weight: float = 1.0):
        self.c = exploration_weight
        self.counts = {}
        self.successes = {}
        
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        tested = {h['candidate'] for h in history}
        remaining = [c for c in candidates if c not in tested]
        if not remaining:
            return None
            
        total_plays = sum(self.counts.values()) + 1
        
        best_ucb = -1.0
        best_candidate = remaining[0]
        
        for c in remaining:
            if c not in self.counts or self.counts[c] == 0:
                # Force exploration if unplayed
                return c
            
            avg_success = self.successes[c] / self.counts[c]
            ucb = avg_success + self.c * math.sqrt(math.log(total_plays) / self.counts[c])
            
            if ucb > best_ucb:
                best_ucb = ucb
                best_candidate = c
                
        return best_candidate
        
    def update(self, candidate: str, success: bool):
        self.counts[candidate] = self.counts.get(candidate, 0) + 1
        self.successes[candidate] = self.successes.get(candidate, 0) + (1 if success else 0)

class DetectorOnlyScheduler(BaseScheduler):
    """No replay execution; relies solely on anomaly detection from trace."""
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        return None # No replays allowed

class GraphOnlyScheduler(BaseScheduler):
    """Uses only structural graph causal analysis; does not execute replays."""
    def select_next(self, candidates: List[str], history: List[Dict[str, Any]]) -> str:
        return None # No replays allowed
