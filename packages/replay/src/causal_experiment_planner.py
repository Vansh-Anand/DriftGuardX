"""
DriftGuard-X v2 — Risk-Limited Sequential Causal Experiment Planner
PRIVATE — All Rights Reserved.

Replaces the 0.8/0.2 hardcoded information-gain heuristic with:
- Real Expected Information Gain (EIG) from the evolving root-cause belief distribution
- Risk/cost/blast-radius utility function: U = EIG / (cost × blast_radius_factor × risk_factor)
- Upfront ResourceReservation that rolls back on failure
- BlastRadiusEstimator from causal graph descendant count
- Integration with EvidentiaryStoppingRule (no hard max_iters as primary gate)
"""
from __future__ import annotations

from typing import Any

from packages.contracts.src.interfaces import ResourceContext, ResourceEstimate, ResourceMeasurement
from packages.contracts.src.recovery_models import ReplayEquivalenceEnvelope
from packages.replay.src.belief_model import (
    HeuristicLikelihoodEstimator,
    LikelihoodEstimator,
    RootCauseBeliefModel,
    calculate_graph_impact,
)


class BlastRadiusEstimator:
    """
    Estimates the blast radius of an experiment using the causal graph.
    blast_radius = number of causal descendants / total graph nodes
    """

    def __init__(
        self,
        graph_nodes: list[str] | None = None,
        graph_edges: list[dict[str, str]] | None = None,
    ) -> None:
        self._nodes = graph_nodes or []
        self._edges = graph_edges or []

    def estimate(self, target_node: str) -> float:
        if not self._nodes:
            return 0.5  # Unknown topology — moderate assumption
        return calculate_graph_impact(self._nodes, self._edges, target_node)


def _compute_experiment_utility(
    eig: float,
    cost_usd: float,
    blast_radius: float,
    regression_risk: float,
    eig_weight: float = 1.0,
    cost_penalty: float = 1.0,
    blast_penalty: float = 1.5,
    risk_penalty: float = 2.0,
) -> float:
    """
    Utility function for experiment selection:

    U = EIG × eig_weight / (cost × cost_penalty + blast × blast_penalty + risk × risk_penalty)

    Higher utility = better experiment to run next.
    Returns 0.0 if cost + blast + risk denominator is zero.
    """
    denominator = (
        cost_usd * cost_penalty
        + blast_radius * blast_penalty
        + regression_risk * risk_penalty
        + 1e-8  # numerical stability
    )
    return (eig * eig_weight) / denominator


class ScoredExperiment:
    """An experiment candidate scored by EIG and utility."""

    def __init__(
        self,
        candidate: dict[str, Any],
        eig: float,
        utility: float,
        blast_radius: float,
        cost_usd: float,
    ) -> None:
        self.candidate = candidate
        self.eig = eig
        self.utility = utility
        self.blast_radius = blast_radius
        self.cost_usd = cost_usd


