"""State-bound admission receipts for replay and recovery execution.

The object is the portable receipt contract.  Durable deployments persist its
canonical payload in :mod:`admission_store` before dispatching to a worker.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.interfaces import (
    ResourceContext,
    ResourceEstimate,
    ResourceMeasurement,
    ResourceReservation,
)

if TYPE_CHECKING:
    from packages.ledger.src.crypto import SignerProtocol


RECEIPT_SCHEMA_VERSION = "1"
RECEIPT_SIGNATURE_ALGORITHM = "Ed25519"
_RECEIPT_HASH_DOMAIN = b"DGX-REPLAY-ADMISSION-V1\0"
_RECEIPT_SIGNATURE_DOMAIN = b"DGX-REPLAY-ADMISSION-SIGNATURE-V1\0"


class ReceiptStatus(StrEnum):
    ISSUED = "ISSUED"
    VERIFIED = "VERIFIED"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"
    VOIDED = "VOIDED"
    EXPIRED = "EXPIRED"


class ReceiptTerminalReason(StrEnum):
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    BINDING_MISMATCH = "BINDING_MISMATCH"
    EVIDENCE_CEILING_EXCEEDED = "EVIDENCE_CEILING_EXCEEDED"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    EXECUTION_FAILED = "EXECUTION_FAILED"


_EVIDENCE_RANK = {
    EvidenceClassification.UNVERIFIED: 0,
    EvidenceClassification.TEST_FIXTURE: 1,
    EvidenceClassification.SYNTHETIC_SIMULATION: 2,
    EvidenceClassification.REAL_CONTROLLED_EXPERIMENT: 3,
    EvidenceClassification.PRODUCTION: 4,
}


@dataclass
class AdmissionReceiptV1:
    """Canonical V1 binding between execution state, policy and reserved capacity."""

    tenant_id: str
    manifest_hash: str
    trace_root_hash: str
    intervention_hash: str
    current_version: str
    candidate_version: str
    policy_hash: str
    predicted_cost: float
    uncertainty_margin: float
    rollback_reserve: float
    evidence_ceiling: EvidenceClassification
    capsule_hash: str
    issued_at: datetime
    expires_at: datetime
    receipt_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: str = RECEIPT_SCHEMA_VERSION
    workload_id: str = ""
    run_id: str = ""
    nonce: str = field(default_factory=lambda: str(uuid4()))
    policy_version: str = ""
    approval_id: str = ""
    resource_pool_id: str = "default"
    key_id: str = ""
    signature_algorithm: str = ""
    payload_signature: str = ""
    issued_by: str = ""
    status: ReceiptStatus = ReceiptStatus.ISSUED
    terminal_reason: ReceiptTerminalReason | None = None
    consumed_by_worker_id: str = ""
    consumed_at: datetime | None = None
    _reservation: ResourceReservation | None = field(default=None, repr=False)
    _binding_hash: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        self.evidence_ceiling = EvidenceClassification(self.evidence_ceiling)
        self.status = ReceiptStatus(self.status)
        if self.terminal_reason is not None:
            self.terminal_reason = ReceiptTerminalReason(self.terminal_reason)
        if self.schema_version != RECEIPT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported admission receipt schema: {self.schema_version}.")
        self.issued_at = self._require_aware_utc(self.issued_at, "issued_at")
        self.expires_at = self._require_aware_utc(self.expires_at, "expires_at")
        if self.consumed_at is not None:
            self.consumed_at = self._require_aware_utc(self.consumed_at, "consumed_at")
        self._validate_numbers()
        if self.expires_at <= self.issued_at:
            raise ValueError("Receipt expiry must be after issue time.")
        self._binding_hash = self._compute_binding_hash()

    @staticmethod
    def _require_aware_utc(value: datetime, field_name: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"Receipt {field_name} must be timezone-aware.")
        return value.astimezone(UTC)

    @staticmethod
    def _canonical_datetime(value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    @classmethod
    def issue(
        cls,
        *,
        resource_context: ResourceContext,
        tenant_id: str,
        manifest_hash: str,
        trace_root_hash: str,
        intervention_hash: str,
        current_version: str,
        candidate_version: str,
        policy_hash: str,
        predicted_cost: float,
        uncertainty_margin: float,
        rollback_reserve: float,
        evidence_ceiling: EvidenceClassification,
        capsule_hash: str,
        expires_at: datetime,
        issued_at: datetime | None = None,
        workload_id: str = "",
        run_id: str = "",
        policy_version: str = "",
        approval_id: str = "",
        resource_pool_id: str = "default",
        issued_by: str = "",
        receipt_id: str | None = None,
        nonce: str | None = None,
    ) -> AdmissionReceiptV1:
        issued = issued_at or datetime.now(UTC)
        receipt = cls(
            tenant_id=tenant_id,
            manifest_hash=manifest_hash,
            trace_root_hash=trace_root_hash,
            intervention_hash=intervention_hash,
            current_version=current_version,
            candidate_version=candidate_version,
            policy_hash=policy_hash,
            predicted_cost=predicted_cost,
            uncertainty_margin=uncertainty_margin,
            rollback_reserve=rollback_reserve,
            evidence_ceiling=evidence_ceiling,
            capsule_hash=capsule_hash,
            issued_at=issued,
            expires_at=expires_at,
            workload_id=workload_id,
            run_id=run_id,
            policy_version=policy_version,
            approval_id=approval_id,
            resource_pool_id=resource_pool_id,
            issued_by=issued_by,
            receipt_id=receipt_id or str(uuid4()),
            nonce=nonce or str(uuid4()),
        )
        estimate = ResourceEstimate(cost_usd=predicted_cost + uncertainty_margin + rollback_reserve)
        receipt._reservation = resource_context.reserve(estimate)
        if receipt._reservation is None:
            raise ValueError("Replay admission refused: reservation exceeds available budget.")
        return receipt

    @property
    def binding_hash(self) -> str:
        # Recompute so accidental mutation cannot expose a stale hash as current.
        return self._compute_binding_hash()

    def _validate_numbers(self) -> None:
        values = (self.predicted_cost, self.uncertainty_margin, self.rollback_reserve)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Receipt resource values must be finite and non-negative.")

    def _canonical_payload(self) -> dict[str, Any]:
        """Return immutable fields covered by the binding hash and signature."""
        return {
            "receipt_id": self.receipt_id,
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "workload_id": self.workload_id,
            "run_id": self.run_id,
            "nonce": self.nonce,
            "manifest_hash": self.manifest_hash,
            "trace_root_hash": self.trace_root_hash,
            "intervention_hash": self.intervention_hash,
            "current_version": self.current_version,
            "candidate_version": self.candidate_version,
            "policy_hash": self.policy_hash,
            "policy_version": self.policy_version,
            "approval_id": self.approval_id,
            "predicted_cost": self.predicted_cost,
            "uncertainty_margin": self.uncertainty_margin,
            "rollback_reserve": self.rollback_reserve,
            "resource_pool_id": self.resource_pool_id,
            "evidence_ceiling": self.evidence_ceiling.value,
            "capsule_hash": self.capsule_hash,
            "issued_at": self._canonical_datetime(self.issued_at),
            "expires_at": self._canonical_datetime(self.expires_at),
            "key_id": self.key_id,
            "signature_algorithm": self.signature_algorithm,
            "issued_by": self.issued_by,
        }

    @property
    def canonical_payload(self) -> dict[str, Any]:
        """Return the exact immutable payload covered by hash/signature operations."""
        return self._canonical_payload().copy()

    @property
    def stored_payload(self) -> dict[str, Any]:
        """Return the durable representation, including mutable signature metadata."""
        return {**self._canonical_payload(), "payload_signature": self.payload_signature}

    @property
    def canonical_bytes(self) -> bytes:
        """Serialize the immutable payload deterministically for hashing and signing."""
        return json.dumps(
            self._canonical_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    @property
    def signing_bytes(self) -> bytes:
        return _RECEIPT_SIGNATURE_DOMAIN + self.canonical_bytes

    def _compute_binding_hash(self) -> str:
        return hashlib.sha256(_RECEIPT_HASH_DOMAIN + self.canonical_bytes).hexdigest()

    def sign(self, signer: SignerProtocol) -> None:
        """Bind signer identity before producing an Ed25519 signature."""
        if self.status != ReceiptStatus.ISSUED:
            raise ValueError("Only an issued receipt can be signed.")
        self.key_id = signer.key_id()
        self.signature_algorithm = RECEIPT_SIGNATURE_ALGORITHM
        self._binding_hash = self._compute_binding_hash()
        self.payload_signature = signer.sign(self.signing_bytes)

    def verify_signature(self, public_key_b64: str) -> tuple[bool, str]:
        """Verify issuer authenticity independently from the issuing process."""
        if not self.key_id or not self.payload_signature:
            return False, "Admission receipt is unsigned."
        if self.signature_algorithm != RECEIPT_SIGNATURE_ALGORITHM:
            return False, "Unsupported admission receipt signature algorithm."
        from packages.ledger.src.crypto import verify_signature

        if not verify_signature(public_key_b64, self.signing_bytes, self.payload_signature):
            return False, "Admission receipt signature is invalid."
        return True, "ok"

    @staticmethod
    def intervention_binding_hash(
        intervention_id: str,
        target_component: str,
        current_version: str,
        candidate_version: str,
    ) -> str:
        """Hash the exact intervention identity shared by coordinator and worker."""
        payload = json.dumps(
            {
                "intervention_id": intervention_id,
                "target_component": target_component,
                "current_version": current_version,
                "candidate_version": candidate_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(b"DGX-REPLAY-INTERVENTION-V1\0" + payload).hexdigest()

    def verify_binding(self, **actual: Any) -> tuple[bool, str]:
        """Verify worker-provided values before any execution allocation."""
        if self.status != ReceiptStatus.ISSUED:
            return False, f"Receipt is {self.status.value.lower()}."
        if datetime.now(UTC) >= self.expires_at:
            self.void()
            return False, "Receipt has expired."
        expected = self._canonical_payload()
        for key, value in actual.items():
            if key not in expected:
                return False, f"Unknown receipt binding: {key}."
            if value != expected[key]:
                return False, f"Receipt binding mismatch: {key}."
        return True, "ok"

    def verify_evidence(self, evidence_class: EvidenceClassification) -> tuple[bool, str]:
        """Prevent a result from being promoted above its admitted authority."""
        actual = EvidenceClassification(evidence_class)
        if _EVIDENCE_RANK[actual] > _EVIDENCE_RANK[self.evidence_ceiling]:
            return False, "Evidence classification exceeds the receipt ceiling."
        return True, "ok"

    def mark_verified(self) -> None:
        """Claim the receipt after a successful worker-boundary verification."""
        if self.status != ReceiptStatus.ISSUED:
            raise ValueError("Receipt is not available for verification.")
        self.status = ReceiptStatus.VERIFIED

    def commit(self, measurement: ResourceMeasurement) -> None:
        if (
            self.status not in {ReceiptStatus.ISSUED, ReceiptStatus.VERIFIED}
            or self._reservation is None
        ):
            raise ValueError("Receipt is not available for commit.")
        self._reservation.commit(measurement)
        self.status = ReceiptStatus.CONSUMED

    def release(self) -> None:
        if (
            self.status not in {ReceiptStatus.ISSUED, ReceiptStatus.VERIFIED}
            or self._reservation is None
        ):
            return
        self._reservation.release()
        self.status = ReceiptStatus.RELEASED

    def void(self) -> None:
        if self.status == ReceiptStatus.ISSUED:
            self.release()
            self.status = ReceiptStatus.VOIDED


# Compatibility name retained while callers migrate to the canonical V1 contract.
ReplayAdmissionReceipt = AdmissionReceiptV1
