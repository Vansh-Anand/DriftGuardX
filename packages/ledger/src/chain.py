"""
DriftGuard-X v2 — Append-Only Ledger Chain
PRIVATE — All Rights Reserved.

Implements the append-only SQLite storage, hash chaining, and verification.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

import aiosqlite

from packages.ledger.src.crypto import verify_signature
from packages.ledger.src.schema import RecoveryCertificate

logger = logging.getLogger(__name__)


class CertificateValidationError(ValueError):
    pass


class LedgerChain:
    """Append-only certificate ledger using SQLite."""

    def __init__(self, db_path: str = "ledger.sqlite"):
        self.db_path = db_path
        self._head_hash: str | None = None
        self._size: int = 0

    async def initialize(self) -> None:
        """Initialize the database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            # We strictly prevent updates and deletes at the application level by design.
            # In a production DB, this table would have triggers or role permissions enforcing append-only.
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cert_id TEXT UNIQUE NOT NULL,
                    cert_hash TEXT UNIQUE NOT NULL,
                    previous_hash TEXT NOT NULL,
                    payload JSON NOT NULL,
                    signature TEXT NOT NULL,
                    signer_pub_key TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """
            )
            await db.commit()
            await self._load_head(db)

    async def _load_head(self, db: aiosqlite.Connection) -> None:
        """Load the latest hash and chain size."""
        async with db.execute("SELECT cert_hash FROM ledger ORDER BY id DESC LIMIT 1") as cursor:
            row = await cursor.fetchone()
            if row:
                self._head_hash = row[0]
            else:
                self._head_hash = "GENESIS"

        async with db.execute("SELECT COUNT(*) FROM ledger") as cursor:
            row = await cursor.fetchone()
            self._size = row[0] if row else 0

    async def append_certificate(self, cert: RecoveryCertificate) -> str:
        """
        Validates and appends a certificate to the ledger.
        Returns the computed hash of the appended certificate.
        """
        if not cert.signature or not cert.signer_pub_key:
            raise CertificateValidationError("Certificate must be signed before appending.")

        if cert.previous_cert_hash != self._head_hash:
            raise CertificateValidationError(
                f"Chain fork detected: Certificate previous_hash ({cert.previous_cert_hash}) "
                f"does not match ledger head ({self._head_hash})."
            )

        cert_hash = cert.compute_hash()

        # Validate signature
        if not verify_signature(cert.signer_pub_key, cert.canonical_bytes(), cert.signature):
            raise CertificateValidationError("Cryptographic signature verification failed.")

        payload_json = json.dumps(asdict(cert))

        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO ledger
                    (cert_id, cert_hash, previous_hash, payload, signature, signer_pub_key, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cert.cert_id,
                        cert_hash,
                        cert.previous_cert_hash,
                        payload_json,
                        cert.signature,
                        cert.signer_pub_key,
                        cert.timestamp,
                    ),
                )
                await db.commit()
                self._head_hash = cert_hash
                self._size += 1
                return cert_hash
            except aiosqlite.IntegrityError as e:
                raise CertificateValidationError(
                    f"Integrity constraint violation (duplicate ID or Hash?): {e}"
                )

    async def get_all_certificates(self) -> list[RecoveryCertificate]:
        """Fetch all certificates in order."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT payload FROM ledger ORDER BY id ASC") as cursor:
                rows = await cursor.fetchall()
                return [RecoveryCertificate.from_dict(json.loads(row[0])) for row in rows]

    async def verify_chain(self) -> bool:
        """
        Verifies the entire chain from genesis to head.
        Checks hash linkage, content digests, and signatures.
        """
        certs = await self.get_all_certificates()
        if not certs:
            return True

        expected_prev = "GENESIS"
        for cert in certs:
            # 1. Check Linkage
            if cert.previous_cert_hash != expected_prev:
                logger.error(
                    f"Linkage broken at cert {cert.cert_id}: expected {expected_prev}, got {cert.previous_cert_hash}"
                )
                return False

            # 2. Check Signatures
            if not cert.signature or not cert.signer_pub_key:
                logger.error(f"Missing signature on cert {cert.cert_id}")
                return False

            if not verify_signature(cert.signer_pub_key, cert.canonical_bytes(), cert.signature):
                logger.error(f"Signature verification failed on cert {cert.cert_id}")
                return False

            expected_prev = cert.compute_hash()

        return True

    @property
    def head_hash(self) -> str:
        return self._head_hash or "GENESIS"

    @property
    def size(self) -> int:
        return self._size
