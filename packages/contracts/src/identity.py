"""
DriftGuard-X v2 — ComponentIdentity

A strongly-typed, tenant-scoped component identifier.
This is richer than ComponentVersion (which tracks a version's lifecycle state).
ComponentIdentity answers: "exactly which artefact in which tenant is this?"

PRIVATE — All Rights Reserved.
"""
from __future__ import annotations

import hashlib
import json
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from packages.contracts.src.models import DGXBaseModel, ComponentType, _new_uuid


class ComponentIdentity(DGXBaseModel):
    """
    Strongly-typed, tenant-scoped identity for a deployed component artefact.

    Fields
    ------
    component_id
        Opaque unique identifier for this component instance (e.g., the UUID of
        a model deployment, a retriever shard, a tool registration).  Must NOT
        be derived from any secret value.
    component_type
        Enumerated type from ComponentType.  No substring matching.
    version
        Optional human-readable version label (e.g. "v1.2.3", "sha256:abc...").
        May be None when the component does not have an explicit versioning scheme.
    artifact_hash
        Optional SHA-256 hex digest of the component artefact (model weights,
        tool schema file, prompt template, etc.).  Must be lowercase hex if set.
        Must NOT be used to store secrets.
    tenant_id
        The tenant UUID that owns/deployed this component.  Cross-tenant reads
        of a ComponentIdentity are rejected by the verifier.
    """
    component_id: str = Field(min_length=1, max_length=255)
    component_type: ComponentType
    version: Optional[str] = Field(default=None, min_length=1, max_length=128)
    artifact_hash: Optional[str] = Field(default=None, min_length=64, max_length=64)
    tenant_id: UUID

    @field_validator("artifact_hash")
    @classmethod
    def validate_artifact_hash(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) != 64:
            raise ValueError("artifact_hash must be a 64-character SHA-256 hex digest")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("artifact_hash must contain only hexadecimal characters")
        return v.lower()

    def identity_hash(self) -> str:
        """
        Deterministic hash of the identity tuple (component_id, component_type,
        version, artifact_hash, tenant_id).  Uses domain separation prefix
        ``DGX-IDENTITY-V1`` to prevent cross-context hash collisions.

        Does NOT use default=str so that non-serialisable values fail loudly.
        """
        payload = {
            "domain": "DGX-IDENTITY-V1",
            "component_id": self.component_id,
            "component_type": self.component_type.value
            if hasattr(self.component_type, "value") else str(self.component_type),
            "version": self.version,
            "artifact_hash": self.artifact_hash,
            "tenant_id": str(self.tenant_id),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                                ensure_ascii=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def is_same_tenant(self, other: "ComponentIdentity") -> bool:
        """Returns True only if both identities belong to the same tenant."""
        return self.tenant_id == other.tenant_id

    def cross_tenant_check(self, requesting_tenant_id: UUID) -> None:
        """
        Raises ValueError if the requesting tenant does not match the identity's
        tenant.  Call this at every boundary that reads a ComponentIdentity.
        """
        if self.tenant_id != requesting_tenant_id:
            raise ValueError(
                f"Cross-tenant access rejected: identity belongs to tenant "
                f"{self.tenant_id}, but request is from {requesting_tenant_id}."
            )
