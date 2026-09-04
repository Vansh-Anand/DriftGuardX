"""
DriftGuard-X v2 — BCRB Dynamic Candidate Generation
PRIVATE — All Rights Reserved.
"""

import uuid

from packages.bcrb.src.calibration import BCRBCalibrator
from packages.bcrb.src.utility_function import calculate_candidate_utility
from packages.contracts.src.agent_models import AgentInvocation
from packages.contracts.src.bcrb_models import BCRBCandidate, BCRBSession, StoppingCondition, UnifiedCandidatePrior
from packages.contracts.src.graph import EdgeType, NodeType
from packages.contracts.src.models import ComponentType, InterventionType
from packages.detectors.src.gat_inference import GATTraceDetector
from packages.diffusion.src.contracts import DiffusionInput, EdgeFeatures, NodeState
from packages.diffusion.src.engine import MultiAgentDiffusionEngine


class CandidatePlanner:
    """
    Generates BCRBCandidates by evaluating causal priors and computing
    budget-constrained mathematical utility.
    """

    def __init__(self, tenant_id: str, calibrator: BCRBCalibrator | None = None):
        self.tenant_id = tenant_id
        self.diffusion_engine = MultiAgentDiffusionEngine()
        self.gat_detector = GATTraceDetector()
        self.calibrator = calibrator or BCRBCalibrator()

    def generate_candidates(
        self, invocations: list[AgentInvocation], run_id: str, failure_symptom: str
    ) -> list[BCRBCandidate]:
        """
        Analyze the invocation history to propose targeted interventions based on priors.
        """
        candidates: list[BCRBCandidate] = []

        if not invocations:
            return candidates

        # 1. Build the mathematically accurate graph and spans from the invocation trace
        nodes = []
        edges = []
        spans = []

        for i, inv in enumerate(invocations):
            role_type = inv.agent_identity.agent_type if inv.agent_identity else inv.agent_name

            node_type = NodeType.COMPUTATION
            if role_type in ["retriever", "retrieval"]:
                node_type = NodeType.INFORMATION
            elif role_type == "policy":
                node_type = NodeType.POLICY

            # Extract true trace errors rather than mocking local symptom
            is_error = inv.metadata.get("is_error", False)
            if i == len(invocations) - 1 and failure_symptom:
                is_error = True
                
            local_symptom = 1.0 if is_error else 0.0

            node_id = f"node_{i}_{role_type}"
            nodes.append(
                NodeState(
                    node_id=node_id,
                    local_symptom_score=local_symptom,
                    severity_weight=1.0,
                    node_type=node_type,
                )
            )

            # Build GAT compatible span
            dur = 0.0
            if inv.start_time and inv.end_time:
                dur = (inv.end_time - inv.start_time).total_seconds() * 1000.0

            parent_id = None
            if i > 0:
                prev_inv = invocations[i-1]
                prev_role = prev_inv.agent_identity.agent_type if prev_inv.agent_identity else prev_inv.agent_name
                parent_id = f"node_{i-1}_{prev_role}"

            span = {
                "span_id": node_id,
                "duration_ms": dur,
                "operation_name": role_type,
                "is_error": is_error,
                "parent_id": parent_id
            }
            spans.append(span)

            # Link sequence as causal edges
            if parent_id:
                edges.append(
                    EdgeFeatures(
                        source_id=parent_id,
                        target_id=node_id,
                        edge_type=EdgeType.EXECUTION_ORDER,
                        confidence=0.9,
                        directionality=1.0,
                    )
                )

        # 2. Run GAT Trace Anomaly Detection
        gat_result = self.gat_detector.detect_trace_anomaly(spans)
        gat_candidates = gat_result.get("root_cause_candidates", [])
        
        # Build GAT score map for easy lookup
        gat_scores = {}
        for gc in gat_candidates:
            # GAT uses a combination of error and self time to rank candidates.
            gat_scores[gc["span_id"]] = gc["self_time_ratio"] * (1.0 if not gc["is_error"] else 2.0)

        # 3. Run backward diffusion to propagate anomaly scores
        diffusion_input = DiffusionInput(nodes=nodes, edges=edges)
        diffusion_result = self.diffusion_engine.run_backward_diffusion(diffusion_input)

        # 4. Create UnifiedCandidatePrior
        for node_id, output in diffusion_result.node_outputs.items():
            diff_score = output.root_probability
            gat_score = gat_scores.get(node_id, 0.0)
            
            # Find matching node state
            node_state = next((n for n in nodes if n.node_id == node_id), None)
            symptom_score = node_state.local_symptom_score if node_state else 0.0

            # Data-driven prior calculation via BCRBCalibrator
            combined_prior, prior_prov = self.calibrator.estimate_prior(
                gat_score=gat_score,
                diff_score=diff_score,
                symptom_score=symptom_score,
            )

            if combined_prior > 0.05:  # Plausible candidate threshold
                comp_type = ComponentType.GENERATOR
                int_type = InterventionType.ALTERNATE_STABLE
                if "retriev" in node_id:
                    comp_type = ComponentType.RETRIEVER
                    int_type = InterventionType.ROLLBACK
                elif "policy" in node_id:
                    comp_type = ComponentType.POLICY_CHECK
                    int_type = InterventionType.CONFIG_PATCH

                evidence_breakdown = {
                    "gat_is_fault_trace": gat_result.get("is_fault", False),
                    "diffusion_explanation": output.explanation.model_dump(),
                    "is_synthetic_gat": not self.gat_detector.is_loaded,
                    "edge_evidence": "EXECUTION_ORDER",
                    "calibration": prior_prov,
                }

                unified_prior = UnifiedCandidatePrior(
                    candidate_component=comp_type.value,
                    derived_gat_signal=gat_score,
                    detector_probability=gat_result.get("fault_probability"),
                    diffusion_score=diff_score,
                    symptom_evidence=symptom_score,
                    combined_prior=combined_prior,
                    evidence_breakdown=evidence_breakdown,
                )

                # Data-driven candidate parameter estimation
                edge_pairs = [(getattr(e, "source_id", getattr(e, "source_node_id", "")), getattr(e, "target_id", getattr(e, "target_node_id", ""))) for e in edges]
                all_ids = [n.node_id for n in nodes]
                est_cost = self.calibrator.estimate_candidate_cost(comp_type.value)
                est_blast_radius = self.calibrator.estimate_candidate_blast_radius(
                    comp_type.value, causal_graph_edges=edge_pairs, all_nodes=all_ids
                )
                est_risk = self.calibrator.estimate_candidate_risk(comp_type.value, int_type.value)
                est_reliability_delta = 0.8
                est_info_gain = 0.6
                
                # Calculate true BCRB Utility based on calibrated unified prior
                utility = calculate_candidate_utility(
                    probability=combined_prior,
                    expected_reliability_delta=est_reliability_delta,
                    information_gain=est_info_gain,
                    cost=est_cost,
                    risk=est_risk,
                    blast_radius=est_blast_radius,
                )
                
                from packages.contracts.src.bcrb_models import ReplayCost, CausalEvidence, CounterfactualSupport

                candidates.append(
                    BCRBCandidate(
                        candidate_id=uuid.uuid4(),
                        component_type=comp_type,
                        intervention_type=int_type,
                        estimated_utility=utility,
                        cost_estimate=ReplayCost(total_cost=est_cost, measurement_status="ESTIMATED"),
                        risk_estimate=est_risk,
                        blast_radius_estimate=est_blast_radius,
                        expected_reliability_delta=est_reliability_delta,
                        expected_information_gain=est_info_gain,
                        causal_evidence=CausalEvidence(
                            prior=combined_prior, 
                            counterfactual_support=CounterfactualSupport(),
                            evidence_provenance="Derived from GAT and Diffusion priors."
                        ),
                        metadata={
                            "rationale": f"Unified Prior calculated: {combined_prior:.2f}",
                            "prior_evidence": unified_prior.model_dump(),
                        },
                    )
                )

        # Sort candidates by utility descending
        candidates.sort(key=lambda c: c.estimated_utility, reverse=True)
        return candidates

    def evaluate_stopping_conditions(
        self, session: BCRBSession, min_confidence: float = 0.9
    ) -> StoppingCondition | None:
        """
        Evaluate if the session should terminate based on budget or utility.
        """
        if session.total_spent_usd >= session.budget_usd:
            return StoppingCondition.BUDGET_EXHAUSTED

        if not session.candidates:
            return StoppingCondition.ALL_SAFE_CANDIDATES_TESTED

        best_candidate = max(session.candidates, key=lambda c: c.estimated_utility, default=None)
        if best_candidate and best_candidate.estimated_utility < 0.1:
            return StoppingCondition.EXPECTED_UTILITY_BELOW_THRESHOLD

        return None
