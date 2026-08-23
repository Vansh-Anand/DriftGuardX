"""
DriftGuard-X v2 — Replay Equivalence Envelope Contracts

Core typed models for the Replay Equivalence Envelope mechanism.

Purpose
-------
The envelope defines BEFORE replay:
  1. What must remain unchanged (frozen);
  2. What is intentionally changed (intervened);
  3. What is permitted to change as a causal consequence (endogenous descendants);
  4. What external variables must be frozen/emulated (exogenous handling);
  5. What divergence would invalidate the experiment (forbidden divergence).

This is NOT a simple diff between two runs.  It is a pre-replay specification
of the causal experiment's validity boundary.

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import enum
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator
from .exogenous import ExogenousStateRecord

from packages.contracts.src.models import DGXBaseModel, _utcnow, _new_uuid


# ─── Causal Intervention Types ───────────────────────────────────────────────

class CausalInterventionType(str, enum.Enum):
    """
    The kind of change being applied in the causal experiment.

    Only ONE intervention is permitted per envelope.  Multiple uncontrolled
    changes inside a "single intervention" are rejected by the validator.
    """
    REPLACE_COMPONENT = "replace_component"
    ROLLBACK_VERSION = "rollback_version"
    REMOVE_MEMORY = "remove_memory"
    CHANGE_PROMPT = "change_prompt"
    CHANGE_RETRIEVER = "change_retriever"
    CHANGE_CONFIG = "change_config"
    REPLAY_TOOL_RESPONSE = "replay_tool_response"
    PATCH_POLICY = "patch_policy"
    CUSTOM = "custom"


class CausalIntervention(DGXBaseModel):
    """
    A single, typed, causal intervention applied to one component variable.

    The intervention must change exactly one variable key on one component.
    Multiple simultaneous changes violate the single-intervention constraint
    and are rejected by the envelope builder.

    Fields
    ------
    intervention_id
        Unique identifier for this intervention.
    component_id
        The ``ComponentIdentity.identity_hash()`` of the target component.
    variable_key
        The ``ExecutionStateValue.key`` being changed.
    original_value_hash
        SHA-256 of the original value (from the ExecutionStateSnapshot).
    replacement_value_hash
        SHA-256 of the replacement value.  Must differ from original.
    intervention_type
        One of the CausalInterventionType values.
    reason
        Human-readable justification for this intervention.
    expected_direct_effects
        List of variable keys that are expected to change as a direct
        (first-order) causal consequence of this intervention.
    """
    intervention_id: UUID = Field(default_factory=_new_uuid)
    component_id: str = Field(min_length=1, max_length=255)
    variable_key: str = Field(min_length=1, max_length=255)
    original_value_hash: str = Field(min_length=64, max_length=64)
    replacement_value_hash: str = Field(min_length=64, max_length=64)
    intervention_type: CausalInterventionType
    reason: str = Field(min_length=1, max_length=2000)
    expected_direct_effects: list[str] = Field(default_factory=list)

    @field_validator("original_value_hash", "replacement_value_hash")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        if len(v) != 64:
            raise ValueError("Hash must be a 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Hash must be hexadecimal")
        return v.lower()

    @model_validator(mode="after")
    def hashes_must_differ(self) -> "CausalIntervention":
        if self.original_value_hash == self.replacement_value_hash:
            raise ValueError(
                "Intervention is a no-op: original_value_hash == replacement_value_hash. "
                "A causal intervention must actually change something."
            )
        return self


# Removed ExogenousHandlingStrategy and ExogenousVariableSpec (migrated to exogenous.py)


# ─── Equivalence Constraint Types ─────────────────────────────────────────────

class EquivalenceConstraintType(str, enum.Enum):
    """
    How to compare a frozen/constrained variable between original and replay.

    EXACT_HASH
        SHA-256 hashes must be byte-identical.  Default for security-critical
        fields (policy hash, tool schema, random seed).

    EXACT_VERSION
        Version strings must be identical (e.g., "v1.2.3" == "v1.2.3").

    TOLERANCE
        Numeric values may differ within a tolerance band.
        The tolerance is specified in the constraint's ``tolerance_value``.

    SET_EQUALITY
        Unordered set of values must be identical (order-invariant).

    SCHEMA_EQUALITY
        Structural equality of schemas (ignoring field ordering and whitespace).

    SEMANTIC_TOLERANCE
        Semantic similarity above a threshold (e.g., cosine > 0.98).
        WARNING: introduces nondeterminism — use sparingly.

    POLICY_DEFINED
        Constraint type is defined by the runtime policy engine.
        The envelope records the policy_version that defines the constraint.
    """
    EXACT_HASH = "exact_hash"
    EXACT_VERSION = "exact_version"
    TOLERANCE = "tolerance"
    SET_EQUALITY = "set_equality"
    SCHEMA_EQUALITY = "schema_equality"
    SEMANTIC_TOLERANCE = "semantic_tolerance"
    POLICY_DEFINED = "policy_defined"


class EquivalenceConstraint(DGXBaseModel):
    """
    A specific equivalence constraint applied to a frozen variable.
    """
    variable_key: str = Field(min_length=1, max_length=255)
    constraint_type: EquivalenceConstraintType
    tolerance_value: Optional[float] = None
    policy_version: Optional[str] = None
    description: str = ""


# ─── Default constraints for security/config fields ──────────────────────────

_DEFAULT_EXACT_HASH_KEYS = frozenset({
    "policy_hash", "tool_schema", "random_seed", "authorization_context_hash",
    "container_image_digest", "dependency_lockfile_hash",
})


# ─── Replay Equivalence Envelope ──────────────────────────────────────────────

_ENVELOPE_DOMAIN_PREFIX = "DGX-REPLAY-EQUIVALENCE-V1"
_ENVELOPE_SCHEMA_VERSION = "1.0"


class ReplayEquivalenceEnvelope(DGXBaseModel):
    """
    Pre-replay specification defining the validity boundary of a causal experiment.

    Created BEFORE replay execution.  Binds:
      - the original trace state
      - the intervention
      - which variables are frozen, intervened, endogenous, exogenous
      - which components may and must not diverge
      - equivalence constraints on frozen variables
      - the policy version governing the experiment
      - a trusted timestamp reference
      - a cryptographic envelope hash committing to all of the above

    Fields
    ------
    envelope_id
        Unique identifier for this envelope instance.
    original_trace_id
        The TraceArtifact.id (or run_id) of the original execution.
    replay_id
        The UUID assigned to the replay execution (pre-allocated).
    tenant_id
        Must match every component identity in the graph.
    intervention
        The single CausalIntervention to be applied.
    original_state_hash
        The ExecutionStateSnapshot.snapshot_hash of the original run.
    frozen_variables
        Keys of variables that MUST remain identical.
    intervened_variables
        Keys of variables that are explicitly changed.
    exogenous_variables
        Specifications for external/uncontrolled variables.
    allowed_descendant_components
        Component identity hashes permitted to exhibit endogenous divergence
        (causally downstream of the intervention).
    forbidden_divergence_components
        Component identity hashes that MUST NOT diverge under any circumstance.
    nondeterministic_variables
        Keys of variables that cannot be guaranteed identical.
    equivalence_constraints
        Typed constraints on frozen variables.
    generated_at
        UTC timestamp when this envelope was generated.
    trusted_timestamp_reference
        Reference to the trusted time source (e.g., TSA URL, Lamport clock ID).
    policy_version
        Version of the policy governing this experiment.
    schema_version
        Envelope schema version for forward compatibility.
    envelope_hash
        SHA-256 of the canonical serialization of all fields above.
    """
    envelope_id: UUID = Field(default_factory=_new_uuid)
    original_trace_id: UUID
    replay_id: UUID
    tenant_id: UUID
    intervention: CausalIntervention
    original_state_hash: str = Field(min_length=64, max_length=64)
    frozen_variables: list[str] = Field(default_factory=list)
    intervened_variables: list[str] = Field(default_factory=list)
    exogenous_variables: list["ExogenousStateRecord"] = Field(default_factory=list)
    allowed_descendant_components: list[str] = Field(default_factory=list)
    forbidden_divergence_components: list[str] = Field(default_factory=list)
    nondeterministic_variables: list[str] = Field(default_factory=list)
    equivalence_constraints: list[EquivalenceConstraint] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=_utcnow)
    trusted_timestamp_reference: Optional[str] = None
    policy_version: str = Field(min_length=1, max_length=128)
    schema_version: str = Field(default=_ENVELOPE_SCHEMA_VERSION, min_length=1)
    envelope_hash: str = ""

    @field_validator("original_state_hash")
    @classmethod
    def validate_state_hash(cls, v: str) -> str:
        if len(v) != 64:
            raise ValueError("original_state_hash must be 64 hex chars")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("original_state_hash must be hexadecimal")
        return v.lower()

    @model_validator(mode="after")
    def validate_and_compute(self) -> "ReplayEquivalenceEnvelope":
        # 1. Frozen and intervened must not overlap
        frozen_set = set(self.frozen_variables)
        intervened_set = set(self.intervened_variables)
        overlap = frozen_set & intervened_set
        if overlap:
            raise ValueError(
                f"Frozen and intervened variable sets overlap: {overlap}. "
                "A variable cannot be both frozen and intervened."
            )

        # 2. Allowed and forbidden descendants must not overlap
        allowed_set = set(self.allowed_descendant_components)
        forbidden_set = set(self.forbidden_divergence_components)
        divergence_overlap = allowed_set & forbidden_set
        if divergence_overlap:
            raise ValueError(
                f"Allowed and forbidden divergence component sets overlap: "
                f"{divergence_overlap}. Contradictory specification."
            )

        # 3. Nondeterministic should not be in frozen
        nondet_set = set(self.nondeterministic_variables)
        frozen_nondet = frozen_set & nondet_set
        if frozen_nondet:
            raise ValueError(
                f"Variables classified as both FROZEN and NONDETERMINISTIC: "
                f"{frozen_nondet}. Nondeterministic variables cannot be frozen."
            )

        # 4. Compute envelope hash
        if not self.envelope_hash:
            self.envelope_hash = self._compute_hash()
        return self

    def _compute_hash(self) -> str:
        """
        Cryptographic binding of all envelope contents.
        Uses domain separation ``DGX-REPLAY-EQUIVALENCE-V1``.
        """
        payload = {
            "domain": _ENVELOPE_DOMAIN_PREFIX,
            "schema_version": self.schema_version,
            "original_trace_id": str(self.original_trace_id),
            "replay_id": str(self.replay_id),
            "tenant_id": str(self.tenant_id),
            "intervention": {
                "intervention_id": str(self.intervention.intervention_id),
                "component_id": self.intervention.component_id,
                "variable_key": self.intervention.variable_key,
                "original_value_hash": self.intervention.original_value_hash,
                "replacement_value_hash": self.intervention.replacement_value_hash,
                "intervention_type": self.intervention.intervention_type.value
                if hasattr(self.intervention.intervention_type, "value")
                else str(self.intervention.intervention_type),
            },
            "original_state_hash": self.original_state_hash,
            "frozen_variables": sorted(self.frozen_variables),
            "intervened_variables": sorted(self.intervened_variables),
            "exogenous_variables": sorted(
                [
                    {
                        "key": ev.key,
                        "replay_strategy": ev.replay_strategy.value
                        if hasattr(ev.replay_strategy, "value") else str(ev.replay_strategy),
                    }
                    for ev in self.exogenous_variables
                ],
                key=lambda x: x["key"],
            ),
            "allowed_descendant_components": sorted(self.allowed_descendant_components),
            "forbidden_divergence_components": sorted(self.forbidden_divergence_components),
            "nondeterministic_variables": sorted(self.nondeterministic_variables),
            "equivalence_constraints": sorted(
                [
                    {
                        "variable_key": ec.variable_key,
                        "constraint_type": ec.constraint_type.value
                        if hasattr(ec.constraint_type, "value")
                        else str(ec.constraint_type),
                    }
                    for ec in self.equivalence_constraints
                ],
                key=lambda x: x["variable_key"],
            ),
            "policy_version": self.policy_version,
            "generated_at": self.generated_at.isoformat(),
            "trusted_timestamp_reference": self.trusted_timestamp_reference,
        }
        serialized = json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Recompute hash and compare to stored hash."""
        return self._compute_hash() == self.envelope_hash
