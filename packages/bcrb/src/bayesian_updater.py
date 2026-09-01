"""
DriftGuard-X v2 — BCRB Bayesian Updater
PRIVATE — All Rights Reserved.
"""

def update_posterior(
    prior: float,
    likelihood_given_cause: float,
    likelihood_given_not_cause: float
) -> float:
    """
    Updates the probability of a candidate being the root cause using Bayes' Theorem.
    
    P(Cause | Evidence) = (P(Evidence | Cause) * P(Cause)) / P(Evidence)
    
    P(Evidence) = P(Evidence | Cause) * P(Cause) + P(Evidence | ~Cause) * P(~Cause)
    
    Args:
        prior: P(Cause), the prior probability of the candidate.
        likelihood_given_cause: P(Evidence | Cause), the likelihood of observing 
                                the replay result if this was the true cause.
        likelihood_given_not_cause: P(Evidence | ~Cause), the likelihood of observing
                                    the replay result if this was NOT the true cause.
                                    
    Returns:
        The updated posterior probability, bounded [0, 1].
    """
    if prior <= 0.0:
        return 0.0
    if prior >= 1.0:
        return 1.0
        
    p_evidence = (likelihood_given_cause * prior) + (likelihood_given_not_cause * (1.0 - prior))
    
    if p_evidence == 0:
        return prior
        
    posterior = (likelihood_given_cause * prior) / p_evidence
    return max(0.0, min(1.0, posterior))
