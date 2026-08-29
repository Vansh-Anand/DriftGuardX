import math
from typing import Protocol


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

class DeterminismEstimator:
    """
    Estimates per-component determinism from observed output variance.
    Falls back to a conservative 0.7 for unseen components (not 0.95 — that was
    overconfident and masked real uncertainty in RAEB scoring).

    Variance is tracked as the fraction of runs where the component produced
    the same output hash as the previous run. Updated via record_observation().
    """

    # Conservative default for unseen components
    _DEFAULT_DETERMINISM = 0.7

    def __init__(self) -> None:
        self._run_counts: dict[str, int] = {}
        self._stable_counts: dict[str, int] = {}

    def record_observation(self, component_id: str, output_hash: str) -> None:
        """Record an output hash for a component run."""
        last_hash_key = f"_last_{component_id}"
        last = self._stable_counts.get(last_hash_key)  # type: ignore[arg-type]
        self._run_counts[component_id] = self._run_counts.get(component_id, 0) + 1
        # We store last hash as a special key to avoid a separate dict
        if not hasattr(self, '_last_hashes'):
            self._last_hashes: dict[str, str] = {}
        prev = self._last_hashes.get(component_id)
        if prev is not None and prev == output_hash:
            self._stable_counts[component_id] = self._stable_counts.get(component_id, 0) + 1
        self._last_hashes[component_id] = output_hash

    def estimate(self, component_id: str) -> float:
        """Returns empirical determinism score for the component, or conservative default."""
        runs = self._run_counts.get(component_id, 0)
        if runs < 2:
            return self._DEFAULT_DETERMINISM
        stable = self._stable_counts.get(component_id, 0)
        # Laplace-smooth: add 1 stable and 2 total to avoid extreme 0 or 1
        return (stable + 1) / (runs + 2)


class RootCauseBeliefModel:
    """
    Bayesian belief model over root-cause candidates.

    Unseen arms (candidates not yet observed) get Laplace-smoothed priors
    so they are always selectable by the experiment planner — fixes the
    BCRB unseen-arm zero-weight bug where unseen components could never be chosen.
    """

    # Laplace smoothing pseudo-count for unseen components
    _LAPLACE_ALPHA = 0.1

    def __init__(self, components: list[str]) -> None:
        if not components:
            self.beliefs: dict[str, float] = {}
        else:
            # Laplace-smoothed uniform prior: each component gets alpha pseudo-count
            total = len(components) * (1.0 + self._LAPLACE_ALPHA)
            self.beliefs = {c: (1.0 + self._LAPLACE_ALPHA) / total for c in components}

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
        r"""
        Updates beliefs in-place: P(C | O) \propto P(O | C) * P(C)
        """
        unnormalized = {}
        total = 0.0
        for c, prior in self.beliefs.items():
            likelihood = self._safe_prob(estimator.estimate_likelihood(intervention_node, c, outcome))
            posterior = likelihood * prior
            unnormalized[c] = posterior
            total += posterior

        if total <= 0.0 or math.isnan(total):
            # Fallback to uniform if all hypotheses are zero or NaNs occurred
            initial_p = 1.0 / max(1, len(self.beliefs))
            self.beliefs = {c: initial_p for c in self.beliefs}
        else:
            self.beliefs = {c: self._safe_prob(unnormalized[c] / total) for c in self.beliefs}

        # Ensure sum to 1 explicitly to avoid float drift
        s = sum(self.beliefs.values())
        if s > 0:
            self.beliefs = {c: v / s for c, v in self.beliefs.items()}

    def expected_information_gain(self, intervention_node: str, estimator: LikelihoodEstimator) -> tuple[float, float]:
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

        return max(0.0, h_prior - expected_h_post), expected_h_post

def calculate_graph_impact(graph_nodes: list[str], graph_edges: list[dict[str, str]], intervention_node: str) -> float:
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
