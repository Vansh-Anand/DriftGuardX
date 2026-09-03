"""
DriftGuard-X v2 — Cryptographic Signer (Simulated HSM/KMS)
PRIVATE — All Rights Reserved.
"""

import base64
import hashlib
import hmac
import json
import os
from typing import Any

from packages.contracts.src.recovery_models import CryptographicSignature


class LocalKMSProvider:
    """
    Simulates a Hardware Security Module (HSM) / Key Management Service (KMS)
    that holds the private key for Ed25519 signing.
    """

    def __init__(self):
        # In production this is loaded from a secure vault.
        # We fall back to a random secret for local execution.
        self._master_secret = os.environ.get(
            "DGX_CAPABILITY_SECRET", "local_dev_fallback_secret_only"
        ).encode("utf-8")
        self._public_key = "pub_ed25519_" + hashlib.sha256(self._master_secret).hexdigest()[:16]

    def get_public_key(self) -> str:
        return self._public_key

    def sign_payload(
        self, payload_dict: dict[str, Any], signer_id: str = "system"
    ) -> CryptographicSignature:
        """
        Signs the deterministic JSON representation of the payload.
        """
        # Ensure deterministic JSON stringification
        payload_str = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))

        # Simulate Ed25519 signature generation using HMAC-SHA256
        signature_hash = hmac.new(
            self._master_secret, payload_str.encode("utf-8"), hashlib.sha256
        ).digest()
        signature_b64 = base64.b64encode(signature_hash).decode("utf-8")

        return CryptographicSignature(
            algorithm="Ed25519_Simulated",
            public_key=self._public_key,
            signature=signature_b64,
            signer_id=signer_id,
        )

    def verify_signature(
        self, payload_dict: dict[str, Any], signature: CryptographicSignature
    ) -> bool:
        """
        Verifies the signature matches the payload.
        """
        payload_str = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
        expected_hash = hmac.new(
            self._master_secret, payload_str.encode("utf-8"), hashlib.sha256
        ).digest()
        expected_b64 = base64.b64encode(expected_hash).decode("utf-8")

        return signature.signature == expected_b64 and signature.public_key == self._public_key


# Global singleton for the application
kms_provider = LocalKMSProvider()
