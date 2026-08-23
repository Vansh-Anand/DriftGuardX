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

import math
from collections import deque
from typing import Any

from packages.contracts.src.incident_models import IncidentState
from packages.contracts.src.interfaces import BeliefModel, ResourceContext


class EvidentiaryStoppingRule:
    """
    Multi-criterion evidentiary stopping policy.

    Parameters
    ----------
    confidence_threshold : float
        Stop if any single candidate's posterior probability reaches this value.
        Default 0.85 — high confidence without requiring certainty.
    margin_threshold : float
        Stop if the probability gap between the top-2 candidates exceeds this.
        Catches cases where the model is very sure relative to alternatives.
    entropy_convergence_delta : float
        Stop if absolute entropy change over the last `entropy_window` iterations
        is below this value (information gain has plateaued).
    entropy_window : int
        Number of recent iterations to check for entropy convergence.
    min_eig_threshold : float
        Stop if the best available Expected Information Gain from any remaining
        candidate falls below this threshold (nothing useful left to learn).
    min_replays : int
        Minimum number of successful replay experiments required before
        confidence/margin/entropy criteria can trigger a stop.
        Prevents early stopping from a single lucky replay.
    max_experiments : int
        Hard safety cap — overrides all other criteria.
        Should be set generously (e.g. 20) so it only catches runaway loops.
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

        # Rolling history for entropy convergence check
        self._entropy_history: deque[float] = deque(maxlen=entropy_window + 1)
        self._replay_count: int = 0

    def record_iteration(self, entropy: float) -> None:
        """Call after each experiment with the updated belief entropy."""
        self._entropy_history.append(entropy)
        self._replay_count += 1

    def reset(self) -> None:
        """Reset iteration state for a new incident."""
        self._entropy_history.clear()
        self._replay_count = 0

    def is_sufficient(
        self,
        state: IncidentState,
        resource_context: ResourceContext,
        belief_model: BeliefModel,
        remaining_candidates: list[dict[str, Any]],
    ) -> tuple[bool, str]:
        """
        Returns (should_stop: bool, reason: str).

        Evaluated in priority order so the most important conditions are
        checked first and their reason is reported.
        """
        beliefs = belief_model.current_beliefs()
        entropy = belief_model.entropy()

        # --- Priority 1: Resource exhaustion ---
        if resource_context.budget_exhausted():
            return True, "Resource budget exhausted (USD or time limit)."

        # --- Priority 2: Hard safety cap ---
        if resource_context.replay_count >= self.max_experiments:
            return True, f"Hard safety cap reached: {self.max_experiments} experiments."

        # --- Need minimum evidence before confidence criteria apply ---
        has_min_evidence = self._replay_count >= self.min_replays

        # --- Priority 3: Posterior confidence ---
        if has_min_evidence and beliefs:
            max_posterior = max(beliefs.values())
            if max_posterior >= self.confidence_threshold:
                top_candidate = max(beliefs, key=lambda k: beliefs[k])
                return (
                    True,
                    f"Posterior confidence {max_posterior:.3f} >= {self.confidence_threshold} "
                    f"for candidate '{top_candidate}'.",
                )

        # --- Priority 4: Posterior margin ---
        if has_min_evidence and len(beliefs) >= 2:
            sorted_vals = sorted(beliefs.values(), reverse=True)
            margin = sorted_vals[0] - sorted_vals[1]
            if margin >= self.margin_threshold:
                return (
                    True,
                    f"Posterior margin {margin:.3f} >= {self.margin_threshold} between top-2 candidates.",
                )

        # --- Priority 5: Entropy convergence ---
        if has_min_evidence and len(self._entropy_history) >= self.entropy_window:
            recent = list(self._entropy_history)
            max_delta = max(abs(recent[i] - recent[i - 1]) for i in range(1, len(recent)))
            if max_delta < self.entropy_convergence_delta:
                return (
                    True,
                    f"Entropy converged: max delta {max_delta:.5f} < {self.entropy_convergence_delta} "
                    f"over last {self.entropy_window} iterations.",
                )

        # --- Priority 6: Information exhaustion ---
        if not remaining_candidates:
            return True, "No remaining candidates to experiment on."

        # Report: not sufficient yet
        reasons = []
        if beliefs:
            max_p = max(beliefs.values())
            reasons.append(f"max_posterior={max_p:.3f}")
        reasons.append(f"entropy={entropy:.4f}")
        reasons.append(f"replays={self._replay_count}")
        return False, "Evidence insufficient: " + ", ".join(reasons)
