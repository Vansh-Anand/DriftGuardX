"""
DriftGuard-X v2 — Diagnosis Engine Aggregation
PRIVATE — All Rights Reserved.
"""

import uuid
from collections.abc import Sequence

from packages.contracts.src.bcrb_models import BCRBCandidate
from packages.contracts.src.models import (
    ComponentType,
    Diagnosis,
    DiagnosisClaim,
    DiagnosisClaimStatus,
)


class DiagnosisEngine:
    """
    Aggregates evaluated BCRBCandidates to form a definitive Diagnosis.
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def generate_diagnosis(
        self,
        run_id: str,
        evaluated_steps: Sequence["packages.contracts.src.bcrb_models.BCRBStep"],
        candidates: Sequence[BCRBCandidate],
    ) -> Diagnosis:
        """
        Evaluate candidates and produce a root cause diagnosis.
        """
        claims = []
        root_cause_component = None
        root_cause_description = "Unknown root cause."

        if not evaluated_steps:
            return Diagnosis(
                id=uuid.uuid4(),
                run_id=uuid.UUID(run_id),
                tenant_id=uuid.UUID(self.tenant_id),
                claims=claims,
                root_cause_component=None,
                root_cause_description="No candidates evaluated.",
            )

        candidate_map = {c.candidate_id: c for c in candidates}

        # Find all steps/candidates with actual CAUSAL CONFIDENCE (Bayesian posterior) >= 0.9
        high_confidence_candidates = []
        highest_posterior = -1.0
        best_candidate = None
        best_step = None

        for step in evaluated_steps:
            cand = candidate_map.get(step.candidate_id)
            if cand and cand.causal_evidence and cand.causal_evidence.posterior is not None:
                posterior = cand.causal_evidence.posterior
                if posterior > highest_posterior:
                    highest_posterior = posterior
                    best_candidate = cand
                    best_step = step

                if posterior >= 0.80:
                    high_confidence_candidates.append((cand, step, posterior))

        # We require high causal confidence (e.g. >= 0.80) to claim a root cause, separating this from recovery utility.
        confidence_threshold = 0.80
        status = "UNKNOWN"
        next_action = None

        if high_confidence_candidates:
            status = "ROOT_CAUSE_ISOLATED"
            # We still return the absolute best candidate as the primary root_cause_component for legacy compatibility
            root_cause_component = ComponentType(best_candidate.component_type)

            if len(high_confidence_candidates) > 1:
                components = [str(c[0].component_type) for c in high_confidence_candidates]
                root_cause_description = (
                    f"Multiple interacting root causes isolated: {', '.join(components)}. "
                )
            else:
                recovery_delta = (
                    best_step.recovery_effect.reliability_delta
                    if best_step and best_step.recovery_effect
                    else 0.0
                )
                root_cause_description = (
                    f"Root cause isolated to {best_candidate.component_type} with Bayesian posterior {highest_posterior:.2f}. "
                    f"Intervention '{best_candidate.intervention_type}' produced a reliability delta of {recovery_delta:.2f}."
                )

            for cand, step, posterior in high_confidence_candidates:
                claims.append(
                    DiagnosisClaim(
                        claim_id=str(uuid.uuid4()),
                        description=f"{cand.component_type} is responsible for the failure.",
                        status=DiagnosisClaimStatus.MEASURED,
                        evidence=[
                            f"Replay ID: {step.replay_episode_id}",
                            f"Bayesian Posterior: {posterior:.2f}",
                        ],
                        confidence=posterior,
                    )
                )
        else:
            status = "INSUFFICIENT_EVIDENCE"
            next_action = "collect another replay"
            root_cause_description = "Evidence is insufficient to confirm a root cause."
            claims.append(
                DiagnosisClaim(
                    claim_id=str(uuid.uuid4()),
                    description="Outcome UNKNOWN due to insufficient causal evidence.",
                    status=DiagnosisClaimStatus.INFERRED,
                    evidence=[],
                    confidence=max(highest_posterior, 0.0),
                )
            )

        return Diagnosis(
            id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(self.tenant_id),
            claims=claims,
            root_cause_component=root_cause_component,
            root_cause_description=root_cause_description,
            status=status,
            highest_candidate_component=(
                ComponentType(best_candidate.component_type) if best_candidate else None
            ),
            highest_posterior=highest_posterior if highest_posterior >= 0.0 else None,
            confidence_threshold=confidence_threshold,
            next_action=next_action,
        )
