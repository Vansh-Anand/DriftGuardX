"""
DriftGuard-X v2 — Causal Recovery Transport Models
PRIVATE — All Rights Reserved.
"""
import base64
import enum
import hashlib
import hmac
from datetime import datetime
from typing import Any

from pydantic import Field

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow


class TransportStatus(str, enum.Enum):
    DIRECTLY_TRANSPORTABLE = "DIRECTLY_TRANSPORTABLE"
    TARGET_VALIDATION_REQUIRED = "TARGET_VALIDATION_REQUIRED"
    NOT_TRANSPORTABLE = "NOT_TRANSPORTABLE"
    UNKNOWN = "UNKNOWN"


class StructuredCalibrationEvidence(DGXBaseModel):
    """Structured evidence of calibration, replacing scalar metrics."""
    metric: str
    sample_size: int
    confidence_level: float
    dataset: str
    time: datetime
    evaluator: str
    source_result: float
    target_result: float | None = None


class CausalEnvironmentDescriptor(DGXBaseModel):
    """Full snapshot of an environment for transportability checks."""
    environment_id: str = Field(default_factory=lambda: str(_new_uuid()))
    tenant_id: str
    model: str
    prompt: str
    retriever: str
    memory: str
    tools: list[str]
    policy: str
    index: str
    data_distribution_fingerprint: str
    execution_configuration: dict[str, Any]
    causal_graph_hash: str
    provenance_hash: str
    calibration_evidence: StructuredCalibrationEvidence | None = None
    captured_at: datetime = Field(default_factory=_utcnow)
    signature: str | None = None

    def recompute_signature(self, secret_key: str) -> str:
        """Compute HMAC over critical descriptor fields."""
        payload = (
            f"{self.tenant_id}|{self.model}|{self.prompt}|{self.retriever}|"
            f"{self.policy}|{self.data_distribution_fingerprint}|{self.causal_graph_hash}"
        ).encode()
        mac = hmac.new(secret_key.encode('utf-8'), payload, hashlib.sha256).digest()
        return base64.b64encode(mac).decode('utf-8')


class EnvironmentDifference(DGXBaseModel):
    """Represents a specific structural/causal difference between environments."""
    variable: str
    source_value_hash: str
    target_value_hash: str
    affected_components: list[str]
    causal_relevance: float  # 0.0 to 1.0
    transport_risk: float    # 0.0 to 1.0


class RecoveryMechanismFootprint(DGXBaseModel):
    """Captures the assumptions that a validated recovery depends upon."""
    recovery_id: str
    required_invariant_components: list[str]
    required_invariant_edges: list[str]
    required_policy_conditions: dict[str, Any]
    required_data_conditions: dict[str, Any]
    required_calibration_conditions: dict[str, Any]


class TransportabilityDecision(DGXBaseModel):
    """Result of the transportability gate evaluation."""
    recovery_id: str
    source_environment: str
    target_environment: str
    status: TransportStatus
    preserved_conditions: list[str]
    violated_conditions: list[str]
    unknown_conditions: list[str]
    required_target_experiments: list[dict[str, Any]]
    confidence_metadata: dict[str, Any]
    explanation: str
    decision_hash: str = ""

    def compute_hash(self) -> str:
        status_str = self.status.value if hasattr(self.status, 'value') else str(self.status)
        payload = f"{self.recovery_id}|{self.source_environment}|{self.target_environment}|{status_str}"
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()
