from datetime import datetime, timezone
from pydantic import BaseModel, Field
import hashlib
from typing import Protocol, Optional

class TrustedTimestampEnvelope(BaseModel):
    timestamp: datetime
    source: str
    issued_at: datetime
    nonce: str
    signature: Optional[str] = None
    verified: bool = False
    
    def recompute_hash(self) -> str:
        data = f"{self.timestamp.isoformat()}|{self.source}|{self.issued_at.isoformat()}|{self.nonce}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

class TrustedTimeVerifier(Protocol):
    def verify(self, envelope: TrustedTimestampEnvelope) -> bool:
        ...

class LocalMockTimeVerifier:
    def verify(self, envelope: TrustedTimestampEnvelope) -> bool:
        # In a real environment, this verifies the cryptographic signature of the envelope.
        # For this local mock, we just verify the hash hasn't been tampered with.
        return envelope.recompute_hash() == envelope.signature
