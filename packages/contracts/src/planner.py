"""
DriftGuard-X v2 — Sequential Planner Contracts
PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import enum
import math
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import Field, model_validator

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow
from packages.contracts.src.envelope import CausalIntervention, ReplayEquivalenceEnvelope


class SafetyRisk(str, enum.Enum):
    NO_SIDE_EFFECT = "no_side_effect"
    READ_ONLY = "read_only"
    LOCAL_STATE_CHANGE = "local_state_change"
    REVERSIBLE_EXTERNAL_CHANGE = "reversible_external_change"
    IRREVERSIBLE_EXTERNAL_CHANGE = "irreversible_external_change"
    UNKNOWN = "unknown"


class RootCauseBeliefModel(DGXBaseModel):
    """
    Tracks the epistemic state of the planner regarding the true root cause.
    """
    version: int = 1
    # Component ID -> normalized probability [0.0, 1.0]
    priors: Dict[str, float] = Field(default_factory=dict)
    is_calibrated: bool = False
    metadata: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_priors(self) -> "RootCauseBeliefModel":
        if not self.priors:
            return self
            
        total_prob = 0.0
        for comp_id, prob in self.priors.items():
            if math.isnan(prob) or math.isinf(prob):
                raise ValueError(f"Probability for {comp_id} cannot be NaN or Inf.")
            if prob < 0.0:
                raise ValueError(f"Probability for {comp_id} cannot be negative.")
            total_prob += prob
            
        # Normalization check (allow slight floating point inaccuracies)
        if total_prob > 0.0 and not math.isclose(total_prob, 1.0, rel_tol=1e-5):
            # Auto-normalize if it's off
            self.priors = {k: v / total_prob for k, v in self.priors.items()}
            
        return self


class CausalExperimentCandidate(DGXBaseModel):
    experiment_id: UUID = Field(default_factory=_new_uuid)
    intervention: CausalIntervention
    envelope: ReplayEquivalenceEnvelope
    
    estimated_information_gain: float
    replay_validity_probability: float
    execution_cost_estimate: float
    execution_cost_uncertainty: float
    safety_risk: SafetyRisk
    expected_blast_radius: float
    expected_duration: float
    evidence_quality: float
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExperimentPlannerState(DGXBaseModel):
    incident_id: UUID
    root_cause_beliefs: RootCauseBeliefModel
    completed_experiments: List[UUID] = Field(default_factory=list)
    rejected_experiments: List[UUID] = Field(default_factory=list)
    remaining_budget: float
    current_entropy: float
    cumulative_cost: float = 0.0
    evidence_version: int = 1


class StoppingReason(str, enum.Enum):
    POSTERIOR_CONFIDENCE = "posterior_confidence"
    LOW_REMAINING_INFORMATION = "low_remaining_information"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SAFETY_LIMIT = "safety_limit"
    NO_ADMISSIBLE_EXPERIMENT = "no_admissible_experiment"
    CONVERGED = "converged"
    MANUAL_STOP = "manual_stop"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    LOW_EXPECTED_DIAGNOSTIC_VALUE = "low_expected_diagnostic_value"


class DiagnosticOutcome(str, enum.Enum):
    DIAGNOSIS_CONFIRMED = "diagnosis_confirmed"
    DIAGNOSIS_TENTATIVE = "diagnosis_tentative"
    DIAGNOSIS_UNRESOLVED = "diagnosis_unresolved"


class StoppingPolicy(DGXBaseModel):
    min_posterior: float = 0.8
    min_margin: float = 0.2
    max_next_ig: float = 0.1
    min_valid_evidence: int = 2
    entropy_convergence_threshold: float = 0.05
    min_evidence_quality: float = 0.5


class DiagnosticStoppingDecision(DGXBaseModel):
    stop: bool
    reason: StoppingReason | None = None
    outcome: DiagnosticOutcome | None = None
    top_root_cause: str | None = None
    posterior_probability: float | None = None
    posterior_margin: float | None = None
    entropy: float | None = None
    next_best_expected_information_gain: float | None = None
    remaining_budget: float | None = None
    evidence_count: int = 0
    valid_replay_count: int = 0
    confidence_metadata: Dict[str, Any] = Field(default_factory=dict)
    policy_version: str = "1.0"
