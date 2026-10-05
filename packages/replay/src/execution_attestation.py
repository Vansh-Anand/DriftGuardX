"""Signed worker evidence linking an admission receipt to its execution outcome."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from packages.ledger.src.crypto import verify_signature

if TYPE_CHECKING:
    from packages.ledger.src.crypto import SignerProtocol

_ATTESTATION_HASH_DOMAIN = b"DGX-EXECUTION-ATTESTATION-V1\0"
_ATTESTATION_SIGNATURE_DOMAIN = b"DGX-EXECUTION-ATTESTATION-SIGNATURE-V1\0"


@dataclass
class ExecutionAttestationV1:
    receipt_id: str
    receipt_binding_hash: str
    tenant_id: str
    worker_id: str
    manifest_hash: str
    policy_hash: str
    runtime_version: str
    image_digest: str
    started_at: datetime
    completed_at: datetime
    outcome: str
    outcome_hash: str
    schema_version: str = "1"
    key_id: str = ""
    signature_algorithm: str = ""
    payload_signature: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != "1":
            raise ValueError(f"Unsupported execution attestation schema: {self.schema_version}.")
        self.started_at = self._aware_utc(self.started_at, "started_at")
        self.completed_at = self._aware_utc(self.completed_at, "completed_at")
        if self.completed_at < self.started_at:
            raise ValueError("Attestation completion cannot precede execution start.")

    @staticmethod
    def _aware_utc(value: datetime, field_name: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"Attestation {field_name} must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _timestamp(value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    @property
    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "receipt_id": self.receipt_id,
            "receipt_binding_hash": self.receipt_binding_hash,
            "tenant_id": self.tenant_id,
            "worker_id": self.worker_id,
            "manifest_hash": self.manifest_hash,
            "policy_hash": self.policy_hash,
            "runtime_version": self.runtime_version,
            "image_digest": self.image_digest,
            "started_at": self._timestamp(self.started_at),
            "completed_at": self._timestamp(self.completed_at),
            "outcome": self.outcome,
            "outcome_hash": self.outcome_hash,
            "key_id": self.key_id,
            "signature_algorithm": self.signature_algorithm,
        }

    @property
    def canonical_bytes(self) -> bytes:
        return json.dumps(
            self.canonical_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    @property
    def signing_bytes(self) -> bytes:
        return _ATTESTATION_SIGNATURE_DOMAIN + self.canonical_bytes

    @property
    def attestation_hash(self) -> str:
        return hashlib.sha256(_ATTESTATION_HASH_DOMAIN + self.canonical_bytes).hexdigest()

    @property
    def stored_payload(self) -> dict[str, Any]:
        return {**self.canonical_payload, "payload_signature": self.payload_signature}

    def sign(self, signer: SignerProtocol) -> None:
        self.key_id = signer.key_id()
        self.signature_algorithm = "Ed25519"
        self.payload_signature = signer.sign(self.signing_bytes)

    def verify_signature(self, public_key_b64: str) -> tuple[bool, str]:
        if not self.key_id or not self.payload_signature:
            return False, "Execution attestation is unsigned."
        if self.signature_algorithm != "Ed25519":
            return False, "Unsupported execution attestation signature algorithm."
        if not verify_signature(public_key_b64, self.signing_bytes, self.payload_signature):
            return False, "Execution attestation signature is invalid."
        return True, "ok"
