"""
DriftGuard-X v2 — Replay Admissibility and Evidence Budget (RAEB)
Update 1: Flagship Admissibility Gateway
Update 2: Envelope-aware admissibility (additive — existing API unchanged)
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

    # ── Envelope-Aware Admissibility (Update 2) ──────────────────────────────

    def evaluate_with_envelope(
        self,
        live_trace: TraceArtifact,
        proposed_replay: ReplayEpisode,
        envelope: "ReplayEquivalenceEnvelope",
        current_time: Optional[datetime] = None,
        divergence_report: Optional["CausalDivergenceReport"] = None,
    ) -> RAEBEvaluation:
        """
        Envelope-aware admissibility evaluation.

        This extends the base admissibility check by:
          1. Validating envelope cryptographic integrity.
          2. Checking that the envelope's tenant matches the trace.
          3. Using the envelope's descendant count to refine the dependency
             impact score (instead of guessing from total span count).
          4. Adjusting determinism score based on nondeterministic variable count.

        The existing ``evaluate_admissibility`` signature is NOT modified.
        This method is additive.

        Parameters
        ----------
        live_trace
            The original TraceArtifact.
        proposed_replay
            The ReplayEpisode to evaluate.
        envelope
            The pre-computed ReplayEquivalenceEnvelope.
        current_time
            Explicit trusted timestamp (overridden by TimeAuthority if set).

        Returns
        -------
        RAEBEvaluation
            With envelope-refined scores and any envelope-specific rejection reason.
        """
        # Import here to avoid circular dependency at module load time
        from packages.contracts.src.envelope import ReplayEquivalenceEnvelope

        # 1. Validate envelope integrity
        if not envelope.verify_integrity():
            return RAEBEvaluation(
                equivalence_vector=EquivalenceVector(
                    freshness_score=0.0,
                    determinism_score=0.0,
                    dependency_impact_score=0.0,
                ),
                admissibility=AdmissibilityScore.UNSUPPORTED,
                information_gain_estimate=0.0,
                risk_score=1.0,
                rejection_reason="Envelope hash integrity check failed. Possible tampering.",
            )

        # 2. Cross-tenant check
        if envelope.tenant_id != live_trace.tenant_id:
            return RAEBEvaluation(
                equivalence_vector=EquivalenceVector(
                    freshness_score=0.0,
                    determinism_score=0.0,
                    dependency_impact_score=0.0,
                ),
                admissibility=AdmissibilityScore.UNSUPPORTED,
                information_gain_estimate=0.0,
                risk_score=1.0,
                rejection_reason=(
                    f"Envelope tenant {envelope.tenant_id} does not match "
                    f"trace tenant {live_trace.tenant_id}."
                ),
            )

        # 3. Get base evaluation
        base_eval = self.evaluate_admissibility(
            live_trace, proposed_replay, current_time
        )

        # 4. Refine dependency impact using envelope's descendant count
        total_nodes = len(envelope.allowed_descendant_components) + \
                      len(envelope.forbidden_divergence_components) + 1  # +1 for intervention
        descendant_count = len(envelope.allowed_descendant_components)

        if total_nodes > 0:
            # Impact is the ratio of affected components to total
            # Lower ratio → higher score (fewer side effects → better experiment)
            impact_ratio = descendant_count / total_nodes
            refined_impact = max(0.0, 1.0 - impact_ratio)
        else:
            refined_impact = base_eval.equivalence_vector.dependency_impact_score

        # 5. Refine determinism based on nondeterministic variable count
        total_vars = (len(envelope.frozen_variables) +
                      len(envelope.intervened_variables) +
                      len(envelope.nondeterministic_variables) +
                      len(envelope.exogenous_variables))
        nondet_count = len(envelope.nondeterministic_variables)

        if total_vars > 0:
            nondet_ratio = nondet_count / total_vars
            # Each nondeterministic variable degrades determinism
            refined_determinism = max(0.0, 1.0 - nondet_ratio)
        else:
            refined_determinism = base_eval.equivalence_vector.determinism_score

        refined_vector = EquivalenceVector(
            freshness_score=base_eval.equivalence_vector.freshness_score,
            determinism_score=refined_determinism,
            dependency_impact_score=refined_impact,
        )

        # 6. Recompute composite and classification
        composite = (refined_vector.freshness_score +
                     refined_vector.determinism_score +
                     refined_vector.dependency_impact_score) / 3.0

        if refined_vector.freshness_score == 0.0:
            admissibility = AdmissibilityScore.UNSUPPORTED
            rejection_reason = "Trace is completely stale."
        elif composite >= 0.8:
            admissibility = AdmissibilityScore.ADMISSIBLE
            rejection_reason = None
        elif composite >= 0.5:
            admissibility = AdmissibilityScore.LIMITED
            rejection_reason = "Envelope-refined composite score is marginal."
        else:
            admissibility = AdmissibilityScore.UNSUPPORTED
            rejection_reason = "Envelope-refined equivalence below threshold."

        # 7. Recompute information gain with envelope-refined impact
        N = max(1.0, float(total_nodes))
        K = max(1e-9, min(N, float(descendant_count + 1)))  # +1 for intervention

        if K <= 1e-9 or K >= N - 1e-9:
            expected_ig = 0.0
        else:
            p_k = K / N
            p_nk = (N - K) / N
            h_prior = math.log2(N)
            e_h_post = p_k * math.log2(K) + p_nk * math.log2(N - K)
            expected_ig = max(0.0, h_prior - e_h_post)

        info_gain = refined_determinism * expected_ig
        risk = (1.0 - refined_vector.freshness_score) * (1.0 - refined_impact)

        # 8. Check Divergence Report (if provided)
        if divergence_report is not None:
            if not divergence_report.verify_integrity():
                admissibility = AdmissibilityScore.UNSUPPORTED
                rejection_reason = "Divergence report hash integrity check failed. Possible tampering."
                info_gain = 0.0
                risk = 1.0
            elif not divergence_report.valid:
                admissibility = AdmissibilityScore.UNSUPPORTED
                rejection_reason = f"Causal divergence escaped frontier: {divergence_report.invalidation_reason}"
                info_gain = 0.0
                risk = 1.0

        return RAEBEvaluation(
            equivalence_vector=refined_vector,
            admissibility=admissibility,
            information_gain_estimate=info_gain,
            risk_score=risk,
            rejection_reason=rejection_reason,
        )

