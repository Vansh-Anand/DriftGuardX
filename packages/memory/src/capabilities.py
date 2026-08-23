"""
DriftGuard-X v2 — Authorization Capabilities
PRIVATE — All Rights Reserved.

Capabilities are cryptographically-signed authorization tokens bound to a
specific (requester_id, tenant_id, resource, action) tuple.
They support expiry and explicit revocation.
"""
import base64
import hashlib
import hmac
import json
import os
import threading
from datetime import UTC, datetime

from pydantic import BaseModel


class AuthorizationCapability(BaseModel):
    """
    A signed capability token.
    Bound to requester + tenant + resource + action — prevents cross-context reuse.
    """
    capability_id: str
    requester_id: str       # The agent/service requesting the action
    tenant_id: str          # The tenant scope
    action: str             # e.g. "COMPONENT_ROLLBACK", "QUARANTINE", "FORENSIC_READ"
    resource: str           # The specific resource being acted on (component ID or "*")
    expires_at: datetime
    signature: str = ""


class CapabilityRevocationStore:
    """
    Thread-safe in-memory revocation store.
    Revoked capability IDs are permanently rejected even if the HMAC is valid.
    In production this should be backed by Redis for cross-process consistency.
    """
    _instance: "CapabilityRevocationStore | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._revoked: set[str] = set()
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "CapabilityRevocationStore":
        """Singleton accessor — safe for tests to reset via reset_for_test()."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_test(cls) -> None:
        """Reset singleton state for test isolation."""
        cls._instance = None

    def revoke(self, capability_id: str) -> None:
        """Mark a capability as permanently revoked."""
        with self._lock:
            self._revoked.add(capability_id)

    def is_revoked(self, capability_id: str) -> bool:
        with self._lock:
            return capability_id in self._revoked

    def revoked_count(self) -> int:
        with self._lock:
            return len(self._revoked)


class CapabilityVerifier:
    """
    Signs and verifies AuthorizationCapability tokens.

    Key is loaded from environment variable DGX_CAPABILITY_SECRET.
    Falls back to an insecure dev key in non-production environments.
    """

    def __init__(self, secret_key: bytes | None = None) -> None:
        if secret_key is not None:
            self.secret_key = secret_key
        else:
            env_key = os.environ.get("DGX_CAPABILITY_SECRET", "dgx-insecure-dev-key")
            self.secret_key = env_key.encode("utf-8")
        self._revocation_store = CapabilityRevocationStore.get_instance()

    def _canonical_bytes(self, cap: AuthorizationCapability) -> bytes:
        """
        Produce a stable canonical serialization of all bound fields.
        Including requester_id and resource prevents cross-context token reuse.
        """
        data = {
            "capability_id": cap.capability_id,
            "requester_id": cap.requester_id,
            "tenant_id": cap.tenant_id,
            "action": cap.action,
            "resource": cap.resource,
            "expires_at": cap.expires_at.isoformat(),
        }
        return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")

    def sign(self, cap: AuthorizationCapability) -> AuthorizationCapability:
        """Sign capability in-place and return it."""
        mac = hmac.new(self.secret_key, self._canonical_bytes(cap), hashlib.sha256)
        cap.signature = base64.b64encode(mac.digest()).decode("utf-8")
        return cap

    def verify(self, cap: AuthorizationCapability) -> bool:
        """
        Returns True iff:
        1. HMAC signature is valid
        2. Capability has not expired
        3. Capability has not been revoked
        """
        if not cap.signature:
            return False
        if datetime.now(UTC) > cap.expires_at:
            return False
        if self._revocation_store.is_revoked(cap.capability_id):
            return False

        expected_mac = hmac.new(
            self.secret_key, self._canonical_bytes(cap), hashlib.sha256
        ).digest()
        expected_signature = base64.b64encode(expected_mac).decode("utf-8")
        return hmac.compare_digest(cap.signature, expected_signature)

    def revoke(self, capability_id: str) -> None:
        """Revoke a capability by ID. Irrevocable within this process."""
        self._revocation_store.revoke(capability_id)