class RiskLimitedSequentialCausalExperimentPlanner:
    """
    Selects the single highest-utility experiment at each step of the
    sequential causal investigation loop.

    At each call to plan_next_experiment():
    1. Compute real EIG for every untested candidate using the current belief model
    2. Estimate blast radius from the causal graph
    3. Compute utility = EIG / (cost × blast × risk factors)
    4. Attempt to reserve budget for the top-utility experiment
    5. Return the experiment, or None if budget is exhausted or EIG is too low

    The stopping rule (EvidentiaryStoppingRule) is evaluated by the orchestrator —
    this planner only handles experiment *selection*, not stopping decisions.
    """

    def __init__(
        self,
        blast_radius_estimator: BlastRadiusEstimator | None = None,
        likelihood_estimator: LikelihoodEstimator | None = None,
        default_experiment_cost_usd: float = 0.05,
        min_eig_threshold: float = 0.01,
        eig_weight: float = 1.0,
        cost_penalty: float = 1.0,
        blast_penalty: float = 1.5,
        risk_penalty: float = 2.0,
    ) -> None:
        self._blast_estimator = blast_radius_estimator or BlastRadiusEstimator()
        self._likelihood_estimator = likelihood_estimator or HeuristicLikelihoodEstimator()
        self._default_cost = default_experiment_cost_usd
        self._min_eig_threshold = min_eig_threshold
        self._eig_weight = eig_weight
        self._cost_penalty = cost_penalty
        self._blast_penalty = blast_penalty
        self._risk_penalty = risk_penalty
        self._tested: set[str] = set()

    def reset(self) -> None:
        self._tested.clear()

    def mark_tested(self, candidate_id: str) -> None:
        self._tested.add(candidate_id)

    def plan_next_experiment(
        self,
        envelope: ReplayEquivalenceEnvelope,
        candidates: list[dict[str, Any]],
        belief_state: dict[str, float],
        resource_context: ResourceContext,
    ) -> dict[str, Any] | None:
        """
        Returns the next experiment to run, or None if:
        - No candidates remain (all tested)
        - Budget is exhausted
        - Best remaining EIG is below min_eig_threshold
        """
        if resource_context.budget_exhausted():
            return None

        # Build a RootCauseBeliefModel from the current belief_state
        if not belief_state:
            return None

        belief_model = RootCauseBeliefModel(components=list(belief_state.keys()))
        belief_model.beliefs = dict(belief_state)

        # Score all untested candidates
        untested = [c for c in candidates if c.get("candidate_id", c.get("id", "")) not in self._tested]
        if not untested:
            return None

        scored: list[ScoredExperiment] = []
        for candidate in untested:
            cand_id = candidate.get("candidate_id", candidate.get("id", ""))
            target_node = candidate.get("target_variable", candidate.get("node_id", cand_id))

            # Real EIG from belief model
            eig, _ = belief_model.expected_information_gain(target_node, self._likelihood_estimator)

            # Blast radius from graph
            blast = self._blast_estimator.estimate(target_node)

            # Cost estimate
            cost = float(candidate.get("estimated_cost_usd", self._default_cost))

            # Regression risk estimate (from candidate metadata or blast radius proxy)
            regression_risk = float(candidate.get("regression_risk", blast * 0.5))

            utility = _compute_experiment_utility(
                eig=eig,
                cost_usd=cost,
                blast_radius=blast,
                regression_risk=regression_risk,
                eig_weight=self._eig_weight,
                cost_penalty=self._cost_penalty,
                blast_penalty=self._blast_penalty,
                risk_penalty=self._risk_penalty,
            )
            scored.append(ScoredExperiment(
                candidate=candidate,
                eig=eig,
                utility=utility,
                blast_radius=blast,
                cost_usd=cost,
            ))

        if not scored:
            return None

        # Select the highest-utility experiment
        best = max(scored, key=lambda s: s.utility)

        # Check EIG threshold — if best is below minimum, nothing useful to learn
        if best.eig < self._min_eig_threshold:
            return None

        # Attempt to reserve budget
        estimate = ResourceEstimate(cost_usd=best.cost_usd, replay_count=1)
        reservation = resource_context.reserve(estimate)
        if not reservation:
            return None  # Budget would be exceeded

        # Mark as tested and attach metadata
        cand_id = best.candidate.get("candidate_id", best.candidate.get("id", ""))
        self._tested.add(cand_id)

        return {
            **best.candidate,
            "envelope_id": envelope.trace_id,
            "expected_eig": best.eig,
            "utility": best.utility,
            "blast_radius": best.blast_radius,
            "reserved_cost_usd": best.cost_usd,
            "_reservation": reservation,  # caller must commit() or release()
        }

    # ── Legacy compatibility method ──────────────────────────────────────────

    def select_minimum_experiments(
        self,
        candidate_experiments: list[dict[str, Any]],
        envelope: ReplayEquivalenceEnvelope,
        belief_state: dict[str, float] | None = None,
        resource_context: ResourceContext | None = None,
        max_to_select: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Batch selection variant (used by transport gate).
        Selects up to max_to_select experiments by utility order.
        """
        if not belief_state:
            belief_state = {c.get("target_variable", ""): 1.0 / max(1, len(candidate_experiments))
                           for c in candidate_experiments}

        if resource_context is None:
            resource_context = ResourceContext(budget_usd=float(max_to_select) * self._default_cost)

        selected = []
        for _ in range(max_to_select):
            exp = self.plan_next_experiment(envelope, candidate_experiments, belief_state, resource_context)
            if exp is None:
                break
            reservation = exp.pop("_reservation", None)
            if reservation:
                measurement = ResourceMeasurement(cost_usd=reservation.estimate.cost_usd, replay_count=1)
                reservation.commit(measurement)
            selected.append(exp)

        return selected
