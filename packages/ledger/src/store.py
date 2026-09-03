import hashlib
import json
import sqlite3
import struct
from datetime import UTC, datetime
from typing import Any, Protocol


class LedgerIntegrityError(Exception):
    pass


from dataclasses import dataclass


@dataclass
class LedgerAppendResult:
    sequence_number: int
    entry_hash: str
    previous_entry_hash: str
    payload_hash: str
    timestamp: str


class TransparencyStore(Protocol):
    def append(self, entry: dict[str, Any]) -> LedgerAppendResult: ...

    def get(self, entry_hash: str) -> dict[str, Any] | None: ...

    def iterate(self) -> list[dict[str, Any]]: ...

    def latest_checkpoint(self) -> dict[str, Any] | None: ...

    def verify_chain(self, entry_hash: str) -> bool: ...

    def verify_full_chain(self) -> bool: ...


def get_canonical_json(data: dict[str, Any]) -> bytes:
    # Remove mutable keys from payload hash to avoid double hashing logic issues
    # but in our design, payload is just the raw event data (e.g. trace, policy).
    return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode(
        "utf-8"
    )


def compute_payload_hash(payload: dict[str, Any]) -> str:
    canonical = get_canonical_json(payload)
    return hashlib.sha256(b"DGX-LEDGER-PAYLOAD-V1" + canonical).hexdigest()


def compute_entry_hash(sequence_number: int, previous_entry_hash: str, payload_hash: str) -> str:
    seq_bytes = struct.pack(">Q", sequence_number)
    prev_bytes = previous_entry_hash.encode("utf-8")
    pay_bytes = payload_hash.encode("utf-8")

    msg = (
        b"DGX-LEDGER-ENTRY-V1"
        + struct.pack(">I", len(seq_bytes))
        + seq_bytes
        + struct.pack(">I", len(prev_bytes))
        + prev_bytes
        + struct.pack(">I", len(pay_bytes))
        + pay_bytes
    )
    return hashlib.sha256(msg).hexdigest()


