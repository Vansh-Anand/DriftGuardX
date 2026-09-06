"""
DriftGuard-X v2 — Ledger Schema and Canonicalization
PRIVATE — All Rights Reserved.

Defines the RecoveryCertificate schema and deterministic serialization.
Byte-for-byte exact hashing is required across all Python versions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from packages.contracts.src.evidence import EvidenceClassification

DOMAIN_SEPARATOR = "DriftGuardX-Recovery-Cert-V2"


@dataclass
class RecoveryCertificate:
    """Canonical recovery certificate schema."""

    # Identity & Linkage
    cert_id: str
    tenant_id: str
    pipeline_id: str
    run_id: str

    # State digests
    trace_before_digest: str
    trace_after_digest: str | None
    replay_capsule_hash: str

    # Intervention & Policy
    intervention_vector: dict[str, Any]
    contribution_metrics: dict[str, float]
    certification_method: str
    epsilon: float
    delta: float
    policy_version: str
    policy_reason: str
    approvals: list[str]

    # Execution
    action_result: str
    verification_result: str
    rollback_capsule_digest: str | None

    # Ledger specific
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    previous_cert_hash: str = "GENESIS"
    evidence_kind: EvidenceClassification = EvidenceClassification.SYNTHETIC_SIMULATION

    # Authentication (Set during signing, excluded from payload hash)
    signature: str | None = None
    signer_key_id: str | None = None
    signer_pub_key: str | None = None

    def _canonical_dict(self) -> dict[str, Any]:
        """Return dict with signature fields omitted for hashing."""
        d = asdict(self)
        d.pop("signature", None)
        d.pop("signer_key_id", None)
        d.pop("signer_pub_key", None)
        return d

    def canonical_bytes(self) -> bytes:
        """
        Deterministic JSON serialization for hashing/signing.
        Includes schema version and domain separator.
        """
        payload = {"domain": DOMAIN_SEPARATOR, "version": "2.0", "data": self._canonical_dict()}
        # Separators=(',', ':') removes whitespace
        # sort_keys=True ensures key ordering is deterministic
        json_str = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=True)
        return json_str.encode("utf-8")

    def compute_hash(self) -> str:
        """Compute the SHA-256 hash of the canonical bytes."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecoveryCertificate:
        return cls(**data)
