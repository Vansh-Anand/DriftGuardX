"""
DriftGuard-X v2 — Cryptographic Signer (Simulated HSM/KMS)
PRIVATE — All Rights Reserved.
"""

import json
from typing import Any

from packages.contracts.src.recovery_models import CryptographicSignature
from packages.ledger.src.crypto import (
    DevelopmentSigner,
    SignerProtocol,
    verify_signature,
)


class LocalKMSProvider:
    """
    Simulates a Hardware Security Module (HSM) / Key Management Service (KMS).
    Delegates to DevelopmentSigner (real Ed25519) instead of faking HMAC.
    """

    def __init__(self):
        # We delegate to true Ed25519 instead of HMAC simulation for roadmap compliance
        self._signer: SignerProtocol = DevelopmentSigner(key_id="local-dev-ed25519-v1")

    def get_public_key(self) -> str:
        return self._signer.public_key_b64()

    def sign_payload(
        self, payload_dict: dict[str, Any], signer_id: str | None = None
    ) -> CryptographicSignature:
        """
        Signs the deterministic JSON representation of the payload.
        """
        payload_str = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
        signature_b64 = self._signer.sign(payload_str.encode("utf-8"))

        return CryptographicSignature(
            algorithm="Ed25519",
            public_key=self._signer.public_key_b64(),
            signature=signature_b64,
            signer_id=signer_id or self._signer.key_id(),
        )

    def verify_signature(
        self, payload_dict: dict[str, Any], signature: CryptographicSignature
    ) -> bool:
        """
        Verifies the signature matches the payload.
        """
        payload_str = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
        return verify_signature(
            public_key_b64=signature.public_key,
            payload=payload_str.encode("utf-8"),
            signature_b64=signature.signature,
        )


# Global singleton for the application
kms_provider = LocalKMSProvider()
