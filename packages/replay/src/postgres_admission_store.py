"""PostgreSQL authority for distributed admission and resource reservations."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast

from packages.contracts.src.evidence import EvidenceClassification
from packages.replay.src.admission_keys import (
    AdmissionReceiptTrustStore,
    receipt_signature_required,
)
from packages.replay.src.admission_receipt import (
    AdmissionReceiptV1,
    ReceiptStatus,
    ReceiptTerminalReason,
    ReplayAdmissionReceipt,
)
from packages.replay.src.admission_store import (
    AdmissionAuditEvent,
    AdmissionReceiptStore,
    _evaluate_verification,
    _receipt_from_persisted_payload,
)
from packages.replay.src.execution_attestation import ExecutionAttestationV1


def normalize_postgres_dsn(database_url: str) -> str:
    for driver in ("postgresql+asyncpg://", "postgresql+psycopg2://"):
        if database_url.startswith(driver):
            return "postgresql://" + database_url.removeprefix(driver)
    if database_url.startswith("postgresql://"):
        return database_url
    raise RuntimeError("Distributed admission requires a PostgreSQL database URL.")


class PostgresAdmissionReceiptStore:
    """Transactional cross-process receipt store with authoritative pool accounting."""

    def __init__(self, database_url: str | None = None, default_budget_usd: float | None = None):
        configured_url = (
            database_url
            or os.getenv("DGX_ADMISSION_DATABASE_URL")
            or os.getenv("DATABASE_URL", "")
            or ""
        )
        self.database_url = normalize_postgres_dsn(configured_url)
        configured_budget = default_budget_usd or float(
            os.getenv("DGX_ADMISSION_DEFAULT_POOL_BUDGET_USD", "1000")
        )
        if configured_budget <= 0:
            raise ValueError("Admission resource-pool budget must be positive.")
        self.default_budget = Decimal(str(configured_budget))

    def _connect(self) -> Any:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        return psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
        value = row["payload_json"]
        if isinstance(value, str):
            return cast(dict[str, Any], json.loads(value))
        return cast(dict[str, Any], value)

    def _append_event(
        self,
        cursor: Any,
        receipt_id: str,
        event_type: str,
        reason: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        from psycopg2.extras import Json

        cursor.execute(
            "SELECT sequence, event_hash FROM admission_audit_events "
            "WHERE receipt_id = %s ORDER BY sequence DESC LIMIT 1",
            (receipt_id,),
        )
        previous = cursor.fetchone()
        sequence = int(previous["sequence"]) + 1 if previous else 1
        previous_hash = str(previous["event_hash"]) if previous else None
        created_at = self._now()
        event_details = details or {}
        event_hash = AdmissionReceiptStore._event_hash(
            receipt_id,
            sequence,
            event_type,
            previous_hash,
            reason,
            event_details,
            created_at.isoformat(),
        )
        cursor.execute(
            "INSERT INTO admission_audit_events "
            "(receipt_id, sequence, event_type, event_hash, previous_event_hash, reason, "
            "details_json, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                receipt_id,
                sequence,
                event_type,
                event_hash,
                previous_hash,
                reason,
                Json(event_details),
                created_at,
            ),
        )

    def issue(self, receipt: ReplayAdmissionReceipt) -> str:
        from psycopg2.extras import Json

        reserved = Decimal(
            str(receipt.predicted_cost + receipt.uncertainty_margin + receipt.rollback_reserve)
        )
        payload = receipt.stored_payload
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT binding_hash FROM admission_receipts WHERE receipt_id = %s FOR UPDATE",
                (receipt.receipt_id,),
            )
            existing = cursor.fetchone()
            if existing:
                if str(existing["binding_hash"]) != receipt.binding_hash:
                    raise ValueError("Receipt ID is already bound to different state.")
                return receipt.receipt_id
            cursor.execute(
                "INSERT INTO admission_resource_pools "
                "(pool_id, budget_usd, reserved_usd, spent_usd, updated_at) "
                "VALUES (%s, %s, 0, 0, %s) ON CONFLICT (pool_id) DO NOTHING",
                (receipt.resource_pool_id, self.default_budget, self._now()),
            )
            cursor.execute(
                "SELECT budget_usd, reserved_usd, spent_usd FROM admission_resource_pools "
                "WHERE pool_id = %s FOR UPDATE",
                (receipt.resource_pool_id,),
            )
            pool = cursor.fetchone()
            available = (
                Decimal(pool["budget_usd"])
                - Decimal(pool["reserved_usd"])
                - Decimal(pool["spent_usd"])
            )
            if reserved > available:
                raise ValueError(
                    "Replay admission refused: shared reservation exceeds pool budget."
                )
            cursor.execute(
                "INSERT INTO admission_receipts "
                "(receipt_id, tenant_id, binding_hash, status, payload_json, reserved_cost_usd, "
                "resource_pool_id, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    receipt.receipt_id,
                    receipt.tenant_id,
                    receipt.binding_hash,
                    ReceiptStatus.ISSUED.value,
                    Json(payload),
                    reserved,
                    receipt.resource_pool_id,
                    self._now(),
                ),
            )
            cursor.execute(
                "UPDATE admission_resource_pools SET reserved_usd = reserved_usd + %s, "
                "updated_at = %s WHERE pool_id = %s",
                (reserved, self._now(), receipt.resource_pool_id),
            )
            self._append_event(cursor, receipt.receipt_id, "ISSUE", details=payload)
        return receipt.receipt_id

    def verify(
        self,
        receipt_id: str,
        *,
        actual: dict[str, Any],
        evidence_class: EvidenceClassification | None = None,
        now: datetime | None = None,
        trusted_public_keys: Mapping[str, str] | None = None,
        require_signature: bool | None = None,
    ) -> tuple[bool, str]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM admission_receipts WHERE receipt_id = %s FOR UPDATE", (receipt_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return False, "Admission receipt not found."
            status = ReceiptStatus(str(row["status"]))
            receipt = _receipt_from_persisted_payload(self._payload(row), receipt_id, status)
            decision = _evaluate_verification(
                receipt,
                actual=actual,
                evidence_class=evidence_class,
                now=now or self._now(),
                trusted_public_keys=trusted_public_keys,
                require_signature=require_signature,
            )
            if decision.reason:
                self._append_event(
                    cursor,
                    receipt_id,
                    "SIGNATURE_REFUSAL" if decision.signature_refusal else "MISMATCH_REFUSAL",
                    reason=decision.reason,
                    details={"actual": actual},
                )
                if status == ReceiptStatus.ISSUED:
                    target = ReceiptStatus.EXPIRED if decision.expired else ReceiptStatus.VOIDED
                    terminal_reason = (
                        ReceiptTerminalReason.EXPIRED
                        if decision.expired
                        else (
                            ReceiptTerminalReason.SIGNATURE_INVALID
                            if decision.signature_refusal
                            else ReceiptTerminalReason.BINDING_MISMATCH
                        )
                    )
                    self._release_reservation(cursor, row, target)
                    self._append_event(
                        cursor,
                        receipt_id,
                        "EXPIRE" if decision.expired else "VOID",
                        reason=decision.reason,
                        details={"terminal_reason": terminal_reason.value},
                    )
                return False, decision.reason
            cursor.execute(
                "UPDATE admission_receipts SET status = %s WHERE receipt_id = %s",
                (ReceiptStatus.VERIFIED.value, receipt_id),
            )
            self._append_event(cursor, receipt_id, "VERIFY", details=actual)
            return True, "ok"

    def _release_reservation(
        self, cursor: Any, row: Mapping[str, Any], target: ReceiptStatus
    ) -> None:
        now = self._now()
        cursor.execute(
            "UPDATE admission_receipts SET status = %s, terminal_at = %s WHERE receipt_id = %s",
            (target.value, now, row["receipt_id"]),
        )
        spent = (
            Decimal(row["reserved_cost_usd"]) if target == ReceiptStatus.CONSUMED else Decimal(0)
        )
        cursor.execute(
            "UPDATE admission_resource_pools SET "
            "reserved_usd = GREATEST(0, reserved_usd - %s), spent_usd = spent_usd + %s, "
            "updated_at = %s WHERE pool_id = %s",
            (row["reserved_cost_usd"], spent, now, row["resource_pool_id"]),
        )

    def _terminal_transition(
        self, receipt_id: str, target: ReceiptStatus, event_type: str, reason: str = ""
    ) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM admission_receipts WHERE receipt_id = %s FOR UPDATE", (receipt_id,)
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Admission receipt not found.")
            current = ReceiptStatus(str(row["status"]))
            allowed = {
                ReceiptStatus.CONSUMED: {ReceiptStatus.VERIFIED},
                ReceiptStatus.RELEASED: {ReceiptStatus.ISSUED, ReceiptStatus.VERIFIED},
                ReceiptStatus.VOIDED: {ReceiptStatus.ISSUED, ReceiptStatus.VERIFIED},
            }[target]
            if current not in allowed:
                return
            self._release_reservation(cursor, row, target)
            self._append_event(cursor, receipt_id, event_type, reason=reason)

    def consume(self, receipt_id: str) -> None:
        self._terminal_transition(receipt_id, ReceiptStatus.CONSUMED, "CONSUME")

    def record_attestation(
        self,
        attestation: ExecutionAttestationV1,
        *,
        trusted_public_keys: Mapping[str, str] | None = None,
        require_signature: bool | None = None,
    ) -> str:
        from psycopg2.extras import Json

        signature_required = (
            receipt_signature_required() if require_signature is None else require_signature
        )
        if attestation.payload_signature or signature_required:
            trust = (
                trusted_public_keys
                if trusted_public_keys is not None
                else AdmissionReceiptTrustStore.from_environment(
                    "DGX_WORKER_ATTESTATION_TRUSTED_KEYS_JSON"
                ).public_keys
            )
            public_key = trust.get(attestation.key_id)
            if public_key is None:
                raise ValueError("Worker attestation signing key is not trusted.")
            valid, reason = attestation.verify_signature(public_key)
            if not valid:
                raise ValueError(reason)
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status, binding_hash FROM admission_receipts "
                "WHERE receipt_id = %s FOR UPDATE",
                (attestation.receipt_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Admission receipt not found.")
            if ReceiptStatus(str(row["status"])) != ReceiptStatus.VERIFIED:
                raise ValueError("Execution attestation requires a verified receipt.")
            if str(row["binding_hash"]) != attestation.receipt_binding_hash:
                raise ValueError("Execution attestation receipt binding mismatch.")
            cursor.execute(
                "INSERT INTO admission_execution_attestations "
                "(receipt_id, attestation_hash, payload_json, created_at) "
                "VALUES (%s, %s, %s, %s)",
                (
                    attestation.receipt_id,
                    attestation.attestation_hash,
                    Json(attestation.stored_payload),
                    self._now(),
                ),
            )
            self._append_event(
                cursor,
                attestation.receipt_id,
                "ATTEST",
                details={"attestation_hash": attestation.attestation_hash},
            )
        return attestation.attestation_hash

    def release(self, receipt_id: str) -> None:
        self._terminal_transition(receipt_id, ReceiptStatus.RELEASED, "RELEASE")

    def void(self, receipt_id: str, reason: str = "") -> None:
        self._terminal_transition(receipt_id, ReceiptStatus.VOIDED, "VOID", reason=reason)

    def status(self, receipt_id: str) -> ReceiptStatus | None:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT status FROM admission_receipts WHERE receipt_id = %s", (receipt_id,)
            )
            row = cursor.fetchone()
            return ReceiptStatus(str(row["status"])) if row else None

    def binding_hash(self, receipt_id: str) -> str:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT binding_hash FROM admission_receipts WHERE receipt_id = %s", (receipt_id,)
            )
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Admission receipt not found.")
            return str(row["binding_hash"])

    def events(self, receipt_id: str) -> list[AdmissionAuditEvent]:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM admission_audit_events WHERE receipt_id = %s ORDER BY sequence",
                (receipt_id,),
            )
            rows = cursor.fetchall()
        return [
            AdmissionAuditEvent(
                receipt_id=str(row["receipt_id"]),
                sequence=int(row["sequence"]),
                event_type=str(row["event_type"]),
                event_hash=str(row["event_hash"]),
                previous_event_hash=(
                    str(row["previous_event_hash"]) if row["previous_event_hash"] else None
                ),
                reason=str(row["reason"]),
                details=cast(dict[str, Any], row["details_json"]),
                created_at=row["created_at"].isoformat(),
            )
            for row in rows
        ]

    def verify_event_chain(self, receipt_id: str) -> tuple[bool, str]:
        events = self.events(receipt_id)
        if not events:
            return False, "Admission receipt has no audit events."
        previous_hash: str | None = None
        for expected_sequence, event in enumerate(events, start=1):
            if event.sequence != expected_sequence:
                return False, f"Audit sequence gap at event {expected_sequence}."
            if event.previous_event_hash != previous_hash:
                return False, f"Audit predecessor mismatch at event {expected_sequence}."
            expected_hash = AdmissionReceiptStore._event_hash(
                event.receipt_id,
                event.sequence,
                event.event_type,
                event.previous_event_hash,
                event.reason,
                event.details,
                event.created_at,
            )
            if event.event_hash != expected_hash:
                return False, f"Audit hash mismatch at event {expected_sequence}."
            previous_hash = event.event_hash
        return True, "ok"
