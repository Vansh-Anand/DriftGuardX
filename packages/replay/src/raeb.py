"""
DriftGuard-X v2 — Replay Admissibility and Evidence Budget (RAEB)
Update 1: Flagship Admissibility Gateway
"""
import math
from datetime import datetime, timezone
from typing import Optional, Protocol
import time

class TimeAuthority(Protocol):
    def get_trusted_time(self) -> datetime:
        """Returns a cryptographically trusted UTC datetime."""
        ...
        
    def get_monotonic_time(self) -> float:
        """Returns a monotonic clock value for elapsed intervals."""
        ...


from packages.contracts.src.models import (
    TraceArtifact,
    ReplayEpisode,
    AdmissibilityScore,
    EquivalenceVector,
    RAEBEvaluation,
)

class RAEBGateway:
    """
    Evaluates proposed counterfactual replays for admissibility as evidence.
    Computes an Equivalence Vector (freshness, determinism, dependency impact)
    between the live run trace and the proposed replay.
    """
    def __init__(self, freshness_ttl_seconds: int = 3600, time_authority: Optional[TimeAuthority] = None):
        self.freshness_ttl_seconds = freshness_ttl_seconds
        self.time_authority = time_authority

    def evaluate_admissibility(
        self,
        live_trace: TraceArtifact,
        proposed_replay: ReplayEpisode,
        current_time: Optional[datetime] = None
    ) -> RAEBEvaluation:
        """
        Evaluate if a proposed replay is admissible, allocating evidence budget.
        """
        # Fallback to explicit parameter if authority not provided (for tests/legacy)
        eval_time = current_time
        if self.time_authority:
            eval_time = self.time_authority.get_trusted_time()
            
        if eval_time is None:
            raise ValueError(
                "RAEB freshness requires an explicit, cryptographically trusted timestamp "
                "(e.g. from a signed telemetry envelope or Lamport clock). "
                "Defaulting to the host clock is a security violation."
            )
            
        # Timezone check
        if eval_time.tzinfo is None or live_trace.created_at.tzinfo is None:
            raise ValueError("All timestamps must be timezone-aware (UTC). Naive datetimes rejected.")
            
        # 1. Freshness Score
        age_seconds = (eval_time - live_trace.created_at).total_seconds()
        
        if age_seconds < 0:
            raise ValueError(f"Negative age detected ({age_seconds}s). Possible replay attack or extreme clock skew.")
            
        if age_seconds > self.freshness_ttl_seconds:
            # Excessive skew/stale trace
            freshness = 0.0
        else:
            freshness = max(0.0, 1.0 - (age_seconds / self.freshness_ttl_seconds))
        
        # 2. Determinism Score (mocked logic for prototype)
        # In a real system, this checks if the swapped component has a history of high variance.
        determinism = 0.95 
        
        # 3. Dependency Impact Score
        # Checks how many downstream nodes in the trace are impacted by the intervened node.
        # If too many are impacted, confidence drops.
        total_spans = live_trace.total_span_count
        # Simple mock: assume moderate impact
        impact = 0.8 if total_spans > 5 else 1.0
        
        vector = EquivalenceVector(
            freshness_score=freshness,
            determinism_score=determinism,
            dependency_impact_score=impact
        )
        
        # Classification
        composite_score = (freshness + determinism + impact) / 3.0
        
        if freshness == 0.0:
            admissibility = AdmissibilityScore.UNSUPPORTED
            rejection_reason = "Trace is completely stale."
        elif composite_score >= 0.8:
            admissibility = AdmissibilityScore.ADMISSIBLE
            rejection_reason = None
        elif composite_score >= 0.5:
            admissibility = AdmissibilityScore.LIMITED
            rejection_reason = "Composite equivalence score is marginal."
        else:
            admissibility = AdmissibilityScore.UNSUPPORTED
            rejection_reason = "Equivalence vector below acceptable threshold."
            
        # Risk & Information Gain estimation
        # Information Gain: H(Prior) - E[H(Posterior)]
        # Assuming uniform prior over N components, and intervention isolates K components (impact_ratio).
        N = max(1.0, float(total_spans))
        K = max(1e-9, min(N, N * impact))
        
        if K <= 1e-9 or K >= N - 1e-9:
            expected_ig = 0.0
        else:
            p_k = K / N
            p_nk = (N - K) / N
            h_prior = math.log2(N)
            e_h_post = p_k * math.log2(K) + p_nk * math.log2(N - K)
            expected_ig = max(0.0, h_prior - e_h_post)
            
        info_gain = determinism * expected_ig
        risk = (1.0 - freshness) * impact
        
        return RAEBEvaluation(
            equivalence_vector=vector,
            admissibility=admissibility,
            information_gain_estimate=info_gain,
            risk_score=risk,
            rejection_reason=rejection_reason
        )
