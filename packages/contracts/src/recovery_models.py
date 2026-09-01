"""
DriftGuard-X v2 — Recovery Causal Cut Models

Defines the core data structures for computing, optimizing, and validating
the Minimum Causal Recovery Cut, and the full ReplayEquivalenceEnvelope state model.

PRIVATE — All Rights Reserved.
"""

import enum
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from packages.contracts.src.evidence import RecoveryEvidenceKind
from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow


class OptimizationMethod(str, enum.Enum):
    EXACT = "exact"
    APPROXIMATE = "approximate"
    HEURISTIC = "heuristic"


class RecoveryActionType(str, enum.Enum):
    ROLLBACK = "ROLLBACK"
    REPLACE = "REPLACE"
    REMOVE = "REMOVE"
    ISOLATE = "ISOLATE"
    RECONFIGURE = "RECONFIGURE"
    RESTORE_SNAPSHOT = "RESTORE_SNAPSHOT"
    REBUILD_INDEX = "REBUILD_INDEX"
    CLEAR_MEMORY_PARTITION = "CLEAR_MEMORY_PARTITION"
    PATCH_POLICY = "PATCH_POLICY"


class SandboxOutcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    SANDBOX_UNAVAILABLE = "SANDBOX_UNAVAILABLE"
    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"
    SANDBOX_POLICY_VIOLATION = "SANDBOX_POLICY_VIOLATION"
    ACTION_UNSUPPORTED = "ACTION_UNSUPPORTED"
    EXOGENOUS_CONTROL_FAILURE = "EXOGENOUS_CONTROL_FAILURE"
    REPLAY_EXECUTION_FAILURE = "REPLAY_EXECUTION_FAILURE"
    TRACE_CAPTURE_FAILURE = "TRACE_CAPTURE_FAILURE"


class FailureTarget(DGXBaseModel):
    """Identifies a node where a failure was observed."""

    node_id: str
    failure_type: str  # e.g. "incorrect final answer", "policy violation", "retrieval failure"
    severity: str  # e.g. "high", "critical", "medium"
    evidence: dict[str, Any] = Field(default_factory=dict)


class FaultSource(DGXBaseModel):
    """A suspected root cause with an associated probability."""

    node_id: str
    probability: float = Field(ge=0.0, le=1.0)


class SignedCapability(DGXBaseModel):
    """
    A cryptographically-signed authorization capability.
    Replaces bare strings for recovery action authorization.
    Bound to: requester + tenant + resource + action tuple.
    """

    capability_id: str = Field(default_factory=lambda: str(_new_uuid()))
    requester_id: str
    tenant_id: str
    action: str  # e.g. "COMPONENT_ROLLBACK", "QUARANTINE", "FORENSIC_READ"
    resource: str  # the specific component/resource being acted upon
    issued_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime
    issuer: str = "DriftGuard-X"
    nonce: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_version: str = "1.0"
    revoked: bool = False
    signature: str = ""


