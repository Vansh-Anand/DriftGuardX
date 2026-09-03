"""
DriftGuard-X v2 — Benchmark Recovery Models
"""

import enum

from packages.contracts.src.recovery_models import FaultSource
from packages.replay.src.stopping_rule import StoppingOutcome


class SourceSelectionPolicy(str, enum.Enum):
    CONFIRMED_SINGLE = "CONFIRMED_SINGLE"
    CREDIBLE_SET = "CREDIBLE_SET"


class SourceSelector:
    """Filters posterior candidate probabilities to construct a credible fault source set."""

    @staticmethod
    def select_sources(
        posterior: dict[str, float],
        outcome: StoppingOutcome,
        policy: SourceSelectionPolicy,
        cumulative_threshold: float = 0.90,
        min_posterior: float = 0.05,
    ) -> list[FaultSource]:

        if (
            outcome == StoppingOutcome.UNRESOLVED
            or outcome == StoppingOutcome.RESOURCE_EXHAUSTED
            or outcome == StoppingOutcome.NO_ADMISSIBLE_EXPERIMENT
        ):
            # Automatic recovery shouldn't proceed
            return []

        if not posterior:
            return []

        sources = []

        if policy == SourceSelectionPolicy.CONFIRMED_SINGLE:
            if outcome == StoppingOutcome.CONFIRMED:
                top_node = max(posterior, key=lambda k: posterior[k])
                sources.append(FaultSource(node_id=top_node, probability=posterior[top_node]))

        elif policy == SourceSelectionPolicy.CREDIBLE_SET:
            # Sort by descending probability
            sorted_items = sorted(posterior.items(), key=lambda x: x[1], reverse=True)
            cumulative = 0.0

            for node, prob in sorted_items:
                if prob < min_posterior:
                    break
                sources.append(FaultSource(node_id=node, probability=prob))
                cumulative += prob
                if cumulative >= cumulative_threshold:
                    break

        return sources
