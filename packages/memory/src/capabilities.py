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

from packages.contracts.src.recovery_models import SignedCapability
from packages.memory.src.auth import AccessContext


class CapabilityRevocationStore:
    """
    Thread-safe in-memory revocation store with file persistence.
    Revoked capability IDs are permanently rejected even if the HMAC is valid.
    """
    _instance: "CapabilityRevocationStore | None" = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, persist_path: str | None = None) -> None:
        self._revoked: set[str] = set()
        self._lock = threading.Lock()
        self._persist_path = persist_path or os.environ.get("DGX_REVOCATION_LOG_PATH", "revoked_caps.log")
        self._load_persisted()

    def _load_persisted(self) -> None:
        if os.path.exists(self._persist_path):
            with open(self._persist_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        self._revoked.add(line.strip())

    @classmethod
    def get_instance(cls) -> "CapabilityRevocationStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_for_test(cls) -> None:
        if cls._instance and os.path.exists(cls._instance._persist_path):
            os.remove(cls._instance._persist_path)
        cls._instance = None

    def revoke(self, capability_id: str) -> None:
        with self._lock:
            if capability_id not in self._revoked:
                self._revoked.add(capability_id)
                with open(self._persist_path, "a", encoding="utf-8") as f:
                    f.write(f"{capability_id}\n")

    def is_revoked(self, capability_id: str) -> bool:
        with self._lock:
            return capability_id in self._revoked

    def revoked_count(self) -> int:
        with self._lock:
            return len(self._revoked)


class CapabilityVerifier:
    """
    Signs and verifies SignedCapability tokens.
    Key is loaded from environment variable DGX_CAPABILITY_SECRET.
    """

    def __init__(self, secret_key: bytes | None = None) -> None:
        if secret_key is not None:
            self.secret_key = secret_key
        else:
            env_key = os.environ.get("DGX_CAPABILITY_SECRET")
            if not env_key:
                raise RuntimeError("DGX_CAPABILITY_SECRET is missing. Cannot verify capabilities.")
            self.secret_key = env_key.encode("utf-8")
        self._revocation_store = CapabilityRevocationStore.get_instance()

    def _canonical_bytes(self, cap: SignedCapability) -> bytes:
        data = {
            "capability_id": cap.capability_id,
            "requester_id": cap.requester_id,
            "tenant_id": cap.tenant_id,
            "action": cap.action,
            "resource": cap.resource,
            "issued_at": cap.issued_at.isoformat(),
            "expires_at": cap.expires_at.isoformat(),
            "issuer": cap.issuer,
            "nonce": cap.nonce,
            "policy_version": cap.policy_version,
        }
        return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")

    def sign(self, cap: SignedCapability) -> SignedCapability:
        mac = hmac.new(self.secret_key, self._canonical_bytes(cap), hashlib.sha256)
        cap.signature = base64.b64encode(mac.digest()).decode("utf-8")
        return cap

    def verify(self, cap: SignedCapability, context: AccessContext, required_action: str, required_resource: str) -> bool:
        """
        Returns True iff:
        1. Context matches token bound requester/tenant
        2. Action matches token bound action (and token action matches required)
        3. Resource matches token bound resource (or token allows wildcard)
        4. HMAC signature is valid
        5. Capability has not expired
        6. Capability has not been revoked
        """
        if cap.requester_id != context.requester_id or cap.tenant_id != context.tenant_id:
            print(f"DEBUG: req/tenant mismatch. cap: {cap.requester_id}/{cap.tenant_id} ctx: {context.requester_id}/{context.tenant_id}")
            return False
        if cap.action != required_action:
            print(f"DEBUG: action mismatch. cap: {cap.action} req: {required_action}")
            return False
        if cap.resource != "*" and cap.resource != required_resource:
            print(f"DEBUG: resource mismatch. cap: {cap.resource} req: {required_resource}")
            return False
        if not cap.signature:
            print("DEBUG: missing sig")
            return False
        if datetime.now(UTC) > cap.expires_at:
            print("DEBUG: expired")
            return False
        if self._revocation_store.is_revoked(cap.capability_id):
            print("DEBUG: revoked")
            return False

        expected_mac = hmac.new(
            self.secret_key, self._canonical_bytes(cap), hashlib.sha256
        ).digest()
        actual_mac = base64.b64decode(cap.signature)
        if not hmac.compare_digest(expected_mac, actual_mac):
            print("DEBUG: sig mismatch")
            return False
        return True

    def revoke(self, capability_id: str) -> None:
        self._revocation_store.revoke(capability_id)
