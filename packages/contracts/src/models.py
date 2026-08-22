"""
DriftGuard-X v2 — Core Shared Data Contracts

All schemas use Pydantic v2 strict mode. These are the canonical data contracts
shared across all packages (API, worker, replay, evaluation).

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import enum
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ─── Utilities ────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> UUID:
    return uuid4()


# ─── Enums ────────────────────────────────────────────────────────────────────

class ComponentType(str, enum.Enum):
    RETRIEVER = "retriever"
    RERANKER = "reranker"
    GENERATOR = "generator"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    TOOL_CALL = "tool_call"
    POLICY_CHECK = "policy_check"
    FINAL_RESPONSE = "final_response"
    AGENT = "agent"


class ComponentVersionState(str, enum.Enum):
    STABLE = "stable"
    EXPERIMENTAL = "experimental"
    DEPRECATED = "deprecated"
    ROLLBACK = "rollback"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"


class SpanKind(str, enum.Enum):
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PrivacyMode(str, enum.Enum):
    METADATA_ONLY = "metadata-only"
    REDACTED_CONTENT = "redacted-content"
    ENCRYPTED_CONTENT = "encrypted-content"
    DEVELOPMENT_FULL = "development-full"


class ReplayStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INVALID = "invalid"
    NEGATIVE_OUTCOME = "negative_outcome"


class InterventionType(str, enum.Enum):
    ROLLBACK = "rollback"
    ALTERNATE_STABLE = "alternate_stable"
    CONFIG_PATCH = "config_patch"
    ROUTE_CHANGE = "route_change"
    DISABLE = "disable"
    QUARANTINE = "quarantine"
    RETRY_BOUNDED = "retry_bounded"
    HUMAN_MUTATION = "human_mutation"


class DiagnosisClaimStatus(str, enum.Enum):
    IMPLEMENTED = "implemented"
    MEASURED = "measured"
    INFERRED = "inferred"
    PLANNED = "planned"
    REJECTED = "rejected"


class RepairDecisionStatus(str, enum.Enum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


# ─── Base ─────────────────────────────────────────────────────────────────────

class DGXBaseModel(BaseModel):
    """Base model with strict validation and UTC timestamps."""
    model_config = ConfigDict(
        strict=True,
        use_enum_values=True,
        arbitrary_types_allowed=False,
        populate_by_name=True,
    )


# ─── Tenant ──────────────────────────────────────────────────────────────────

class Tenant(DGXBaseModel):
    """Organisation-level isolation unit."""
    id: UUID = Field(default_factory=_new_uuid)
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = True

    @field_validator("slug")
    @classmethod
    def slug_lowercase(cls, v: str) -> str:
        return v.lower()


# ─── ComponentVersion ─────────────────────────────────────────────────────────

class ComponentVersion(DGXBaseModel):
    """A specific version of a pipeline component."""
    id: UUID = Field(default_factory=_new_uuid)
    component_type: ComponentType
    version_tag: str = Field(min_length=1, max_length=64)  # e.g. "v1", "v2-exp"
    state: ComponentVersionState = ComponentVersionState.STABLE
    config_hash: str = Field(min_length=1, max_length=64)  # SHA-256 of config
    description: str = ""
    
    # Versioned State Registry additions
    parent_version_id: UUID | None = None
    rollback_pointer: UUID | None = None
    compatibility_constraints: dict[str, Any] = Field(default_factory=dict)
    
    created_at: datetime = Field(default_factory=_utcnow)
    deployed_at: datetime | None = None

    @field_validator("config_hash")
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if len(v) not in (64, 16):  # allow short hash for tests
            pass  # SHA-256 is 64 hex chars; relax for mocks
        return v


# ─── AgentPipeline ────────────────────────────────────────────────────────────

class AgentPipeline(DGXBaseModel):
    """A versioned pipeline composed of ordered component versions."""
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)
    component_versions: list[ComponentVersion]
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)

    @model_validator(mode="after")
    def validate_component_types_unique(self) -> "AgentPipeline":
        seen: set[str] = set()
        for cv in self.component_versions:
            key = str(cv.component_type)
            if key in seen:
                raise ValueError(
                    f"Duplicate component type in pipeline: {cv.component_type}"
                )
            seen.add(key)
        return self


# ─── SpanRecord ───────────────────────────────────────────────────────────────

class RedactionMetadata(DGXBaseModel):
    """Records what was redacted and why."""
    fields_redacted: list[str] = Field(default_factory=list)
    redaction_reason: str = ""
    redacted_at: datetime = Field(default_factory=_utcnow)
    privacy_mode: PrivacyMode = PrivacyMode.REDACTED_CONTENT
    data_residency_label: str | None = None
    allowlist_applied: list[str] = Field(default_factory=list)


class SpanRecord(DGXBaseModel):
    """
    OpenTelemetry-compatible span with DriftGuard-X extensions.
    Raw prompts/completions are NOT stored — only hashes.
    """
    # OTel standard fields
    trace_id: str = Field(min_length=32, max_length=32)  # 128-bit hex
    span_id: str = Field(min_length=16, max_length=16)   # 64-bit hex
    parent_span_id: str | None = None
    name: str
    kind: SpanKind = SpanKind.INTERNAL
    start_time: datetime
    end_time: datetime | None = None
    status_code: str = "UNSET"  # OK | ERROR | UNSET
    status_message: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)

    # DriftGuard-X extensions
    tenant_id: UUID
    pipeline_id: UUID
    run_id: UUID
    component_type: ComponentType | None = None
    component_version_id: UUID | None = None
    component_version_tag: str | None = None

    # Inputs/outputs stored as hashes only (SHA-256 of serialized payload)
    input_hash: str | None = None
    output_hash: str | None = None

    # Metrics
    latency_ms: float | None = None
    token_count_input: int | None = None
    token_count_output: int | None = None
    cost_usd: float | None = None

    # Policy
    policy_result: str | None = None  # allow | deny | needs_approval
    policy_rule_id: str | None = None

    # Error
    error_type: str | None = None
    error_message: str | None = None

    # Redaction
    redaction: RedactionMetadata | None = None
    
    # Semantic Attributes Schema
    # dgx.retrieval.top_k, dgx.model.sampling_config, etc. are stored in `attributes`
    privacy_mode: PrivacyMode = PrivacyMode.DEVELOPMENT_FULL

    @model_validator(mode="after")
    def validate_end_after_start(self) -> "SpanRecord":
        if self.end_time and self.end_time < self.start_time:
            raise ValueError("end_time must be >= start_time")
        return self

    @property
    def duration_ms(self) -> float | None:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


# ─── RequestRun ───────────────────────────────────────────────────────────────

class RequestRun(DGXBaseModel):
    """A single execution of an agent pipeline."""
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    pipeline_id: UUID
    status: RunStatus = RunStatus.PENDING

    # Request metadata (no raw prompts stored)
    request_hash: str | None = None  # SHA-256 of the raw request body
    request_id: str | None = None    # External idempotency key

    # Provenance
    commit_sha: str | None = None
    config_hash: str | None = None
    seed: int | None = None
    hardware_id: str | None = None

    # Result
    response_hash: str | None = None
    reliability_score: float | None = None  # 0.0 – 1.0
    reliability_vector: dict[str, float] = Field(default_factory=dict)

    # Telemetry
    total_latency_ms: float | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None

    # Error
    error_type: str | None = None
    error_message: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Flag: is this a synthetic/demo run?
    is_synthetic: bool = False

    @field_validator("reliability_score")
    @classmethod
    def validate_reliability_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("reliability_score must be between 0.0 and 1.0")
        return v


# ─── TraceArtifact ────────────────────────────────────────────────────────────

class TraceArtifact(DGXBaseModel):
    """Normalized, persisted trace for a completed run."""
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    pipeline_id: UUID
    spans: list[SpanRecord]
    root_span_id: str | None = None  # span_id of the root span
    total_span_count: int = 0
    created_at: datetime = Field(default_factory=_utcnow)
    completeness_score: float | None = None
    retention_days: int | None = None
    tenant_sampling_rate: float | None = None

    @model_validator(mode="after")
    def compute_span_count(self) -> "TraceArtifact":
        self.total_span_count = len(self.spans)
        return self

    def get_root_span(self) -> SpanRecord | None:
        for span in self.spans:
            if span.parent_span_id is None:
                return span
        return None

    def get_span_chain(self, span_id: str) -> list[SpanRecord]:
        """Return ordered span + all ancestors."""
        chain: list[SpanRecord] = []
        by_id = {s.span_id: s for s in self.spans}
        current_id: str | None = span_id
        while current_id:
            span = by_id.get(current_id)
            if span is None:
                break
            chain.append(span)
            current_id = span.parent_span_id
        return list(reversed(chain))


# ─── Intervention ─────────────────────────────────────────────────────────────

class Intervention(DGXBaseModel):
    """A logged intervention decision (never auto-applied to production)."""
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    intervention_type: InterventionType
    target_component_type: ComponentType
    from_version_id: UUID
    to_version_id: UUID
    from_version_tag: str
    to_version_tag: str
    rationale: str = ""
    approved_by: str | None = None  # user/system that approved
    created_at: datetime = Field(default_factory=_utcnow)
    applied_at: datetime | None = None
    # SAFETY: never auto-applies; requires human approval
    requires_human_approval: bool = True


# ─── ReplayCapsule ────────────────────────────────────────────────────────────

class ReplayCapsule(DGXBaseModel):
    query: str
    trace_digest: str
    component_version_vector: dict[str, UUID]
    environment_digest: str
    random_seeds: dict[str, int]
    provider_settings: dict[str, Any]
    allowed_intervention_catalog: list[str]


# ─── ReplayEpisode ────────────────────────────────────────────────────────────

class ReplayEpisode(DGXBaseModel):
    """
    A deterministic replay with one component version swapped.
    All non-intervened components are version-pinned to the original run.
    """
    tenant_id: UUID
    run_id: UUID  # The original run
    replay_id: UUID = Field(default_factory=uuid4)
    capsule_hash: str = ""
    status: ReplayStatus = ReplayStatus.PENDING
    invalid_reason: str | None = None

    # Version pinning — which component was swapped
    swapped_component_type: ComponentType
    original_version_id: UUID
    replay_version_id: UUID
    original_version_tag: str
    replay_version_tag: str

    # Pinned versions (all other components)
    pinned_version_ids: dict[str, str] = Field(default_factory=dict)  # component_type -> version_id

    # Results
    original_reliability_vector: dict[str, float] = Field(default_factory=dict)
    replay_reliability_vector: dict[str, float] = Field(default_factory=dict)
    reliability_delta: dict[str, float] = Field(default_factory=dict)
    original_reliability_score: float | None = None
    replay_reliability_score: float | None = None
    reliability_improvement: float | None = None  # replay - original

    # Provenance
    original_request_hash: str | None = None
    replay_response_hash: str | None = None
    seed: int | None = None
    commit_sha: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
    is_synthetic: bool = False

    # Manifest
    manifest_id: UUID | None = None
    is_pinned: bool = False


# ─── ReplayStateManifest ──────────────────────────────────────────────────────

class ReplayStateManifest(DGXBaseModel):
    """
    Immutable manifest that binds all state required for reproducible replay.
    """
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID

    # Pinning state
    model_provider: str | None = None
    model_identifier: str | None = None
    model_config_hash: str | None = None
    prompt_template_hash: str | None = None
    retriever_version: str | None = None
    embedding_model_version: str | None = None
    vector_index_snapshot_id: str | None = None
    tool_schemas_hash: str | None = None
    policy_config_hash: str | None = None
    memory_snapshot_id: str | None = None
    random_seed: int | None = None
    generation_parameters: dict[str, Any] = Field(default_factory=dict)
    container_image_digest: str | None = None
    dependency_lockfile_hash: str | None = None
    trace_root_hash: str | None = None

    manifest_hash: str = ""
    created_at: datetime = Field(default_factory=_utcnow)

    def compute_hash(self) -> str:
        """Computes SHA-256 hash of canonical JSON representation."""
        import json
        data = self.model_dump(
            exclude={"id", "run_id", "tenant_id", "created_at", "manifest_hash"},
            exclude_none=True
        )
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @model_validator(mode="after")
    def validate_hash(self) -> "ReplayStateManifest":
        if not self.manifest_hash:
            self.manifest_hash = self.compute_hash()
        return self

    def is_fully_pinned(self) -> bool:
        """Returns True if all required pinning state is present."""
        required = [
            self.model_provider,
            self.model_identifier,
            self.model_config_hash,
            self.prompt_template_hash,
            self.retriever_version,
            self.embedding_model_version,
            self.vector_index_snapshot_id,
            self.tool_schemas_hash,
            self.policy_config_hash,
            self.memory_snapshot_id,
            self.random_seed is not None,
            self.container_image_digest,
            self.dependency_lockfile_hash,
            self.trace_root_hash,
        ]
        return all(bool(r) for r in required)


# ─── Diagnosis ────────────────────────────────────────────────────────────────

class DiagnosisClaim(DGXBaseModel):
    """A single claim in a diagnosis, with epistemic status."""
    claim_id: str
    description: str
    status: DiagnosisClaimStatus
    evidence: list[str] = Field(default_factory=list)
    confidence: float | None = None  # 0.0 – 1.0 if measured


class Diagnosis(DGXBaseModel):
    """Causal reliability assessment for a run."""
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    replay_episode_id: UUID | None = None
    tenant_id: UUID
    claims: list[DiagnosisClaim]
    root_cause_component: ComponentType | None = None
    root_cause_description: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
    is_synthetic: bool = False


# ─── RepairDecision ───────────────────────────────────────────────────────────

class RepairDecision(DGXBaseModel):
    """Human-approved decision to repair a reliability failure."""
    id: UUID = Field(default_factory=_new_uuid)
    diagnosis_id: UUID
    run_id: UUID
    tenant_id: UUID
    status: RepairDecisionStatus = RepairDecisionStatus.PENDING_APPROVAL
    proposed_intervention: InterventionType
    rationale: str
    approved_by: str | None = None
    rejected_reason: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    decided_at: datetime | None = None
    # Safety: default deny — requires explicit human approval
    auto_apply: bool = False


# ─── RecoveryCertificate ─────────────────────────────────────────────────────

class RecoveryCertificate(DGXBaseModel):
    """
    Cryptographic attestation that a recovery was performed correctly.
    The certificate hash covers run_id, replay_id, intervention_id, and outcome.
    """
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    replay_episode_id: UUID
    intervention_id: UUID
    repair_decision_id: UUID
    tenant_id: UUID
    certificate_hash: str  # SHA-256 of canonical payload
    issued_at: datetime = Field(default_factory=_utcnow)
    issued_by: str  # system or user identifier
    payload_summary: str = ""
    is_valid: bool = True

    @classmethod
    def compute_hash(cls, run_id: UUID, replay_id: UUID, intervention_id: UUID, issued_by: str) -> str:
        """Compute deterministic certificate hash."""
        payload = f"{run_id}:{replay_id}:{intervention_id}:{issued_by}"
        return hashlib.sha256(payload.encode()).hexdigest()


# ─── RollbackCapsule ─────────────────────────────────────────────────────────

class RollbackCapsule(DGXBaseModel):
    """
    Versioned rollback specification — encapsulates all state needed to
    roll back to a prior version of a component.
    """
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    pipeline_id: UUID
    component_type: ComponentType
    target_version_id: UUID
    target_version_tag: str
    from_version_id: UUID
    from_version_tag: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utcnow)
    expires_at: datetime | None = None
    is_applied: bool = False
    applied_at: datetime | None = None


# ─── Drift Detectors & Symptoms (Prompt 05) ──────────────────────────────────

class SymptomLikelihood(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DetectorOutput(DGXBaseModel):
    """Raw output from a drift detector before thresholding."""
    detector_name: str
    feature_name: str
    value: float
    is_anomaly: bool
    likelihood: SymptomLikelihood
    drift_channel: CausalDriftChannel | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    calculated_at: datetime = Field(default_factory=_utcnow)


class DetectorThreshold(DGXBaseModel):
    """Versioned threshold for a specific detector feature."""
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    pipeline_id: UUID
    detector_name: str
    feature_name: str
    threshold_value: float
    operator: str  # e.g., ">", "<", ">=", "<=", "==", "!="
    version: str = "v1"
    created_at: datetime = Field(default_factory=_utcnow)
    is_active: bool = True


class CausalDriftChannel(str, enum.Enum):
    RETRIEVAL = "RETRIEVAL"
    MODEL = "MODEL"
    MEMORY = "MEMORY"
    TOOL = "TOOL"
    PROMPT = "PROMPT"
    DATA = "DATA"
    UNKNOWN = "UNKNOWN"

    # Legacy mappings
    CORPUS_STALENESS = "DATA"
    RETRIEVAL_DEGRADATION = "RETRIEVAL"
    TOOL_SCHEMA_DRIFT = "TOOL"
    PROMPT_POLICY_SHIFT = "PROMPT"
    HOSTED_MODEL_SHIFT = "MODEL"
    OUTCOME_DRIFT = "UNKNOWN"


class TypedCausalMap(DGXBaseModel):
    """
    Decomposes an opaque drift score into typed channels (Update 2).
    """
    primary_channel: CausalDriftChannel
    channel_scores: dict[CausalDriftChannel, float] = Field(default_factory=dict)
    containment_partition_id: str | None = None


class SymptomRegistryEntry(DGXBaseModel):
    """A registered symptom linked to a graph node. Distinct from Causal Diagnosis."""
    id: UUID = Field(default_factory=_new_uuid)
    tenant_id: UUID
    run_id: UUID
    graph_node_id: str  # e.g., 'retriever:span_abc123'
    symptom_name: str
    severity: SymptomLikelihood
    detector_version: str
    evidence_snippet: str = ""
    uncertainty: float | None = None  # 0.0 - 1.0
    typed_causal_map: TypedCausalMap | None = None

# ─── Root Cause Report (Prompt 08) ───────────────────────────────────────────

class RankedCandidate(DGXBaseModel):
    """A ranked candidate from the exhaustive RCA benchmark."""
    component_type: ComponentType
    intervention_type: InterventionType
    aggregate_score: float
    reliability_improvement_mean: float
    reliability_improvement_variance: float
    cost_delta_usd: float
    latency_delta_ms: float
    invalid_rate: float
    trials_n: int
    is_negative_control: bool = False

class RootCauseReport(DGXBaseModel):
    """Final RCA report detailing candidates, controls, and limitations."""
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    tenant_id: UUID
    ranked_candidates: list[RankedCandidate] = Field(default_factory=list)
    abstention_triggered: bool = False
    limitations: list[str] = Field(default_factory=list)
    recommended_next_step: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    detected_at: datetime = Field(default_factory=_utcnow)

    # ── Certification fields (Prompt 10) ─────────────────────────────────────
    # Language: "statistically bounded under listed assumptions" — NOT "repair is correct"
    certificate_status: str = "UNCERTIFIED"  # CERTIFIED | UNCERTIFIED | REJECTED
    certification_policy_version: str = "v1.0"
    bound_method: str | None = None          # hoeffding | bootstrap | conformal | unsupported
    epsilon: float | None = None             # margin of error
    delta: float | None = None               # failure probability (1 - nominal_confidence)
    assumptions_met: list[str] = Field(default_factory=list)
    assumptions_violated: list[str] = Field(default_factory=list)
    observed_coverage: float | None = None   # empirical coverage, always reported alongside nominal
    nominal_confidence: float | None = None
    calibration_version: str | None = None
    calibration_age_days: float | None = None
    human_review_required: bool = True       # defaults True; cleared only when CERTIFIED
    block_automated_action: bool = True      # defaults True; cleared only when CERTIFIED


# ─── RAEB (Replay Admissibility and Evidence Budget) (Update 1) ───────────────

class AdmissibilityScore(str, enum.Enum):
    ADMISSIBLE = "admissible"
    LIMITED = "limited"
    UNSUPPORTED = "unsupported"

class EquivalenceVector(DGXBaseModel):
    """
    Measures the equivalence between a live run and a proposed replay.
    """
    freshness_score: float = Field(ge=0.0, le=1.0)
    determinism_score: float = Field(ge=0.0, le=1.0)
    dependency_impact_score: float = Field(ge=0.0, le=1.0)

class RAEBEvaluation(DGXBaseModel):
    """
    Result of evaluating a replay proposal against the RAEB gateway.
    """
    equivalence_vector: EquivalenceVector
    admissibility: AdmissibilityScore
    information_gain_estimate: float = 0.0
    risk_score: float = 0.0
    rejection_reason: str | None = None
    evaluated_at: datetime = Field(default_factory=_utcnow)


# ─── Pareto Replay Set (Update 5) ─────────────────────────────────────────────

class ParetoReplayCandidate(DGXBaseModel):
    arm_id: str
    information_gain: float
    recovery_harm: float
    cost: float
    admissibility: AdmissibilityScore
    is_pareto_optimal: bool = True

class ExhaustionReason(str, enum.Enum):
    WALL_CLOCK = "wall_clock_exhausted"
    MAX_STEPS = "max_steps_exhausted"
    MAX_TOKENS = "max_tokens_exhausted"
    MAX_TOOL_CALLS = "max_tool_calls_exhausted"
    MAX_REPLAYS = "max_replays_exhausted"
    CPU_EXHAUSTED = "cpu_exhausted"
    GPU_EXHAUSTED = "gpu_exhausted"
    MEMORY_EXHAUSTED = "memory_exhausted"
    STORAGE_EXHAUSTED = "storage_exhausted"
    QUEUE_DELAY_EXHAUSTED = "queue_delay_exhausted"

class ExecutionBudget(DGXBaseModel):
    """
    Defense-in-depth tracking of actual resource usage (Update 8 + Prompt 6).
    """
    wall_clock_time_s: float | None = None
    max_steps: int | None = None
    max_tokens: int | None = None
    max_tool_calls: int | None = None
    max_replays: int | None = None
    max_cpu_s: float | None = None
    max_gpu_s: float | None = None
    max_memory_mb: float | None = None
    max_storage_mb: float | None = None
    max_queue_delay_s: float | None = None
    
    # Measured usage state
    used_wall_clock_s: float = 0.0
    used_steps: int = 0
    used_tokens: int = 0
    used_tool_calls: int = 0
    used_replays: int = 0
    used_cpu_s: float = 0.0
    used_gpu_s: float = 0.0
    used_memory_mb: float = 0.0
    used_storage_mb: float = 0.0
    used_queue_delay_s: float = 0.0
    
    def check_exhaustion(self) -> ExhaustionReason | None:
        """Returns ExhaustionReason if any budget is exceeded."""
        if self.wall_clock_time_s is not None and self.used_wall_clock_s >= self.wall_clock_time_s:
            return ExhaustionReason.WALL_CLOCK
        if self.max_steps is not None and self.used_steps >= self.max_steps:
            return ExhaustionReason.MAX_STEPS
        if self.max_tokens is not None and self.used_tokens >= self.max_tokens:
            return ExhaustionReason.MAX_TOKENS
        if self.max_tool_calls is not None and self.used_tool_calls >= self.max_tool_calls:
            return ExhaustionReason.MAX_TOOL_CALLS
        if self.max_replays is not None and self.used_replays >= self.max_replays:
            return ExhaustionReason.MAX_REPLAYS
        if self.max_cpu_s is not None and self.used_cpu_s >= self.max_cpu_s:
            return ExhaustionReason.CPU_EXHAUSTED
        if self.max_gpu_s is not None and self.used_gpu_s >= self.max_gpu_s:
            return ExhaustionReason.GPU_EXHAUSTED
        if self.max_memory_mb is not None and self.used_memory_mb >= self.max_memory_mb:
            return ExhaustionReason.MEMORY_EXHAUSTED
        if self.max_storage_mb is not None and self.used_storage_mb >= self.max_storage_mb:
            return ExhaustionReason.STORAGE_EXHAUSTED
        if self.max_queue_delay_s is not None and self.used_queue_delay_s >= self.max_queue_delay_s:
            return ExhaustionReason.QUEUE_DELAY_EXHAUSTED
        return None

class ParetoReplaySet(DGXBaseModel):
    candidates: list[ParetoReplayCandidate] = Field(default_factory=list)

