"""
DriftGuard-X v2 — Replay Admissibility and Evidence Budget (RAEB)
Update 1: Flagship Admissibility Gateway
Update 2: Probabilistic Information Gain and Trusted Time integration
"""
import os
from datetime import UTC, datetime

from packages.contracts.src.models import (
    AdmissibilityScore,
    EquivalenceVector,
    RAEBEvaluation,
    ReplayEpisode,
    TraceArtifact,
)
from packages.replay.src.belief_model import (
    DeterminismEstimator,
    HeuristicLikelihoodEstimator,
    RootCauseBeliefModel,
    calculate_graph_impact,
)
from packages.replay.src.time_authority import TrustedTimestampEnvelope, TrustedTimeVerifier


class RAEBGateway:
    """
    Evaluates proposed counterfactual replays for admissibility as evidence.
    Computes an Equivalence Vector (freshness, determinism, dependency impact)
    and expected Information Gain using a proper Bayesian belief model.
    """
    def __init__(self, freshness_ttl_seconds: int = 3600, time_verifier: TrustedTimeVerifier | None = None):
        self.freshness_ttl_seconds = freshness_ttl_seconds
        self.time_verifier = time_verifier
        self.estimator = HeuristicLikelihoodEstimator()
        self.determinism_estimator = DeterminismEstimator()

    def evaluate_admissibility(
        self,
        live_trace: TraceArtifact,
        proposed_replay: ReplayEpisode,
        belief_model: RootCauseBeliefModel | None = None,
        trusted_timestamp: TrustedTimestampEnvelope | None = None
    ) -> RAEBEvaluation:
        """
        Evaluate if a proposed replay is admissible, allocating evidence budget.
        """
        if os.getenv("DGX_MODE") == "production":
            if not self.time_verifier:
                raise ValueError("Configuration error: TrustedTimeVerifier missing in production mode.")
            if not trusted_timestamp:
                raise ValueError("Production RAEB requires a TrustedTimestampEnvelope.")

        if trusted_timestamp:
            if self.time_verifier and not self.time_verifier.verify(trusted_timestamp):
                raise ValueError("TrustedTimestampEnvelope failed verification.")
            eval_time = trusted_timestamp.timestamp
        else:
            # Fallback for synthetic/tests ONLY. Production will fail fast earlier.
            eval_time = datetime.now(UTC)

        # Timezone check
        if eval_time.tzinfo is None or live_trace.created_at.tzinfo is None:
            raise ValueError("All timestamps must be timezone-aware (UTC). Naive datetimes rejected.")

        # 1. Freshness Score
        age_seconds = (eval_time - live_trace.created_at).total_seconds()

        if age_seconds < 0:
            # Clock skew boundary allowance could be configured, but for now strict.
            if age_seconds < -5:  # Allow up to 5s of ntp clock skew
                raise ValueError(f"Negative age detected ({age_seconds}s). Possible replay attack or extreme clock skew.")
            age_seconds = 0

        if age_seconds > self.freshness_ttl_seconds:
            freshness = 0.0
        else:
            freshness = max(0.0, 1.0 - (age_seconds / self.freshness_ttl_seconds))

        # 2. Determinism Score
        # 3. Dependency Impact Score (Calculated from DAG)
        # Using trace span IDs as mock graph nodes if a real graph isn't supplied
        graph_nodes = [s.span_id for s in live_trace.spans] if hasattr(live_trace, "spans") else ["mock_node"]
        graph_edges = []
        if hasattr(live_trace, "spans"):
            for s in live_trace.spans:
                if s.parent_span_id:
                    graph_edges.append({"source_id": s.parent_span_id, "target_id": s.span_id})

        component_id = getattr(proposed_replay, "component_id", None)
        if component_id and hasattr(live_trace, "spans"):
            # Find the span whose component_type matches the intervention target
            intervention_node = next(
                (s.span_id for s in live_trace.spans
                 if getattr(s, "component_type", "") == component_id),
                component_id  # fallback to component_id itself as node label
            )
        else:
            intervention_node = component_id or "mock_node"

        determinism = self.determinism_estimator.estimate(intervention_node)

        impact = calculate_graph_impact(graph_nodes, graph_edges, intervention_node)

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

        # Expected Information Gain calculation via Belief Model
        if belief_model is None:
            belief_model = RootCauseBeliefModel(components=graph_nodes)
        expected_ig = belief_model.expected_information_gain(intervention_node, self.estimator)

        # We append a simple metadata tracking block
        estimator_name = self.estimator.__class__.__name__

        # Overall Information Gain combines expected entropy reduction with determinism
        info_gain = determinism * expected_ig
        risk = (1.0 - freshness) * impact

        eval_result = RAEBEvaluation(
            equivalence_vector=vector,
            admissibility=admissibility,
            information_gain_estimate=info_gain,
            risk_score=risk,
            rejection_reason=rejection_reason
        )
        # Attach metadata explicitly per requirements
        eval_result.ig_estimator_metadata = {"model": estimator_name, "raw_expected_ig": expected_ig}
        return eval_result
