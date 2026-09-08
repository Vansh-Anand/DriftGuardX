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
from typing import Any
from uuid import uuid4

from packages.contracts.src.evidence import EvidenceClassification
from packages.contracts.src.interfaces import (
    ResourceContext,
    ResourceEstimate,
    ResourceMeasurement,
    ResourceReservation,
)


class ReceiptStatus(StrEnum):
    ISSUED = "ISSUED"
    VERIFIED = "VERIFIED"
    CONSUMED = "CONSUMED"
    RELEASED = "RELEASED"
    VOIDED = "VOIDED"


_EVIDENCE_RANK = {
    EvidenceClassification.UNVERIFIED: 0,
    EvidenceClassification.TEST_FIXTURE: 1,
    EvidenceClassification.SYNTHETIC_SIMULATION: 2,
    EvidenceClassification.REAL_CONTROLLED_EXPERIMENT: 3,
    EvidenceClassification.PRODUCTION: 4,
}


@dataclass
class ReplayAdmissionReceipt:
    """A single-use binding between replay identity, policy and reserved capacity."""

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
    status: ReceiptStatus = ReceiptStatus.ISSUED
    _reservation: ResourceReservation | None = field(default=None, repr=False)
    _binding_hash: str = field(default="", init=False, repr=False)

    def __post_init__(self) -> None:
        self.evidence_ceiling = EvidenceClassification(self.evidence_ceiling)
        self._validate_numbers()
        if self.expires_at <= self.issued_at:
            raise ValueError("Receipt expiry must be after issue time.")
        self._binding_hash = self._compute_binding_hash()

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
    ) -> ReplayAdmissionReceipt:
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
        )
        estimate = ResourceEstimate(cost_usd=predicted_cost + uncertainty_margin + rollback_reserve)
        receipt._reservation = resource_context.reserve(estimate)
        if receipt._reservation is None:
            raise ValueError("Replay admission refused: reservation exceeds available budget.")
        return receipt

    @property
    def binding_hash(self) -> str:
        return self._binding_hash

    def _validate_numbers(self) -> None:
        values = (self.predicted_cost, self.uncertainty_margin, self.rollback_reserve)
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Receipt resource values must be finite and non-negative.")

    def _canonical_payload(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "manifest_hash": self.manifest_hash,
            "trace_root_hash": self.trace_root_hash,
            "intervention_hash": self.intervention_hash,
            "current_version": self.current_version,
            "candidate_version": self.candidate_version,
            "policy_hash": self.policy_hash,
            "predicted_cost": self.predicted_cost,
            "uncertainty_margin": self.uncertainty_margin,
            "rollback_reserve": self.rollback_reserve,
            "evidence_ceiling": self.evidence_ceiling.value,
            "capsule_hash": self.capsule_hash,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }

    @property
    def canonical_payload(self) -> dict[str, Any]:
        """Return the exact state-bound payload persisted by a durable store."""
        return self._canonical_payload().copy()

    def _compute_binding_hash(self) -> str:
        payload = json.dumps(
            self._canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(b"DGX-REPLAY-ADMISSION-V1\0" + payload).hexdigest()

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
            if value != expected[key] and str(value) != str(expected[key]):
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