class RecoveryAction(DGXBaseModel):
    """A potential recovery action evaluated during causal cut optimization."""

    action_id: str = Field(default_factory=lambda: str(_new_uuid()))
    target_component: str
    action_type: RecoveryActionType | str
    replacement: str | None = None
    change_cost: float = 0.0
    blast_radius: float = 0.0
    regression_risk: float = 0.0
    expected_downtime: float = 0.0
    reversibility: bool = True
    # Signed capability object — replaces bare string
    required_capability: SignedCapability | None = None
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
    """
    Full state model for executing a validation replay.

    Specifies:
    - snapshot_hash: SHA-256 of the original pipeline state at trace time
    - frozen_variables: components whose output hash must not change
    - intervened_variables: the components being mutated in this experiment
    - exogenous_variables: controlled stubs (RNG seeds, time, API responses, DB snapshots, etc.)
    - allowed_causal_descendants: nodes whose state may legitimately change due to the intervention
    - forbidden_divergence_nodes: any change here is an immediate violation + early termination
    - constraints: per-variable tolerance thresholds (numeric delta or exact-match)
    - policy_binding: signed policy document hash, must match live policy
    - trusted_time_binding: TrustedTimestampEnvelope id used at original trace time
    - envelope_hash: HMAC-SHA256 over all fields — computed and verified before replay begins
    """

    trace_id: str
    recovery_cut: CausalRecoveryCut
    invariants: list[RecoveryInvariant]

    # === Full state model fields ===
    snapshot_hash: str = ""
    frozen_variables: dict[str, str] = Field(
        default_factory=dict,
        description="variable_name -> expected SHA-256 hash. Any change is a violation.",
    )
    intervened_variables: list[str] = Field(
        default_factory=list,
        description="Component IDs being mutated. Their state change is expected.",
    )
    exogenous_variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Controlled stubs: rng_seed, frozen_time_iso, api_stubs, db_snapshot_id, llm_stub, tool_stubs, feature_flags",
    )
    allowed_causal_descendants: list[str] = Field(
        default_factory=list,
        description="Node IDs whose state may legitimately diverge due to the intervention.",
    )
    forbidden_divergence_nodes: list[str] = Field(
        default_factory=list,
        description="Any divergence in these nodes terminates the replay immediately.",
    )
    constraints: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-variable tolerance: {var: {'type': 'numeric_delta'|'exact', 'threshold': float}}",
    )
    policy_binding: str | None = Field(
        default=None,
        description="Hash of the policy document in effect when the original trace was recorded.",
    )
    trusted_time_binding: str | None = Field(
        default=None, description="ID of the TrustedTimestampEnvelope used at original trace time."
    )
    sandbox_config: dict[str, Any] = Field(default_factory=lambda: {"isolation_level": "strict"})
    schema_version: str = "2.0"
    graph_hash: str = ""

    # Computed on construction — verified before replay begins
    envelope_hash: str = ""

    @model_validator(mode="after")
    def compute_envelope_hash(self) -> "ReplayEquivalenceEnvelope":
        """Compute HMAC-SHA256 envelope hash over all critical fields."""
        if self.envelope_hash:
            return self
        secret = os.environ.get("DGX_CAPABILITY_SECRET")
        if not secret:
            raise RuntimeError("DGX_CAPABILITY_SECRET is missing. Cannot bind envelope.")

        # Serialize invariants deterministically
        serialized_invariants = [inv.model_dump(mode="json") for inv in self.invariants]

        payload = json.dumps(
            {
                "trace_id": self.trace_id,
                "snapshot_hash": self.snapshot_hash,
                "frozen_variables": self.frozen_variables,
                "intervened_variables": sorted(self.intervened_variables),
                "exogenous_variables": self.exogenous_variables,
                "allowed_causal_descendants": sorted(self.allowed_causal_descendants),
                "forbidden_divergence_nodes": sorted(self.forbidden_divergence_nodes),
                "constraints": self.constraints,
                "invariants": serialized_invariants,
                "sandbox_config": self.sandbox_config,
                "graph_hash": self.graph_hash,
                "schema_version": self.schema_version,
                "policy_binding": self.policy_binding,
                "trusted_time_binding": self.trusted_time_binding,
                "recovery_id": self.recovery_cut.recovery_id,
            },
            sort_keys=True,
        )

        mac = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        self.envelope_hash = mac
        return self

    def verify_envelope_hash(self) -> bool:
        """Re-derive the HMAC and compare. Returns False if tampered."""
        expected = self.envelope_hash
        # Temporarily clear so compute_envelope_hash recalculates
        self.envelope_hash = ""
        self.compute_envelope_hash()  # type: ignore[operator]
        result = hmac.compare_digest(self.envelope_hash, expected)
        return result


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
    evidence_kind: RecoveryEvidenceKind = RecoveryEvidenceKind.SYNTHETIC_SIMULATION
    validated_at: datetime = Field(default_factory=_utcnow)


