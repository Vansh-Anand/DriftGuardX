"""
DriftGuard-X v2 — BCRB Orchestrator
PRIVATE — All Rights Reserved.
"""

from packages.bcrb.src.calibration import BCRBCalibrator
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

    def __init__(self, tenant_id: str, calibrator: BCRBCalibrator | None = None):
        self.tenant_id = tenant_id
        self.calibrator = calibrator or BCRBCalibrator()
        self.planner = CandidatePlanner(tenant_id, calibrator=self.calibrator)
        self.test_framework = CanaryTestFramework(tenant_id)

    async def execute_session(
        self, session: BCRBSession, invocations: list[AgentInvocation], failure_symptom: str, db=None
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
                # Check budget using data-driven estimated cost
                comp_name = cand.component_type.value if hasattr(cand.component_type, "value") else str(cand.component_type)
                expected_cost = (
                    cand.cost_estimate.total_cost
                    if cand.cost_estimate
                    else self.calibrator.estimate_candidate_cost(comp_name)
                )
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
            step = await self.test_framework.execute_canary(best_candidate, str(session.run_id), str(session.session_id), db)
            session.steps.append(step)
            
            # Step 3: Record Costs
            # Use actual cost if available; do not treat UNAVAILABLE as actual zero cost without logging.
            if step.cost_incurred and step.cost_incurred.measurement_status == "ACTUAL":
                session.total_spent_usd += step.cost_incurred.total_cost
                
            # Step 4: Bayesian Update (Posterior Calculation)
            # If contaminated, we don't treat it as valid causal evidence
            is_clean = "contaminated" not in (step.decision_reason or "").lower() and "confounded" not in (step.decision_reason or "").lower()
            
            if step.recovery_effect and is_clean:
                reliability_improvement = step.recovery_effect.reliability_delta
                
                # Data-driven calibrated likelihoods
                likelihood_given_cause, likelihood_given_not_cause = self.calibrator.calculate_calibrated_likelihoods(
                    reliability_improvement
                )
                
                # Update beliefs for ALL candidates based on evidence. 
                # (A real implementation might update dependent probabilities. Here we just update the tested one.)
                for candidate in session.candidates:
                    if candidate.candidate_id == best_candidate.candidate_id:
                        new_posterior = update_posterior(
                            candidate.causal_evidence.prior,
                            likelihood_given_cause,
                            likelihood_given_not_cause
                        )
                        candidate.causal_evidence.posterior = new_posterior
                        candidate.causal_evidence.intervention_evidence = {
                            "reliability_improvement": reliability_improvement,
                            "likelihood_given_cause": likelihood_given_cause,
                            "likelihood_given_not_cause": likelihood_given_not_cause,
                            "likelihood_model": "calibrated_logistic",
                            "calibration": "DATA_DRIVEN_CALIBRATED",
                        }
                    else:
                        # In a fully connected causal graph, evidence for one candidate might decrease posterior for others.
                        # For now, we leave other candidates' posteriors as their priors if unobserved.
                        pass
                        
                    # Recompute utilities for all untested candidates
                    if candidate.candidate_id not in tested_candidate_ids:
                        current_prob = candidate.causal_evidence.posterior if candidate.causal_evidence.posterior is not None else candidate.causal_evidence.prior
                        candidate.estimated_utility = calculate_candidate_utility(
                            probability=current_prob,
                            expected_reliability_delta=candidate.expected_reliability_delta,
                            information_gain=candidate.expected_information_gain,
                            cost=candidate.cost_estimate.total_cost if candidate.cost_estimate else 0.05,
                            risk=candidate.risk_estimate,
                            blast_radius=candidate.blast_radius_estimate,
                        )
                
                # Set observed utility for step history
                step.utility_observed = best_candidate.estimated_utility
                
                # Stop if we hit a high confidence threshold on ANY candidate
                highest_posterior = max((c.causal_evidence.posterior for c in session.candidates if c.causal_evidence.posterior is not None), default=0.0)
                if highest_posterior >= 0.9:
                    session.stopping_condition_met = StoppingCondition.CONFIDENCE_REACHED
                    break
                    
        # Update session diagnosis outcome
        if session.stopping_condition_met == StoppingCondition.CONFIDENCE_REACHED:
            # Handled by DiagnosisEngine, but we can set session outcome
            pass

        return session
