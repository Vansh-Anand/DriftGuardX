import math
from typing import Dict, List, Protocol

class LikelihoodEstimator(Protocol):
    def estimate_likelihood(self, intervention_node: str, root_cause: str, outcome: str) -> float:
        """
        P(outcome | intervention, root_cause)
        Returns a probability between 0.0 and 1.0.
        """
        ...

class HeuristicLikelihoodEstimator:
    """
    A clearly named heuristic estimator for prototype use.
    If we intervene on a node, and it WAS the root cause, it should heavily mitigate the failure.
    outcome in ["mitigated", "reproduced"]
    """
    def estimate_likelihood(self, intervention_node: str, root_cause: str, outcome: str) -> float:
        if intervention_node == root_cause:
            if outcome == "mitigated":
                return 0.9  # high likelihood of fixing it
            else:
                return 0.1
        else:
            if outcome == "mitigated":
                return 0.1  # low likelihood of fixing it if we didn't touch the root cause
            else:
                return 0.9


class RootCauseBeliefModel:
    def __init__(self, components: List[str]):
        if not components:
            self.beliefs = {}
        else:
            initial_p = 1.0 / len(components)
            self.beliefs = {c: initial_p for c in components}
            
    def _safe_prob(self, p: float) -> float:
        if math.isnan(p) or p < 0.0:
            return 0.0
        return min(1.0, p)

    def entropy(self) -> float:
        h = 0.0
        for p in self.beliefs.values():
            if p > 0:
                h -= p * math.log2(p)
        return max(0.0, h)

    def update(self, intervention_node: str, outcome: str, estimator: LikelihoodEstimator) -> None:
        """
        Updates beliefs in-place: P(C | O) \propto P(O | C) * P(C)
        """
        unnormalized = {}
        total = 0.0
        for c, prior in self.beliefs.items():
            likelihood = self._safe_prob(estimator.estimate_likelihood(intervention_node, c, outcome))
            posterior = likelihood * prior
            unnormalized[c] = posterior
            total += posterior
            
        if total <= 0.0:
            # Fallback to uniform if all hypotheses are zero
            initial_p = 1.0 / max(1, len(self.beliefs))
            self.beliefs = {c: initial_p for c in self.beliefs}
        else:
            self.beliefs = {c: unnormalized[c] / total for c in self.beliefs}

    def expected_information_gain(self, intervention_node: str, estimator: LikelihoodEstimator) -> float:
        """
        IG = H(Prior) - E[H(Posterior)]
        E[H(Posterior)] = sum_{O} P(O) * H(Posterior | O)
        where P(O) = sum_{C} P(O | C) * P(C)
        """
        outcomes = ["mitigated", "reproduced"]
        h_prior = self.entropy()
        
        expected_h_post = 0.0
        for o in outcomes:
            p_o = 0.0
            # Calculate P(O)
            for c, p_c in self.beliefs.items():
                p_o += self._safe_prob(estimator.estimate_likelihood(intervention_node, c, o)) * p_c
                
            if p_o > 0:
                # Calculate H(Posterior | O)
                h_post_o = 0.0
                for c, p_c in self.beliefs.items():
                    p_o_given_c = self._safe_prob(estimator.estimate_likelihood(intervention_node, c, o))
                    p_c_given_o = (p_o_given_c * p_c) / p_o
                    if p_c_given_o > 0:
                        h_post_o -= p_c_given_o * math.log2(p_c_given_o)
                        
                expected_h_post += p_o * h_post_o
                
        return max(0.0, h_prior - expected_h_post)

def calculate_graph_impact(graph_nodes: List[str], graph_edges: List[Dict[str, str]], intervention_node: str) -> float:
    """
    Calculates impact based on actual DAG descendants.
    impact_ratio = affected_descendants / total_nodes
    """
    if not graph_nodes:
        return 0.0
        
    descendants = set()
    queue = [intervention_node]
    
    # Simple BFS for descendants
    while queue:
        curr = queue.pop(0)
        descendants.add(curr)
        for edge in graph_edges:
            if edge.get("source_id") == curr:
                target = edge.get("target_id")
                if target and target not in descendants:
                    queue.append(target)
                    
    # The intervention node and all its descendants are considered affected
    return len(descendants) / len(graph_nodes)
