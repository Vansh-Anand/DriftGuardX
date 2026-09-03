"""
DriftGuard-X v2 — BCRB Orchestrator
PRIVATE — All Rights Reserved.
"""

from packages.bcrb.src.candidate_planner import CandidatePlanner
from packages.bcrb.src.bayesian_updater import update_posterior
from packages.bcrb.src.utility_function import calculate_candidate_utility
from packages.contracts.src.bcrb_models import BCRBSession, BCRBStepStatus, StoppingCondition
from packages.replay.src.test_framework import CanaryTestFramework
from packages.contracts.src.agent_models import AgentInvocation
import logging

logger = logging.getLogger(__name__)

class BCRBOrchestrator:
    """
    Coordinates the sequential Bayesian Causal Reasoning Board (BCRB) decision loop.
    Iteratively plans, selects, executes, updates beliefs, and evaluates stopping conditions.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.planner = CandidatePlanner(tenant_id)
        self.test_framework = CanaryTestFramework(tenant_id)

    def execute_session(
        self, session: BCRBSession, invocations: list[AgentInvocation], failure_symptom: str
    ) -> BCRBSession:
        """
        Executes the BCRB sequential decision process.
        """
        # Step 1: Generate initial candidates
        session.candidates = self.planner.generate_candidates(invocations, str(session.run_id), failure_symptom)

        tested_candidate_ids = set()

        while True:
            # Check stopping conditions before next loop
            stopping_condition = self.planner.evaluate_stopping_conditions(session)
            if stopping_condition:
                session.stopping_condition_met = stopping_condition
                break

            # Find the best candidate that hasn't been tested yet and can be afforded
            untested_candidates = [c for c in session.candidates if c.candidate_id not in tested_candidate_ids]
            
            if not untested_candidates:
                session.stopping_condition_met = StoppingCondition.ALL_SAFE_CANDIDATES_TESTED
                break
                
            # Sort by utility
            untested_candidates.sort(key=lambda c: c.estimated_utility, reverse=True)
            
            best_candidate = None
            for cand in untested_candidates:
                # Check budget
                expected_cost = cand.cost_estimate.total_cost if cand.cost_estimate else 0.05
                if expected_cost + session.total_spent_usd > session.budget_usd:
                    # Mark as budget blocked, but try next candidate which might be cheaper
                    continue
                
                best_candidate = cand
                break
                
            if not best_candidate:
                session.stopping_condition_met = StoppingCondition.BUDGET_EXHAUSTED
                break
                
            tested_candidate_ids.add(best_candidate.candidate_id)
            
            # Step 2: Execute Replay / Canary
            step = self.test_framework.execute_canary(best_candidate, str(session.run_id), str(session.session_id))
            session.steps.append(step)
            
            # Step 3: Record Costs
            if step.cost_incurred:
                session.total_spent_usd += step.cost_incurred.total_cost
                
            # Step 4: Bayesian Update (Posterior Calculation)
            # If contaminated, we don't treat it as valid causal evidence
            is_clean = "contaminated" not in (step.decision_reason or "").lower()
            
            if step.recovery_effect and is_clean:
                # Heuristic likelihoods for simulation:
                # If reliability delta is positive, likelihood of it being the cause is high.
                reliability_improvement = step.recovery_effect.reliability_delta
                
                # These are NOT statistically calibrated.
                likelihood_given_cause = 0.8 if reliability_improvement > 0.5 else 0.2
                likelihood_given_not_cause = 0.2 if reliability_improvement > 0.5 else 0.8
                
                new_posterior = update_posterior(
                    best_candidate.causal_evidence.prior,
                    likelihood_given_cause,
                    likelihood_given_not_cause
                )
                
                best_candidate.causal_evidence.posterior = new_posterior
                best_candidate.causal_evidence.intervention_evidence = {
                    "reliability_improvement": reliability_improvement,
                    "likelihood_given_cause_used": likelihood_given_cause
                }
                
                # Update utility based on new posterior for future decision reference
                best_candidate.estimated_utility = calculate_candidate_utility(
                    probability=new_posterior,
                    expected_reliability_delta=best_candidate.expected_reliability_delta,
                    information_gain=best_candidate.expected_information_gain,
                    cost=best_candidate.cost_estimate.total_cost if best_candidate.cost_estimate else 0.05,
                    risk=best_candidate.risk_estimate,
                    blast_radius=best_candidate.blast_radius_estimate,
                )
                
                step.utility_observed = best_candidate.estimated_utility
                
                # Stop if we hit a high confidence threshold
                if new_posterior >= 0.9:
                    session.stopping_condition_met = StoppingCondition.CONFIDENCE_REACHED
                    break
                    
        # Update session diagnosis outcome
        if session.stopping_condition_met == StoppingCondition.CONFIDENCE_REACHED:
            # Handled by DiagnosisEngine, but we can set session outcome
            pass

        return session
