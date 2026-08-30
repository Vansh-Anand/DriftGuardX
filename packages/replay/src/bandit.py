"""
DriftGuard-X v2 — Resource-Admitted Budget-Constrained Root-Cause Bandit (BCRB)
PRIVATE — All Rights Reserved.
"""
import math

from packages.contracts.src.models import (
    AdmissibilityScore,
    ExecutionBudget,
    ParetoReplayCandidate,
    ParetoReplaySet,
    RAEBEvaluation,
)
from packages.evaluation.src.bandit_baselines import BaseScheduler, CandidateArm

# Confidence multiplier for uncertainty margin (k * sigma)
_UNCERTAINTY_K = 2.0  # ~95% confidence assuming Gaussian distribution


class ResourceAdmittedBCRBController(BaseScheduler):
    """
    Measured Resource-Admission Controller (Prompt 6).
    
    Instead of relying solely on declared prior costs, this controller tracks
    actual multi-dimensional physical resource consumption (CPU, GPU, memory,
    storage, tokens, wall-clock, queue-delay) and defines an explicit admission
    rule based on predicted cost, historical uncertainty margin, remaining budget,
    and a static rollback reserve.
    """

    def __init__(self, total_budget: float, exploration_constant: float = 1.0, execution_budget: ExecutionBudget | None = None, rollback_reserve_ratio: float = 0.1):
        super().__init__(total_budget)
        self.c = exploration_constant
        self.execution_budget = execution_budget
        self.rollback_reserve = total_budget * rollback_reserve_ratio

        self.rewards: dict[str, float] = {}
        self.total_pulls = 0
        self.stop_reason: str | None = None

        # Track actual cost history per arm for uncertainty margin calculation
        self._cost_history: dict[str, list[float]] = {}
        self.shed_log: list[str] = []

    # ── Measured Admission Control ────────────────────────────────────────────

    def _get_cost_statistics(self, arm: CandidateArm) -> tuple[float, float]:
        """
        Returns (mean_predicted_cost, uncertainty_margin) based on history.
        Uses declared priors for unseen arms and a conservative margin once
        measured telemetry exists.
        """
        history = self._cost_history.get(arm.arm_id, [])
        floor_cost = 0.05
        default_margin = 0.05

        if not history:
            return max(arm.cost, floor_cost), 0.0

        # Filter out NaNs to ensure graceful handling of corrupted telemetry
        valid_history = [x for x in history if not math.isnan(x)]
        if not valid_history:
            return max(arm.cost, floor_cost), 0.0

        n = len(valid_history)
        mean_cost = sum(valid_history) / n

        if n < 2:
            return mean_cost, default_margin

        variance = sum((x - mean_cost) ** 2 for x in valid_history) / (n - 1)
        std_dev = math.sqrt(variance)

        # Uncertainty margin: k * sigma
        uncertainty_margin = _UNCERTAINTY_K * std_dev

        return mean_cost, uncertainty_margin

    def _violates_admission_rule(self, arm: CandidateArm) -> bool:
        """
        Explicit admission rule:
        predicted_cost + uncertainty_margin <= remaining_budget - rollback_reserve
        """
        mean_cost, uncertainty_margin = self._get_cost_statistics(arm)
        admitted = (mean_cost + uncertainty_margin) <= (self.remaining_budget - self.rollback_reserve)
        return not admitted

    # ── Arm Selection ─────────────────────────────────────────────────────────

    def select_arm(self, arms: list[CandidateArm]) -> str | None:
        # Multi-dimensional exhaustion check
        if self.execution_budget:
            exhaustion = self.execution_budget.check_exhaustion()
            if exhaustion:
                self.stop_reason = exhaustion.value
                return None

        # Admission Control (reject before queue allocation)
        admitted: list[CandidateArm] = []
        for arm in arms:
            if self._violates_admission_rule(arm):
                self.shed_log.append(arm.arm_id)
            else:
                admitted.append(arm)

        if not admitted:
            self.stop_reason = "Shed: Budget Exhausted or All Candidates Failed Admission"
            return None

        best_arm: str | None = None
        best_value = float("-inf")

        # Tie-breaking sort to preserve determinism
        admitted.sort(key=lambda x: x.arm_id)

        for arm in admitted:
            pulls = self.pulls.get(arm.arm_id, 0)

            # Use empirical mean cost if available, otherwise prior
            mean_cost, _ = self._get_cost_statistics(arm)
            effective_cost = max(mean_cost, 0.0001)

            if pulls == 0:
                expected_reward = arm.prior
                # Unseen arms get a high bonus to encourage exploration initially,
                # but scaled relative to the exploration constant.
                ucb_bonus = self.c * math.sqrt(math.log(max(self.total_pulls, 1) + 1))
            else:
                expected_reward = self.rewards.get(arm.arm_id, 0.0) / pulls
                # Safe log for total_pulls to prevent math domain error
                ucb_bonus = self.c * math.sqrt(math.log(max(self.total_pulls, 1)) / pulls)

            if math.isnan(expected_reward):
                expected_reward = 0.0
            if math.isnan(ucb_bonus):
                ucb_bonus = 0.0

            ucb_score = expected_reward + ucb_bonus
            knapsack_score = ucb_score / effective_cost

            if knapsack_score > best_value:
                best_value = knapsack_score
                best_arm = arm.arm_id

        return best_arm

    def update(self, arm_id: str, reward: float, cost: float) -> None:
        """Update controller with empirical telemetry."""
        # Handle NaN reward or cost
        if math.isnan(reward):
            reward = 0.0
        if math.isnan(cost):
            # Corrupt cost telemetry is unmeasured, not a real resource charge.
            # Ignore it so it cannot poison either the budget or cost history.
            cost = 0.0

        super().update(arm_id, reward, cost)

        self.rewards[arm_id] = self.rewards.get(arm_id, 0.0) + reward
        self.total_pulls += 1

        if cost > 0.0:  # Only add real costs to history
            if arm_id not in self._cost_history:
                self._cost_history[arm_id] = []
            self._cost_history[arm_id].append(cost)

    def select_pareto_set(
        self,
        arms: list[CandidateArm],
        raeb_evaluations: dict[str, RAEBEvaluation]
    ) -> ParetoReplaySet:

        admitted = []
        for arm in arms:
            if self._violates_admission_rule(arm):
                self.shed_log.append(arm.arm_id)
                continue

            eval_data = raeb_evaluations.get(arm.arm_id)
            if not eval_data or eval_data.admissibility == AdmissibilityScore.UNSUPPORTED:
                continue

            admitted.append(arm)

        candidates = []
        for arm in admitted:
            eval_data = raeb_evaluations[arm.arm_id]
            mean_cost, _ = self._get_cost_statistics(arm)
            candidates.append(
                ParetoReplayCandidate(
                    arm_id=arm.arm_id,
                    information_gain=eval_data.information_gain_estimate,
                    recovery_harm=eval_data.risk_score,
                    cost=mean_cost,
                    admissibility=AdmissibilityScore(eval_data.admissibility),
                    is_pareto_optimal=False
                )
            )

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
                    if c2.arm_id < c1.arm_id:
                        is_dominated = True
                        break

            if not is_dominated:
                c1.is_pareto_optimal = True
                pareto_candidates.append(c1)

        pareto_candidates.sort(key=lambda x: x.arm_id)
        return ParetoReplaySet(candidates=pareto_candidates)
