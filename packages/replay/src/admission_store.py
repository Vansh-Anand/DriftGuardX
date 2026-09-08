"""Durable, transactional storage for state-bound admission receipts.

SQLite is used as the portable reference implementation.  ``BEGIN IMMEDIATE``
serializes receipt transitions across API and worker processes, while the
receipt event table forms a hash chain that is append-only from the service API.
Production deployments can place the database on durable shared storage or
replace this class with the same transition contract backed by PostgreSQL.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.contracts.src.evidence import EvidenceClassification
from packages.replay.src.admission_receipt import ReceiptStatus, ReplayAdmissionReceipt


@dataclass(frozen=True)
class AdmissionAuditEvent:
    receipt_id: str
    sequence: int
    event_type: str
    event_hash: str
    previous_event_hash: str | None
    reason: str
    details: dict[str, Any]
    created_at: str


class AdmissionReceiptStore:
    """A durable receipt store with fail-closed, single-use transitions."""

    def __init__(self, path: str | os.PathLike[str] | None = None) -> None:
        configured = path or os.environ.get(
            "DGX_ADMISSION_STORE_PATH", ".local-runtime/admission_receipts.sqlite3"
        )
        self.path = Path(configured)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=15.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS admission_receipts (
                    receipt_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    binding_hash TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    reserved_cost_usd REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    terminal_at TEXT
                );
                CREATE TABLE IF NOT EXISTS admission_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    receipt_id TEXT NOT NULL REFERENCES admission_receipts(receipt_id),
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    previous_event_hash TEXT,
                    reason TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(receipt_id, sequence)
                );
                CREATE INDEX IF NOT EXISTS ix_admission_audit_receipt
                    ON admission_audit_events(receipt_id, sequence);
                """)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _event_hash(
        receipt_id: str,
        sequence: int,
        event_type: str,
        previous_event_hash: str | None,
        reason: str,
        details: dict[str, Any],
        created_at: str,
    ) -> str:
        import hashlib

        payload = json.dumps(
            {
                "receipt_id": receipt_id,
                "sequence": sequence,
                "event_type": event_type,
                "previous_event_hash": previous_event_hash,
                "reason": reason,
                "details": details,
                "created_at": created_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(b"DGX-ADMISSION-AUDIT-V1\0" + payload).hexdigest()

    def _append_event(
        self,
        connection: sqlite3.Connection,
        receipt_id: str,
        event_type: str,
        reason: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        previous = connection.execute(
            "SELECT sequence, event_hash FROM admission_audit_events "
            "WHERE receipt_id = ? ORDER BY sequence DESC LIMIT 1",
            (receipt_id,),
        ).fetchone()
        sequence = int(previous["sequence"]) + 1 if previous else 1
        previous_hash = str(previous["event_hash"]) if previous else None
        created_at = self._now()
        event_details = details or {}
        event_hash = self._event_hash(
            receipt_id,
            sequence,
            event_type,
            previous_hash,
            reason,
            event_details,
            created_at,
        )
        connection.execute(
            "INSERT INTO admission_audit_events "
            "(receipt_id, sequence, event_type, event_hash, previous_event_hash, "
            "reason, details_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                receipt_id,
                sequence,
                event_type,
                event_hash,
                previous_hash,
                reason,
                json.dumps(event_details, sort_keys=True, separators=(",", ":")),
                created_at,
            ),
        )

    def issue(self, receipt: ReplayAdmissionReceipt) -> str:
        """Persist an issued receipt and its first audit event atomically."""
        payload = receipt.canonical_payload
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT binding_hash FROM admission_receipts WHERE receipt_id = ?",
                (receipt.receipt_id,),
            ).fetchone()
            if existing:
                if str(existing["binding_hash"]) != receipt.binding_hash:
                    raise ValueError("Receipt ID is already bound to different state.")
                return receipt.receipt_id
            connection.execute(
                "INSERT INTO admission_receipts "
                "(receipt_id, tenant_id, binding_hash, status, payload_json, "
                "reserved_cost_usd, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt.receipt_id,
                    receipt.tenant_id,
                    receipt.binding_hash,
                    ReceiptStatus.ISSUED.value,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    receipt.predicted_cost + receipt.uncertainty_margin + receipt.rollback_reserve,
                    self._now(),
                ),
            )
            self._append_event(connection, receipt.receipt_id, "ISSUE", details=payload)
        return receipt.receipt_id

    def _load_row(self, connection: sqlite3.Connection, receipt_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM admission_receipts WHERE receipt_id = ?", (receipt_id,)
        ).fetchone()

    @staticmethod
    def _payload(row: sqlite3.Row) -> dict[str, Any]:
        return json.loads(str(row["payload_json"]))

    @staticmethod
    def _receipt_from_row(row: sqlite3.Row) -> ReplayAdmissionReceipt:
        payload = AdmissionReceiptStore._payload(row)
        payload["issued_at"] = datetime.fromisoformat(payload["issued_at"])
        payload["expires_at"] = datetime.fromisoformat(payload["expires_at"])
        return ReplayAdmissionReceipt(
            **payload,
            receipt_id=str(row["receipt_id"]),
            status=ReceiptStatus(str(row["status"])),
        )

    def verify(
        self,
        receipt_id: str,
        *,
        actual: dict[str, Any],
        evidence_class: EvidenceClassification | None = None,
        now: datetime | None = None,
    ) -> tuple[bool, str]:
        """Atomically verify and claim a receipt before worker execution."""
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._load_row(connection, receipt_id)
            if row is None:
                return False, "Admission receipt not found."
            payload = self._payload(row)
            status = ReceiptStatus(str(row["status"]))

            reason = ""
            if status != ReceiptStatus.ISSUED:
                reason = f"Receipt is {status.value.lower()}."
            elif (now or datetime.now(UTC)) >= datetime.fromisoformat(payload["expires_at"]):
                reason = "Receipt has expired."
            else:
                for key, expected in payload.items():
                    if (
                        key in actual
                        and actual[key] != expected
                        and str(actual[key]) != str(expected)
                    ):
                        reason = f"Receipt binding mismatch: {key}."
                        break
                if not reason and evidence_class is not None:
                    if not self._receipt_from_row(row).verify_evidence(evidence_class)[0]:
                        reason = "Evidence classification exceeds the receipt ceiling."

            if reason:
                self._append_event(
                    connection,
                    receipt_id,
                    "MISMATCH_REFUSAL",
                    reason=reason,
                    details={"actual": actual},
                )
                # An unclaimed receipt is voided on drift.  A VERIFIED receipt
                # belongs to an executing worker; retain that claim so a late
                # duplicate cannot cancel the legitimate execution.
                if status == ReceiptStatus.ISSUED:
                    connection.execute(
                        "UPDATE admission_receipts SET status = ?, terminal_at = ? "
                        "WHERE receipt_id = ?",
                        (ReceiptStatus.VOIDED.value, self._now(), receipt_id),
                    )
                    self._append_event(connection, receipt_id, "VOID", reason=reason)
                return False, reason

            connection.execute(
                "UPDATE admission_receipts SET status = ? WHERE receipt_id = ?",
                (ReceiptStatus.VERIFIED.value, receipt_id),
            )
            self._append_event(connection, receipt_id, "VERIFY", details=actual)
            return True, "ok"

    def _terminal_transition(
        self, receipt_id: str, target: ReceiptStatus, event_type: str, reason: str = ""
    ) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._load_row(connection, receipt_id)
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
            connection.execute(
                "UPDATE admission_receipts SET status = ?, terminal_at = ? WHERE receipt_id = ?",
                (target.value, self._now(), receipt_id),
            )
            self._append_event(connection, receipt_id, event_type, reason=reason)

    def consume(self, receipt_id: str) -> None:
        self._terminal_transition(receipt_id, ReceiptStatus.CONSUMED, "CONSUME")

    def release(self, receipt_id: str) -> None:
        self._terminal_transition(receipt_id, ReceiptStatus.RELEASED, "RELEASE")

    def void(self, receipt_id: str, reason: str = "") -> None:
        self._terminal_transition(receipt_id, ReceiptStatus.VOIDED, "VOID", reason=reason)

    def status(self, receipt_id: str) -> ReceiptStatus | None:
        with self._lock, self._connect() as connection:
            row = self._load_row(connection, receipt_id)
            return ReceiptStatus(str(row["status"])) if row else None

    def events(self, receipt_id: str) -> list[AdmissionAuditEvent]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM admission_audit_events WHERE receipt_id = ? ORDER BY sequence",
                (receipt_id,),
            ).fetchall()
        return [
            AdmissionAuditEvent(
                receipt_id=str(row["receipt_id"]),
                sequence=int(row["sequence"]),
                event_type=str(row["event_type"]),
                event_hash=str(row["event_hash"]),
                previous_event_hash=row["previous_event_hash"],
                reason=str(row["reason"]),
                details=json.loads(str(row["details_json"])),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]
