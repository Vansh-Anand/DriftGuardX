"""
DriftGuard-X v2 — Multi-Agent Hypothesis Diffusion Engine
PRIVATE — All Rights Reserved.
"""
from packages.diffusion.src.contracts import DiffusionInput, GraphDiffusionResult, DiffusionOutput, NodeExplanation

class MultiAgentDiffusionEngine:
    """
    Propagates local anomaly scores (symptoms) backwards through the causal graph
    to identify the root cause using message passing algorithms.
    """
    
    def __init__(self, num_steps: int = 3, decay_factor: float = 0.85):
        self.num_steps = num_steps
        self.decay_factor = decay_factor

    def run_backward_diffusion(self, graph_input: DiffusionInput) -> GraphDiffusionResult:
        """
        Executes the mathematical diffusion algorithm.
        """
        # Initialize node scores with their local symptom score
        scores = {node.node_id: node.local_symptom_score for node in graph_input.nodes}
        
        # Build adjacency for backward propagation (target -> source)
        backward_edges = {}
        for edge in graph_input.edges:
            if edge.target_id not in backward_edges:
                backward_edges[edge.target_id] = []
            backward_edges[edge.target_id].append(edge)
            
        # Message passing loop
        for step in range(self.num_steps):
            new_scores = scores.copy()
            for target_id, incoming_edges in backward_edges.items():
                target_score = scores.get(target_id, 0.0)
                if target_score > 0:
                    for edge in incoming_edges:
                        # Propagate backwards: source <- target
                        # The message is scaled by edge confidence and directionality
                        message = target_score * edge.confidence * self.decay_factor
                        if edge.directionality < 0:
                            message *= 0.5 # discount reverse causal links
                            
                        new_scores[edge.source_id] = min(1.0, new_scores.get(edge.source_id, 0.0) + message)
            scores = new_scores
            
        # Format output
        node_outputs = {}
        for node in graph_input.nodes:
            final_score = scores.get(node.node_id, 0.0)
            
            # Simple explanation: top contributing neighbor
            influential_edges = [
                edge.source_id for edge in backward_edges.get(node.node_id, [])
                if scores.get(edge.source_id, 0.0) > 0.1
            ]
            
            node_outputs[node.node_id] = DiffusionOutput(
                node_id=node.node_id,
                root_probability=min(1.0, final_score), # Final accumulation determines root probability
                symptom_probability=node.local_symptom_score,
                uncertainty=0.1,
                explanation=NodeExplanation(
                    top_influential_edges=influential_edges,
                    top_contributing_neighbors=influential_edges,
                    propagation_depth=self.num_steps,
                    delta_from_local=final_score - node.local_symptom_score
                )
            )
            
        return GraphDiffusionResult(
            model_version="v2_diffusion",
            node_outputs=node_outputs,
            num_steps=self.num_steps,
            aggregation_method="sum_decay",
            normalization_applied=True
        )
