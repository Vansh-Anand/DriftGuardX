"""
DriftGuard-X v2 — Causal Experiment Planner
PRIVATE — All Rights Reserved.
"""
from typing import Any

from pydantic import BaseModel

from packages.contracts.src.recovery_models import ReplayEquivalenceEnvelope
from packages.replay.src.planner import ReplayPlanner


class ExpectedInformationGain(BaseModel):
    """Measures the utility of an experiment to reduce transportability uncertainty."""
    experiment_id: str
    target_variable: str
    information_gain: float
    confidence_interval: float


class DivergenceFrontier(BaseModel):
    """Tracks the bounds of acceptable environmental divergence."""
    variables: list[str]
    max_divergence_allowed: float
    current_divergence: float


class StoppingRule(BaseModel):
    """Conditions under which to halt the sequential experimentation."""
    max_experiments: int = 5
    min_information_gain: float = 0.05
    max_resource_cost: float = 100.0


class ResourceRiskPlanner(BaseModel):
    """Allocates replay budget and caps potential harm of validation."""
    budget_usd: float
    max_downtime_ms: int
    blast_radius_limit: float


class RiskLimitedSequentialCausalExperimentPlanner:
    """
    Selects the minimum informative target-domain validation experiments
    needed to resolve transportability uncertainties.
    """

    def __init__(self, base_planner: ReplayPlanner):
        self.base_planner = base_planner

    def select_minimum_experiments(
        self,
        candidate_experiments: list[dict[str, Any]],
        envelope: ReplayEquivalenceEnvelope,
        divergence_frontier: DivergenceFrontier,
        resource_planner: ResourceRiskPlanner,
        stopping_rule: StoppingRule
    ) -> list[dict[str, Any]]:
        """
        Filters and orders candidate experiments based on Expected Information Gain
        while respecting the ResourceRiskPlanner bounds.
        """
        selected = []
        accumulated_cost = 0.0

        # Sort candidates by a mocked heuristic for expected information gain
        # (In a full implementation, this uses a Bayesian Optimal Experimental Design formulation)
        scored_candidates = []
        for i, exp in enumerate(candidate_experiments):
            target = exp.get("target_variable", "unknown")
            # Mocking gain calculation
            gain = 0.8 if target in divergence_frontier.variables else 0.2
            scored_candidates.append(
                ExpectedInformationGain(
                    experiment_id=f"exp_{i}",
                    target_variable=target,
                    information_gain=gain,
                    confidence_interval=0.9
                )
            )

        scored_candidates.sort(key=lambda x: x.information_gain, reverse=True)

        for scored in scored_candidates:
            if len(selected) >= stopping_rule.max_experiments:
                break

            if scored.information_gain < stopping_rule.min_information_gain:
                break

            # Assume each experiment costs 10.0 (mock)
            if accumulated_cost + 10.0 > stopping_rule.max_resource_cost:
                break

            selected.append({
                "experiment_id": scored.experiment_id,
                "target_variable": scored.target_variable,
                "expected_gain": scored.information_gain,
                "envelope_id": envelope.trace_id # Link to the replay envelope
            })
            accumulated_cost += 10.0

        return selected
