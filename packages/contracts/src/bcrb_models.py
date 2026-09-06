"""
DriftGuard-X v2 — BCRB Models
PRIVATE — All Rights Reserved.
"""

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from packages.contracts.src.models import (
    ComponentType,
    DGXBaseModel,
    InterventionType,
    _new_uuid,
    _utcnow,
)


class BCRBCalibrationArtifact(DGXBaseModel):
    schema_version: str = "1.0.0"
    experiment_count: int
    detector_accuracy: float
    diffusion_accuracy: float
    symptom_accuracy: float
    likelihood_parameters: dict[str, Any] = Field(default_factory=dict)
    cost_model: dict[str, float] = Field(default_factory=dict)
    dataset_hash: str
    commit_sha: str
    created_at: datetime = Field(default_factory=_utcnow)


class BCRBStepStatus(str, enum.Enum):
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BUDGET_BLOCKED = "budget_blocked"


class UnifiedCandidatePrior(DGXBaseModel):
    candidate_component: str
    derived_gat_signal: float
    detector_probability: float | None = None
    diffusion_score: float
    symptom_evidence: float
    combined_prior: float
    evidence_breakdown: dict[str, Any]

    @property
    def gat_score(self) -> float:
        return self.derived_gat_signal

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        d = super().model_dump(*args, **kwargs)
        d["gat_score"] = self.derived_gat_signal
        return d


class ReplayCost(DGXBaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    api_cost: float | None = None
    compute_seconds: float | None = None
    infrastructure_cost: float | None = None
    total_cost: float = 0.0
    measurement_status: str = "ESTIMATED"  # ESTIMATED, ACTUAL, or UNAVAILABLE


class RecoveryEffect(DGXBaseModel):
    reliability_delta: float
    latency_delta: float | None = None
    safety_delta: float | None = None
    cost_delta: float | None = None


class ContaminationState(str, enum.Enum):
    CLEAN = "clean"
    CONTAMINATED = "contaminated"
    CONFOUNDED = "confounded"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class CounterfactualSupport(DGXBaseModel):
    baseline_available: bool = False
    intervention_available: bool = False
    negative_control_available: bool = False
    alternative_intervention_available: bool = False
    repeated_replay_count: int = 0
    observed_effect: dict[str, Any] | None = None


class CausalEvidence(DGXBaseModel):
    prior: float
    posterior: float | None = None
    intervention_evidence: dict[str, Any] = Field(default_factory=dict)
    counterfactual_support: CounterfactualSupport = Field(default_factory=CounterfactualSupport)
    contamination_status: ContaminationState = ContaminationState.INSUFFICIENT_EVIDENCE
    confounding_reason: str | None = None
    evidence_provenance: str | None = None


class BCRBCandidate(DGXBaseModel):
    candidate_id: UUID = Field(default_factory=_new_uuid)
    component_type: ComponentType
    intervention_type: InterventionType
    estimated_utility: float = 0.0
    cost_estimate: ReplayCost = Field(default_factory=ReplayCost)
    risk_estimate: float = 0.0
    blast_radius_estimate: float = 0.0
    expected_reliability_delta: float = 0.0
    expected_information_gain: float = 0.0
    causal_evidence: CausalEvidence = Field(default_factory=lambda: CausalEvidence(prior=0.0))
    metadata: dict[str, Any] = Field(default_factory=dict)
    diagnosis_hash: str | None = None
    candidate_hash: str | None = None

    def compute_hash(self) -> str:
        import hashlib
        import json

        data = self.model_dump(
            mode="json", exclude={"candidate_id", "candidate_hash"}, exclude_none=True
        )
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class BCRBStep(DGXBaseModel):
    step_id: UUID = Field(default_factory=_new_uuid)
    session_id: UUID
    candidate_id: UUID
    status: BCRBStepStatus = BCRBStepStatus.PLANNED
    replay_episode_id: UUID | None = None
    utility_observed: float | None = None
    cost_incurred: ReplayCost | None = None
    recovery_effect: RecoveryEffect | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    decision_reason: str | None = None
    replay_hash: str | None = None
    posterior_hash: str | None = None

    def compute_hash(self) -> str:
        import hashlib
        import json

        data = self.model_dump(
            mode="json",
            exclude={"step_id", "start_time", "end_time", "posterior_hash"},
            exclude_none=True,
        )
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class StoppingCondition(str, enum.Enum):
    CONFIDENCE_REACHED = "confidence_reached"
    RELIABILITY_RECOVERED = "reliability_recovered"
    BUDGET_EXHAUSTED = "budget_exhausted"
    ALL_SAFE_CANDIDATES_TESTED = "all_safe_candidates_tested"
    EXPECTED_UTILITY_BELOW_THRESHOLD = "expected_utility_below_threshold"
    NO_SAFE_INTERVENTION = "no_safe_intervention"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class DiagnosisOutcome(str, enum.Enum):
    ROOT_CAUSE_SUPPORTED = "root_cause_supported"
    ROOT_CAUSE_UNCERTAIN = "root_cause_uncertain"
    UNKNOWN = "unknown"
    NO_SAFE_INTERVENTION = "no_safe_intervention"
    BUDGET_EXHAUSTED = "budget_exhausted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class BCRBSession(DGXBaseModel):
    session_id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    budget_usd: float
    total_spent_usd: float = 0.0
    candidates: list[BCRBCandidate] = Field(default_factory=list)
    steps: list[BCRBStep] = Field(default_factory=list)
    stopping_condition_met: StoppingCondition | None = None
    diagnosis_outcome: DiagnosisOutcome | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None


class AblationConfig(DGXBaseModel):
    without_gat: bool = False
    without_diffusion: bool = False
    without_bayesian: bool = False
    without_bcrb_utility: bool = False
    random_recovery: bool = False
    fixed_order_recovery: bool = False
    without_replay: bool = False
    without_provenance: bool = False
    gat_only: bool = False
    diffusion_only: bool = False
    symptoms_only: bool = False
