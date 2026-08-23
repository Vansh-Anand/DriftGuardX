import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime

from pydantic import BaseModel


class AuthorizationCapability(BaseModel):
    capability_id: str
    tenant_id: str
    action: str  # e.g., "FORENSIC_READ", "QUARANTINE", "UNQUARANTINE"
    resource: str  # e.g., "partition_id" or "*"
    expires_at: datetime
    signature: str = ""

class CapabilityVerifier:
    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key

    def _canonical_bytes(self, cap: AuthorizationCapability) -> bytes:
        data = {
            "capability_id": cap.capability_id,
            "tenant_id": cap.tenant_id,
            "action": cap.action,
            "resource": cap.resource,
            "expires_at": cap.expires_at.isoformat()
        }
        return json.dumps(data, separators=(',', ':'), sort_keys=True).encode("utf-8")

    def sign(self, cap: AuthorizationCapability) -> AuthorizationCapability:
        mac = hmac.new(self.secret_key, self._canonical_bytes(cap), hashlib.sha256)
        cap.signature = base64.b64encode(mac.digest()).decode('utf-8')
        return cap

    def verify(self, cap: AuthorizationCapability) -> bool:
        if not cap.signature:
            return False
        if datetime.now(UTC) > cap.expires_at:
            return False

        expected_mac = hmac.new(self.secret_key, self._canonical_bytes(cap), hashlib.sha256).digest()
        expected_signature = base64.b64encode(expected_mac).decode('utf-8')
        return hmac.compare_digest(cap.signature, expected_signature)
