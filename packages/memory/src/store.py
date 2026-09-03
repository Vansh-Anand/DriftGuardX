"""
DriftGuard-X v2 — Provenance Memory Store
PRIVATE — All Rights Reserved.

Central memory store mapping provenance partitions to memory entries.
Enforces partition quarantine securely before any read operation.
"""

import hashlib
import sqlite3
import threading
from datetime import UTC, datetime
from typing import Any

from packages.memory.src.auth import AccessContext, AuditEvent
from packages.memory.src.capabilities import CapabilityVerifier


class QuarantineViolationError(Exception):
    pass


class AuthorizationError(Exception):
    pass


class ProvenanceMemoryStore:
    """
    Thread-safe store for provenance-backed memory with Persistent Quarantine.
    Enforces access control using AccessContext capabilities.
    """

    def __init__(
        self, db_path: str = "quarantine_state.db", verifier: CapabilityVerifier | None = None
    ):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._partitions: dict[str, list[dict[str, Any]]] = {}
        self._verifier = verifier or CapabilityVerifier()
        self._init_db()

    def _has_capability(self, context: AccessContext, action: str, resource: str) -> bool:
        for cap in context.capabilities:
            if cap.action == action and (cap.resource == "*" or cap.resource == resource):
                if self._verifier.verify(cap, context, action, resource):
                    return True
        return False

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quarantine_state (
                    partition_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    status TEXT NOT NULL
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS access_audit (
                    event_id TEXT PRIMARY KEY,
                    requester TEXT NOT NULL,
                    tenant TEXT NOT NULL,
                    partition TEXT NOT NULL,
                    action TEXT NOT NULL,
                    capability_id TEXT,
                    timestamp TEXT NOT NULL,
                    policy_version TEXT NOT NULL,
                    result TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    previous_hash TEXT NOT NULL
                )
            """
            )

    def _hash_audit_event(self, event: AuditEvent, previous_hash: str) -> str:
        data = f"DGX-AUDIT-EVENT-V1|{previous_hash}|{event.event_id}|{event.requester}|{event.tenant}|{event.partition}|{event.action}|{event.capability_id}|{event.policy_version}|{event.result}|{event.timestamp.isoformat()}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    def _log_audit(self, event: AuditEvent) -> None:
        with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
            cursor = conn.execute("SELECT event_hash FROM access_audit ORDER BY rowid DESC LIMIT 1")
            row = cursor.fetchone()
            previous_hash = row[0] if row else "GENESIS-AUDIT"

            event.event_hash = self._hash_audit_event(event, previous_hash)

            conn.execute(
                """
                INSERT INTO access_audit (
                    event_id, requester, tenant, partition, action,
                    capability_id, timestamp, policy_version, result, event_hash, previous_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    event.event_id,
                    event.requester,
                    event.tenant,
                    event.partition,
                    event.action,
                    event.capability_id,
                    event.timestamp.isoformat(),
                    event.policy_version,
                    event.result,
                    event.event_hash,
                    previous_hash,
                ),
            )

    def _is_quarantined(self, partition_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status FROM quarantine_state WHERE partition_id = ?", (partition_id,)
            )
            row = cursor.fetchone()
            if row and row[0] == "ACTIVE":
                return True
        return False

    def write(self, partition_id: str, data: dict[str, Any], context: AccessContext) -> None:
        """Write data to a partition. Fails if quarantined."""
        with self._lock:
            if not context.is_valid():
                raise AuthorizationError("AccessContext is invalid or expired.")

            if not partition_id.startswith(f"{context.tenant_id}_"):
                raise AuthorizationError(
                    f"Cross-tenant write violation: tenant {context.tenant_id} cannot write to partition {partition_id}"
                )

            if self._is_quarantined(partition_id):
                self._log_audit(
                    AuditEvent(
                        requester=context.requester_id,
                        tenant=context.tenant_id,
                        partition=partition_id,
                        action="WRITE",
                        capability_id=None,
                        policy_version="v2",
                        result="DENIED_QUARANTINE",
                    )
                )
                raise QuarantineViolationError(
                    f"Partition {partition_id} is quarantined. Write denied."
                )

            if partition_id not in self._partitions:
                self._partitions[partition_id] = []
            self._partitions[partition_id].append(data)

            self._log_audit(
                AuditEvent(
                    requester=context.requester_id,
                    tenant=context.tenant_id,
                    partition=partition_id,
                    action="WRITE",
                    capability_id=None,
                    policy_version="v2",
                    result="ALLOWED",
                )
            )

    def read(self, partition_id: str, context: AccessContext) -> list[dict[str, Any]]:
        """Read data from a partition. Enforces quarantine and capability capabilities."""
        with self._lock:
            if not context.is_valid():
                raise AuthorizationError("AccessContext is invalid or expired.")

            if not partition_id.startswith(f"{context.tenant_id}_"):
                raise AuthorizationError(
                    f"Cross-tenant read violation: tenant {context.tenant_id} cannot read from partition {partition_id}"
                )

            is_quar = self._is_quarantined(partition_id)

            if is_quar:
                # Requires explicit forensic authorization
                if not self._has_capability(context, "FORENSIC_READ", partition_id):
                    self._log_audit(
                        AuditEvent(
                            requester=context.requester_id,
                            tenant=context.tenant_id,
                            partition=partition_id,
                            action="READ",
                            capability_id=None,
                            policy_version="v2",
                            result="DENIED_MISSING_CAPABILITY",
                        )
                    )
                    raise QuarantineViolationError(
                        "Read denied. Forensic access requires an explicit approval capability."
                    )

                # Forensic access granted
                self._log_audit(
                    AuditEvent(
                        requester=context.requester_id,
                        tenant=context.tenant_id,
                        partition=partition_id,
                        action="FORENSIC_READ",
                        capability_id=None,
                        policy_version="v2",
                        result="ALLOWED",
                    )
                )
            else:
                self._log_audit(
                    AuditEvent(
                        requester=context.requester_id,
                        tenant=context.tenant_id,
                        partition=partition_id,
                        action="READ",
                        capability_id=None,
                        policy_version="v2",
                        result="ALLOWED",
                    )
                )

            return list(self._partitions.get(partition_id, []))

    def quarantine_partition(self, partition_id: str, context: AccessContext, reason: str) -> None:
        """Quarantine a partition persistently."""
        with self._lock:
            if not context.is_valid() or not self._has_capability(
                context, "QUARANTINE", partition_id
            ):
                raise AuthorizationError("Quarantine requires an explicit QUARANTINE capability.")

            with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO quarantine_state (
                        partition_id, tenant_id, reason, created_at, created_by, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        partition_id,
                        context.tenant_id,
                        reason,
                        datetime.now(UTC).isoformat(),
                        context.requester_id,
                        "ACTIVE",
                    ),
                )

            self._log_audit(
                AuditEvent(
                    requester=context.requester_id,
                    tenant=context.tenant_id,
                    partition=partition_id,
                    action="QUARANTINE",
                    capability_id=None,
                    policy_version="v2",
                    result="SUCCESS",
                )
            )

    def unquarantine_partition(self, partition_id: str, context: AccessContext) -> None:
        """Restore access to a quarantined partition requires auth."""
        with self._lock:
            if not context.is_valid() or not self._has_capability(
                context, "UNQUARANTINE", partition_id
            ):
                raise AuthorizationError(
                    "Unquarantine requires an explicit UNQUARANTINE capability."
                )

            with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
                conn.execute(
                    "UPDATE quarantine_state SET status = 'RELEASED' WHERE partition_id = ?",
                    (partition_id,),
                )

            self._log_audit(
                AuditEvent(
                    requester=context.requester_id,
                    tenant=context.tenant_id,
                    partition=partition_id,
                    action="UNQUARANTINE",
                    capability_id=None,
                    policy_version="v2",
                    result="SUCCESS",
                )
            )

    def verify_audit_chain(self) -> bool:
        """Verify the integrity of the audit log chain."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM access_audit ORDER BY rowid ASC")
            expected_prev = "GENESIS-AUDIT"
            for row in cursor.fetchall():
                if row["previous_hash"] != expected_prev:
                    return False

                # Reconstruct event for hashing
                event = AuditEvent(
                    event_id=row["event_id"],
                    requester=row["requester"],
                    tenant=row["tenant"],
                    partition=row["partition"],
                    action=row["action"],
                    capability_id=row["capability_id"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    policy_version=row["policy_version"],
                    result=row["result"],
                    event_hash=row["event_hash"],
                )

                expected_hash = self._hash_audit_event(event, expected_prev)
                if expected_hash != row["event_hash"]:
                    return False

                expected_prev = row["event_hash"]

        return True

    def clear(self) -> None:
        """Clear the store (for testing)."""
        with self._lock:
            self._partitions.clear()
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM quarantine_state")
                conn.execute("DELETE FROM access_audit")


# Global instance for the Mock RAG pipeline to use
global_provenance_store = ProvenanceMemoryStore()
