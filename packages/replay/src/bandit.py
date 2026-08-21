"""
DriftGuard-X v2 — Budget-Constrained Root-Cause Bandit (BCRB)
Now includes Pre-emptive Compute Shedding.
PRIVATE — All Rights Reserved.
"""
import math
from typing import List, Dict, Optional
from packages.evaluation.src.bandit_baselines import CandidateArm, BaseScheduler
from packages.contracts.src.models import (
    ParetoReplaySet,
    ParetoReplayCandidate,
    AdmissibilityScore,
    RAEBEvaluation,
    ExecutionBudget,
    ExhaustionReason
)

# Confidence threshold above which an arm is shed before entering the GPU queue.
_SHED_CONFIDENCE_THRESHOLD = 0.99


class BCRBScheduler(BaseScheduler):
    """
    Budget-Constrained Root-Cause Bandit (Knapsack-UCB) with Pre-emptive
    Compute Shedding.

    Pre-emptive Shedding:
      Before scheduling a diagnostic thread, the BCRB models the historical
      compute trajectory of each intervention arm.  If the statistical model
      predicts the arm will exceed the remaining budget with >= 99% certainty,
      the arm is 'shed' (dropped) before it ever enters the GPU queue,
      preventing GPU starvation and wasted OS task-queue cycles.

    Patent Claim: Thread-scheduling and compute-allocation software protocol
    that prevents GPU starvation by pre-emptively eliminating budget-busting
    interventions at selection time.
    """

    def __init__(self, total_budget: float, exploration_constant: float = 1.0, execution_budget: Optional[ExecutionBudget] = None):
        super().__init__(total_budget)
        self.c = exploration_constant
        self.execution_budget = execution_budget
        self.rewards: Dict[str, float] = {}
        self.total_pulls = 0
        self.stop_reason = None
        # Tracks per-arm cost observations for trajectory modelling
        self._cost_history: Dict[str, List[float]] = {}
        self.shed_log: List[str] = []

    # ── Pre-emptive Shedding ──────────────────────────────────────────────────

    def _predicted_cost(self, arm: CandidateArm) -> float:
        """
        Estimate the expected cost of executing this arm based on historical
        observations.  Falls back to arm.cost (the declared prior) if we have
        no history.
        """
        history = self._cost_history.get(arm.arm_id, [])
        if not history:
            return arm.cost
        return sum(history) / len(history)

    def _overbudget_confidence(self, arm: CandidateArm) -> float:
        """
        Return the probability [0, 1] that this arm will exceed the remaining
        budget, modelled as a Gaussian confidence from historical variance.

        With no history: returns 0.0 (optimistic — give it a chance).
        With sufficient history: uses mean + std to compute a z-score-like
        confidence that mean_cost > remaining_budget.
        """
        history = self._cost_history.get(arm.arm_id, [])
        if len(history) < 2:
            return 0.0

        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std = math.sqrt(variance) if variance > 0 else 1e-9

        # How many std-devs above the remaining budget is the predicted cost?
        z = (mean - self.remaining_budget) / std

        # Map z-score to a probability using a logistic approximation of the
        # standard normal CDF (valid for moderate z values).
        confidence = 1.0 / (1.0 + math.exp(-1.7 * z))
        return confidence

    def _should_shed(self, arm: CandidateArm) -> bool:
        """
        True if we are >= SHED_CONFIDENCE_THRESHOLD certain this arm will bust
        the budget.  Arm is then dropped before the GPU queue.
        """
        if self._predicted_cost(arm) <= self.remaining_budget:
            return False
        return self._overbudget_confidence(arm) >= _SHED_CONFIDENCE_THRESHOLD

    # ── Arm Selection ─────────────────────────────────────────────────────────

    def select_arm(self, arms: List[CandidateArm]) -> Optional[str]:
        # Filter 0: Hard execution limits based on ACTUAL measured usage
        if self.execution_budget:
            exhaustion = self.execution_budget.check_exhaustion()
            if exhaustion:
                self.stop_reason = exhaustion.value
                return None
                
        # Filter 1: hard budget constraint (arm declared cost > remaining)
        eligible = [a for a in arms if a.cost <= self.remaining_budget]
        if not eligible:
            self.stop_reason = (
                "Budget Exhausted"
                if self.remaining_budget < min((a.cost for a in arms), default=float("inf"))
                else "No Eligible Arms"
            )
            return None

        # Filter 2: Pre-emptive Compute Shedding — drop arms predicted to bust
        survivable = []
        for arm in eligible:
            if self._should_shed(arm):
                self.shed_log.append(arm.arm_id)
            else:
                survivable.append(arm)

        if not survivable:
            self.stop_reason = "All Arms Shed (Pre-emptive Compute Shedding)"
            return None

        best_arm = None
        best_value = float("-inf")

        for arm in survivable:
            pulls = self.pulls.get(arm.arm_id, 0)

            if pulls == 0:
                expected_reward = arm.prior
                ucb_bonus = self.c
            else:
                expected_reward = self.rewards[arm.arm_id] / pulls
                ucb_bonus = self.c * math.sqrt(math.log(self.total_pulls) / pulls)

            ucb_score = expected_reward + ucb_bonus
            knapsack_score = ucb_score / max(arm.cost, 0.0001)

            if knapsack_score > best_value:
                best_value = knapsack_score
                best_arm = arm.arm_id

        return best_arm

    def update(self, arm_id: str, reward: float, cost: float):
        super().update(arm_id, reward, cost)
        self.rewards[arm_id] = self.rewards.get(arm_id, 0.0) + reward
        self.total_pulls += 1
        # Record actual cost for future trajectory modelling
        if arm_id not in self._cost_history:
            self._cost_history[arm_id] = []
        self._cost_history[arm_id].append(cost)

    def select_pareto_set(
        self, 
        arms: List[CandidateArm], 
        raeb_evaluations: Dict[str, RAEBEvaluation]
    ) -> ParetoReplaySet:
        """
        Rank replays by admissibility, expected information gain, recovery harm, and cost.
        Returns a Pareto set of replays instead of a single opaque UCB winner.
        """
        eligible = []
        for arm in arms:
            if self._should_shed(arm):
                self.shed_log.append(arm.arm_id)
                continue
            if arm.cost > self.remaining_budget:
                continue
                
            eval_data = raeb_evaluations.get(arm.arm_id)
            if not eval_data or eval_data.admissibility == AdmissibilityScore.UNSUPPORTED:
                continue
                
            eligible.append(arm)
            
        # Convert eligible arms to candidates
        candidates = []
        for arm in eligible:
            eval_data = raeb_evaluations[arm.arm_id]
            candidates.append(
                ParetoReplayCandidate(
                    arm_id=arm.arm_id,
                    information_gain=eval_data.information_gain_estimate,
                    recovery_harm=eval_data.risk_score,
                    cost=arm.cost,
                    admissibility=AdmissibilityScore(eval_data.admissibility),
                    is_pareto_optimal=False  # To be computed
                )
            )
            
        # Compute Pareto Frontier (Non-Dominated Sorting)
        # Filter out candidates with NaN or invalid metrics
        valid_candidates = []
        for c in candidates:
            if math.isnan(c.information_gain) or math.isnan(c.recovery_harm) or math.isnan(c.cost):
                continue
            valid_candidates.append(c)
            
        pareto_candidates = []
        for i, c1 in enumerate(valid_candidates):
            is_dominated = False
            for j, c2 in enumerate(valid_candidates):
                if i == j:
                    continue
                # c2 dominates c1 if it is better or equal in all dimensions and strictly better in at least one.
                # Maximize info_gain, Minimize recovery_harm, Minimize cost
                info_geq = c2.information_gain >= c1.information_gain
                harm_leq = c2.recovery_harm <= c1.recovery_harm
                cost_leq = c2.cost <= c1.cost
                
                info_strict = c2.information_gain > c1.information_gain
                harm_strict = c2.recovery_harm < c1.recovery_harm
                cost_strict = c2.cost < c1.cost
                
                no_worse = info_geq and harm_leq and cost_leq
                strictly_better = info_strict or harm_strict or cost_strict
                
                if no_worse and strictly_better:
                    is_dominated = True
                    break
                elif no_worse and not strictly_better:
                    # They are mathematically identical in all objectives.
                    # Handle duplicate deterministically using arm_id to tie-break
                    if c2.arm_id < c1.arm_id:
                        is_dominated = True
                        break
                    
            if not is_dominated:
                c1.is_pareto_optimal = True
                pareto_candidates.append(c1)
                
        # Optional sorting for deterministic output order
        pareto_candidates.sort(key=lambda x: x.arm_id)
                
        return ParetoReplaySet(candidates=pareto_candidates)