class SQLiteTransparencyStore:
    def __init__(self, db_path: str = "witness_ledger.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger (
                    sequence_number INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    previous_entry_hash TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    entry_hash TEXT UNIQUE NOT NULL,
                    hash_version TEXT NOT NULL,
                    payload JSON NOT NULL
                )
            """
            )
            # Ensure index on entry_hash
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_entry_hash ON ledger(entry_hash)
            """
            )
            # Genesis constraint could be added here, but managed via application logic.

    def append(self, payload: dict[str, Any]) -> LedgerAppendResult:
        """
        Appends a payload to the ledger atomically.
        The entry dict passed in should be the payload.
        Metadata (seq, hashes) are wrapped automatically.
        """
        with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT sequence_number, entry_hash FROM ledger ORDER BY sequence_number DESC LIMIT 1"
            )
            last_row = cursor.fetchone()

            if last_row:
                seq = last_row["sequence_number"] + 1
                prev_hash = last_row["entry_hash"]
            else:
                seq = 0
                prev_hash = "GENESIS-DGX-LEDGER-V1"

            payload_hash = compute_payload_hash(payload)
            entry_hash = compute_entry_hash(seq, prev_hash, payload_hash)
            timestamp = datetime.now(UTC).isoformat()

            try:
                conn.execute(
                    """
                    INSERT INTO ledger (
                        sequence_number, timestamp, previous_entry_hash,
                        payload_hash, entry_hash, hash_version, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        seq,
                        timestamp,
                        prev_hash,
                        payload_hash,
                        entry_hash,
                        "V1",
                        json.dumps(payload, separators=(",", ":"), sort_keys=True),
                    ),
                )
                return LedgerAppendResult(
                    sequence_number=seq,
                    entry_hash=entry_hash,
                    previous_entry_hash=prev_hash,
                    payload_hash=payload_hash,
                    timestamp=timestamp,
                )
            except sqlite3.IntegrityError as e:
                raise LedgerIntegrityError(f"Concurrency/Integrity failure during append: {e}")

    def get(self, entry_hash: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM ledger WHERE entry_hash = ?", (entry_hash,))
            row = cursor.fetchone()
            if row:
                return {
                    "sequence_number": row["sequence_number"],
                    "timestamp": row["timestamp"],
                    "previous_entry_hash": row["previous_entry_hash"],
                    "payload_hash": row["payload_hash"],
                    "entry_hash": row["entry_hash"],
                    "hash_version": row["hash_version"],
                    "payload": json.loads(row["payload"]),
                }
        return None

    def iterate(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM ledger ORDER BY sequence_number ASC")
            results = []
            for row in cursor.fetchall():
                results.append(
                    {
                        "sequence_number": row["sequence_number"],
                        "timestamp": row["timestamp"],
                        "previous_entry_hash": row["previous_entry_hash"],
                        "payload_hash": row["payload_hash"],
                        "entry_hash": row["entry_hash"],
                        "hash_version": row["hash_version"],
                        "payload": json.loads(row["payload"]),
                    }
                )
            return results

    def latest_checkpoint(self) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM ledger ORDER BY sequence_number DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return {
                    "sequence_number": row["sequence_number"],
                    "timestamp": row["timestamp"],
                    "previous_entry_hash": row["previous_entry_hash"],
                    "payload_hash": row["payload_hash"],
                    "entry_hash": row["entry_hash"],
                    "hash_version": row["hash_version"],
                    "payload": json.loads(row["payload"]),
                }
        return None

    def verify_chain(self, target_entry_hash: str) -> bool:
        """
        Verifies the chain backwards from the target_entry_hash to the Genesis block.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            current_hash = target_entry_hash

            while True:
                cursor = conn.execute("SELECT * FROM ledger WHERE entry_hash = ?", (current_hash,))
                row = cursor.fetchone()

                if not row:
                    raise LedgerIntegrityError(f"Missing link in chain at hash: {current_hash}")

                # Verify payload integrity
                payload = json.loads(row["payload"])
                recomputed_payload_hash = compute_payload_hash(payload)
                if recomputed_payload_hash != row["payload_hash"]:
                    raise LedgerIntegrityError(
                        f"Payload hash mismatch at seq {row['sequence_number']}. Tampering detected."
                    )

                # Verify entry integrity
                recomputed_entry_hash = compute_entry_hash(
                    row["sequence_number"], row["previous_entry_hash"], row["payload_hash"]
                )
                if recomputed_entry_hash != row["entry_hash"]:
                    raise LedgerIntegrityError(
                        f"Entry hash mismatch at seq {row['sequence_number']}. Tampering detected."
                    )

                if row["sequence_number"] == 0:
                    if row["previous_entry_hash"] != "GENESIS-DGX-LEDGER-V1":
                        raise LedgerIntegrityError("Genesis block tampering detected.")
                    break

                current_hash = row["previous_entry_hash"]

        return True

    def verify_full_chain(self) -> bool:
        """
        Verifies every entry in the database.
        Detects deleted, inserted, or reordered rows.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM ledger ORDER BY sequence_number ASC")

            expected_seq = 0
            expected_prev_hash = "GENESIS-DGX-LEDGER-V1"

            rows = cursor.fetchall()
            if not rows:
                return True  # Empty chain is valid

            for row in rows:
                if row["sequence_number"] != expected_seq:
                    raise LedgerIntegrityError(
                        f"Sequence number gap/reorder at expected {expected_seq}, found {row['sequence_number']}."
                    )

                if row["previous_entry_hash"] != expected_prev_hash:
                    raise LedgerIntegrityError(
                        f"Previous hash mismatch at seq {row['sequence_number']}."
                    )

                # Verify payload integrity
                payload = json.loads(row["payload"])
                recomputed_payload_hash = compute_payload_hash(payload)
                if recomputed_payload_hash != row["payload_hash"]:
                    raise LedgerIntegrityError(
                        f"Payload hash mismatch at seq {row['sequence_number']}. Row mutated."
                    )

                # Verify entry integrity
                recomputed_entry_hash = compute_entry_hash(
                    row["sequence_number"], row["previous_entry_hash"], row["payload_hash"]
                )
                if recomputed_entry_hash != row["entry_hash"]:
                    raise LedgerIntegrityError(
                        f"Entry hash mismatch at seq {row['sequence_number']}. Row mutated."
                    )

                expected_seq += 1
                expected_prev_hash = row["entry_hash"]

        return True
