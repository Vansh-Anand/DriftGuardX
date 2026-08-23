"""
DriftGuard-X v2 — Risk-Limited Sequential Causal Experiment Planner
PRIVATE — All Rights Reserved.
"""

import math
from typing import List, Dict, Optional, Tuple
from uuid import UUID

from packages.contracts.src.planner import (
    SafetyRisk, 
    RootCauseBeliefModel, 
    CausalExperimentCandidate, 
    ExperimentPlannerState,
    StoppingPolicy,
    DiagnosticStoppingDecision,
    StoppingReason,
    DiagnosticOutcome
)
from packages.contracts.src.models import ExecutionBudget, ExhaustionReason, ReplayEpisode

# Weights for Utility calculation (λ1, λ2, λ3)
LAMBDA_COST = 0.1
LAMBDA_SAFETY = 10.0
LAMBDA_BLAST = 5.0

# Safety Risk numerical mappings (lower is safer)
SAFETY_RISK_SCORES: Dict[SafetyRisk, float] = {
    SafetyRisk.NO_SIDE_EFFECT: 0.0,
    SafetyRisk.READ_ONLY: 1.0,
    SafetyRisk.LOCAL_STATE_CHANGE: 3.0,
    SafetyRisk.REVERSIBLE_EXTERNAL_CHANGE: 5.0,
    SafetyRisk.UNKNOWN: 8.0,
    SafetyRisk.IRREVERSIBLE_EXTERNAL_CHANGE: 10.0,
}