class ReplayContext(DGXBaseModel):
    """Context block provided to the RecoveryReplayExecutor."""

    original_trace_id: str
    original_spans: list[dict[str, Any]]
    run_id: str | None = None
    tenant_id: str | None = None
    pipeline_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class RecoveryReplayResult(DGXBaseModel):
    """The result of attempting to execute a recovery replay pipeline."""

    outcome: SandboxOutcome
    evidence_kind: RecoveryEvidenceKind = RecoveryEvidenceKind.SYNTHETIC_SIMULATION
    new_trace_id: str | None = None
    new_spans: list[dict[str, Any]] = Field(default_factory=list)
    new_state_snapshot: dict[str, Any] | None = None
    target_failure_status: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    resource_usage: dict[str, float] = Field(default_factory=dict)
    external_side_effects: list[dict[str, Any]] = Field(default_factory=list)
    executor_metadata: dict[str, Any] = Field(default_factory=dict)
    reproducibility_metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(DGXBaseModel):
    request_id: str = Field(default_factory=lambda: str(_new_uuid()))
    tenant_id: str
    run_id: str
    recovery_id: str
    status: str = "PENDING"
    requester_id: str
    justification: str
    requested_at: datetime = Field(default_factory=_utcnow)
    decided_at: datetime | None = None
    decided_by: str | None = None


class CanaryEpisode(DGXBaseModel):
    episode_id: str = Field(default_factory=lambda: str(_new_uuid()))
    recovery_id: str
    tenant_id: str
    status: str = "PENDING"
    traffic_percentage: float = 0.0
    start_time: datetime | None = None
    end_time: datetime | None = None
    metrics_snapshot: dict[str, Any] = Field(default_factory=dict)


class RecoveryExecution(DGXBaseModel):
    execution_id: str = Field(default_factory=lambda: str(_new_uuid()))
    recovery_id: str
    tenant_id: str
    status: str = "PENDING"
    start_time: datetime | None = None
    end_time: datetime | None = None
    applied_actions: list[RecoveryAction] = Field(default_factory=list)
    rollback_status: str | None = None

class JobState(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"

class CryptographicSignature(DGXBaseModel):
    algorithm: str = "Ed25519"
    public_key: str
    signature: str
    timestamp: datetime = Field(default_factory=_utcnow)
    signer_id: str

class InterventionSpec(DGXBaseModel):
    spec_id: str = Field(default_factory=lambda: str(_new_uuid()))
    target_component: str
    current_version: str | None = None
    candidate_version: str | None = None
    intervention_type: str
    expected_cost: float = 0.0
    risk_score: float = 0.0
    blast_radius: float = 0.0
    rollback_plan: str | None = None
    dependencies: list[str] = Field(default_factory=list)

class QuarantineAction(DGXBaseModel):
    action_id: str = Field(default_factory=lambda: str(_new_uuid()))
    target_component: str
    reason: str
    duration_seconds: int | None = None
    fallback_routing: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class ReplayStateManifest(DGXBaseModel):
    manifest_id: str = Field(default_factory=lambda: str(_new_uuid()))
    trace_id: str
    agent_versions: dict[str, str] = Field(default_factory=dict)
    routing_graph_hash: str | None = None
    task_state: dict[str, Any] = Field(default_factory=dict)
    prompts: dict[str, str] = Field(default_factory=dict)
    tools: list[str] = Field(default_factory=list)
    memory_snapshots: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, str] = Field(default_factory=dict)
    model_versions: dict[str, str] = Field(default_factory=dict)
    retrieval_state: dict[str, Any] = Field(default_factory=dict)
    rng_seeds: dict[str, int] = Field(default_factory=dict)
    dependencies: dict[str, str] = Field(default_factory=dict)
    image_digest: str | None = None
    signature: CryptographicSignature | None = None

class ApprovalState(str, enum.Enum):
    PROPOSED = "PROPOSED"
    REPLAY_CONFIRMED = "REPLAY_CONFIRMED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANARY = "CANARY"
    PROMOTED = "PROMOTED"
    ROLLED_BACK = "ROLLED_BACK"

class RBACRole(str, enum.Enum):
    VIEWER = "VIEWER"
    INVESTIGATOR = "INVESTIGATOR"
    OPERATOR = "OPERATOR"
    APPROVER = "APPROVER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"
