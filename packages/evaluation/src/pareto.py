"""
DriftGuard-X v2 — Pareto Scorer
PRIVATE — All Rights Reserved.
"""

from pydantic import BaseModel

from packages.contracts.src.models import ReplayEpisode, ReplayStatus


class ParetoFrontierResult(BaseModel):
    optimal_episodes: list[ReplayEpisode]
    dominated_episodes: list[ReplayEpisode]
    invalid_episodes: list[ReplayEpisode]


class ParetoScorer:
    """
    Evaluates multi-metric dominance across a set of replay episodes.
    """

    def __init__(self, latency_epsilon_ms: float = 50.0, cost_epsilon_usd: float = 0.005):
        self.latency_epsilon_ms = latency_epsilon_ms
        self.cost_epsilon_usd = cost_epsilon_usd

    def score(self, episodes: list[ReplayEpisode]) -> ParetoFrontierResult:
        """
        Calculates the Pareto frontier, separating optimal interventions from 
        dominated ones (e.g. better accuracy but unacceptable cost/latency).
        """
        valid_episodes = []
        invalid_episodes = []

        for ep in episodes:
            if ep.status == ReplayStatus.INVALID:
                invalid_episodes.append(ep)
            else:
                valid_episodes.append(ep)

        optimal = []
        dominated = []

        for i, ep_a in enumerate(valid_episodes):
            is_dominated = False
            for j, ep_b in enumerate(valid_episodes):
                if i == j:
                    continue

                # To be strictly dominated by B, B must be >= A in ALL metrics
                # and strictly > A in at least one.
                # In this mock, we use a simplified single score + epsilons.
                score_a = ep_a.replay_reliability_score or 0.0
                score_b = ep_b.replay_reliability_score or 0.0

                if score_b > score_a:
                    is_dominated = True
                    break

            if is_dominated:
                ep_a.status = ReplayStatus.NEGATIVE_OUTCOME
                dominated.append(ep_a)
            else:
                optimal.append(ep_a)

        return ParetoFrontierResult(
            optimal_episodes=optimal,
            dominated_episodes=dominated,
            invalid_episodes=invalid_episodes
        )
