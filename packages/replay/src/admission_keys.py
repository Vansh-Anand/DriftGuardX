"""Runtime signing and trust configuration for admission receipts.

Raw private keys are supported as a deployment bridge for controlled environments.
Production key custody should provide the same ``SignerProtocol`` through KMS/HSM.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Mapping
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import ed25519

from packages.ledger.src.crypto import DevelopmentSigner, SignerProtocol
from packages.replay.src.admission_receipt import AdmissionReceiptV1


def receipt_signature_required() -> bool:
    explicit = os.getenv("DGX_ADMISSION_REQUIRE_SIGNATURE", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False
    return (
        os.getenv("DGX_MODE", "").lower() == "production"
        or os.getenv("APP_ENV", "").lower() in {"staging", "production", "prod"}
        or os.getenv("ENVIRONMENT", "").lower() in {"staging", "prod"}
    )


def load_environment_signer(*, required: bool | None = None) -> SignerProtocol | None:
    """Load a configured Ed25519 signer without generating an implicit key."""
    must_sign = receipt_signature_required() if required is None else required
    key_id = os.getenv("DGX_ADMISSION_SIGNING_KEY_ID", "").strip()
    private_key_b64 = os.getenv("DGX_ADMISSION_PRIVATE_KEY_B64", "").strip()
    if not key_id or not private_key_b64:
        if must_sign:
            raise RuntimeError(
                "Admission receipt signing is required, but signing key configuration is missing."
            )
        return None
    try:
        private_key_bytes = base64.b64decode(private_key_b64, validate=True)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Admission receipt private key is invalid.") from exc
    return DevelopmentSigner(private_key=private_key, key_id=key_id)


def sign_receipt_for_runtime(receipt: AdmissionReceiptV1) -> bool:
    signer = load_environment_signer()
    if signer is None:
        return False
    receipt.sign(signer)
    return True


def load_worker_attestation_signer(*, required: bool | None = None) -> SignerProtocol | None:
    must_sign = receipt_signature_required() if required is None else required
    key_id = os.getenv("DGX_WORKER_ATTESTATION_KEY_ID", "").strip()
    private_key_b64 = os.getenv("DGX_WORKER_ATTESTATION_PRIVATE_KEY_B64", "").strip()
    if not key_id or not private_key_b64:
        if must_sign:
            raise RuntimeError(
                "Worker attestation signing is required, but signing key configuration is missing."
            )
        return None
    try:
        private_key_bytes = base64.b64decode(private_key_b64, validate=True)
        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Worker attestation private key is invalid.") from exc
    return DevelopmentSigner(private_key=private_key, key_id=key_id)


@dataclass(frozen=True)
class AdmissionReceiptTrustStore:
    """Resolve trusted issuer public keys by stable key ID."""

    public_keys: Mapping[str, str]

    @classmethod
    def from_environment(
        cls, variable: str = "DGX_ADMISSION_TRUSTED_KEYS_JSON"
    ) -> AdmissionReceiptTrustStore:
        raw = os.getenv(variable, "{}").strip() or "{}"
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{variable} is not valid JSON.") from exc
        if not isinstance(decoded, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in decoded.items()
        ):
            raise RuntimeError("Trusted admission keys must be a JSON object of key IDs to keys.")
        return cls(public_keys=decoded)

    def verify(self, receipt: AdmissionReceiptV1) -> tuple[bool, str]:
        if not receipt.key_id or not receipt.payload_signature:
            return False, "Admission receipt is unsigned."
        public_key = self.public_keys.get(receipt.key_id)
        if public_key is None:
            return False, "Admission receipt signing key is not trusted."
        return receipt.verify_signature(public_key)
