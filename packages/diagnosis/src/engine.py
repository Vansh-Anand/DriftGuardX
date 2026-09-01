"""
DriftGuard-X v2 — Diagnosis Engine Aggregation
PRIVATE — All Rights Reserved.
"""

import uuid
from typing import Sequence

from packages.contracts.src.bcrb_models import BCRBCandidate
from packages.contracts.src.models import (
    Diagnosis, 
    DiagnosisClaim, 
    DiagnosisClaimStatus,
    ComponentType,
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
        evaluated_steps: Sequence['packages.contracts.src.bcrb_models.BCRBStep'],
        candidates: Sequence[BCRBCandidate]
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
            
        # Find the best step (highest utility)
        best_step = max(
            evaluated_steps,
            key=lambda s: s.utility_observed if s.utility_observed is not None else -1.0
        )
        
        best_candidate = candidate_map.get(best_step.candidate_id)
        
        # We consider a candidate successful if its utility observed is > 0.8
        if best_step.utility_observed and best_step.utility_observed > 0.8 and best_candidate:
            root_cause_component = ComponentType(best_candidate.component_type)
            root_cause_description = (
                f"Root cause isolated to {best_candidate.component_type}. "
                f"Intervention '{best_candidate.intervention_type}' successfully restored reliability "
                f"to {best_step.utility_observed:.2f}."
            )
            
            claims.append(
                DiagnosisClaim(
                    claim_id=str(uuid.uuid4()),
                    description=f"{best_candidate.component_type} is responsible for the failure.",
                    status=DiagnosisClaimStatus.MEASURED,
                    evidence=[f"Replay ID: {best_step.replay_episode_id}"],
                    confidence=best_step.utility_observed
                )
            )
        else:
            root_cause_description = "Exhaustive evaluation failed to find a definitive root cause."
            claims.append(
                DiagnosisClaim(
                    claim_id=str(uuid.uuid4()),
                    description="Multiple components may be interacting to cause the failure.",
                    status=DiagnosisClaimStatus.INFERRED,
                    evidence=[],
                    confidence=0.5
                )
            )

        return Diagnosis(
            id=uuid.uuid4(),
            run_id=uuid.UUID(run_id),
            tenant_id=uuid.UUID(self.tenant_id),
            claims=claims,
            root_cause_component=root_cause_component,
            root_cause_description=root_cause_description,
        )
