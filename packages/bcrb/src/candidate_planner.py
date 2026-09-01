"""
DriftGuard-X v2 — BCRB Dynamic Candidate Generation
PRIVATE — All Rights Reserved.
"""
from typing import Any
import uuid

from packages.contracts.src.agent_models import AgentInvocation
from packages.contracts.src.bcrb_models import BCRBCandidate, BCRBSession, StoppingCondition
from packages.contracts.src.models import ComponentType, InterventionType
from packages.bcrb.src.utility_function import calculate_candidate_utility


from packages.contracts.src.graph import EdgeType, NodeType
from packages.diffusion.src.contracts import DiffusionInput, EdgeFeatures, NodeState
from packages.diffusion.src.engine import MultiAgentDiffusionEngine
from packages.detectors.src.gat_inference import GATTraceDetector


class CandidatePlanner:
    """
    Generates BCRBCandidates by evaluating causal priors and computing 
    budget-constrained mathematical utility.
    """
    
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.diffusion_engine = MultiAgentDiffusionEngine()
        self.gat_detector = GATTraceDetector()

    def generate_candidates(
        self, 
        invocations: list[AgentInvocation], 
        run_id: str,
        failure_symptom: str
    ) -> list[BCRBCandidate]:
        """
        Analyze the invocation history to propose targeted interventions based on priors.
        """
        candidates: list[BCRBCandidate] = []
        
        if not invocations:
            return candidates

        # Phase 4: Use GAT + Diffusion to calculate the causal prior (P(cause_i))
        
        # 1. Build the mathematical graph from the invocation trace
        nodes = []
        edges = []
        
        for i, inv in enumerate(invocations):
            role_type = inv.agent_identity.agent_type if inv.agent_identity else inv.agent_name
            
            # Map role to Item 18 NodeType taxonomy
            node_type = NodeType.COMPUTATION
            if role_type in ["retriever", "retrieval"]:
                node_type = NodeType.INFORMATION
            elif role_type == "policy":
                node_type = NodeType.POLICY
            
            # Use GAT or localized symptom score. (Mocking local symptom based on position/failure)
            local_symptom = 0.9 if (i == len(invocations) - 1 and failure_symptom) else 0.0
            
            nodes.append(NodeState(
                node_id=f"node_{i}_{role_type}",
                local_symptom_score=local_symptom,
                severity_weight=1.0,
                node_type=node_type
            ))
            
            # Link sequence as causal edges
            if i > 0:
                edges.append(EdgeFeatures(
                    source_id=f"node_{i-1}_{invocations[i-1].agent_name}",
                    target_id=f"node_{i}_{role_type}",
                    edge_type=EdgeType.CONTROL_FLOW,
                    confidence=0.9,
                    directionality=1.0
                ))
                
        diffusion_input = DiffusionInput(nodes=nodes, edges=edges)
        
        # 2. Run backward diffusion to propagate anomaly scores
        diffusion_result = self.diffusion_engine.run_backward_diffusion(diffusion_input)
        
        # 3. Create candidates based on the mathematically derived prior
        for node_id, output in diffusion_result.node_outputs.items():
            if output.root_probability > 0.1: # Only propose if mathematically plausible
                
                # Determine component type from node ID string for legacy mapping
                comp_type = ComponentType.GENERATOR
                int_type = InterventionType.ALTERNATE_STABLE
                if "retriev" in node_id:
                    comp_type = ComponentType.RETRIEVER
                    int_type = InterventionType.ROLLBACK
                elif "policy" in node_id:
                    comp_type = ComponentType.POLICY_CHECK
                    int_type = InterventionType.CONFIG_PATCH
                    
                # 4. Calculate true BCRB Utility
                utility = calculate_candidate_utility(
                    probability=output.root_probability,
                    expected_reliability_delta=0.8,
                    information_gain=0.6,
                    cost=0.02,
                    risk=0.1,
                    blast_radius=0.1
                )
                
                candidates.append(
                    BCRBCandidate(
                        candidate_id=uuid.uuid4(),
                        component_type=comp_type,
                        intervention_type=int_type,
                        estimated_utility=utility,
                        cost_estimate=0.02,
                        metadata={
                            "rationale": f"Diffusion engine flagged root probability: {output.root_probability:.2f}",
                            "prior": output.root_probability,
                            "explanation": output.explanation.model_dump()
                        },
                    )
                )

        # Sort candidates by utility descending
        candidates.sort(key=lambda c: c.estimated_utility, reverse=True)
        return candidates

    def evaluate_stopping_conditions(self, session: BCRBSession, min_confidence: float = 0.9) -> StoppingCondition | None:
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
