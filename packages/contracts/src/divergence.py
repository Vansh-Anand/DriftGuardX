"""
DriftGuard-X v2 — Dynamic Causal Divergence Frontier Contracts

Core types for detecting and classifying state divergence during
counterfactual replay, ensuring differences stay within the boundaries
authorized by a ReplayEquivalenceEnvelope.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import enum
import hashlib
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, model_validator

from packages.contracts.src.models import DGXBaseModel, _new_uuid, _utcnow


class DivergenceType(str, enum.Enum):
    """
    Classification of observed state differences between original and replay.
    """
    EXPECTED_INTERVENTION = "expected_intervention"
    EXPECTED_CAUSAL_DESCENDANT = "expected_causal_descendant"
    PERMITTED_EXOGENOUS_CHANGE = "permitted_exogenous_change"
    PERMITTED_NONDETERMINISM = "permitted_nondeterminism"
    UNEXPECTED_DIVERGENCE = "unexpected_divergence"
    MISSING_STATE = "missing_state"
    UNVERIFIABLE = "unverifiable"


class DivergenceObservation(DGXBaseModel):
    """
    A single observation of state divergence (or verification) during replay.
    """
    observation_id: UUID = Field(default_factory=_new_uuid)
    key: str = Field(min_length=1, max_length=255)
    component_id: Optional[str] = None
    original_hash: Optional[str] = Field(default=None, max_length=64)
    replay_hash: Optional[str] = Field(default=None, max_length=64)
    divergence_type: DivergenceType
    causal_distance_from_intervention: Optional[int] = None
    constraint_used: Optional[str] = None
    timestamp: datetime = Field(default_factory=_utcnow)
    explanation: str = ""

    @model_validator(mode="after")
    def validate_hashes(self) -> "DivergenceObservation":
        for h in (self.original_hash, self.replay_hash):
            if h is not None:
                if len(h) != 64:
                    raise ValueError(f"Hash must be 64 chars, got {len(h)}")
                try:
                    int(h, 16)
                except ValueError:
                    raise ValueError("Hash must be hexadecimal")
        return self


class CausalDivergenceReport(DGXBaseModel):
    """
    Summary report of all observations across a replay experiment.
    """
    report_id: UUID = Field(default_factory=_new_uuid)
    envelope_id: UUID
    replay_id: UUID
    observations: list[DivergenceObservation] = Field(default_factory=list)
    frontier_components: list[str] = Field(default_factory=list)
    escaped_components: list[str] = Field(default_factory=list)
    valid: bool
    invalidation_reason: Optional[str] = None
    generated_at: datetime = Field(default_factory=_utcnow)
    
    # Benchmark Metrics
    reproducibility_rate: float = 0.0
    external_calls_avoided: int = 0
    unsafe_side_effects_prevented: int = 0
    
    report_hash: str = ""

    @model_validator(mode="after")
    def compute_hash(self) -> "CausalDivergenceReport":
        if not self.report_hash:
            payload = {
                "domain": "DGX-DIVERGENCE-REPORT-V1",
                "report_id": str(self.report_id),
                "envelope_id": str(self.envelope_id),
                "replay_id": str(self.replay_id),
                "valid": self.valid,
                "invalidation_reason": self.invalidation_reason,
                "observations": [
                    {
                        "key": obs.key,
                        "type": obs.divergence_type.value if hasattr(obs.divergence_type, "value") else str(obs.divergence_type),
                        "original_hash": obs.original_hash,
                        "replay_hash": obs.replay_hash
                    }
                    for obs in self.observations
                ],
                "escaped_components": sorted(self.escaped_components),
                "metrics": {
                    "reproducibility_rate": self.reproducibility_rate,
                    "external_calls_avoided": self.external_calls_avoided,
                    "unsafe_side_effects_prevented": self.unsafe_side_effects_prevented,
                }
            }
            serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            self.report_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return self

    def verify_integrity(self) -> bool:
        """Verify the cryptographic hash of the report."""
        # Save current hash, clear it to recompute
        current = self.report_hash
        self.report_hash = ""
        try:
            self.compute_hash()
            return current == self.report_hash
        finally:
            self.report_hash = current
