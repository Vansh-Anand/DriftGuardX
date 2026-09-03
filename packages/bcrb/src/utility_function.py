"""
DriftGuard-X v2 — BCRB Utility Function
PRIVATE — All Rights Reserved.
"""


def calculate_candidate_utility(
    probability: float,
    expected_reliability_delta: float,
    information_gain: float,
    cost: float,
    risk: float,
    blast_radius: float,
    lambda_risk: float = 1.0,
    mu_blast: float = 1.0,
    epsilon: float = 1e-6,
) -> float:
    """
    Calculates the true utility for a candidate intervention based on the
    budget-constrained causal selection formula:

    U_i = (P_i * E[ΔR_i] * IG_i) / (C_i + λ*Risk_i + μ*BlastRadius_i)

    Args:
        probability: P(cause_i), the causal prior/posterior.
        expected_reliability_delta: E[ΔR_i], expected reliability improvement.
        information_gain: IG_i, expected information gain from the experiment.
        cost: C_i, expected monetary or temporal cost of the replay.
        risk: Risk_i, risk of the intervention.
        blast_radius: BlastRadius_i, expected blast radius.
        lambda_risk: Weight for risk penalty.
        mu_blast: Weight for blast radius penalty.
        epsilon: Small constant to prevent division by zero.

    Returns:
        The calculated utility value.
    """
    numerator = probability * expected_reliability_delta * information_gain
    denominator = cost + (lambda_risk * risk) + (mu_blast * blast_radius) + epsilon

    return numerator / denominator
