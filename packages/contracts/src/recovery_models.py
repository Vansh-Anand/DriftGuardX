"""
DriftGuard-X v2 — Recovery Causal Cut Models

Defines the core data structures for computing, optimizing, and validating 
the Minimum Causal Recovery Cut.
"""
import enum
from datetime import datetime
from typing import Any

from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow


class OptimizationMethod(str, enum.Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    HEURISTIC = "heuristic"


class FailureTarget(DGXBaseModel):
    """Identifies a node where a failure was observed."""
    node_id: str
    failure_type: str  # e.g. "incorrect final answer", "policy violation", "retrieval failure"
    severity: str      # e.g. "high", "critical", "medium"
    evidence: dict[str, Any] = Field(default_factory=dict)


class FaultSource(DGXBaseModel):
    """A suspected root cause with an associated probability."""
    node_id: str
    probability: float = Field(ge=0.0, le=1.0)


class RecoveryAction(DGXBaseModel):
    """A potential recovery action evaluated during causal cut optimization."""
    action_id: str = Field(default_factory=lambda: str(_new_uuid()))
    target_component: str
    action_type: str # Can map to RecoveryActionType
    replacement: str | None = None
    change_cost: float = 0.0
    blast_radius: float = 0.0
    regression_risk: float = 0.0
    expected_downtime: float = 0.0
    reversibility: bool = True
    required_capability: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CausalRecoveryCut(DGXBaseModel):
    """The computed recovery cut to resolve the failure."""
    recovery_id: str = Field(default_factory=lambda: str(_new_uuid()))
    fault_sources: list[FaultSource]
    failure_targets: list[FailureTarget]
    selected_actions: list[RecoveryAction]
    blocked_failure_paths: list[list[str]] = Field(default_factory=list)
    residual_failure_paths: list[list[str]] = Field(default_factory=list)

    # Aggregated metrics
    total_change_cost: float = 0.0
    blast_radius: float = 0.0
    regression_risk: float = 0.0
    expected_downtime: float = 0.0

    optimization_method: OptimizationMethod
    evidence_hash: str

    created_at: datetime = Field(default_factory=_utcnow)


class RecoveryInvariant(DGXBaseModel):
    """A property that must remain preserved despite the recovery cut."""
    invariant_id: str = Field(default_factory=lambda: str(_new_uuid()))
    scope: str
    metric: str
    baseline: float
    allowed_deviation: float
    severity: str
    evidence_source: str


class ReplayEquivalenceEnvelope(DGXBaseModel):
    """Constructed environment parameters for executing validation replay."""
    recovery_cut: CausalRecoveryCut
    invariants: list[RecoveryInvariant]
    trace_id: str
    sandbox_config: dict[str, Any] = Field(default_factory=dict)


class RecoveryValidationResult(DGXBaseModel):
    """The result of validating a proposed recovery cut."""
    recovery_cut: CausalRecoveryCut
    failure_resolved: bool
    invariants: list[RecoveryInvariant]
    invariants_satisfied: bool
    divergence_report: dict[str, Any] = Field(default_factory=dict)
    residual_risk: float = 0.0
    eligible_for_canary: bool = False
    reason: str = ""
    validated_at: datetime = Field(default_factory=_utcnow)
