"""
DriftGuard-X v2 — Execution State Foundation

Defines the typed execution state model required by:
  A. Replay Equivalence Envelope + Dynamic Causal Divergence Frontier
  B. Risk-Limited Sequential Causal Experiment Planner
  C. Minimum Causal Recovery Cut + Transportability Gate

Key design constraints
----------------------
- Canonical serialization uses domain separation (``DGX-EXECUTION-STATE-V1``).
- ``default=str`` is NEVER used in hashing paths — non-serialisable values fail loudly.
- Secrets MUST NOT be stored as raw values in ExecutionStateValue.
  Store only their hash (e.g., SHA-256 of a key, not the key itself).
- All datetimes must be timezone-aware UTC.

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

from packages.contracts.src.models import DGXBaseModel, _utcnow, _new_uuid


# ─── ExecutionVariableClass ───────────────────────────────────────────────────

class ExecutionVariableClass(str, enum.Enum):
    """
    Classifies how a state variable may change between an original run and a
    replay or causal intervention.

    FROZEN
        This variable MUST be identical between the original run and any replay.
        If it differs, the replay is invalid.  Example: random seed, corpus version.

    INTERVENED
        This variable was explicitly changed as part of the causal intervention.
        It is the "treatment" in the causal experiment.  Example: the swapped
        prompt template hash.

    ENDOGENOUS
        This variable is permitted to change, but ONLY because it is causally
        downstream of an INTERVENED variable.  Its change is expected and
        correctly attributed to the intervention.  Example: generated answer text
        when the model version is INTERVENED.

    EXOGENOUS
        This variable originates outside the agent execution boundary (e.g.,
        live retrieval results, external API responses, system time).  It is not
        controlled by the replay harness and must be hashed, not re-fetched.

    DERIVED
        This variable is computed deterministically from other state variables.
        Its value should be reproducible given the same inputs.  Example:
        reliability_score derived from span latencies.

    NONDETERMINISTIC
        This variable cannot be guaranteed identical across runs even with the
        same inputs (e.g., sampling from a stochastic model without a fixed seed).
        Its presence degrades replay equivalence evidence quality.

    UNKNOWN
        Classification is insufficient with available information.  Using UNKNOWN
        explicitly is preferred over fabricating a classification.
    """
    FROZEN = "frozen"
    INTERVENED = "intervened"
    ENDOGENOUS = "endogenous"
    EXOGENOUS = "exogenous"
    DERIVED = "derived"
    NONDETERMINISTIC = "nondeterministic"
    UNKNOWN = "unknown"


# ─── ExecutionStateValue ──────────────────────────────────────────────────────

# Allowed value kinds for ExecutionStateValue.
# Use these string literals as the ``source`` field.
_ALLOWED_STATE_SOURCES = frozenset({
    "model_version",
    "prompt_hash",
    "tool_schema",
    "retriever_config",
    "memory_snapshot_hash",
    "index_version",
    "random_seed",
    "temperature",
    "policy_hash",
    "external_api_response_hash",
    "environment_version",
    "tenant",
    "authorization_context_hash",
    "trusted_timestamp_metadata",
    "corpus_version",
    "embedding_model_version",
    "container_image_digest",
    "dependency_lockfile_hash",
    "custom",         # Allowed for extension; caller must document semantics.
})


class ExecutionStateValue(DGXBaseModel):
    """
    A single typed key-value pair in an execution state snapshot.

    The ``value_hash`` stores the SHA-256 of the canonical serialization of the
    actual value.  Raw secrets (API keys, auth tokens) MUST NOT be placed here.
    Hash them before constructing this object.

    Fields
    ------
    key
        Logical name of the variable (e.g., ``"prompt_template_version"``).
        Must be unique within a snapshot (enforced by ExecutionStateSnapshot).
    value_hash
        SHA-256 hex digest of the canonical value.  64 hex chars.  Computed by
        the caller using ``hash_state_value()``.
    component_id
        The ComponentIdentity (as its identity_hash string) of the component
        that produced or owns this value.  May be None for cross-cutting state.
    variable_class
        Classification of how this variable may change across replays.
    source
        One of the allowed source kinds from ``_ALLOWED_STATE_SOURCES``.
    timestamp
        UTC timestamp when this value was captured.  Timezone-aware required.
    metadata
        Optional structured metadata for auditing (e.g., version label, tool
        name).  Must be JSON-serialisable.  Must NOT contain secrets.
    """
    key: str = Field(min_length=1, max_length=255)
    value_hash: str = Field(min_length=64, max_length=64)
    component_id: Optional[str] = None    # ComponentIdentity.identity_hash()
    variable_class: ExecutionVariableClass
    source: str
    timestamp: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("value_hash")
    @classmethod
    def validate_sha256_hex(cls, v: str) -> str:
        if len(v) != 64:
            raise ValueError("value_hash must be a 64-character hex string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("value_hash must be hexadecimal")
        return v.lower()

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in _ALLOWED_STATE_SOURCES:
            raise ValueError(
                f"source '{v}' is not in the allowed set: {sorted(_ALLOWED_STATE_SOURCES)}"
            )
        return v

    @field_validator("timestamp")
    @classmethod
    def require_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return v

    @field_validator("metadata")
    @classmethod
    def metadata_no_secrets(cls, v: dict) -> dict:
        """Basic guard: reject keys that look like secrets."""
        forbidden_keys = {"password", "secret", "api_key", "token", "private_key"}
        for k in v:
            if any(f in k.lower() for f in forbidden_keys):
                raise ValueError(
                    f"metadata key '{k}' appears to contain a secret. "
                    "Store only the hash, not the raw value."
                )
        return v


def hash_state_value(value: Any) -> str:
    """
    Canonical hashing helper for execution state values.

    Accepts any JSON-serialisable value.  Uses domain separation prefix
    ``DGX-STATE-VALUE-V1``.  Does NOT fall back to str() for non-serialisable
    objects — raises TypeError instead so callers know they need to pre-process.

    Parameters
    ----------
    value
        The raw value to hash (str, int, float, dict, list, None, bool).

    Returns
    -------
    str
        64-character lowercase SHA-256 hex digest.
    """
    payload = {
        "domain": "DGX-STATE-VALUE-V1",
        "value": value,
    }
    # Raises TypeError for non-JSON-serialisable input — intentional.
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                            ensure_ascii=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# ─── ExecutionStateSnapshot ───────────────────────────────────────────────────

_SNAPSHOT_SCHEMA_VERSION = "1.0"
_SNAPSHOT_DOMAIN_PREFIX = "DGX-EXECUTION-STATE-V1"


class ExecutionStateSnapshot(DGXBaseModel):
    """
    Immutable snapshot of all typed execution state variables for one run.

    The ``snapshot_hash`` commits to the domain-separated canonical serialization
    of all values.  Any tampering with individual ``ExecutionStateValue`` entries
    will break the hash.

    Fields
    ------
    run_id
        The RequestRun.id this snapshot belongs to.
    trace_id
        The TraceArtifact.id this snapshot was captured from.
    tenant_id
        Must match every ``ExecutionStateValue.component_id``'s tenant.
    captured_at
        Timezone-aware UTC timestamp of when the snapshot was taken.
    values
        List of typed state values.  No duplicate keys allowed.
    snapshot_hash
        SHA-256 hex digest of the canonical form.  Computed automatically.
    schema_version
        Schema version for forward-compatibility checks.
    """
    id: UUID = Field(default_factory=_new_uuid)
    run_id: UUID
    trace_id: UUID
    tenant_id: UUID
    captured_at: datetime = Field(default_factory=_utcnow)
    values: list[ExecutionStateValue] = Field(default_factory=list)
    snapshot_hash: str = ""
    schema_version: str = _SNAPSHOT_SCHEMA_VERSION

    @field_validator("captured_at")
    @classmethod
    def require_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware (UTC)")
        return v

    @model_validator(mode="after")
    def validate_and_compute(self) -> "ExecutionStateSnapshot":
        # 1. Reject duplicate keys
        seen_keys: set[str] = set()
        for sv in self.values:
            if sv.key in seen_keys:
                raise ValueError(
                    f"Duplicate state key '{sv.key}' in ExecutionStateSnapshot. "
                    "Each key must appear exactly once."
                )
            seen_keys.add(sv.key)

        # 2. Compute snapshot hash if not already set
        if not self.snapshot_hash:
            self.snapshot_hash = self._compute_hash()
        return self

    def _compute_hash(self) -> str:
        """
        Deterministic canonical hash.  Uses domain separation prefix.
        Sorted by key to guarantee ordering independence.
        Does NOT use default=str — non-serialisable metadata will raise TypeError.
        """
        sorted_values = sorted(self.values, key=lambda v: v.key)
        value_entries = [
            {
                "key": sv.key,
                "value_hash": sv.value_hash,
                "variable_class": sv.variable_class.value
                if hasattr(sv.variable_class, "value") else str(sv.variable_class),
                "source": sv.source,
                "component_id": sv.component_id,
            }
            for sv in sorted_values
        ]
        payload = {
            "domain": _SNAPSHOT_DOMAIN_PREFIX,
            "schema_version": self.schema_version,
            "run_id": str(self.run_id),
            "trace_id": str(self.trace_id),
            "tenant_id": str(self.tenant_id),
            "captured_at": self.captured_at.isoformat(),
            "values": value_entries,
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def verify_integrity(self) -> bool:
        """Recompute hash and compare to stored hash. Returns False if tampered."""
        return self._compute_hash() == self.snapshot_hash

    def get_value(self, key: str) -> Optional[ExecutionStateValue]:
        """Look up a state value by key."""
        for sv in self.values:
            if sv.key == key:
                return sv
        return None

    def frozen_keys(self) -> list[str]:
        """Return all keys classified as FROZEN."""
        return [sv.key for sv in self.values
                if sv.variable_class == ExecutionVariableClass.FROZEN]

    def intervened_keys(self) -> list[str]:
        """Return all keys classified as INTERVENED."""
        return [sv.key for sv in self.values
                if sv.variable_class == ExecutionVariableClass.INTERVENED]