class RiskLimitedSequentialPlanner:
    def __init__(
        self, 
        incident_id: UUID,
        initial_beliefs: RootCauseBeliefModel,
        budget: ExecutionBudget,
        stopping_policy: Optional[StoppingPolicy] = None
    ):
        self.state = ExperimentPlannerState(
            incident_id=incident_id,
            root_cause_beliefs=initial_beliefs,
            remaining_budget=budget.wall_clock_time_s or 100.0, # Simple fallback
            current_entropy=self._calculate_entropy(initial_beliefs.priors)
        )
        self.budget = budget
        self.stopping_policy = stopping_policy or StoppingPolicy()
        self.entropy_history = [self.state.current_entropy]
        
        # Internal reservation tracking
        self._reserved_budget: Dict[str, float] = {}

    def _calculate_entropy(self, priors: Dict[str, float]) -> float:
        entropy = 0.0
        for p in priors.values():
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def generate_candidates(self) -> List[CausalExperimentCandidate]:
        """
        Generates causally plausible candidates. In a real system, this would 
        traverse the causal graph and propose interventions for components 
        with non-zero prior belief.
        """
        # This is a stub for the real generator that would use EnvelopeBuilder
        return []

    def filter_admissible(self, candidates: List[CausalExperimentCandidate]) -> List[CausalExperimentCandidate]:
        """
        Filters candidates that exceed budget or pose unacceptable safety risks.
        """
        admissible = []
        for c in candidates:
            if c.safety_risk == SafetyRisk.IRREVERSIBLE_EXTERNAL_CHANGE:
                continue
                
            # Check cost bounds (conservative check)
            predicted_cost = c.execution_cost_estimate + c.execution_cost_uncertainty
            if self.budget.wall_clock_time_s is not None:
                remaining = self.budget.wall_clock_time_s - self.budget.used_wall_clock_s
                if predicted_cost > remaining:
                    continue
                    
            admissible.append(c)
        return admissible

    def calculate_utility(self, candidate: CausalExperimentCandidate) -> float:
        """
        Utility(I) = (ExpectedInformationGain(I) × ReplayValidityProbability(I) × EvidenceQuality(I)) 
                     - (λ1 ResourceCost(I)) - (λ2 SafetyRisk(I)) - (λ3 BlastRadius(I))
        """
        gain_factor = (
            candidate.estimated_information_gain * 
            candidate.replay_validity_probability * 
            candidate.evidence_quality
        )
        
        safety_score = SAFETY_RISK_SCORES.get(candidate.safety_risk, 10.0)
        
        penalty_factor = (
            (LAMBDA_COST * (candidate.execution_cost_estimate + candidate.execution_cost_uncertainty)) +
            (LAMBDA_SAFETY * safety_score) +
            (LAMBDA_BLAST * candidate.expected_blast_radius)
        )
        
        return gain_factor - penalty_factor

    def apply_pareto_filter(self, candidates: List[CausalExperimentCandidate]) -> List[CausalExperimentCandidate]:
        """
        Applies a first-front dominance (Pareto) filter.
        Candidate A dominates B if A is no worse in all dimensions (Utility, Safety, Cost) 
        and strictly better in at least one.
        """
        if not candidates:
            return []
            
        utilities = {c.experiment_id: self.calculate_utility(c) for c in candidates}
        
        pareto_front = []
        for i, c1 in enumerate(candidates):
            is_dominated = False
            for j, c2 in enumerate(candidates):
                if i == j:
                    continue
                    
                # Dimensions to maximize/minimize
                u1 = utilities[c1.experiment_id]
                u2 = utilities[c2.experiment_id]
                
                s1 = SAFETY_RISK_SCORES.get(c1.safety_risk, 10.0)
                s2 = SAFETY_RISK_SCORES.get(c2.safety_risk, 10.0)
                
                cost1 = c1.execution_cost_estimate + c1.execution_cost_uncertainty
                cost2 = c2.execution_cost_estimate + c2.execution_cost_uncertainty
                
                # A dominates B if A is >= Utility, <= Safety, <= Cost, and strictly better in one
                u_geq = u2 >= u1
                s_leq = s2 <= s1
                c_leq = cost2 <= cost1
                
                u_strict = u2 > u1
                s_strict = s2 < s1
                c_strict = cost2 < cost1
                
                if (u_geq and s_leq and c_leq) and (u_strict or s_strict or c_strict):
                    is_dominated = True
                    break
                    
            if not is_dominated:
                pareto_front.append(c1)
                
        return pareto_front

    def select_next_experiment(self, candidates: List[CausalExperimentCandidate]) -> Optional[CausalExperimentCandidate]:
        admissible = self.filter_admissible(candidates)
        pareto_optimal = self.apply_pareto_filter(admissible)
        
        if not pareto_optimal:
            return None
            
        # Tie-break using raw utility on the Pareto front
        best_candidate = None
        best_utility = float("-inf")
        
        # Sort for determinism
        pareto_optimal.sort(key=lambda x: x.experiment_id)
        
        for c in pareto_optimal:
            u = self.calculate_utility(c)
            if u > best_utility:
                best_utility = u
                best_candidate = c
                
        return best_candidate

    def reserve_resources(self, candidate: CausalExperimentCandidate) -> bool:
        """Atomic reservation of budget for execution."""
        estimated_cost = candidate.execution_cost_estimate + candidate.execution_cost_uncertainty
        if self.budget.wall_clock_time_s is not None:
            remaining = self.budget.wall_clock_time_s - self.budget.used_wall_clock_s
            if estimated_cost > remaining:
                return False
                
            self.budget.used_wall_clock_s += estimated_cost
            self._reserved_budget[str(candidate.experiment_id)] = estimated_cost
            return True
        return True

    def reconcile_resources(self, candidate: CausalExperimentCandidate, actual_cost: float):
        """Reconciles actual cost with reserved cost."""
        reserved = self._reserved_budget.pop(str(candidate.experiment_id), 0.0)
        
        # If we reserved 10s and it took 4s, we refund 6s.
        if self.budget.wall_clock_time_s is not None:
            refund = reserved - actual_cost
            self.budget.used_wall_clock_s -= refund

    def release_resources(self, candidate: CausalExperimentCandidate):
        """Frees up the reservation without execution (e.g. if execution failed to start)."""
        reserved = self._reserved_budget.pop(str(candidate.experiment_id), 0.0)
        if self.budget.wall_clock_time_s is not None:
            self.budget.used_wall_clock_s -= reserved

    def update_beliefs(self, candidate: CausalExperimentCandidate, replay_outcome: str):
        """
        Updates posterior probabilities based on the causal observation.
        """
        # Basic heuristic Bayesian update stub
        target_component = candidate.intervention.component_id.split("_")[0] if "_" in candidate.intervention.component_id else candidate.intervention.component_id
        if target_component not in self.state.root_cause_beliefs.priors:
            return
            
        priors = self.state.root_cause_beliefs.priors
        
        # If the replay fixed the issue, this component is very likely the root cause
        if replay_outcome == "RECOVERY_SUCCESS":
            for k in priors:
                if k == target_component:
                    priors[k] = min(1.0, priors[k] * 2.0)
                else:
                    priors[k] *= 0.5
        elif replay_outcome == "RECOVERY_FAILURE":
            # Target component is less likely
            for k in priors:
                if k == target_component:
                    priors[k] *= 0.1
                else:
                    priors[k] *= 1.2
                    
        # Force re-validation and normalization via model update
        self.state.root_cause_beliefs = RootCauseBeliefModel(
            version=self.state.root_cause_beliefs.version + 1,
            priors=priors,
            is_calibrated=self.state.root_cause_beliefs.is_calibrated,
            metadata=self.state.root_cause_beliefs.metadata
        )
        self.state.current_entropy = self._calculate_entropy(self.state.root_cause_beliefs.priors)
        self.entropy_history.append(self.state.current_entropy)

    def evaluate_stopping_rule(
        self, 
        candidates: List[CausalExperimentCandidate], 
        valid_replay_count: int
    ) -> DiagnosticStoppingDecision:
        """
        Evaluates the stopping policy against the current epistemic state and budget.
        """
        priors = self.state.root_cause_beliefs.priors
        sorted_priors = sorted(priors.items(), key=lambda x: x[1], reverse=True)
        top_rc = sorted_priors[0][0] if sorted_priors else None
        top_prob = sorted_priors[0][1] if sorted_priors else 0.0
        second_prob = sorted_priors[1][1] if len(sorted_priors) > 1 else 0.0
        margin = top_prob - second_prob
        
        admissible = self.filter_admissible(candidates)
        next_best = self.select_next_experiment(admissible)
        next_ig = next_best.estimated_information_gain if next_best else 0.0
        
        remaining = self.budget.wall_clock_time_s - self.budget.used_wall_clock_s if self.budget.wall_clock_time_s else 100.0
        
        decision = DiagnosticStoppingDecision(
            stop=False,
            top_root_cause=top_rc,
            posterior_probability=top_prob,
            posterior_margin=margin,
            entropy=self.state.current_entropy,
            next_best_expected_information_gain=next_ig,
            remaining_budget=remaining,
            evidence_count=len(self.state.completed_experiments),
            valid_replay_count=valid_replay_count,
            confidence_metadata={
                "is_calibrated": self.state.root_cause_beliefs.is_calibrated,
                "entropy_history": self.entropy_history[-5:]
            }
        )

        # 1. No admissible experiments (Safety/Budget)
        if not admissible:
            decision.stop = True
            decision.reason = StoppingReason.NO_ADMISSIBLE_EXPERIMENT
            decision.outcome = DiagnosticOutcome.DIAGNOSIS_UNRESOLVED
            return decision

        # 2. Minimum evidence check
        if valid_replay_count < self.stopping_policy.min_valid_evidence:
            return decision  # Cannot stop yet

        # 3. Posterior Confidence & Margin
        if top_prob >= self.stopping_policy.min_posterior and margin >= self.stopping_policy.min_margin:
            if next_ig <= self.stopping_policy.max_next_ig:
                decision.stop = True
                decision.reason = StoppingReason.POSTERIOR_CONFIDENCE
                decision.outcome = DiagnosticOutcome.DIAGNOSIS_CONFIRMED
                return decision

        # 4. Low Expected Diagnostic Value (Value < Cost equivalent)
        if next_best:
            u = self.calculate_utility(next_best)
            if u <= 0:
                decision.stop = True
                decision.reason = StoppingReason.LOW_EXPECTED_DIAGNOSTIC_VALUE
                decision.outcome = DiagnosticOutcome.DIAGNOSIS_TENTATIVE if top_prob > 0.5 else DiagnosticOutcome.DIAGNOSIS_UNRESOLVED
                return decision

        # 5. Entropy Convergence Plateau
        if len(self.entropy_history) >= 3:
            recent_deltas = [abs(self.entropy_history[i] - self.entropy_history[i-1]) for i in range(-1, -3, -1)]
            if all(d < self.stopping_policy.entropy_convergence_threshold for d in recent_deltas):
                decision.stop = True
                decision.reason = StoppingReason.CONVERGED
                decision.outcome = DiagnosticOutcome.DIAGNOSIS_TENTATIVE if top_prob > 0.5 else DiagnosticOutcome.DIAGNOSIS_UNRESOLVED
                return decision

        return decision
