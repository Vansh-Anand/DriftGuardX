"""
DriftGuard-X v2 — Ledger Schema and Canonicalization
PRIVATE — All Rights Reserved.

Defines the RecoveryCertificate schema and deterministic serialization.
Byte-for-byte exact hashing is required across all Python versions.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

DOMAIN_SEPARATOR = "DriftGuardX-Recovery-Cert-V1"

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
    trace_after_digest: Optional[str]
    replay_capsule_hash: str
    
    # Intervention & Policy
    intervention_vector: Dict[str, Any]
    contribution_metrics: Dict[str, float]
    certification_method: str
    epsilon: float
    delta: float
    policy_version: str
    policy_reason: str
    approvals: List[str]
    
    # Execution
    action_result: str
    verification_result: str
    rollback_capsule_digest: Optional[str]
    
    # Ledger specific
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_cert_hash: str = "GENESIS"
    
    # Authentication (Set during signing, excluded from payload hash)
    signature: Optional[str] = None
    signer_key_id: Optional[str] = None
    signer_pub_key: Optional[str] = None

    def _canonical_dict(self) -> Dict[str, Any]:
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
        payload = {
            "domain": DOMAIN_SEPARATOR,
            "version": "1.0",
            "data": self._canonical_dict()
        }
        # Separators=(',', ':') removes whitespace
        # sort_keys=True ensures key ordering is deterministic
        json_str = json.dumps(payload, separators=(',', ':'), sort_keys=True, ensure_ascii=True)
        return json_str.encode('utf-8')

    def compute_hash(self) -> str:
        """Compute the SHA-256 hash of the canonical bytes."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecoveryCertificate:
        return cls(**data)
