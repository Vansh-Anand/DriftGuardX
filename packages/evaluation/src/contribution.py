"""
DriftGuard-X v2 — Causal Contribution Vector
PRIVATE — All Rights Reserved.
"""

import math

from pydantic import BaseModel


class ContributionVector(BaseModel):
    """
    Multidimensional scoring of an intervention's causal impact.
    """

    reliability_improvement_mean: float
    reliability_improvement_variance: float
    reliability_bootstrap_lower: float
    reliability_bootstrap_upper: float
    cost_delta_usd: float
    latency_delta_ms: float
    risk_penalty: float
    invalid_rate: float
    trials_n: int

    @property
    def aggregate_score(self) -> float:
        """
        Aggregate causal contribution score.
        Score = max(0, Reliability) - (CostWeight * Cost) - (LatencyWeight * Latency) - RiskPenalty
        Defaults: CostWeight=10.0 per USD, LatencyWeight=0.0001 per ms
        """
        # If invalid rate is too high (> 0.5), we heavily penalize
        if self.invalid_rate > 0.5:
            return 0.0

        base_gain = max(0.0, self.reliability_improvement_mean)
        cost_impact = max(0.0, self.cost_delta_usd * 10.0)
        latency_impact = max(0.0, self.latency_delta_ms * 0.0001)

        return max(0.0, base_gain - cost_impact - latency_impact - self.risk_penalty)


def calculate_contribution_vector(
    reliability_improvements: list[float],
    cost_delta_usd: float,
    latency_delta_ms: float,
    risk_penalty: float,
    invalid_count: int,
    total_trials: int,
) -> ContributionVector:
    """
    Calculates mean, variance, and simple bootstrap bounds from repeated trials.
    """
    if not reliability_improvements:
        return ContributionVector(
            reliability_improvement_mean=0.0,
            reliability_improvement_variance=0.0,
            reliability_bootstrap_lower=0.0,
            reliability_bootstrap_upper=0.0,
            cost_delta_usd=cost_delta_usd,
            latency_delta_ms=latency_delta_ms,
            risk_penalty=risk_penalty,
            invalid_rate=invalid_count / max(1, total_trials),
            trials_n=total_trials,
        )

    n = len(reliability_improvements)
    mean = sum(reliability_improvements) / n
    variance = sum((x - mean) ** 2 for x in reliability_improvements) / n if n > 1 else 0.0

    # Simple approx for CI: mean +/- 1.96 * std_err
    std_err = math.sqrt(variance) / math.sqrt(n) if n > 1 else 0.0
    lower = mean - (1.96 * std_err)
    upper = mean + (1.96 * std_err)

    return ContributionVector(
        reliability_improvement_mean=mean,
        reliability_improvement_variance=variance,
        reliability_bootstrap_lower=lower,
        reliability_bootstrap_upper=upper,
        cost_delta_usd=cost_delta_usd,
        latency_delta_ms=latency_delta_ms,
        risk_penalty=risk_penalty,
        invalid_rate=invalid_count / total_trials,
        trials_n=total_trials,
    )
