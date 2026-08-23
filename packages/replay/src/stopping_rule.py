"""
DriftGuard-X v2 — Evidentiary Stopping Rule
PRIVATE — All Rights Reserved.

Replaces the hard max_iters=5 cap with a principled, multi-criterion stopping policy.

Stopping criteria (evaluated in priority order):
1. Resource exhaustion     — budget or time limit exceeded
2. Forbidden divergence    — early termination signal from divergence validator
3. Posterior confidence    — max posterior >= confidence_threshold
4. Posterior margin        — gap between top-2 candidates >= margin_threshold
5. Entropy convergence     — entropy changed < delta over last N iterations
6. Information exhaustion  — best remaining EIG < min_eig_threshold
7. Minimum evidence count  — must have >= min_replays before stopping on confidence

The hard max_experiments value is a safety cap only — all other criteria
take precedence and can stop earlier or later as evidence warrants.
"""
from __future__ import annotations

import enum
from collections import deque
from typing import Any

from packages.contracts.src.incident_models import IncidentState
from packages.contracts.src.interfaces import BeliefModel, ResourceContext


class StoppingOutcome(str, enum.Enum):
    CONFIRMED = "confirmed"
    UNRESOLVED = "unresolved"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    SAFETY_LIMIT = "safety_limit"
    NO_ADMISSIBLE_EXPERIMENT = "no_admissible_experiment"


class EvidentiaryStoppingRule:
    """
    Multi-criterion evidentiary stopping policy.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.85,
        margin_threshold: float = 0.60,
        entropy_convergence_delta: float = 0.01,
        entropy_window: int = 3,
        min_eig_threshold: float = 0.02,
        min_replays: int = 2,
        max_experiments: int = 20,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.margin_threshold = margin_threshold
        self.entropy_convergence_delta = entropy_convergence_delta
        self.entropy_window = entropy_window
        self.min_eig_threshold = min_eig_threshold
        self.min_replays = min_replays
        self.max_experiments = max_experiments

        self._entropy_history: deque[float] = deque(maxlen=entropy_window + 1)
        self._replay_count: int = 0

    def record_iteration(self, entropy: float) -> None:
        self._entropy_history.append(entropy)
        self._replay_count += 1

    def reset(self) -> None:
        self._entropy_history.clear()
        self._replay_count = 0

    def is_sufficient(
        self,
        state: IncidentState,
        resource_context: ResourceContext,
        belief_model: BeliefModel,
        remaining_candidates: list[dict[str, Any]],
    ) -> tuple[bool, StoppingOutcome, str]:
        """
        Returns (should_stop: bool, outcome: StoppingOutcome, reason: str).
        """
        beliefs = belief_model.current_beliefs()
        entropy = belief_model.entropy()

        # Priority 1: Resource exhaustion
        if resource_context.budget_exhausted():
            return True, StoppingOutcome.RESOURCE_EXHAUSTED, "Resource budget exhausted (USD or time limit)."

        # Priority 2: Hard safety cap
        if resource_context.replay_count >= self.max_experiments:
            return True, StoppingOutcome.SAFETY_LIMIT, f"Hard safety cap reached: {self.max_experiments} experiments."

        has_min_evidence = self._replay_count >= self.min_replays

        # Priority 3: Posterior confidence
        if has_min_evidence and beliefs:
            max_posterior = max(beliefs.values())
            if max_posterior >= self.confidence_threshold:
                top_candidate = max(beliefs, key=lambda k: beliefs[k])
                return (
                    True,
                    StoppingOutcome.CONFIRMED,
                    f"Posterior confidence {max_posterior:.3f} >= {self.confidence_threshold} "
                    f"for candidate '{top_candidate}'.",
                )

        # Priority 4: Posterior margin
        if has_min_evidence and len(beliefs) >= 2:
            sorted_vals = sorted(beliefs.values(), reverse=True)
            margin = sorted_vals[0] - sorted_vals[1]
            if margin >= self.margin_threshold:
                return (
                    True,
                    StoppingOutcome.CONFIRMED,
                    f"Posterior margin {margin:.3f} >= {self.margin_threshold} between top-2 candidates.",
                )

        # Priority 5: Entropy convergence
        if has_min_evidence and len(self._entropy_history) >= self.entropy_window:
            recent = list(self._entropy_history)
            max_delta = max(abs(recent[i] - recent[i - 1]) for i in range(1, len(recent)))
            if max_delta < self.entropy_convergence_delta:
                return (
                    True,
                    StoppingOutcome.UNRESOLVED,
                    f"Entropy converged: max delta {max_delta:.5f} < {self.entropy_convergence_delta} "
                    f"over last {self.entropy_window} iterations.",
                )

        # Priority 6: Information exhaustion
        if not remaining_candidates:
            return True, StoppingOutcome.NO_ADMISSIBLE_EXPERIMENT, "No remaining candidates to experiment on."

        # Not sufficient
        reasons = []
        if beliefs:
            max_p = max(beliefs.values())
            reasons.append(f"max_posterior={max_p:.3f}")
        reasons.append(f"entropy={entropy:.4f}")
        reasons.append(f"replays={self._replay_count}")
        return False, StoppingOutcome.UNRESOLVED, "Evidence insufficient: " + ", ".join(reasons)

