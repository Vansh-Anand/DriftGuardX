import hashlib
from datetime import UTC, datetime
from typing import Protocol

from pydantic import BaseModel


class TrustedTimestampEnvelope(BaseModel):
    timestamp: datetime
    source: str
    issued_at: datetime
    nonce: str
    signature: str | None = None
    verified: bool = False

    def recompute_hash(self) -> str:
        data = f"{self.timestamp.isoformat()}|{self.source}|{self.issued_at.isoformat()}|{self.nonce}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

class TrustedTimeVerifier(Protocol):
    def verify(self, envelope: TrustedTimestampEnvelope) -> bool:
        ...

import base64
import hmac
import sqlite3


class HMACTimeVerifier:
    def __init__(self, secret_key: bytes, db_path: str = "time_nonce_state.db"):
        self.secret_key = secret_key
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS seen_nonces (
                    nonce TEXT PRIMARY KEY,
                    seen_at TEXT NOT NULL
                )
            ''')

    def _canonical_bytes(self, envelope: TrustedTimestampEnvelope) -> bytes:
        data = f"{envelope.timestamp.isoformat()}|{envelope.source}|{envelope.issued_at.isoformat()}|{envelope.nonce}"
        return data.encode("utf-8")

    def verify(self, envelope: TrustedTimestampEnvelope) -> bool:
        if not envelope.signature:
            return False

        expected_mac = hmac.new(self.secret_key, self._canonical_bytes(envelope), hashlib.sha256).digest()
        expected_signature = base64.b64encode(expected_mac).decode('utf-8')
        if not hmac.compare_digest(envelope.signature, expected_signature):
            return False

        with sqlite3.connect(self.db_path, isolation_level="EXCLUSIVE") as conn:
            try:
                conn.execute('''
                    INSERT INTO seen_nonces (nonce, seen_at) VALUES (?, ?)
                ''', (envelope.nonce, datetime.now(UTC).isoformat()))
            except sqlite3.IntegrityError:
                return False # Replay attack detected

        envelope.verified = True
        return True
